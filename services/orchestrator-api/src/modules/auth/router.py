import redis as redis_lib
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from src.database import get_db, get_redis
from src.modules.auth import service
from src.modules.auth import token as token_utils
from src.modules.auth.schemas import (
    CandidateTokenRequest,
    CandidateTokenResponse,
    CandidateVerifyRequest,
    ClientTokenRequest,
    ClientTokenResponse,
    ClientVerifyRequest,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    RefreshRequest,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(
    body: LoginRequest,
    db: Session = Depends(get_db),
    r: redis_lib.Redis = Depends(get_redis),
):
    try:
        user = service.login_user(db, body.email, body.password, body.org_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    payload = {"sub": str(user.id), "role": user.role, "org_id": str(user.org_id)}
    access = token_utils.create_access_token(payload)
    refresh = token_utils.create_refresh_token(r, str(user.id), str(user.org_id), user.role)
    return LoginResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=LoginResponse)
def refresh(
    body: RefreshRequest,
    db: Session = Depends(get_db),
    r: redis_lib.Redis = Depends(get_redis),
):
    try:
        data, new_refresh = token_utils.rotate_refresh_token(r, body.refresh_token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    payload = {"sub": data["user_id"], "role": data["role"], "org_id": data["org_id"]}
    access = token_utils.create_access_token(payload)
    service.write_refresh_audit(db, data["user_id"], data["org_id"])
    return LoginResponse(access_token=access, refresh_token=new_refresh)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    body: LogoutRequest,
    request: Request,
    db: Session = Depends(get_db),
    r: redis_lib.Redis = Depends(get_redis),
):
    claims = getattr(request.state, "claims", None)
    if claims and claims.role in ("user", "admin") and body.refresh_token:
        token_utils.delete_refresh_token(r, body.refresh_token)
    if claims:
        service.write_logout_audit(db, claims)


@router.post("/candidate/request-token", response_model=CandidateTokenResponse)
def candidate_request_token(body: CandidateTokenRequest, db: Session = Depends(get_db)):
    try:
        raw = service.request_candidate_token(
            db, body.email, body.org_id, body.assessment_session_id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    return CandidateTokenResponse(token=raw)


@router.post("/candidate/verify-token", response_model=TokenResponse)
def candidate_verify_token(body: CandidateVerifyRequest, db: Session = Depends(get_db)):
    try:
        candidate, session = service.verify_candidate_token(
            db, body.token, body.assessment_session_id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    payload = {
        "sub": str(candidate.id),
        "role": "candidate",
        "org_id": str(session.org_id),
        "assessment_session_id": str(session.id),
    }
    return TokenResponse(access_token=token_utils.create_access_token(payload))


@router.post("/client/request-token", response_model=ClientTokenResponse)
def client_request_token(body: ClientTokenRequest, db: Session = Depends(get_db)):
    try:
        raw = service.request_client_token(
            db, body.email, body.org_id, body.report_share_id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    return ClientTokenResponse(token=raw)


@router.post("/client/verify-token", response_model=TokenResponse)
def client_verify_token(body: ClientVerifyRequest, db: Session = Depends(get_db)):
    try:
        client, share = service.verify_client_token(
            db, body.token, body.report_share_id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    payload = {
        "sub": str(client.id),
        "role": "client",
        "org_id": str(share.org_id),
        "report_share_id": str(share.id),
    }
    return TokenResponse(access_token=token_utils.create_access_token(payload))
