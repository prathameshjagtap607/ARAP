# M5 — Test Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the full candidate test-delivery loop — emailed magic link → passwordless login → DISC-style Q&A with autosave → server-enforced timer → submit — with disconnect/reconnect safety.

**Architecture:** Option A (REST + polling). A new `sessions` FastAPI module handles invite, state, start, per-answer PATCH, and submit. Four Next.js App Router pages in `candidate-web` cover the login → consent → test → done flow. JWT lives in React context (memory only). Every answered question is written to DB before the frontend advances state.

**Tech Stack:** FastAPI, SQLAlchemy 2.x, PostgreSQL, pytest-asyncio, httpx (backend); Next.js 14 App Router, React 18, TypeScript, Tailwind CSS (frontend). No new npm packages required — no WebSocket, no SSE.

## Global Constraints

- Python ≥ 3.11; SQLAlchemy 2.x mapped_column style (match existing models)
- All new FastAPI routes follow the pattern in `src/modules/question_sets/router.py`
- Candidate auth dependency: `require_candidate_scope` from `src/modules/auth/dependencies.py` — already enforces `role == "candidate"` and `assessment_session_id` claim match
- Tests use real PostgreSQL at `TEST_DATABASE_URL` (default `postgresql://arap:arap@localhost:5434/arap_test`) — no mocking DB
- Test fixture pattern: follow `tests/question_sets/conftest.py` — `engine` (session-scoped), `db`, `seed`, `async_client`
- Frontend: no `localStorage` for JWT — React context only
- WCAG 2.1 AA: all inputs have `<label htmlFor>`, focus rings never suppressed, timer in `aria-live="polite"` region
- Git commit format: `[TASK-001] <type>: <description>`
- Never commit to `main` directly — all work on feature branch

---

## File Map

### Backend — `services/orchestrator-api/`

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `src/config.py` | Add SMTP/SendGrid + CANDIDATE_PORTAL_URL settings |
| Create | `src/modules/sessions/__init__.py` | Empty package marker |
| Create | `src/modules/sessions/email.py` | `send_invite_email()` util — SMTP or SendGrid with stdout fallback |
| Create | `src/modules/sessions/schemas.py` | Pydantic request/response models for all 5 endpoints |
| Create | `src/modules/sessions/service.py` | Business logic: invite, get_state, start, save_answer, submit |
| Create | `src/modules/sessions/router.py` | FastAPI routes wiring service + auth deps |
| Modify | `src/main.py` | Register sessions router |
| Create | `tests/sessions/__init__.py` | Empty |
| Create | `tests/sessions/conftest.py` | Fixtures: engine, db, seed (with locked question_set + session_questions), candidate_token, async_client |
| Create | `tests/sessions/test_service.py` | Unit tests for service functions |
| Create | `tests/sessions/test_router.py` | Integration tests for all 5 HTTP endpoints |

### Frontend — `apps/candidate-web/`

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `src/lib/api.ts` | Typed fetch wrapper with Bearer auth header |
| Create | `src/lib/types.ts` | Shared TS types: `SessionState`, `Question`, `AnswerFormat` |
| Create | `src/context/SessionContext.tsx` | `useReducer` context: jwt, session, questions, answers, currentIndex, submitting |
| Create | `src/app/assessment/[sessionId]/page.tsx` | LoginPage: email input → verify-token → redirect to consent |
| Create | `src/app/assessment/[sessionId]/consent/page.tsx` | ConsentPage: show job/duration, T&C checkbox → start → redirect to test |
| Create | `src/app/assessment/[sessionId]/test/page.tsx` | QuestionPage: Q&A runtime, timer, autosave, submit |
| Create | `src/app/assessment/[sessionId]/done/page.tsx` | SubmittedPage: static thank-you |

---

## Task 1: Backend config + email util

**Files:**
- Modify: `services/orchestrator-api/src/config.py`
- Create: `services/orchestrator-api/src/modules/sessions/__init__.py`
- Create: `services/orchestrator-api/src/modules/sessions/email.py`
- Test: `services/orchestrator-api/tests/sessions/test_email.py`

**Interfaces:**
- Produces: `send_invite_email(to: str, link: str, job_title: str, duration_minutes: int) -> bool`
- Produces: `settings.CANDIDATE_PORTAL_URL`, `settings.SMTP_HOST`, `settings.SMTP_PORT`, `settings.SMTP_USER`, `settings.SMTP_PASSWORD`, `settings.SMTP_FROM`, `settings.SENDGRID_API_KEY`

- [ ] **Step 1: Write failing test**

Create `tests/sessions/__init__.py` (empty) and `tests/sessions/test_email.py`:

```python
# tests/sessions/__init__.py
# (empty)
```

```python
# tests/sessions/test_email.py
import logging
from unittest.mock import MagicMock, patch

from src.modules.sessions.email import send_invite_email


def test_send_invite_email_stdout_fallback(caplog):
    """When no SMTP or SendGrid configured, logs warning and returns False."""
    with patch("src.modules.sessions.email.settings") as mock_settings:
        mock_settings.SMTP_HOST = ""
        mock_settings.SENDGRID_API_KEY = ""
        with caplog.at_level(logging.WARNING):
            result = send_invite_email(
                to="alice@example.com",
                link="http://localhost:3000/assessment/abc?token=tok",
                job_title="Engineer",
                duration_minutes=60,
            )
    assert result is False
    assert "no email provider" in caplog.text.lower()


def test_send_invite_email_smtp(monkeypatch):
    """When SMTP_HOST set, calls smtplib.SMTP and returns True."""
    with patch("src.modules.sessions.email.settings") as mock_settings:
        mock_settings.SMTP_HOST = "smtp.example.com"
        mock_settings.SMTP_PORT = 587
        mock_settings.SMTP_USER = "user"
        mock_settings.SMTP_PASSWORD = "pass"
        mock_settings.SMTP_FROM = "noreply@arap.dev"
        mock_settings.SENDGRID_API_KEY = ""
        mock_smtp = MagicMock()
        with patch("smtplib.SMTP", return_value=mock_smtp):
            result = send_invite_email(
                to="alice@example.com",
                link="http://localhost:3000/assessment/abc?token=tok",
                job_title="Engineer",
                duration_minutes=60,
            )
    assert result is True
    mock_smtp.__enter__.return_value.sendmail.assert_called_once()
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd services/orchestrator-api
pytest tests/sessions/test_email.py -v
```
Expected: `ModuleNotFoundError` — `src.modules.sessions.email` does not exist yet.

- [ ] **Step 3: Add config fields**

In `src/config.py`, add after `INGESTION_SERVICE_URL`:

```python
    CANDIDATE_PORTAL_URL: str = "http://localhost:3000"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@arap.dev"
    SENDGRID_API_KEY: str = ""
```

- [ ] **Step 4: Create package and email util**

```python
# src/modules/sessions/__init__.py
# (empty)
```

```python
# src/modules/sessions/email.py
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.config import settings

logger = logging.getLogger(__name__)

_BODY_TEMPLATE = """\
<p>Hi,</p>
<p>You have been invited to complete an assessment for <strong>{job_title}</strong>.</p>
<p>Duration: {duration_minutes} minutes.</p>
<p><a href="{link}">Click here to start your assessment</a></p>
<p>This link is valid for 15 minutes from the time of clicking.</p>
"""


def send_invite_email(
    to: str,
    link: str,
    job_title: str,
    duration_minutes: int,
) -> bool:
    """Send magic-link invite email. Returns True if sent, False if no provider configured."""
    body_html = _BODY_TEMPLATE.format(
        job_title=job_title, duration_minutes=duration_minutes, link=link
    )

    if settings.SENDGRID_API_KEY:
        return _send_via_sendgrid(to, body_html, job_title)
    if settings.SMTP_HOST:
        return _send_via_smtp(to, body_html, job_title)

    logger.warning("no email provider configured — link not sent: %s", link)
    return False


def _send_via_smtp(to: str, body_html: str, job_title: str) -> bool:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Your assessment invitation: {job_title}"
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    msg.attach(MIMEText(body_html, "html"))
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as smtp:
        smtp.starttls()
        if settings.SMTP_USER:
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.sendmail(settings.SMTP_FROM, to, msg.as_string())
    return True


def _send_via_sendgrid(to: str, body_html: str, job_title: str) -> bool:
    import urllib.request, json as _json, urllib.error
    payload = _json.dumps({
        "personalizations": [{"to": [{"email": to}]}],
        "from": {"email": settings.SMTP_FROM},
        "subject": f"Your assessment invitation: {job_title}",
        "content": [{"type": "text/html", "value": body_html}],
    }).encode()
    req = urllib.request.Request(
        "https://api.sendgrid.com/v3/mail/send",
        data=payload,
        headers={
            "Authorization": f"Bearer {settings.SENDGRID_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status in (200, 202)
    except urllib.error.HTTPError as e:
        logger.error("sendgrid error %s: %s", e.code, e.read())
        return False
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd services/orchestrator-api
pytest tests/sessions/test_email.py -v
```
Expected: 2 PASSED.

- [ ] **Step 6: Commit**

```bash
git add services/orchestrator-api/src/config.py \
        services/orchestrator-api/src/modules/sessions/__init__.py \
        services/orchestrator-api/src/modules/sessions/email.py \
        services/orchestrator-api/tests/sessions/__init__.py \
        services/orchestrator-api/tests/sessions/test_email.py
git commit -m "[TASK-001] feat: add sessions module skeleton, email util, config fields (M5-F01)"
```

---

## Task 2: Backend schemas + service (invite, get_state, start)

**Files:**
- Create: `services/orchestrator-api/src/modules/sessions/schemas.py`
- Create: `services/orchestrator-api/src/modules/sessions/service.py` (partial — invite, get_state, start)
- Create: `services/orchestrator-api/tests/sessions/conftest.py`
- Create: `services/orchestrator-api/tests/sessions/test_service.py` (invite + get_state + start)

**Interfaces:**
- Consumes: `AssessmentSession`, `QuestionSet`, `SessionQuestion`, `Candidate`, `JobAssessment` models; `auth.service.request_candidate_token()`; `send_invite_email()`
- Produces:
  - `invite_candidate(db, session_id, org_id) -> InviteResponse`
  - `get_session_state(db, session_id, org_id) -> SessionStateResponse`
  - `start_session(db, session_id, org_id) -> SessionStateResponse`

- [ ] **Step 1: Write conftest**

Create `tests/sessions/conftest.py`:

```python
import os
import uuid as _uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

import src.models  # noqa: F401
from src.models.assessment_sessions import AssessmentSession
from src.models.base import Base
from src.models.candidates import Candidate
from src.models.job_assessments import JobAssessment
from src.models.orgs import Org
from src.models.question_sets import QuestionSet
from src.models.session_questions import SessionQuestion
from src.models.users import User
from src.modules.auth.token import create_access_token

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://arap:arap@localhost:5434/arap_test"
)


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
def seed(db: Session) -> dict:
    uid = _uuid.uuid4().hex[:8]
    org = Org(name=f"Sessions Test Org {uid}")
    db.add(org)
    db.flush()

    admin = User(
        org_id=org.id,
        email=f"admin-{uid}@test.com",
        role="admin",
        password_hash="x",
    )
    db.add(admin)
    db.flush()

    candidate = Candidate(
        org_id=org.id,
        name="Alice",
        email=f"alice-{uid}@example.com",
        auth_method="magic_link",
    )
    db.add(candidate)
    db.flush()

    job = JobAssessment(
        org_id=org.id,
        title="Senior Engineer",
        department="Engineering",
        difficulty_level="senior",
        duration_minutes=30,
        competency_weightage={"problem_solving": 100.0},
        created_by=admin.id,
    )
    db.add(job)
    db.flush()

    session = AssessmentSession(
        org_id=org.id,
        job_assessment_id=job.id,
        candidate_id=candidate.id,
        time_budget_seconds=1800,
    )
    db.add(session)
    db.flush()

    # Locked question set with 2 questions
    qset = QuestionSet(
        org_id=org.id,
        session_id=session.id,
        generation_prompt_version="v1",
        locked_at=datetime.now(UTC),
    )
    db.add(qset)
    db.flush()

    q1 = SessionQuestion(
        org_id=org.id,
        question_set_id=qset.id,
        sequence_no=1,
        question={"text": "Describe your Python experience."},
        category="Technical",
        target_competencies=["problem_solving"],
        difficulty="medium",
        answer_format="long_text",
    )
    q2 = SessionQuestion(
        org_id=org.id,
        question_set_id=qset.id,
        sequence_no=2,
        question={"text": "What is 2+2?", "options": {"A": "3", "B": "4", "C": "5"}},
        category="Technical",
        target_competencies=["problem_solving"],
        difficulty="easy",
        answer_format="multiple_choice",
        options={"A": "3", "B": "4", "C": "5"},
    )
    db.add_all([q1, q2])
    db.commit()

    db.refresh(org); db.refresh(admin); db.refresh(candidate)
    db.refresh(job); db.refresh(session); db.refresh(qset)
    db.refresh(q1); db.refresh(q2)

    return {
        "org": org,
        "admin": admin,
        "candidate": candidate,
        "job": job,
        "session": session,
        "qset": qset,
        "q1": q1,
        "q2": q2,
    }


@pytest.fixture
def candidate_token(seed: dict) -> str:
    return create_access_token({
        "sub": str(seed["candidate"].id),
        "role": "candidate",
        "org_id": str(seed["org"].id),
        "assessment_session_id": str(seed["session"].id),
    })


@pytest.fixture
def user_token(seed: dict) -> str:
    return create_access_token({
        "sub": str(seed["admin"].id),
        "role": "admin",
        "org_id": str(seed["org"].id),
    })


@pytest_asyncio.fixture
async def async_client(db: Session):
    from src.main import app
    from src.database import get_db
    app.dependency_overrides[get_db] = lambda: db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Write failing service tests**

Create `tests/sessions/test_service.py`:

```python
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from src.modules.sessions import service


def test_invite_candidate_raises_if_not_locked(db, seed):
    """invite_candidate raises ValueError if question set has no locked_at."""
    from src.models.question_sets import QuestionSet
    qset = db.query(QuestionSet).filter_by(session_id=seed["session"].id).first()
    qset.locked_at = None
    db.flush()
    with pytest.raises(ValueError, match="locked"):
        service.invite_candidate(db, seed["session"].id, seed["org"].id)
    qset.locked_at = datetime.now(UTC)
    db.flush()


def test_invite_candidate_returns_link_and_email_sent(db, seed):
    """invite_candidate returns link and calls send_invite_email."""
    with patch("src.modules.sessions.service.send_invite_email", return_value=True) as mock_mail:
        result = service.invite_candidate(db, seed["session"].id, seed["org"].id)
    assert "assessment" in result.link
    assert str(seed["session"].id) in result.link
    assert result.email_sent is True
    mock_mail.assert_called_once()


def test_get_session_state_not_started(db, seed):
    """get_session_state returns seconds_remaining=None before start."""
    result = service.get_session_state(db, seed["session"].id, seed["org"].id)
    assert result.status == "invited"
    assert result.seconds_remaining is None
    assert len(result.questions) == 2
    assert result.questions[0].sequence_no == 1


def test_start_session_transitions_status(db, seed):
    """start_session sets started_at and transitions status to in_progress."""
    result = service.start_session(db, seed["session"].id, seed["org"].id)
    assert result.status == "in_progress"
    assert result.seconds_remaining is not None
    assert result.seconds_remaining <= 1800


def test_start_session_idempotent(db, seed):
    """Calling start_session twice returns same in_progress state."""
    r1 = service.start_session(db, seed["session"].id, seed["org"].id)
    r2 = service.start_session(db, seed["session"].id, seed["org"].id)
    assert r2.status == "in_progress"
    # started_at must not change on second call
    from src.models.assessment_sessions import AssessmentSession
    s = db.query(AssessmentSession).filter_by(id=seed["session"].id).first()
    assert s.started_at == db.query(AssessmentSession).filter_by(id=seed["session"].id).first().started_at


def test_get_session_state_seconds_remaining_after_start(db, seed):
    """seconds_remaining decreases from time_budget_seconds after start."""
    result = service.get_session_state(db, seed["session"].id, seed["org"].id)
    assert result.seconds_remaining is not None
    assert result.seconds_remaining < 1800
    assert result.seconds_remaining > 0
```

- [ ] **Step 3: Run to verify failure**

```bash
cd services/orchestrator-api
pytest tests/sessions/test_service.py -v
```
Expected: `ImportError` — `src.modules.sessions.service` does not exist.

- [ ] **Step 4: Write schemas**

Create `src/modules/sessions/schemas.py`:

```python
import uuid
from datetime import datetime

from pydantic import BaseModel


class QuestionInSession(BaseModel):
    id: uuid.UUID
    sequence_no: int
    question: dict
    category: str
    target_competencies: list[str]
    difficulty: str
    answer_format: str
    options: dict | None
    answer_text: str | None
    answered_at: datetime | None

    model_config = {"from_attributes": True}


class SessionStateResponse(BaseModel):
    id: uuid.UUID
    status: str
    seconds_remaining: int | None
    time_budget_seconds: int
    job_title: str
    duration_minutes: int
    questions: list[QuestionInSession]

    model_config = {"from_attributes": True}


class InviteResponse(BaseModel):
    link: str
    email_sent: bool


class StartResponse(BaseModel):
    status: str
    seconds_remaining: int | None


class AnswerRequest(BaseModel):
    answer_text: str


class AnswerResponse(BaseModel):
    id: uuid.UUID
    answer_text: str | None
    answered_at: datetime | None

    model_config = {"from_attributes": True}


class SubmitResponse(BaseModel):
    status: str
    completed_at: datetime | None
```

- [ ] **Step 5: Write service (invite, get_state, start)**

Create `src/modules/sessions/service.py`:

```python
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from src.config import settings
from src.models.assessment_sessions import AssessmentSession
from src.models.candidates import Candidate
from src.models.job_assessments import JobAssessment
from src.models.question_sets import QuestionSet
from src.models.session_questions import SessionQuestion
from src.modules.auth import service as auth_service
from src.modules.sessions.email import send_invite_email
from src.modules.sessions.schemas import (
    AnswerResponse,
    InviteResponse,
    QuestionInSession,
    SessionStateResponse,
    SubmitResponse,
)

logger = logging.getLogger(__name__)


def _get_session_or_404(db: Session, session_id: uuid.UUID, org_id: uuid.UUID) -> AssessmentSession:
    s = db.query(AssessmentSession).filter_by(id=session_id, org_id=org_id).first()
    if not s:
        raise LookupError("assessment session not found")
    return s


def _seconds_remaining(session: AssessmentSession) -> int | None:
    if session.started_at is None:
        return None
    started = session.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    elapsed = int((datetime.now(UTC) - started).total_seconds())
    return max(0, session.time_budget_seconds - elapsed)


def _build_state(db: Session, session: AssessmentSession) -> SessionStateResponse:
    job = db.query(JobAssessment).filter_by(id=session.job_assessment_id).first()
    qset = db.query(QuestionSet).filter_by(session_id=session.id).first()
    questions: list[QuestionInSession] = []
    if qset:
        rows = (
            db.query(SessionQuestion)
            .filter_by(question_set_id=qset.id)
            .order_by(SessionQuestion.sequence_no)
            .all()
        )
        questions = [QuestionInSession.model_validate(r) for r in rows]
    return SessionStateResponse(
        id=session.id,
        status=session.status,
        seconds_remaining=_seconds_remaining(session),
        time_budget_seconds=session.time_budget_seconds,
        job_title=job.title if job else "",
        duration_minutes=job.duration_minutes if job else 0,
        questions=questions,
    )


def invite_candidate(
    db: Session, session_id: uuid.UUID, org_id: uuid.UUID
) -> InviteResponse:
    session = _get_session_or_404(db, session_id, org_id)
    qset = db.query(QuestionSet).filter_by(session_id=session_id).first()
    if not qset or qset.locked_at is None:
        raise ValueError("question set must be locked before sending invite")

    candidate = db.query(Candidate).filter_by(id=session.candidate_id, org_id=org_id).first()
    job = db.query(JobAssessment).filter_by(id=session.job_assessment_id).first()

    raw_token = auth_service.request_candidate_token(
        db, candidate.email, org_id, session_id
    )
    link = f"{settings.CANDIDATE_PORTAL_URL}/assessment/{session_id}?token={raw_token}"

    email_sent = send_invite_email(
        to=candidate.email,
        link=link,
        job_title=job.title if job else "",
        duration_minutes=job.duration_minutes if job else 0,
    )
    logger.info("invite sent session=%s email_sent=%s", session_id, email_sent)
    return InviteResponse(link=link, email_sent=email_sent)


def get_session_state(
    db: Session, session_id: uuid.UUID, org_id: uuid.UUID
) -> SessionStateResponse:
    session = _get_session_or_404(db, session_id, org_id)
    return _build_state(db, session)


def start_session(
    db: Session, session_id: uuid.UUID, org_id: uuid.UUID
) -> SessionStateResponse:
    session = _get_session_or_404(db, session_id, org_id)
    if session.status in ("completed", "expired"):
        raise ValueError(f"session is already {session.status}")
    if session.status == "invited":
        session.started_at = datetime.now(UTC)
        session.status = "in_progress"
        db.flush()
        db.commit()
    return _build_state(db, session)
```

- [ ] **Step 6: Run service tests**

```bash
cd services/orchestrator-api
pytest tests/sessions/test_service.py -v
```
Expected: 6 PASSED.

- [ ] **Step 7: Commit**

```bash
git add services/orchestrator-api/src/modules/sessions/schemas.py \
        services/orchestrator-api/src/modules/sessions/service.py \
        services/orchestrator-api/tests/sessions/conftest.py \
        services/orchestrator-api/tests/sessions/test_service.py
git commit -m "[TASK-001] feat: sessions service — invite, get_state, start (M5-F01 F02)"
```

---

## Task 3: Backend service — save_answer + submit + router + main.py

**Files:**
- Modify: `services/orchestrator-api/src/modules/sessions/service.py` (add save_answer, submit)
- Create: `services/orchestrator-api/src/modules/sessions/router.py`
- Modify: `services/orchestrator-api/src/main.py`
- Modify: `services/orchestrator-api/tests/sessions/test_service.py` (add answer + submit tests)
- Create: `services/orchestrator-api/tests/sessions/test_router.py`

**Interfaces:**
- Consumes: all schemas from Task 2; `require_candidate_scope`, `require_user` from `src/modules/auth/dependencies.py`
- Produces:
  - `save_answer(db, session_id, question_id, org_id, answer_text) -> AnswerResponse`
  - `submit_session(db, session_id, org_id) -> SubmitResponse`
  - HTTP routes: `POST /sessions/{id}/invite`, `GET /sessions/{id}`, `POST /sessions/{id}/start`, `PATCH /sessions/{id}/questions/{qid}/answer`, `POST /sessions/{id}/submit`

- [ ] **Step 1: Write failing tests for save_answer and submit**

Append to `tests/sessions/test_service.py`:

```python
def test_save_answer_long_text(db, seed):
    """save_answer persists answer_text and answered_at for long_text question."""
    # ensure session is started first
    service.start_session(db, seed["session"].id, seed["org"].id)
    result = service.save_answer(
        db, seed["session"].id, seed["q1"].id, seed["org"].id, "My Python answer"
    )
    assert result.answer_text == "My Python answer"
    assert result.answered_at is not None


def test_save_answer_rejects_completed_session(db, seed):
    """save_answer raises ValueError if session is completed."""
    from src.models.assessment_sessions import AssessmentSession
    s = db.query(AssessmentSession).filter_by(id=seed["session"].id).first()
    orig_status = s.status
    s.status = "completed"
    db.flush()
    with pytest.raises(ValueError, match="completed"):
        service.save_answer(
            db, seed["session"].id, seed["q1"].id, seed["org"].id, "late answer"
        )
    s.status = orig_status
    db.flush()


def test_submit_session_marks_completed(db, seed):
    """submit_session transitions in_progress → completed."""
    result = service.submit_session(db, seed["session"].id, seed["org"].id)
    assert result.status == "completed"
    assert result.completed_at is not None


def test_submit_session_idempotent(db, seed):
    """submit_session called twice returns completed without error."""
    r1 = service.submit_session(db, seed["session"].id, seed["org"].id)
    r2 = service.submit_session(db, seed["session"].id, seed["org"].id)
    assert r2.status in ("completed", "expired")


def test_submit_session_expired_no_answers(db, seed):
    """submit_session with no answers and past deadline → expired."""
    from datetime import timedelta
    from src.models.assessment_sessions import AssessmentSession
    # Create a fresh session that has already expired
    from src.models.question_sets import QuestionSet
    new_session = AssessmentSession(
        org_id=seed["org"].id,
        job_assessment_id=seed["job"].id,
        candidate_id=seed["candidate"].id,
        time_budget_seconds=1,
        started_at=datetime.now(UTC) - timedelta(seconds=10),
        status="in_progress",
    )
    db.add(new_session)
    db.flush()
    new_qset = QuestionSet(
        org_id=seed["org"].id,
        session_id=new_session.id,
        generation_prompt_version="v1",
        locked_at=datetime.now(UTC),
    )
    db.add(new_qset)
    db.flush()
    db.commit()
    result = service.submit_session(db, new_session.id, seed["org"].id)
    assert result.status == "expired"
```

- [ ] **Step 2: Run to verify failure**

```bash
cd services/orchestrator-api
pytest tests/sessions/test_service.py -v -k "save_answer or submit"
```
Expected: `AttributeError` — `save_answer`/`submit_session` not defined.

- [ ] **Step 3: Add save_answer and submit_session to service.py**

Append to `src/modules/sessions/service.py`:

```python
def save_answer(
    db: Session,
    session_id: uuid.UUID,
    question_id: uuid.UUID,
    org_id: uuid.UUID,
    answer_text: str,
) -> AnswerResponse:
    session = _get_session_or_404(db, session_id, org_id)
    if session.status in ("completed", "expired"):
        raise ValueError(f"session is {session.status} — answers no longer accepted")
    q = db.query(SessionQuestion).filter_by(id=question_id).first()
    if not q:
        raise LookupError("question not found")
    q.answer_text = answer_text
    q.answered_at = datetime.now(UTC)
    db.flush()
    db.commit()
    db.refresh(q)
    return AnswerResponse.model_validate(q)


def submit_session(
    db: Session, session_id: uuid.UUID, org_id: uuid.UUID
) -> SubmitResponse:
    session = _get_session_or_404(db, session_id, org_id)
    if session.status in ("completed", "expired"):
        return SubmitResponse(status=session.status, completed_at=session.completed_at)

    now = datetime.now(UTC)
    has_answers = (
        db.query(SessionQuestion)
        .join(QuestionSet, SessionQuestion.question_set_id == QuestionSet.id)
        .filter(QuestionSet.session_id == session_id, SessionQuestion.answered_at.isnot(None))
        .count()
    ) > 0

    expired = _seconds_remaining(session) == 0

    if expired and not has_answers:
        session.status = "expired"
    else:
        session.status = "completed"
        session.completed_at = now

    db.flush()
    db.commit()
    logger.info("session %s submitted status=%s", session_id, session.status)
    return SubmitResponse(status=session.status, completed_at=session.completed_at)
```

- [ ] **Step 4: Run service tests**

```bash
cd services/orchestrator-api
pytest tests/sessions/test_service.py -v
```
Expected: all PASSED.

- [ ] **Step 5: Write failing router tests**

Create `tests/sessions/test_router.py`:

```python
import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def started_client(async_client, seed, candidate_token, db):
    """Client fixture with session already started."""
    from src.models.assessment_sessions import AssessmentSession
    from datetime import UTC, datetime
    s = db.query(AssessmentSession).filter_by(id=seed["session"].id).first()
    if s.status == "invited":
        s.status = "in_progress"
        s.started_at = datetime.now(UTC)
        db.commit()
    return async_client


@pytest.mark.asyncio
async def test_invite_endpoint_requires_user_token(async_client, seed, candidate_token):
    """POST /sessions/{id}/invite rejects candidate JWT."""
    resp = await async_client.post(
        f"/sessions/{seed['session'].id}/invite",
        headers={"Authorization": f"Bearer {candidate_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_invite_endpoint_returns_link(async_client, seed, user_token):
    """POST /sessions/{id}/invite returns link and email_sent."""
    from unittest.mock import patch
    with patch("src.modules.sessions.service.send_invite_email", return_value=False):
        resp = await async_client.post(
            f"/sessions/{seed['session'].id}/invite",
            headers={"Authorization": f"Bearer {user_token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "link" in data
    assert str(seed["session"].id) in data["link"]
    assert data["email_sent"] is False


@pytest.mark.asyncio
async def test_get_session_state(async_client, seed, candidate_token):
    """GET /sessions/{id} returns status and questions."""
    resp = await async_client.get(
        f"/sessions/{seed['session'].id}",
        headers={"Authorization": f"Bearer {candidate_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("invited", "in_progress", "completed", "expired")
    assert len(data["questions"]) == 2


@pytest.mark.asyncio
async def test_start_session_endpoint(async_client, seed, candidate_token, db):
    """POST /sessions/{id}/start transitions to in_progress."""
    from src.models.assessment_sessions import AssessmentSession
    s = db.query(AssessmentSession).filter_by(id=seed["session"].id).first()
    s.status = "invited"
    s.started_at = None
    db.commit()
    resp = await async_client.post(
        f"/sessions/{seed['session'].id}/start",
        headers={"Authorization": f"Bearer {candidate_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"


@pytest.mark.asyncio
async def test_patch_answer_endpoint(started_client, seed, candidate_token):
    """PATCH /sessions/{id}/questions/{qid}/answer saves answer."""
    resp = await started_client.patch(
        f"/sessions/{seed['session'].id}/questions/{seed['q1'].id}/answer",
        json={"answer_text": "I have 5 years of Python experience."},
        headers={"Authorization": f"Bearer {candidate_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer_text"] == "I have 5 years of Python experience."
    assert data["answered_at"] is not None


@pytest.mark.asyncio
async def test_patch_answer_wrong_session_rejected(async_client, seed, candidate_token):
    """PATCH with question not belonging to this session returns 404."""
    import uuid
    resp = await async_client.patch(
        f"/sessions/{seed['session'].id}/questions/{uuid.uuid4()}/answer",
        json={"answer_text": "Anything"},
        headers={"Authorization": f"Bearer {candidate_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_submit_endpoint(started_client, seed, candidate_token):
    """POST /sessions/{id}/submit transitions to completed."""
    resp = await started_client.post(
        f"/sessions/{seed['session'].id}/submit",
        headers={"Authorization": f"Bearer {candidate_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] in ("completed", "expired")


@pytest.mark.asyncio
async def test_candidate_cannot_access_other_session(async_client, seed, db):
    """Candidate JWT for session A cannot access session B."""
    import uuid
    from src.modules.auth.token import create_access_token
    other_id = uuid.uuid4()
    token = create_access_token({
        "sub": str(seed["candidate"].id),
        "role": "candidate",
        "org_id": str(seed["org"].id),
        "assessment_session_id": str(other_id),
    })
    resp = await async_client.get(
        f"/sessions/{seed['session'].id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
```

- [ ] **Step 6: Run router tests to verify failure**

```bash
cd services/orchestrator-api
pytest tests/sessions/test_router.py -v
```
Expected: `404 Not Found` for all routes — router not registered yet.

- [ ] **Step 7: Create router**

Create `src/modules/sessions/router.py`:

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.modules.auth.dependencies import TokenClaims, require_candidate_scope, require_user
from src.modules.sessions import service
from src.modules.sessions.schemas import (
    AnswerRequest,
    AnswerResponse,
    InviteResponse,
    SessionStateResponse,
    SubmitResponse,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("/{session_id}/invite", response_model=InviteResponse)
def invite(
    session_id: uuid.UUID,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        return service.invite_candidate(db, session_id, claims.org_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("/{session_id}", response_model=SessionStateResponse)
def get_state(
    session_id: uuid.UUID,
    claims: TokenClaims = Depends(require_candidate_scope),
    db: Session = Depends(get_db),
):
    try:
        return service.get_session_state(db, session_id, claims.org_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{session_id}/start", response_model=SessionStateResponse)
def start(
    session_id: uuid.UUID,
    claims: TokenClaims = Depends(require_candidate_scope),
    db: Session = Depends(get_db),
):
    try:
        return service.start_session(db, session_id, claims.org_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.patch(
    "/{session_id}/questions/{question_id}/answer",
    response_model=AnswerResponse,
)
def answer(
    session_id: uuid.UUID,
    question_id: uuid.UUID,
    body: AnswerRequest,
    claims: TokenClaims = Depends(require_candidate_scope),
    db: Session = Depends(get_db),
):
    try:
        return service.save_answer(db, session_id, question_id, claims.org_id, body.answer_text)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post("/{session_id}/submit", response_model=SubmitResponse)
def submit(
    session_id: uuid.UUID,
    claims: TokenClaims = Depends(require_candidate_scope),
    db: Session = Depends(get_db),
):
    try:
        return service.submit_session(db, session_id, claims.org_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
```

- [ ] **Step 8: Register router in main.py**

In `src/main.py`, add after the `question_sets_router` import:

```python
from src.modules.sessions.router import router as sessions_router
```

And after `app.include_router(question_sets_router)`:

```python
app.include_router(sessions_router)
```

- [ ] **Step 9: Run all session tests**

```bash
cd services/orchestrator-api
pytest tests/sessions/ -v
```
Expected: all PASSED.

- [ ] **Step 10: Commit**

```bash
git add services/orchestrator-api/src/modules/sessions/service.py \
        services/orchestrator-api/src/modules/sessions/router.py \
        services/orchestrator-api/src/main.py \
        services/orchestrator-api/tests/sessions/test_service.py \
        services/orchestrator-api/tests/sessions/test_router.py
git commit -m "[TASK-001] feat: sessions router — answer, submit, invite endpoints (M5-F02 F03 F04 F05)"
```

---

## Task 4: Frontend — shared types, API client, SessionContext

**Files:**
- Create: `apps/candidate-web/src/lib/types.ts`
- Create: `apps/candidate-web/src/lib/api.ts`
- Create: `apps/candidate-web/src/context/SessionContext.tsx`

**Interfaces:**
- Produces:
  - `SessionState`, `Question`, `SessionAction` types
  - `apiFetch(path, options)` — typed fetch with Bearer header
  - `SessionProvider`, `useSession()` hook — exposes state + dispatch

> Frontend has no test runner configured. Verify correctness by running `npm run build` after each task — TypeScript compilation is the check.

- [ ] **Step 1: Create types**

Create `apps/candidate-web/src/lib/types.ts`:

```typescript
export type AnswerFormat = "multiple_choice" | "short_text" | "long_text";

export interface Question {
  id: string;
  sequence_no: number;
  question: { text: string; options?: Record<string, string> };
  category: string;
  target_competencies: string[];
  difficulty: string;
  answer_format: AnswerFormat;
  options: Record<string, string> | null;
  answer_text: string | null;
  answered_at: string | null;
}

export interface SessionData {
  id: string;
  status: "invited" | "in_progress" | "completed" | "expired";
  seconds_remaining: number | null;
  time_budget_seconds: number;
  job_title: string;
  duration_minutes: number;
  questions: Question[];
}

export interface SessionState {
  jwt: string | null;
  session: SessionData | null;
  answers: Record<string, string>;
  currentIndex: number;
  submitting: boolean;
}

export type SessionAction =
  | { type: "SET_JWT"; jwt: string }
  | { type: "SET_SESSION"; session: SessionData }
  | { type: "SET_ANSWER"; questionId: string; text: string }
  | { type: "SET_INDEX"; index: number }
  | { type: "SET_SUBMITTING"; value: boolean }
  | { type: "REHYDRATE"; session: SessionData };
```

- [ ] **Step 2: Create API client**

Create `apps/candidate-web/src/lib/api.ts`:

```typescript
const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function apiFetch<T>(
  path: string,
  options: RequestInit & { jwt?: string } = {}
): Promise<T> {
  const { jwt, ...rest } = options;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(rest.headers as Record<string, string>),
  };
  if (jwt) headers["Authorization"] = `Bearer ${jwt}`;
  const res = await fetch(`${BASE_URL}${path}`, { ...rest, headers });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail?.detail ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}
```

- [ ] **Step 3: Create SessionContext**

Create `apps/candidate-web/src/context/SessionContext.tsx`:

```typescript
"use client";

import {
  createContext,
  useContext,
  useReducer,
  ReactNode,
} from "react";
import type { SessionAction, SessionState } from "@/lib/types";

const initialState: SessionState = {
  jwt: null,
  session: null,
  answers: {},
  currentIndex: 0,
  submitting: false,
};

function reducer(state: SessionState, action: SessionAction): SessionState {
  switch (action.type) {
    case "SET_JWT":
      return { ...state, jwt: action.jwt };
    case "SET_SESSION":
      return { ...state, session: action.session };
    case "REHYDRATE": {
      const serverAnswers: Record<string, string> = {};
      for (const q of action.session.questions) {
        if (q.answer_text) serverAnswers[q.id] = q.answer_text;
      }
      // Server answers fill gaps — locally unsaved answers (not yet in DB) win
      return {
        ...state,
        session: action.session,
        answers: { ...serverAnswers, ...state.answers },
      };
    }
    case "SET_ANSWER":
      return {
        ...state,
        answers: { ...state.answers, [action.questionId]: action.text },
      };
    case "SET_INDEX":
      return { ...state, currentIndex: action.index };
    case "SET_SUBMITTING":
      return { ...state, submitting: action.value };
    default:
      return state;
  }
}

const SessionContext = createContext<{
  state: SessionState;
  dispatch: React.Dispatch<SessionAction>;
} | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);
  return (
    <SessionContext.Provider value={{ state, dispatch }}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used within SessionProvider");
  return ctx;
}
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd apps/candidate-web
npm run build
```
Expected: Build succeeds (or fails only on pre-existing unrelated issues — not on the new files).

- [ ] **Step 5: Commit**

```bash
git add apps/candidate-web/src/lib/types.ts \
        apps/candidate-web/src/lib/api.ts \
        apps/candidate-web/src/context/SessionContext.tsx
git commit -m "[TASK-001] feat: candidate-web shared types, api client, SessionContext (M5)"
```

---

## Task 5: Frontend — LoginPage + ConsentPage

**Files:**
- Create: `apps/candidate-web/src/app/assessment/[sessionId]/page.tsx`
- Create: `apps/candidate-web/src/app/assessment/[sessionId]/layout.tsx`
- Create: `apps/candidate-web/src/app/assessment/[sessionId]/consent/page.tsx`

**Interfaces:**
- Consumes: `useSession()`, `apiFetch()`, `SessionData`, `SessionAction`
- Produces: pages at `/assessment/[sessionId]` and `/assessment/[sessionId]/consent`

- [ ] **Step 1: Create layout wrapping SessionProvider**

Create `apps/candidate-web/src/app/assessment/[sessionId]/layout.tsx`:

```typescript
import { SessionProvider } from "@/context/SessionContext";

export default function AssessmentLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <SessionProvider>{children}</SessionProvider>;
}
```

- [ ] **Step 2: Create LoginPage**

Create `apps/candidate-web/src/app/assessment/[sessionId]/page.tsx`:

```typescript
"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { apiFetch } from "@/lib/api";
import { useSession } from "@/context/SessionContext";

export default function LoginPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { dispatch } = useSession();
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const token = searchParams.get("token") ?? "";

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const data = await apiFetch<{ access_token: string }>(
        "/auth/candidate/verify-token",
        {
          method: "POST",
          body: JSON.stringify({ token, assessment_session_id: sessionId }),
        }
      );
      dispatch({ type: "SET_JWT", jwt: data.access_token });
      router.push(`/assessment/${sessionId}/consent`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-6">
      <div className="max-w-md w-full space-y-6">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          Access Your Assessment
        </h1>
        <p className="text-slate-500">Enter the email address your invitation was sent to.</p>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-slate-700 mb-1">
              Email address
            </label>
            <input
              id="email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-4 py-2 text-slate-900
                         focus:outline focus:outline-2 focus:outline-slate-900"
            />
          </div>
          {error && (
            <p role="alert" className="text-sm text-red-600">
              {error}
            </p>
          )}
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-slate-900 px-6 py-3 text-white font-medium
                       disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {loading ? "Verifying…" : "Continue"}
          </button>
        </form>
      </div>
    </main>
  );
}
```

- [ ] **Step 3: Create ConsentPage**

Create `apps/candidate-web/src/app/assessment/[sessionId]/consent/page.tsx`:

```typescript
"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useSession } from "@/context/SessionContext";
import type { SessionData } from "@/lib/types";

export default function ConsentPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const router = useRouter();
  const { state, dispatch } = useSession();
  const [agreed, setAgreed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!state.jwt) return;
    apiFetch<SessionData>(`/sessions/${sessionId}`, { jwt: state.jwt })
      .then((data) => dispatch({ type: "SET_SESSION", session: data }))
      .catch(() => {});
  }, [state.jwt, sessionId, dispatch]);

  async function handleStart() {
    if (!state.jwt) return;
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch<SessionData>(`/sessions/${sessionId}/start`, {
        method: "POST",
        jwt: state.jwt,
      });
      dispatch({ type: "SET_SESSION", session: data });
      router.push(`/assessment/${sessionId}/test`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to start");
    } finally {
      setLoading(false);
    }
  }

  const session = state.session;

  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-6">
      <div className="max-w-md w-full space-y-6">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          {session?.job_title ?? "Assessment"}
        </h1>
        <ul className="text-slate-600 space-y-1 text-sm list-disc list-inside">
          <li>Duration: {session?.duration_minutes ?? "—"} minutes</li>
          <li>Questions: {session?.questions.length ?? "—"}</li>
          <li>You may navigate between questions before submitting.</li>
          <li>Your progress is saved after each answer.</li>
        </ul>
        <div className="flex items-start gap-3">
          <input
            id="consent"
            type="checkbox"
            checked={agreed}
            onChange={(e) => setAgreed(e.target.checked)}
            className="mt-1"
          />
          <label htmlFor="consent" className="text-sm text-slate-700">
            I confirm this is my own work and I agree to the assessment terms.
          </label>
        </div>
        {error && (
          <p role="alert" className="text-sm text-red-600">
            {error}
          </p>
        )}
        <button
          onClick={handleStart}
          disabled={!agreed || loading}
          className="w-full rounded-lg bg-slate-900 px-6 py-3 text-white font-medium
                     disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {loading ? "Starting…" : "Start Assessment"}
        </button>
      </div>
    </main>
  );
}
```

- [ ] **Step 4: Verify build**

```bash
cd apps/candidate-web
npm run build
```
Expected: Build succeeds with no TypeScript errors on the new files.

- [ ] **Step 5: Commit**

```bash
git add apps/candidate-web/src/app/assessment/
git commit -m "[TASK-001] feat: LoginPage and ConsentPage for candidate portal (M5-F01)"
```

---

## Task 6: Frontend — QuestionPage (timer + autosave + submit)

**Files:**
- Create: `apps/candidate-web/src/app/assessment/[sessionId]/test/page.tsx`
- Create: `apps/candidate-web/src/app/assessment/[sessionId]/done/page.tsx`

**Interfaces:**
- Consumes: `useSession()`, `apiFetch()`, `Question`, `SessionData`
- Produces: pages at `/assessment/[sessionId]/test` and `/assessment/[sessionId]/done`

- [ ] **Step 1: Create SubmittedPage**

Create `apps/candidate-web/src/app/assessment/[sessionId]/done/page.tsx`:

```typescript
export default function SubmittedPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-6">
      <div className="max-w-md w-full text-center space-y-4">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          Assessment Submitted
        </h1>
        <p className="text-slate-500">
          Thank you for completing your assessment. You will be contacted with
          next steps.
        </p>
      </div>
    </main>
  );
}
```

- [ ] **Step 2: Create QuestionPage**

Create `apps/candidate-web/src/app/assessment/[sessionId]/test/page.tsx`:

```typescript
"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useSession } from "@/context/SessionContext";
import type { Question, SessionData } from "@/lib/types";

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60).toString().padStart(2, "0");
  const s = (seconds % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

export default function QuestionPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const router = useRouter();
  const { state, dispatch } = useSession();
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null);
  const [saving, setSaving] = useState<Record<string, boolean>>({});
  const [saveError, setSaveError] = useState<string | null>(null);
  const submitCalledRef = useRef(false);

  // Rehydrate from server on mount and on reconnect
  const rehydrate = useCallback(async () => {
    if (!state.jwt) return;
    try {
      const data = await apiFetch<SessionData>(`/sessions/${sessionId}`, {
        jwt: state.jwt,
      });
      dispatch({ type: "REHYDRATE", session: data });
      if (data.seconds_remaining !== null) {
        setSecondsLeft(data.seconds_remaining);
      }
    } catch {}
  }, [state.jwt, sessionId, dispatch]);

  useEffect(() => {
    rehydrate();
    window.addEventListener("online", rehydrate);
    return () => window.removeEventListener("online", rehydrate);
  }, [rehydrate]);

  // Client-side countdown
  useEffect(() => {
    if (secondsLeft === null || secondsLeft <= 0) return;
    const id = setInterval(() => {
      setSecondsLeft((prev) => {
        if (prev === null || prev <= 1) {
          clearInterval(id);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(id);
  }, [secondsLeft !== null]);

  // Auto-submit at expiry
  useEffect(() => {
    if (secondsLeft !== 0 || submitCalledRef.current) return;
    submitCalledRef.current = true;
    handleSubmit();
  }, [secondsLeft]);

  const questions = state.session?.questions ?? [];
  const current: Question | undefined = questions[state.currentIndex];

  async function saveAnswer(questionId: string, text: string) {
    if (!state.jwt) return;
    dispatch({ type: "SET_ANSWER", questionId, text });
    setSaving((s) => ({ ...s, [questionId]: true }));
    setSaveError(null);
    try {
      await apiFetch(`/sessions/${sessionId}/questions/${questionId}/answer`, {
        method: "PATCH",
        jwt: state.jwt,
        body: JSON.stringify({ answer_text: text }),
      });
    } catch (err: unknown) {
      setSaveError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving((s) => ({ ...s, [questionId]: false }));
    }
  }

  async function handleSubmit() {
    if (!state.jwt || state.submitting) return;
    dispatch({ type: "SET_SUBMITTING", value: true });
    try {
      await apiFetch(`/sessions/${sessionId}/submit`, {
        method: "POST",
        jwt: state.jwt,
      });
      router.push(`/assessment/${sessionId}/done`);
    } catch {
      dispatch({ type: "SET_SUBMITTING", value: false });
    }
  }

  const allAnswered = questions.length > 0 && questions.every((q) => !!state.answers[q.id]);
  const timerWarning = secondsLeft !== null && secondsLeft <= 60;

  return (
    <main className="flex min-h-screen flex-col px-6 py-8 max-w-2xl mx-auto">
      {/* Timer */}
      <div className="flex justify-between items-center mb-6">
        <span className="text-sm text-slate-500">
          Question {state.currentIndex + 1} of {questions.length}
        </span>
        {secondsLeft !== null && (
          <div
            aria-live="polite"
            aria-atomic="true"
            className={`text-sm font-mono font-semibold ${
              timerWarning ? "text-red-600" : "text-slate-700"
            }`}
          >
            {formatTime(secondsLeft)}
          </div>
        )}
      </div>

      {/* Question pill nav */}
      <div className="flex gap-2 flex-wrap mb-6" role="navigation" aria-label="Questions">
        {questions.map((q, i) => (
          <button
            key={q.id}
            onClick={() => dispatch({ type: "SET_INDEX", index: i })}
            aria-label={`Question ${i + 1}${state.answers[q.id] ? " (answered)" : ""}`}
            className={`w-8 h-8 rounded-full text-sm font-medium border
              ${state.currentIndex === i ? "bg-slate-900 text-white border-slate-900" : ""}
              ${state.answers[q.id] && state.currentIndex !== i ? "bg-green-100 border-green-400 text-green-800" : ""}
              ${!state.answers[q.id] && state.currentIndex !== i ? "border-slate-300 text-slate-600" : ""}
            `}
          >
            {i + 1}
          </button>
        ))}
      </div>

      {/* Current question */}
      {current && (
        <div className="flex-1 space-y-4">
          <p className="text-slate-900 text-lg font-medium leading-relaxed">
            {current.question.text}
          </p>

          {current.answer_format === "multiple_choice" && current.options && (
            <fieldset className="space-y-2">
              <legend className="sr-only">Select an answer</legend>
              {Object.entries(current.options).map(([key, label]) => (
                <label
                  key={key}
                  className="flex items-center gap-3 p-3 rounded-lg border border-slate-200 cursor-pointer
                             hover:border-slate-400 has-[:checked]:border-slate-900 has-[:checked]:bg-slate-50"
                >
                  <input
                    type="radio"
                    name={`q-${current.id}`}
                    value={key}
                    checked={state.answers[current.id] === key}
                    onChange={() => saveAnswer(current.id, key)}
                    className="accent-slate-900"
                  />
                  <span className="text-slate-800">{label}</span>
                </label>
              ))}
            </fieldset>
          )}

          {current.answer_format === "short_text" && (
            <div>
              <label htmlFor={`short-${current.id}`} className="sr-only">
                Your answer
              </label>
              <input
                id={`short-${current.id}`}
                type="text"
                defaultValue={state.answers[current.id] ?? ""}
                onBlur={(e) => saveAnswer(current.id, e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-4 py-2 text-slate-900
                           focus:outline focus:outline-2 focus:outline-slate-900"
              />
            </div>
          )}

          {current.answer_format === "long_text" && (
            <div>
              <label htmlFor={`long-${current.id}`} className="sr-only">
                Your answer
              </label>
              <textarea
                id={`long-${current.id}`}
                rows={6}
                defaultValue={state.answers[current.id] ?? ""}
                onBlur={(e) => saveAnswer(current.id, e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-4 py-2 text-slate-900
                           focus:outline focus:outline-2 focus:outline-slate-900 resize-y"
              />
            </div>
          )}

          {saving[current.id] && (
            <p className="text-xs text-slate-400">Saving…</p>
          )}
          {saveError && (
            <p role="alert" className="text-xs text-red-600">{saveError}</p>
          )}
        </div>
      )}

      {/* Navigation */}
      <div className="flex justify-between items-center mt-8 pt-4 border-t border-slate-100">
        <button
          onClick={() => dispatch({ type: "SET_INDEX", index: state.currentIndex - 1 })}
          disabled={state.currentIndex === 0}
          className="px-4 py-2 rounded-lg border border-slate-300 text-slate-700 text-sm
                     disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Previous
        </button>

        {state.currentIndex < questions.length - 1 ? (
          <button
            onClick={() => dispatch({ type: "SET_INDEX", index: state.currentIndex + 1 })}
            className="px-4 py-2 rounded-lg bg-slate-900 text-white text-sm"
          >
            Next
          </button>
        ) : (
          <button
            onClick={handleSubmit}
            disabled={!allAnswered || state.submitting}
            className="px-6 py-2 rounded-lg bg-slate-900 text-white text-sm font-medium
                       disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {state.submitting ? "Submitting…" : "Submit Assessment"}
          </button>
        )}
      </div>
    </main>
  );
}
```

- [ ] **Step 3: Add NEXT_PUBLIC_API_URL to next.config**

Read current `apps/candidate-web/next.config.mjs`, then update to expose env var:

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
  },
};

export default nextConfig;
```

- [ ] **Step 4: Verify build**

```bash
cd apps/candidate-web
npm run build
```
Expected: Build succeeds with no TypeScript errors.

- [ ] **Step 5: Commit**

```bash
git add apps/candidate-web/src/app/assessment/[sessionId]/test/page.tsx \
        apps/candidate-web/src/app/assessment/[sessionId]/done/page.tsx \
        apps/candidate-web/next.config.mjs
git commit -m "[TASK-001] feat: QuestionPage with timer, autosave, submit; SubmittedPage (M5-F02 F03 F04 F05)"
```

---

## Task 7: Full-flow verification + globals.css WCAG fix

**Files:**
- Modify: `apps/candidate-web/src/app/globals.css` — ensure focus rings are never suppressed
- Verify: run full backend test suite; run frontend build

**Interfaces:**
- Consumes: all prior tasks
- Produces: exit criterion sign-off

- [ ] **Step 1: Check globals.css for focus suppression**

Read `apps/candidate-web/src/app/globals.css`. If it contains `outline: none` or `outline: 0` anywhere without a `:focus-visible` replacement, add:

```css
/* WCAG 2.1 AA — never suppress focus rings */
*:focus {
  outline: revert;
}
*:focus:not(:focus-visible) {
  outline: none;
}
*:focus-visible {
  outline: 2px solid #0f172a;
  outline-offset: 2px;
}
```

- [ ] **Step 2: Run full backend test suite**

```bash
cd services/orchestrator-api
pytest tests/sessions/ -v
```
Expected: all PASSED.

- [ ] **Step 3: Run full frontend build**

```bash
cd apps/candidate-web
npm run build
```
Expected: Build succeeds.

- [ ] **Step 4: Exit criterion checklist**

Verify each item against the implementation:

| Criterion | Verified by |
|---|---|
| Emailed magic link | `POST /sessions/{id}/invite` → `send_invite_email` with link containing `?token=` |
| Passwordless login | `POST /auth/candidate/verify-token` → JWT with `assessment_session_id` claim |
| DISC-style one-at-a-time | QuestionPage renders `questions[currentIndex]` with pill nav |
| MCQ, short_text, long_text | `answer_format` switch in QuestionPage renders radio / input / textarea |
| Timer enforcement | client countdown seeded from `seconds_remaining`; server recomputes at submit |
| Auto-submit at expiry | `useEffect` when `secondsLeft === 0` calls `handleSubmit()` |
| Per-answer autosave | `saveAnswer()` calls `PATCH …/answer` on every change |
| Disconnect safe | `window.addEventListener("online", rehydrate)` + REHYDRATE action fills gaps |
| No raw score shown | SubmittedPage is a static thank-you only |
| WCAG 2.1 AA | All inputs labelled; focus rings present; timer `aria-live="polite"` |

- [ ] **Step 5: Commit**

```bash
git add apps/candidate-web/src/app/globals.css
git commit -m "[TASK-001] fix: WCAG focus ring rules in globals.css (M5 accessibility)"
```
