import logging
import uuid

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from agents.resume_analysis.agent import run_resume_analysis_agent
from src.config import settings
from src.database import get_db
from src.embeddings import cosine_similarity, embed
from src.models import Candidate, CandidateProfile, JobAssessment
from src.parsers import extract_text
from src.s3 import download_file

logger = logging.getLogger(__name__)
router = APIRouter(tags=["analyze"])


class AnalyzeRequest(BaseModel):
    candidate_id: uuid.UUID
    job_assessment_id: uuid.UUID
    org_id: uuid.UUID


class CandidateProfileResponse(BaseModel):
    id: uuid.UUID
    candidate_id: uuid.UUID
    job_assessment_id: uuid.UUID
    org_id: uuid.UUID
    parsing_confidence: float | None
    field_confidence: dict | None
    match_score: float | None
    github_enrichment: dict | None
    skill_matrix: dict
    experience_matrix: dict
    leadership_level_estimate: str | None

    class Config:
        from_attributes = True


def _fetch_github(github_url: str) -> dict | None:
    try:
        handle = github_url.rstrip("/").rsplit("/", 1)[-1].lstrip("@")
        user_resp = httpx.get(
            f"https://api.github.com/users/{handle}",
            headers={"Accept": "application/vnd.github+json"},
            timeout=10,
        )
        if user_resp.status_code != 200:
            return None
        user_data = user_resp.json()

        repos_resp = httpx.get(
            f"https://api.github.com/users/{handle}/repos?sort=pushed&per_page=10",
            headers={"Accept": "application/vnd.github+json"},
            timeout=10,
        )
        if repos_resp.status_code != 200:
            return None
        repos = repos_resp.json()

        languages = list(dict.fromkeys(
            r["language"] for r in repos if r.get("language")
        ))
        most_recent = max((r["pushed_at"] for r in repos), default=None)
        return {
            "username": handle,
            "public_repos": user_data.get("public_repos", 0),
            "top_languages": languages[:5],
            "most_recent_push": most_recent,
            "repos": [
                {
                    "name": r["name"],
                    "language": r.get("language"),
                    "stars": r.get("stargazers_count", 0),
                    "pushed_at": r.get("pushed_at"),
                }
                for r in repos
            ],
        }
    except Exception:
        logger.exception("GitHub enrichment failed")
        return None


def _run_pipeline_bg(
    candidate_id: uuid.UUID,
    job_id: uuid.UUID,
    org_id: uuid.UUID,
    file_bytes: bytes,
    mime: str,
) -> None:
    """Background task wrapper that opens its own fresh DB session to avoid DetachedInstanceError."""
    from src.database import SessionLocal
    db = SessionLocal()
    try:
        candidate = db.query(Candidate).filter_by(id=candidate_id).first()
        job = db.query(JobAssessment).filter_by(id=job_id).first()
        if candidate and job:
            try:
                _run_pipeline(db, candidate, job, org_id, file_bytes, mime)
            except ValueError as exc:
                logger.error("Pipeline rejected resume for candidate %s: %s", candidate_id, exc)
    finally:
        db.close()


def _run_pipeline(
    db: Session,
    candidate: Candidate,
    job: JobAssessment,
    org_id: uuid.UUID,
    file_bytes: bytes | None,
    mime: str | None,
) -> CandidateProfile:
    raw_text: str | None = None
    if file_bytes and mime:
        try:
            raw_text = extract_text(file_bytes, mime)
        except ValueError:
            raise
        except Exception:
            logger.exception("Text extraction failed for candidate %s", candidate.id)

    job_profile = job.job_profile
    extraction: dict | None = None
    if raw_text:
        extraction = run_resume_analysis_agent(raw_text, job_profile)

    github_enrichment: dict | None = None
    if candidate.github_url:
        github_enrichment = _fetch_github(candidate.github_url)

    match_score: float | None = None
    field_confidence: dict | None = None
    parsing_confidence: float | None = None
    skill_matrix: dict = {}
    experience_matrix: dict = {}
    leadership_level_estimate: str | None = None

    if extraction:
        field_confidence = extraction.get("field_confidence")
        if field_confidence:
            parsing_confidence = round(
                sum(field_confidence.values()) / len(field_confidence), 3
            )
        skill_matrix = {
            "explicit": extraction.get("skills", {}).get("explicit", []),
            "inferred": extraction.get("skills", {}).get("inferred", []),
            "tech_used": extraction.get("tech_used", []),
        }
        experience_matrix = {
            "employment_history": extraction.get("employment_history", []),
            "career_timeline": extraction.get("career_timeline", {}),
        }
        leadership_level_estimate = extraction.get("_leadership_level")

        try:
            req_skills = list(job.required_skills or []) + list(job.preferred_skills or [])
            resume_tokens = (
                extraction.get("skills", {}).get("explicit", [])
                + extraction.get("skills", {}).get("inferred", [])
                + extraction.get("domain_keywords", [])
            )
            if resume_tokens and req_skills:
                vec_resume = embed(" ".join(resume_tokens))
                vec_jd = embed(" ".join(req_skills))
                match_score = round(cosine_similarity(vec_resume, vec_jd), 3)
        except Exception:
            logger.exception("Match score computation failed for candidate %s", candidate.id)

    stmt = pg_insert(CandidateProfile).values(
        org_id=org_id,
        candidate_id=candidate.id,
        job_assessment_id=job.id,
        skill_matrix=skill_matrix,
        experience_matrix=experience_matrix,
        leadership_level_estimate=leadership_level_estimate,
        strengths=[],
        risk_flags=[],
        parsing_confidence=parsing_confidence,
        field_confidence=field_confidence,
        match_score=match_score,
        github_enrichment=github_enrichment,
    ).on_conflict_do_update(
        index_elements=["candidate_id", "job_assessment_id"],
        set_={
            "skill_matrix": skill_matrix,
            "experience_matrix": experience_matrix,
            "leadership_level_estimate": leadership_level_estimate,
            "parsing_confidence": parsing_confidence,
            "field_confidence": field_confidence,
            "match_score": match_score,
            "github_enrichment": github_enrichment,
        },
    )
    db.execute(stmt)
    db.commit()

    return db.query(CandidateProfile).filter_by(
        candidate_id=candidate.id, job_assessment_id=job.id
    ).first()


@router.post("/analyze", status_code=status.HTTP_200_OK)
def analyze(body: AnalyzeRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter_by(id=body.candidate_id, org_id=body.org_id).first()
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

    job = db.query(JobAssessment).filter_by(id=body.job_assessment_id, org_id=body.org_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job assessment not found")

    if not candidate.resume_file_url:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Candidate has no resume file uploaded",
        )

    file_bytes: bytes | None = None
    mime: str | None = None
    is_large = False
    try:
        file_bytes = download_file(candidate.resume_file_url)
        ext = candidate.resume_file_url.rsplit(".", 1)[-1].lower()
        mime_map = {
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "txt": "text/plain",
        }
        mime = mime_map.get(ext, "text/plain")
        if len(file_bytes) > settings.LARGE_DOC_BYTES:
            is_large = True
    except Exception:
        pass

    if is_large:
        background_tasks.add_task(
            _run_pipeline_bg,
            candidate.id,
            job.id,
            body.org_id,
            file_bytes,
            mime,
        )
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={"status": "processing", "candidate_profile_id": None},
        )

    try:
        profile = _run_pipeline(db, candidate, job, body.org_id, file_bytes, mime)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    return CandidateProfileResponse.model_validate(profile)


@router.get("/analyze/{candidate_id}/{job_assessment_id}")
def get_analyze(candidate_id: uuid.UUID, job_assessment_id: uuid.UUID, db: Session = Depends(get_db)):
    profile = db.query(CandidateProfile).filter_by(
        candidate_id=candidate_id, job_assessment_id=job_assessment_id
    ).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found or still processing")
    return CandidateProfileResponse.model_validate(profile)
