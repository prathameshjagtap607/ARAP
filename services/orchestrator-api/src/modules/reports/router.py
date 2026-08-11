import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.database import get_db
from src.modules.auth.dependencies import TokenClaims, require_user
from src.modules.reports import service
from src.modules.reports.schemas import (
    FullReportResponse,
    ReportListResponse,
    ReportResponse,
    ReviewerFeedbackRequest,
    ReviewerFeedbackResponse,
    SharedReportResponse,
    ShareLinkRequest,
    ShareLinkResponse,
)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("", response_model=ReportListResponse)
def list_reports(
    verdict: str | None = None,
    disc_category: str | None = None,
    disc_confidence_band: list[str] | None = Query(default=None),
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    return service.list_reports(
        db, claims.org_id, verdict, disc_category, disc_confidence_band,
        status, date_from, date_to, limit, offset
    )


# --- Public endpoint (no auth) must come before parameterised routes ---

@router.get("/shared/{token}", response_model=SharedReportResponse)
def get_shared_report(
    token: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Public share-link endpoint — no JWT required."""
    try:
        return service.get_shared_report(db, token)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# --- Authenticated endpoints ---

@router.get("/{session_id}", response_model=ReportResponse)
def get_report(
    session_id: uuid.UUID,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        return service.get_report(db, session_id, claims.org_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{session_id}/full", response_model=FullReportResponse)
def get_full_report(
    session_id: uuid.UUID,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        return service.get_full_report(db, session_id, claims.org_id)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{session_id}/pdf")
def get_pdf_report(
    session_id: uuid.UUID,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        pdf_bytes = service.get_pdf_bytes(db, session_id, claims.org_id)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    headers = {"Content-Disposition": f'attachment; filename="report-{session_id}.pdf"'}
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers=headers,
    )


@router.post("/{session_id}/share", response_model=ShareLinkResponse)
def create_share_link(
    session_id: uuid.UUID,
    body: ShareLinkRequest,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        return service.create_share_link(
            db, session_id, claims.org_id, uuid.UUID(claims.sub), body
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{session_id}/feedback", response_model=ReviewerFeedbackResponse)
def submit_reviewer_feedback(
    session_id: uuid.UUID,
    body: ReviewerFeedbackRequest,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        return service.submit_reviewer_feedback(db, session_id, claims.org_id, uuid.UUID(claims.sub), body)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
