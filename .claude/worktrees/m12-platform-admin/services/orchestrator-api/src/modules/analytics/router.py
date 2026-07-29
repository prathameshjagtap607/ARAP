import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.database import get_db, get_redis
from src.modules.analytics import service
from src.modules.analytics.cache import get_cached, make_cache_key, set_cached
from src.modules.analytics.schemas import (
    BenchmarkResponse,
    FunnelResponse,
    QuestionAnalyticsResponse,
    ScoreTrendsResponse,
    SkillTrendsResponse,
)
from src.modules.auth.dependencies import TokenClaims, require_user

router = APIRouter(prefix="/analytics", tags=["analytics"])

_DEFAULT_FROM = datetime(2020, 1, 1, tzinfo=timezone.utc)


@router.get("/score-trends", response_model=ScoreTrendsResponse)
def score_trends(
    dept: str | None = Query(None),
    role: str | None = Query(None),
    from_date: datetime = Query(default=_DEFAULT_FROM),
    to_date: datetime | None = Query(default=None),
    granularity: str = Query(default="week", pattern="^(week|month)$"),
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    if to_date is None:
        to_date = datetime.now(timezone.utc)
    redis = get_redis()
    key = make_cache_key(claims.org_id, "score_trends", {
        "dept": dept, "role": role,
        "from_date": from_date.isoformat(), "to_date": to_date.isoformat(),
        "granularity": granularity,
    })
    cached = get_cached(redis, key)
    if cached:
        return ScoreTrendsResponse.model_validate_json(cached)

    result = service.get_score_trends(db, claims.org_id, dept, role, from_date, to_date, granularity)
    set_cached(redis, key, result.model_dump_json())
    return result


@router.get("/funnel", response_model=FunnelResponse)
def funnel(
    dept: str | None = Query(None),
    role: str | None = Query(None),
    from_date: datetime = Query(default=_DEFAULT_FROM),
    to_date: datetime | None = Query(default=None),
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    if to_date is None:
        to_date = datetime.now(timezone.utc)
    redis = get_redis()
    key = make_cache_key(claims.org_id, "funnel", {
        "dept": dept, "role": role,
        "from_date": from_date.isoformat(), "to_date": to_date.isoformat(),
    })
    cached = get_cached(redis, key)
    if cached:
        return FunnelResponse.model_validate_json(cached)

    result = service.get_funnel(db, claims.org_id, dept, role, from_date, to_date)
    set_cached(redis, key, result.model_dump_json())
    return result


@router.get("/questions", response_model=QuestionAnalyticsResponse)
def question_analytics(
    job_assessment_id: uuid.UUID | None = Query(None),
    from_date: datetime = Query(default=_DEFAULT_FROM),
    to_date: datetime | None = Query(default=None),
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    if to_date is None:
        to_date = datetime.now(timezone.utc)
    redis = get_redis()
    key = make_cache_key(claims.org_id, "questions", {
        "job_assessment_id": str(job_assessment_id) if job_assessment_id else None,
        "from_date": from_date.isoformat(), "to_date": to_date.isoformat(),
    })
    cached = get_cached(redis, key)
    if cached:
        return QuestionAnalyticsResponse.model_validate_json(cached)

    result = service.get_question_analytics(db, claims.org_id, job_assessment_id, from_date, to_date)
    set_cached(redis, key, result.model_dump_json())
    return result


@router.get("/benchmarks/{session_id}", response_model=BenchmarkResponse)
def benchmark(
    session_id: uuid.UUID,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    redis = get_redis()
    key = make_cache_key(claims.org_id, "benchmark", {"session_id": str(session_id)})
    cached = get_cached(redis, key)
    if cached:
        return BenchmarkResponse.model_validate_json(cached)

    try:
        result = service.get_benchmark(db, claims.org_id, session_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    set_cached(redis, key, result.model_dump_json())
    return result


@router.get("/skill-trends", response_model=SkillTrendsResponse)
def skill_trends(
    dept: str | None = Query(None),
    role: str | None = Query(None),
    from_date: datetime = Query(default=_DEFAULT_FROM),
    to_date: datetime | None = Query(default=None),
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    if to_date is None:
        to_date = datetime.now(timezone.utc)
    redis = get_redis()
    key = make_cache_key(claims.org_id, "skill_trends", {
        "dept": dept, "role": role,
        "from_date": from_date.isoformat(), "to_date": to_date.isoformat(),
    })
    cached = get_cached(redis, key)
    if cached:
        return SkillTrendsResponse.model_validate_json(cached)

    result = service.get_skill_trends(db, claims.org_id, dept, role, from_date, to_date)
    set_cached(redis, key, result.model_dump_json())
    return result
