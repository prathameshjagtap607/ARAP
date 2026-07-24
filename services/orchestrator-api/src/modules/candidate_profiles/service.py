import uuid

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from agents.candidate_profile.agent import run_candidate_profile_agent
from src.models.candidate_profiles import CandidateProfile
from src.models.job_assessments import JobAssessment


def synthesize_profile(
    db: Session,
    org_id: uuid.UUID,
    candidate_id: uuid.UUID,
    job_assessment_id: uuid.UUID,
) -> CandidateProfile:
    profile = db.query(CandidateProfile).filter_by(
        candidate_id=candidate_id,
        job_assessment_id=job_assessment_id,
        org_id=org_id,
    ).first()
    if profile is None:
        raise LookupError("Candidate profile not found — run resume ingestion first")

    if profile.parsing_confidence is None:
        raise ValueError("Resume parsing failed — M2 agent returned no data; re-upload resume")

    job = db.query(JobAssessment).filter_by(
        id=job_assessment_id, org_id=org_id
    ).first()
    if job is None or job.job_profile is None:
        raise ValueError("Job profile not generated — retry job assessment creation")

    extraction = {
        "skill_matrix": profile.skill_matrix,
        "experience_matrix": profile.experience_matrix,
        "leadership_level_estimate": profile.leadership_level_estimate,
        "field_confidence": profile.field_confidence or {},
    }

    result = run_candidate_profile_agent(extraction, job.job_profile)
    if result is None:
        raise RuntimeError("Candidate profile agent failed — retry request")

    raw_skill_matrix = (
        profile.skill_matrix.get("raw", profile.skill_matrix)
        if isinstance(profile.skill_matrix, dict)
        else {}
    )

    profile.summary = result["summary"]
    profile.skill_matrix = {
        "aligned": result["skill_matrix_aligned"],
        "raw": raw_skill_matrix,
    }
    profile.experience_matrix = {
        **profile.experience_matrix,
        "leadership_scope": result["leadership"]["scope"],
    }
    profile.leadership_level_estimate = result["leadership"]["level"]
    profile.strengths = result["strengths"]
    profile.risk_flags = result["risk_flags"]

    flag_modified(profile, "skill_matrix")
    flag_modified(profile, "experience_matrix")

    db.commit()
    db.refresh(profile)
    return profile


def get_profile(
    db: Session,
    org_id: uuid.UUID,
    candidate_id: uuid.UUID,
    job_assessment_id: uuid.UUID,
) -> CandidateProfile:
    profile = db.query(CandidateProfile).filter_by(
        candidate_id=candidate_id,
        job_assessment_id=job_assessment_id,
        org_id=org_id,
    ).first()
    if profile is None:
        raise LookupError("Candidate profile not found")
    return profile
