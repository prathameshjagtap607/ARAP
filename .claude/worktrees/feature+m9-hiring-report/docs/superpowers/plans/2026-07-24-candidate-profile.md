# Candidate Profile Engine (M3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build M3 — synthesize a narrative summary, aligned skill matrix, leadership estimate, and strength/risk flags from M2-extracted resume data + job profile, persisting all fields on the existing `candidate_profiles` row.

**Architecture:** A new `agents/candidate_profile/` agent calls Claude Sonnet with forced tool_use, taking the resume extraction already stored in `candidate_profiles` + `job_assessments.job_profile` as input and returning structured synthesis output. A new `modules/candidate_profiles/` module in orchestrator-api exposes `POST /candidate-profiles/synthesize` (triggers agent, writes back) and `GET /candidate-profiles/{candidate_id}/{job_assessment_id}` (read profile).

**Tech Stack:** FastAPI, SQLAlchemy 2.x, Anthropic SDK (`claude-sonnet-4-6` forced tool_use), pytest-asyncio, httpx AsyncClient, fakeredis.

## Global Constraints

- Python ≥ 3.11; SQLAlchemy ≥ 2.0; FastAPI ≥ 0.111; anthropic ≥ 0.28
- `pythonpath = [".", "../.."]` in pyproject.toml — agents importable as `agents.candidate_profile.agent`
- No new migration — all target columns exist on `candidate_profiles`
- All endpoints require `require_user` (org-scoped JWT); `org_id` comes from `claims.org_id`
- Agent failure is non-fatal to the process but fatal to the HTTP request: return `None` and raise `RuntimeError` in service → `HTTPException(502)`
- Commit format: `[TASK-001] <type>: <what changed>`
- Test DB: `postgresql://arap:arap@localhost:5434/arap_test`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `agents/candidate_profile/__init__.py` | Create | Package marker |
| `agents/candidate_profile/prompts.py` | Create | `SYSTEM_PROMPT` + `CANDIDATE_PROFILE_TOOL` schema |
| `agents/candidate_profile/agent.py` | Create | `run_candidate_profile_agent(extraction, job_profile) -> dict \| None` |
| `agents/candidate_profile/tests/__init__.py` | Create | Package marker |
| `agents/candidate_profile/tests/test_agent.py` | Create | Unit tests for agent (mocked Anthropic) |
| `services/orchestrator-api/src/modules/candidate_profiles/__init__.py` | Create | Package marker |
| `services/orchestrator-api/src/modules/candidate_profiles/schemas.py` | Create | `SynthesizeRequest`, `CandidateProfileResponse` |
| `services/orchestrator-api/src/modules/candidate_profiles/service.py` | Create | `synthesize_profile()`, `get_profile()` |
| `services/orchestrator-api/src/modules/candidate_profiles/router.py` | Create | `POST /synthesize`, `GET /{candidate_id}/{job_assessment_id}` |
| `services/orchestrator-api/src/main.py` | Modify | Register `candidate_profiles_router` |
| `services/orchestrator-api/tests/candidate_profiles/__init__.py` | Create | Package marker |
| `services/orchestrator-api/tests/candidate_profiles/conftest.py` | Create | DB fixtures, seeded profile row, mock agent |
| `services/orchestrator-api/tests/candidate_profiles/test_service.py` | Create | Unit tests for service (mocked agent, real DB) |
| `services/orchestrator-api/tests/candidate_profiles/test_router.py` | Create | Integration tests via AsyncClient |

---

### Task 1: Candidate Profile Agent

**Files:**
- Create: `agents/candidate_profile/__init__.py`
- Create: `agents/candidate_profile/prompts.py`
- Create: `agents/candidate_profile/agent.py`
- Create: `agents/candidate_profile/tests/__init__.py`
- Create: `agents/candidate_profile/tests/test_agent.py`

**Interfaces:**
- Produces: `run_candidate_profile_agent(extraction: dict, job_profile: dict) -> dict | None`
  - `extraction` keys: `skill_matrix` (dict with `explicit`, `inferred`, `tech_used`), `experience_matrix` (dict with `employment_history`, `career_timeline`), `leadership_level_estimate` (str | None), `field_confidence` (dict)
  - `job_profile` keys: `normalized_title`, `role_summary`, `key_responsibilities`, `required_skills`, `preferred_skills`, `difficulty_level`
  - Returns dict with keys: `summary` (str), `skill_matrix_aligned` (list[dict]), `leadership` (dict), `strengths` (list[str]), `risk_flags` (list[str])
  - Returns `None` on any exception

- [ ] **Step 1: Create package markers**

```python
# agents/candidate_profile/__init__.py
# (empty)

# agents/candidate_profile/tests/__init__.py
# (empty)
```

- [ ] **Step 2: Write the failing agent test**

Create `agents/candidate_profile/tests/test_agent.py`:

```python
from unittest.mock import MagicMock, patch

_FAKE_RESULT = {
    "summary": "Jane is a senior backend engineer with 8 years of Python experience.",
    "skill_matrix_aligned": [
        {
            "skill": "Python",
            "source": "required",
            "alignment": "yes",
            "estimated_years": 8.0,
            "confidence": 0.95,
            "evidence": "8 years Python development across 3 companies",
        }
    ],
    "leadership": {
        "level": "Manager",
        "career_velocity": "Promoted twice in 4 years",
        "scope": {"team_size": 8, "budget": None, "geography": "Remote — APAC"},
    },
    "strengths": ["Deep Python expertise", "Cross-functional leadership"],
    "risk_flags": ["No direct people-management despite Manager title at Acme Corp"],
}


def _make_mock_client(result: dict = _FAKE_RESULT):
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.input = result

    message = MagicMock()
    message.content = [tool_block]

    client = MagicMock()
    client.messages.create.return_value = message
    return client


_EXTRACTION = {
    "skill_matrix": {
        "explicit": ["Python", "FastAPI"],
        "inferred": ["REST APIs"],
        "tech_used": ["PostgreSQL"],
    },
    "experience_matrix": {
        "employment_history": [
            {
                "company": "Acme Corp",
                "title": "Engineering Manager",
                "start": "2020-01",
                "end": None,
                "team_size": 8,
                "scope": "Backend platform",
                "key_achievements": ["Reduced latency by 40%"],
            }
        ],
        "career_timeline": {"total_years": 8, "job_count": 3, "gaps": []},
    },
    "leadership_level_estimate": "Manager",
    "field_confidence": {"skills": 0.9, "employment_history": 0.85},
}

_JOB_PROFILE = {
    "normalized_title": "Senior Backend Engineer",
    "role_summary": "Build scalable APIs.",
    "key_responsibilities": ["Design REST APIs", "Mentor junior engineers"],
    "required_skills": ["Python", "FastAPI"],
    "preferred_skills": ["Docker"],
    "difficulty_level": "senior",
}


def test_agent_returns_structured_output():
    from agents.candidate_profile.agent import run_candidate_profile_agent

    with patch("agents.candidate_profile.agent.anthropic.Anthropic", return_value=_make_mock_client()):
        result = run_candidate_profile_agent(_EXTRACTION, _JOB_PROFILE)

    assert result is not None
    assert "summary" in result
    assert "skill_matrix_aligned" in result
    assert isinstance(result["skill_matrix_aligned"], list)
    assert result["skill_matrix_aligned"][0]["skill"] == "Python"
    assert result["skill_matrix_aligned"][0]["alignment"] == "yes"
    assert "leadership" in result
    assert result["leadership"]["level"] == "Manager"
    assert "strengths" in result
    assert "risk_flags" in result
    assert isinstance(result["risk_flags"], list)


def test_agent_returns_none_on_api_error():
    from agents.candidate_profile.agent import run_candidate_profile_agent

    failing_client = MagicMock()
    failing_client.messages.create.side_effect = Exception("API down")

    with patch("agents.candidate_profile.agent.anthropic.Anthropic", return_value=failing_client):
        result = run_candidate_profile_agent(_EXTRACTION, _JOB_PROFILE)

    assert result is None
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd agents/candidate_profile
pytest tests/test_agent.py -v
```

Expected: `ModuleNotFoundError: No module named 'agents.candidate_profile.agent'`

- [ ] **Step 4: Write `prompts.py`**

Create `agents/candidate_profile/prompts.py`:

```python
SYSTEM_PROMPT = (
    "You are a candidate profile synthesis assistant. "
    "Given structured resume extraction data and a normalized job profile, "
    "produce a comprehensive candidate profile using the provided tool. "
    "Base all claims strictly on the provided data — do not invent information. "
    "Risk flags must be specific and actionable (e.g. cite the company name, "
    "the gap dates, or the exact missing skill). "
    "The summary must cover: current role, career trajectory, standout achievements, "
    "and fit for this specific job. Write 2-3 paragraphs."
)

CANDIDATE_PROFILE_TOOL = {
    "name": "synthesize_candidate_profile",
    "description": "Synthesize a structured candidate profile from resume extraction and job profile data.",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "2-3 paragraph narrative: current role, trajectory, standout achievements, domain fit for this job.",
            },
            "skill_matrix_aligned": {
                "type": "array",
                "description": "One entry per required/preferred skill from the job profile.",
                "items": {
                    "type": "object",
                    "properties": {
                        "skill": {"type": "string"},
                        "source": {"type": "string", "enum": ["required", "preferred"]},
                        "alignment": {
                            "type": "string",
                            "enum": ["yes", "partial", "no"],
                            "description": "yes = clearly evidenced, partial = inferred/limited, no = not found",
                        },
                        "estimated_years": {"type": ["number", "null"]},
                        "confidence": {
                            "type": "number",
                            "description": "0.0–1.0 reflecting how clearly the evidence was stated",
                        },
                        "evidence": {
                            "type": ["string", "null"],
                            "description": "Short phrase or quote from resume supporting the alignment",
                        },
                    },
                    "required": ["skill", "source", "alignment", "estimated_years", "confidence", "evidence"],
                },
            },
            "leadership": {
                "type": "object",
                "properties": {
                    "level": {
                        "type": "string",
                        "enum": ["IC", "Team Lead", "Manager", "Director", "VP-equiv"],
                    },
                    "career_velocity": {
                        "type": "string",
                        "description": "e.g. 'Promoted 3 times in 5 years' or 'Lateral moves only'",
                    },
                    "scope": {
                        "type": "object",
                        "properties": {
                            "team_size": {"type": ["integer", "null"]},
                            "budget": {"type": ["string", "null"]},
                            "geography": {"type": ["string", "null"]},
                        },
                        "required": ["team_size", "budget", "geography"],
                    },
                },
                "required": ["level", "career_velocity", "scope"],
            },
            "strengths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "3–5 concise strength statements grounded in resume evidence.",
            },
            "risk_flags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "1–5 specific flags that seed targeted interview questions (e.g. 'No direct people-management despite Manager title at Acme Corp').",
            },
        },
        "required": ["summary", "skill_matrix_aligned", "leadership", "strengths", "risk_flags"],
    },
}
```

- [ ] **Step 5: Write `agent.py`**

Create `agents/candidate_profile/agent.py`:

```python
import json
import logging

import anthropic

from agents.candidate_profile.prompts import CANDIDATE_PROFILE_TOOL, SYSTEM_PROMPT

logger = logging.getLogger(__name__)

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 4096


def _build_user_message(extraction: dict, job_profile: dict) -> str:
    sm = extraction.get("skill_matrix", {})
    em = extraction.get("experience_matrix", {})
    lines = [
        "RESUME EXTRACTION:",
        f"  skills.explicit: {sm.get('explicit', [])}",
        f"  skills.inferred: {sm.get('inferred', [])}",
        f"  tech_used: {sm.get('tech_used', [])}",
        f"  employment_history: {json.dumps(em.get('employment_history', []))}",
        f"  career_timeline: {json.dumps(em.get('career_timeline', {}))}",
        f"  leadership_level_estimate: {extraction.get('leadership_level_estimate')}",
        f"  field_confidence: {json.dumps(extraction.get('field_confidence', {}))}",
        "",
        "JOB PROFILE:",
        f"  normalized_title: {job_profile.get('normalized_title', '')}",
        f"  role_summary: {job_profile.get('role_summary', '')}",
        f"  key_responsibilities: {job_profile.get('key_responsibilities', [])}",
        f"  required_skills: {job_profile.get('required_skills', [])}",
        f"  preferred_skills: {job_profile.get('preferred_skills', [])}",
        f"  difficulty_level: {job_profile.get('difficulty_level', '')}",
    ]
    return "\n".join(lines)


def run_candidate_profile_agent(extraction: dict, job_profile: dict) -> dict | None:
    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=[CANDIDATE_PROFILE_TOOL],
            tool_choice={"type": "tool", "name": "synthesize_candidate_profile"},
            messages=[{"role": "user", "content": _build_user_message(extraction, job_profile)}],
        )
        tool_block = next(b for b in response.content if b.type == "tool_use")
        return dict(tool_block.input)
    except Exception:
        logger.exception("Candidate profile agent failed — returning None")
        return None
```

- [ ] **Step 6: Run test to verify it passes**

```bash
cd agents/candidate_profile
pytest tests/test_agent.py -v
```

Expected: `2 passed`

- [ ] **Step 7: Commit**

```bash
git add agents/candidate_profile/
git commit -m "[TASK-001] feat: add candidate_profile agent with synthesize_candidate_profile tool"
```

---

### Task 2: Schemas and Service

**Files:**
- Create: `services/orchestrator-api/src/modules/candidate_profiles/__init__.py`
- Create: `services/orchestrator-api/src/modules/candidate_profiles/schemas.py`
- Create: `services/orchestrator-api/src/modules/candidate_profiles/service.py`
- Create: `services/orchestrator-api/tests/candidate_profiles/__init__.py`
- Create: `services/orchestrator-api/tests/candidate_profiles/conftest.py`
- Create: `services/orchestrator-api/tests/candidate_profiles/test_service.py`

**Interfaces:**
- Consumes: `run_candidate_profile_agent(extraction: dict, job_profile: dict) -> dict | None` from Task 1
- Produces:
  - `synthesize_profile(db, org_id, candidate_id, job_assessment_id) -> CandidateProfile` — raises `LookupError` (no profile row), `ValueError` (NULL parsing_confidence or NULL job_profile), `RuntimeError` (agent returned None)
  - `get_profile(db, org_id, candidate_id, job_assessment_id) -> CandidateProfile` — raises `LookupError`

- [ ] **Step 1: Create package markers**

```python
# services/orchestrator-api/src/modules/candidate_profiles/__init__.py
# (empty)

# services/orchestrator-api/tests/candidate_profiles/__init__.py
# (empty)
```

- [ ] **Step 2: Write the failing service test**

Create `services/orchestrator-api/tests/candidate_profiles/conftest.py`:

```python
import os
from unittest.mock import patch

import fakeredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from passlib.context import CryptContext
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from src.models.base import Base
import src.models  # noqa: F401
from src.models.orgs import Org
from src.models.users import User
from src.models.candidates import Candidate
from src.models.job_assessments import JobAssessment
from src.models.candidate_profiles import CandidateProfile
from src.modules.auth.token import create_access_token

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://arap:arap@localhost:5434/arap_test",
)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

FAKE_AGENT_RESULT = {
    "summary": "Jane is a seasoned backend engineer with 8 years of Python expertise.",
    "skill_matrix_aligned": [
        {
            "skill": "Python",
            "source": "required",
            "alignment": "yes",
            "estimated_years": 8.0,
            "confidence": 0.95,
            "evidence": "8 years Python development across 3 companies",
        }
    ],
    "leadership": {
        "level": "Manager",
        "career_velocity": "Promoted twice in 4 years",
        "scope": {"team_size": 8, "budget": None, "geography": "Remote — APAC"},
    },
    "strengths": ["Deep Python expertise", "Cross-functional leadership"],
    "risk_flags": ["No direct people-management despite Manager title at Acme Corp"],
}


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(TEST_DB_URL)
    with eng.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture
def db(engine) -> Session:
    _Session = sessionmaker(engine)
    s = _Session()
    yield s
    s.rollback()
    s.close()


@pytest.fixture
def r():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def seed(db):
    org = Org(name="CP Test Org")
    db.add(org)
    db.flush()

    admin = User(
        org_id=org.id, email="admin@cp.com", role="admin",
        password_hash=pwd_context.hash("pw"),
    )
    db.add(admin)
    db.flush()

    candidate = Candidate(
        org_id=org.id, name="Jane Doe", email="jane@example.com",
        auth_method="magic_link",
    )
    db.add(candidate)
    db.flush()

    job = JobAssessment(
        org_id=org.id,
        title="Senior Backend Engineer",
        department="Engineering",
        difficulty_level="senior",
        duration_minutes=60,
        required_skills=["Python", "FastAPI"],
        preferred_skills=["Docker"],
        behavioral_competencies=["problem_solving"],
        leadership_competencies=["mentoring"],
        competency_weightage={"problem_solving": 60.0, "mentoring": 40.0},
        created_by=admin.id,
        job_profile={
            "normalized_title": "Senior Backend Engineer",
            "role_summary": "Build scalable APIs.",
            "key_responsibilities": ["Design REST APIs"],
            "required_skills": ["Python", "FastAPI"],
            "preferred_skills": ["Docker"],
            "difficulty_level": "senior",
            "generated_at": "2026-07-24T00:00:00",
        },
    )
    db.add(job)
    db.flush()

    profile = CandidateProfile(
        org_id=org.id,
        candidate_id=candidate.id,
        job_assessment_id=job.id,
        skill_matrix={
            "explicit": ["Python", "FastAPI"],
            "inferred": ["REST APIs"],
            "tech_used": ["PostgreSQL"],
        },
        experience_matrix={
            "employment_history": [
                {
                    "company": "Acme Corp",
                    "title": "Engineering Manager",
                    "start": "2020-01",
                    "end": None,
                    "team_size": 8,
                    "scope": "Backend platform",
                    "key_achievements": ["Reduced latency by 40%"],
                }
            ],
            "career_timeline": {"total_years": 8, "job_count": 3, "gaps": []},
        },
        leadership_level_estimate="Manager",
        strengths=[],
        risk_flags=[],
        parsing_confidence=0.85,
        field_confidence={"skills": 0.9, "employment_history": 0.85},
    )
    db.add(profile)
    db.commit()
    db.refresh(org); db.refresh(admin); db.refresh(candidate)
    db.refresh(job); db.refresh(profile)

    return {
        "org": org,
        "admin": admin,
        "candidate": candidate,
        "job": job,
        "profile": profile,
    }


@pytest.fixture
def user_token(seed):
    return create_access_token({
        "sub": str(seed["admin"].id),
        "role": "admin",
        "org_id": str(seed["org"].id),
    })


@pytest.fixture
def mock_cp_agent():
    with patch(
        "src.modules.candidate_profiles.service.run_candidate_profile_agent"
    ) as m:
        m.return_value = FAKE_AGENT_RESULT
        yield m


@pytest_asyncio.fixture
async def async_client(db, r):
    from src.main import app
    from src.database import get_db, get_redis
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_redis] = lambda: r
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
```

Create `services/orchestrator-api/tests/candidate_profiles/test_service.py`:

```python
import uuid
from unittest.mock import patch

import pytest

from src.models.candidate_profiles import CandidateProfile


def test_synthesize_profile_writes_all_fields(db, seed, mock_cp_agent):
    from src.modules.candidate_profiles.service import synthesize_profile

    org_id = seed["org"].id
    candidate_id = seed["candidate"].id
    job_id = seed["job"].id

    result = synthesize_profile(db, org_id, candidate_id, job_id)

    assert result.summary == "Jane is a seasoned backend engineer with 8 years of Python expertise."
    assert result.leadership_level_estimate == "Manager"
    assert result.strengths == ["Deep Python expertise", "Cross-functional leadership"]
    assert len(result.risk_flags) == 1
    assert "people-management" in result.risk_flags[0]
    aligned = result.skill_matrix.get("aligned")
    assert aligned is not None
    assert aligned[0]["skill"] == "Python"
    assert aligned[0]["alignment"] == "yes"
    raw = result.skill_matrix.get("raw")
    assert raw is not None
    assert "explicit" in raw
    assert "leadership_scope" in result.experience_matrix


def test_synthesize_profile_raises_lookup_when_no_profile(db, seed):
    from src.modules.candidate_profiles.service import synthesize_profile

    with pytest.raises(LookupError):
        synthesize_profile(db, seed["org"].id, uuid.uuid4(), seed["job"].id)


def test_synthesize_profile_raises_value_error_when_parsing_confidence_null(db, seed):
    from src.modules.candidate_profiles.service import synthesize_profile

    profile = db.query(CandidateProfile).filter_by(
        candidate_id=seed["candidate"].id,
        job_assessment_id=seed["job"].id,
    ).first()
    original = profile.parsing_confidence
    profile.parsing_confidence = None
    db.commit()

    try:
        with pytest.raises(ValueError, match="parsing"):
            synthesize_profile(db, seed["org"].id, seed["candidate"].id, seed["job"].id)
    finally:
        profile.parsing_confidence = original
        db.commit()


def test_synthesize_profile_raises_runtime_when_agent_returns_none(db, seed):
    from src.modules.candidate_profiles.service import synthesize_profile

    with patch(
        "src.modules.candidate_profiles.service.run_candidate_profile_agent",
        return_value=None,
    ):
        with pytest.raises(RuntimeError, match="agent"):
            synthesize_profile(db, seed["org"].id, seed["candidate"].id, seed["job"].id)


def test_get_profile_returns_row(db, seed, mock_cp_agent):
    from src.modules.candidate_profiles.service import get_profile, synthesize_profile

    synthesize_profile(db, seed["org"].id, seed["candidate"].id, seed["job"].id)
    result = get_profile(db, seed["org"].id, seed["candidate"].id, seed["job"].id)
    assert result is not None
    assert str(result.candidate_id) == str(seed["candidate"].id)


def test_get_profile_raises_lookup_when_missing(db, seed):
    from src.modules.candidate_profiles.service import get_profile

    with pytest.raises(LookupError):
        get_profile(db, seed["org"].id, uuid.uuid4(), seed["job"].id)
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd services/orchestrator-api
pytest tests/candidate_profiles/test_service.py -v
```

Expected: `ImportError: cannot import name 'synthesize_profile'`

- [ ] **Step 4: Write `schemas.py`**

Create `services/orchestrator-api/src/modules/candidate_profiles/schemas.py`:

```python
import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


class SynthesizeRequest(BaseModel):
    candidate_id: uuid.UUID
    job_assessment_id: uuid.UUID
    org_id: uuid.UUID


class CandidateProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    candidate_id: uuid.UUID
    job_assessment_id: uuid.UUID
    summary: Optional[str]
    skill_matrix: dict
    experience_matrix: dict
    leadership_level_estimate: Optional[str]
    strengths: list[str]
    risk_flags: list[str]
    parsing_confidence: Optional[float]
    match_score: Optional[float]
    created_at: datetime
```

- [ ] **Step 5: Write `service.py`**

Create `services/orchestrator-api/src/modules/candidate_profiles/service.py`:

```python
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
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
cd services/orchestrator-api
pytest tests/candidate_profiles/test_service.py -v
```

Expected: `6 passed`

- [ ] **Step 7: Commit**

```bash
git add services/orchestrator-api/src/modules/candidate_profiles/
git add services/orchestrator-api/tests/candidate_profiles/
git commit -m "[TASK-001] feat: add candidate_profiles schemas and service"
```

---

### Task 3: Router, Registration, and Integration Tests

**Files:**
- Create: `services/orchestrator-api/src/modules/candidate_profiles/router.py`
- Modify: `services/orchestrator-api/src/main.py`
- Create: `services/orchestrator-api/tests/candidate_profiles/test_router.py`

**Interfaces:**
- Consumes: `synthesize_profile()`, `get_profile()` from Task 2
- Consumes: `require_user`, `TokenClaims` from `src.modules.auth.dependencies`
- Produces: `POST /candidate-profiles/synthesize` → 200 `CandidateProfileResponse`
- Produces: `GET /candidate-profiles/{candidate_id}/{job_assessment_id}` → 200 `CandidateProfileResponse`

- [ ] **Step 1: Write the failing router tests**

Create `services/orchestrator-api/tests/candidate_profiles/test_router.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_synthesize_returns_200(async_client, seed, user_token, mock_cp_agent):
    resp = await async_client.post(
        "/candidate-profiles/synthesize",
        json={
            "candidate_id": str(seed["candidate"].id),
            "job_assessment_id": str(seed["job"].id),
            "org_id": str(seed["org"].id),
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"] == "Jane is a seasoned backend engineer with 8 years of Python expertise."
    assert body["leadership_level_estimate"] == "Manager"
    assert body["risk_flags"] == ["No direct people-management despite Manager title at Acme Corp"]
    aligned = body["skill_matrix"]["aligned"]
    assert aligned[0]["skill"] == "Python"
    assert aligned[0]["alignment"] == "yes"


@pytest.mark.asyncio
async def test_synthesize_returns_404_when_no_profile(async_client, seed, user_token, mock_cp_agent):
    import uuid
    resp = await async_client.post(
        "/candidate-profiles/synthesize",
        json={
            "candidate_id": str(uuid.uuid4()),
            "job_assessment_id": str(seed["job"].id),
            "org_id": str(seed["org"].id),
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_synthesize_returns_422_when_parsing_confidence_null(
    async_client, seed, user_token, db
):
    from src.models.candidate_profiles import CandidateProfile

    profile = db.query(CandidateProfile).filter_by(
        candidate_id=seed["candidate"].id,
        job_assessment_id=seed["job"].id,
    ).first()
    original = profile.parsing_confidence
    profile.parsing_confidence = None
    db.commit()

    try:
        resp = await async_client.post(
            "/candidate-profiles/synthesize",
            json={
                "candidate_id": str(seed["candidate"].id),
                "job_assessment_id": str(seed["job"].id),
                "org_id": str(seed["org"].id),
            },
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 422
    finally:
        profile.parsing_confidence = original
        db.commit()


@pytest.mark.asyncio
async def test_synthesize_returns_502_when_agent_fails(async_client, seed, user_token):
    from unittest.mock import patch

    with patch(
        "src.modules.candidate_profiles.service.run_candidate_profile_agent",
        return_value=None,
    ):
        resp = await async_client.post(
            "/candidate-profiles/synthesize",
            json={
                "candidate_id": str(seed["candidate"].id),
                "job_assessment_id": str(seed["job"].id),
                "org_id": str(seed["org"].id),
            },
            headers={"Authorization": f"Bearer {user_token}"},
        )
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_get_profile_returns_200_after_synthesize(async_client, seed, user_token, mock_cp_agent):
    await async_client.post(
        "/candidate-profiles/synthesize",
        json={
            "candidate_id": str(seed["candidate"].id),
            "job_assessment_id": str(seed["job"].id),
            "org_id": str(seed["org"].id),
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )
    resp = await async_client.get(
        f"/candidate-profiles/{seed['candidate'].id}/{seed['job'].id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["candidate_id"] == str(seed["candidate"].id)


@pytest.mark.asyncio
async def test_get_profile_returns_404_when_missing(async_client, seed, user_token):
    import uuid
    resp = await async_client.get(
        f"/candidate-profiles/{uuid.uuid4()}/{seed['job'].id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_synthesize_requires_auth(async_client, seed):
    resp = await async_client.post(
        "/candidate-profiles/synthesize",
        json={
            "candidate_id": str(seed["candidate"].id),
            "job_assessment_id": str(seed["job"].id),
            "org_id": str(seed["org"].id),
        },
    )
    assert resp.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd services/orchestrator-api
pytest tests/candidate_profiles/test_router.py -v
```

Expected: `404 Not Found` on all routes (router not registered yet)

- [ ] **Step 3: Write `router.py`**

Create `services/orchestrator-api/src/modules/candidate_profiles/router.py`:

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.modules.auth.dependencies import TokenClaims, require_user
from src.modules.candidate_profiles import service
from src.modules.candidate_profiles.schemas import CandidateProfileResponse, SynthesizeRequest

router = APIRouter(prefix="/candidate-profiles", tags=["candidate-profiles"])


@router.post("/synthesize", response_model=CandidateProfileResponse)
def synthesize(
    body: SynthesizeRequest,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        return service.synthesize_profile(
            db, claims.org_id, body.candidate_id, body.job_assessment_id
        )
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.get("/{candidate_id}/{job_assessment_id}", response_model=CandidateProfileResponse)
def get_profile(
    candidate_id: uuid.UUID,
    job_assessment_id: uuid.UUID,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        return service.get_profile(db, claims.org_id, candidate_id, job_assessment_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
```

- [ ] **Step 4: Register router in `main.py`**

Edit `services/orchestrator-api/src/main.py` — add after the existing router imports and `include_router` calls:

```python
# Add to imports (after the job_assessments import):
from src.modules.candidate_profiles.router import router as candidate_profiles_router

# Add after app.include_router(job_assessments_router):
app.include_router(candidate_profiles_router)
```

The final `main.py` should look like:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import HTTPException

from src.config import settings
from src.middleware.auth import AuthMiddleware
from src.middleware.rate_limit import RateLimitMiddleware
from src.middleware.error_handler import http_exception_handler, unhandled_exception_handler
from src.api.health import router as health_router
from src.modules.auth.router import router as auth_router
from src.modules.competency_library.router import router as competency_library_router
from src.modules.job_assessments.router import router as job_assessments_router
from src.modules.candidate_profiles.router import router as candidate_profiles_router

app = FastAPI(
    title="ARAP Orchestrator API",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuthMiddleware)

app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(competency_library_router)
app.include_router(job_assessments_router)
app.include_router(candidate_profiles_router)
```

- [ ] **Step 5: Run all candidate_profiles tests**

```bash
cd services/orchestrator-api
pytest tests/candidate_profiles/ -v
```

Expected: `13 passed` (6 service + 7 router)

- [ ] **Step 6: Run the full orchestrator-api test suite to check for regressions**

```bash
cd services/orchestrator-api
pytest -v
```

Expected: all previously passing tests still pass, plus the 13 new ones.

- [ ] **Step 7: Commit**

```bash
git add services/orchestrator-api/src/modules/candidate_profiles/router.py
git add services/orchestrator-api/src/main.py
git add services/orchestrator-api/tests/candidate_profiles/test_router.py
git commit -m "[TASK-001] feat: add candidate_profiles router and register in main; M3 complete"
```

---

## Self-Review Checklist

- [x] **M3-F01 Candidate Summary Generation:** agent produces 2-3 paragraph `summary` field; written to `candidate_profiles.summary` — Task 1 + Task 2
- [x] **M3-F02 Skill & Experience Matrix:** `skill_matrix_aligned` per-skill with alignment/years/confidence/evidence; stored in `candidate_profiles.skill_matrix["aligned"]` — Task 1 + Task 2
- [x] **M3-F03 Career Growth & Leadership Estimate:** `leadership.level`, `career_velocity`, `scope` produced by agent; `leadership_level_estimate` updated, `experience_matrix.leadership_scope` added — Task 1 + Task 2
- [x] **M3-F04 Strength/Risk Flagging:** `strengths[]` and `risk_flags[]` produced by agent; stored in `candidate_profiles.strengths` and `risk_flags` — Task 1 + Task 2
- [x] **Exit criteria — synthesized end-to-end from real parsed resume:** `POST /synthesize` reads M2 row, calls agent, writes back; integration test covers full path — Task 3
- [x] **Exit criteria — risk_flags feed M4:** `risk_flags` written to `candidate_profiles.risk_flags text[]`; M4 reads this column
- [x] **No placeholders:** all steps contain exact code
- [x] **Type consistency:** `run_candidate_profile_agent` defined in Task 1, consumed by service in Task 2; service functions defined in Task 2, consumed by router in Task 3
- [x] **Auth guard:** `require_user` on both endpoints, tested in `test_synthesize_requires_auth`
- [x] **502 on agent failure:** `RuntimeError` → `HTTPException(502)`, tested in Task 3
