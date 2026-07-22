import uuid
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, Request, status


@dataclass
class TokenClaims:
    sub: str
    role: str
    org_id: uuid.UUID
    type: str
    assessment_session_id: Optional[uuid.UUID] = None
    report_share_id: Optional[uuid.UUID] = None


def get_claims(request: Request) -> TokenClaims:
    claims = getattr(request.state, "claims", None)
    if claims is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return claims


def require_user(claims: TokenClaims = Depends(get_claims)) -> TokenClaims:
    if claims.role not in ("user", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return claims


def require_admin(claims: TokenClaims = Depends(get_claims)) -> TokenClaims:
    if claims.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return claims


class RequireCandidateScope:
    def __call__(
        self,
        session_id: uuid.UUID,
        claims: TokenClaims = Depends(get_claims),
    ) -> TokenClaims:
        if claims.role != "candidate":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Candidate scope required — role mismatch",
            )
        if claims.assessment_session_id != session_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Candidate scope mismatch — session_id does not match token",
            )
        return claims


class RequireClientScope:
    def __call__(
        self,
        share_id: uuid.UUID,
        claims: TokenClaims = Depends(get_claims),
    ) -> TokenClaims:
        if claims.role != "client":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Client scope required — role mismatch",
            )
        if claims.report_share_id != share_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Client scope mismatch — share_id does not match token",
            )
        return claims


require_candidate_scope = RequireCandidateScope()
require_client_scope = RequireClientScope()
