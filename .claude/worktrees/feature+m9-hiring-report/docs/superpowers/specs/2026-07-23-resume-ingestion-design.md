# Resume & Profile Ingestion — Design

**Date:** 2026-07-23
**PRD ref:** §7, M2-F01 – M2-F04
**Task:** TASK-001
**Phase:** 1 — MVP
**Status:** Approved

---

## Scope

Build M2 (Resume & Profile Ingestion) end-to-end.
Module boundaries: `services/ingestion-service/` and `agents/resume_analysis/` ONLY.
One supporting migration in `services/orchestrator-api/migrations/`.

Out of scope: M3 (Candidate Profile Engine), question generation, anything downstream.

---

## Cross-Cutting Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Parse strategy | Sync-first, asyncio background fallback for large docs | Matches PRD "<10s target with job-queue fallback"; no Celery at MVP |
| Large-doc threshold | File > 5 MB OR text extraction > 8 s → 202 + asyncio task | asyncio.create_task is sufficient at MVP; Celery upgrade is one session |
| Resume Analysis model | `claude-sonnet-4-6` tool_use | Sonnet needed for inferred skills + leadership signal; Haiku insufficient |
| Embedding model | `text-embedding-3-small` (OpenAI) — `vector(1536)` | Matches existing HNSW index dimension in schema |
| Match score | Cosine similarity of resume chunk vs JD skills text | Embeddings-based semantic match per M2-F04 |
| GitHub enrichment | httpx to public GitHub REST API (no auth for public repos) | Additive evidence only — never a hard gate per PRD M2-F03 |
| LinkedIn | Accept URL as context hint only; no scraping | LinkedIn ToS prohibits automated scraping |
| S3 storage | MinIO (S3-compatible) added to docker-compose | Self-hosted; boto3 client works against any S3-compatible endpoint |
| DB connection | ingestion-service connects to shared PostgreSQL via async SQLAlchemy | Same DB cluster; minimal SA models for the tables it reads/writes |
| Per-field confidence | `field_confidence jsonb` column on `candidate_profiles` | PRD M2-F02 explicitly requires per-field score |
| `parsing_confidence` | Kept as aggregate (mean of field scores) | Backward compat; downstream M3 reads both |
| Agent non-fatal | Agent error → row written with `parsing_confidence = NULL` | Ingestion must not fail the session; M3 checks for NULL |

---

## Migration: `0003_resume_ingestion`

Three columns + one unique constraint added to `candidate_profiles`:

| Column | Type | Constraint | Default |
|---|---|---|---|
| `field_confidence` | `jsonb` | nullable | — |
| `match_score` | `numeric(4,3)` | `CHECK BETWEEN 0 AND 1`, nullable | — |
| `github_enrichment` | `jsonb` | nullable | — |

No columns dropped. `parsing_confidence numeric(4,3)` stays as the aggregate overall score.

Also adds: `UNIQUE(candidate_id, job_assessment_id)` — required for the upsert `ON CONFLICT` clause. The original schema design omitted this constraint.

---

## docker-compose.yml Additions

```yaml
minio:
  image: minio/minio:latest
  command: server /data --console-address ":9001"
  environment:
    MINIO_ROOT_USER: arap
    MINIO_ROOT_PASSWORD: arap_secret
  ports:
    - "9000:9000"   # S3 API
    - "9001:9001"   # MinIO console
  volumes:
    - minio-data:/data
  healthcheck:
    test: ["CMD", "mc", "ready", "local"]
    interval: 5s
    timeout: 5s
    retries: 5

ingestion-service:
  build:
    context: services/ingestion-service
    dockerfile: ../../infra/docker/ingestion-service.Dockerfile
  environment:
    DATABASE_URL: postgresql+psycopg://arap:arap@db-dev:5432/arap_dev
    ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
    OPENAI_API_KEY: ${OPENAI_API_KEY}
    S3_ENDPOINT_URL: http://minio:9000
    S3_ACCESS_KEY: arap
    S3_SECRET_KEY: arap_secret
    S3_BUCKET_RESUMES: arap-resumes
  ports:
    - "8001:8001"
  depends_on:
    db-dev:
      condition: service_healthy
    minio:
      condition: service_healthy
  profiles:
    - full

volumes:
  minio-data:   # add alongside existing pgdata-dev / pgdata-test
```

---

## Config

### `services/ingestion-service/src/config.py`

```python
class Settings(BaseSettings):
    DATABASE_URL: str
    ANTHROPIC_API_KEY: str
    OPENAI_API_KEY: str
    S3_ENDPOINT_URL: str
    S3_ACCESS_KEY: str
    S3_SECRET_KEY: str
    S3_BUCKET_RESUMES: str = "arap-resumes"
    LARGE_DOC_BYTES: int = 5_242_880   # 5 MB
    LARGE_DOC_PARSE_TIMEOUT: float = 8.0
```

### `services/orchestrator-api/src/config.py` additions

```python
OPENAI_API_KEY: str
INGESTION_SERVICE_URL: str = "http://localhost:8001"
```

---

## Module Layout: `services/ingestion-service/src/`

```
config.py        — Settings (pydantic-settings)
database.py      — async SQLAlchemy engine, get_db()
models.py        — minimal SA models: Candidate, CandidateProfile,
                   JobAssessment (mirrors orchestrator-api; read/write only
                   the columns this service touches)
s3.py            — upload_file(bytes, key) → str
                   download_file(key) → bytes
                   presigned_get_url(key, expires=3600) → str
parsers.py       — extract_text(file_bytes, content_type) → str
                   Raises ValueError("resume too short") if len(text) < 50
embeddings.py    — embed(text: str) → list[float]
                   cosine_similarity(a, b) → float
main.py          — FastAPI app, include_router x3

routers/
  upload.py      — POST /upload
  analyze.py     — POST /analyze
                   GET  /analyze/{candidate_id}/{job_assessment_id}
  health.py      — GET /health
```

---

## API

### `POST /upload`

**Auth:** internal service call (no JWT — called only by orchestrator-api on same network).
Body: `multipart/form-data` with `file` field.
Accepted MIME types: `application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, `text/plain`.

Returns:
```json
{ "s3_key": "resumes/{uuid}.pdf", "presigned_url": "http://minio:9000/..." }
```

Errors:
- `422` — unsupported MIME type (before S3 upload)
- `502` — S3 upload failure

### `POST /analyze`

Body:
```json
{
  "candidate_id": "uuid",
  "job_assessment_id": "uuid",
  "org_id": "uuid"
}
```

Flow:
1. Fetch `candidates` row; fetch `job_assessments` row (with `job_profile` jsonb).
2. If `resume_file_url` present: download from S3 → `extract_text()`.
3. If file > `LARGE_DOC_BYTES` OR extraction > `LARGE_DOC_PARSE_TIMEOUT`: return `202 Accepted` `{"status":"processing"}`, run step 4-8 in `asyncio.create_task`.
4. Call `run_resume_analysis_agent(raw_text, job_profile)` → structured extraction.
5. If `github_url` present: call GitHub REST API → `github_enrichment` dict.
6. Embed resume skills text + JD skills text → `match_score` via cosine similarity.
7. Compute `parsing_confidence` = mean of `field_confidence` values.
8. Upsert `candidate_profiles` row (INSERT … ON CONFLICT (candidate_id, job_assessment_id) DO UPDATE).
9. Return `CandidateProfileResponse`.

Returns `200` (sync) or `202` (async large-doc).

### `GET /analyze/{candidate_id}/{job_assessment_id}`

Returns current `candidate_profiles` row or `{"status":"processing"}` if not yet written.

---

## Agent: `agents/resume_analysis/`

### Files

```
agents/resume_analysis/
  __init__.py
  agent.py       — run_resume_analysis_agent(raw_text, job_profile) → dict
  prompts.py     — SYSTEM_PROMPT str + resume_extraction_tool definition
```

### Tool definition output shape

```json
{
  "skills": {
    "explicit": ["Python", "FastAPI"],
    "inferred":  ["async programming", "REST design"]
  },
  "projects": [
    {"name": "...", "tech": ["..."], "description": "..."}
  ],
  "tech_used": ["PostgreSQL", "Redis"],
  "employment_history": [
    {
      "company": "...", "title": "...",
      "start": "2021-06", "end": "2024-01",
      "team_size": 8, "scope": "regional",
      "key_achievements": ["..."]
    }
  ],
  "education": [
    {"degree": "B.Tech", "field": "CS", "institution": "...", "year": 2018}
  ],
  "certifications": [
    {"name": "AWS SAA", "issuer": "Amazon", "year": 2022}
  ],
  "achievements": ["Reduced API latency 40% by ..."],
  "leadership_indicators": {
    "max_team_size": 12,
    "scope": "national",
    "budget_ownership": null
  },
  "career_timeline": {
    "total_years": 6.5,
    "job_count": 3,
    "gaps": [{"start": "2022-03", "end": "2022-09", "months": 6}]
  },
  "domain_keywords": ["fintech", "payments", "KYC"],
  "field_confidence": {
    "skills": 0.92,
    "projects": 0.85,
    "tech_used": 0.90,
    "employment_history": 0.95,
    "education": 0.97,
    "certifications": 0.80,
    "achievements": 0.75,
    "leadership_indicators": 0.70,
    "career_timeline": 0.88,
    "domain_keywords": 0.83
  }
}
```

### Non-fatal rule

Any exception from the Anthropic API → log error → return `None`.
Caller writes `candidate_profiles` row with `parsing_confidence = NULL`, `field_confidence = NULL`.
Ingestion still returns `200`; M3 must check for NULL before synthesis.

---

## `parsers.py`

| MIME type | Library | Notes |
|---|---|---|
| `application/pdf` | `pypdf` | `PdfReader(BytesIO(bytes)).pages[i].extract_text()` |
| `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | `python-docx` | `Document(BytesIO(bytes)).paragraphs` |
| `text/plain` | built-in | `bytes.decode("utf-8", errors="replace")` |

Raises `ValueError("resume too short to parse")` if extracted text < 50 chars.

---

## `s3.py`

Uses `boto3` with `endpoint_url=settings.S3_ENDPOINT_URL`.
Bucket created on startup if not exists (`create_bucket` idempotent).
Keys: `resumes/{org_id}/{candidate_id}/{uuid}.{ext}`.

---

## `embeddings.py`

```python
def embed(text: str) -> list[float]:
    # openai.OpenAI().embeddings.create(model="text-embedding-3-small", input=text[:8000])
    # truncate to 8000 chars to stay within token limit

def cosine_similarity(a: list[float], b: list[float]) -> float:
    # dot(a, b) / (norm(a) * norm(b))
```

Match score: embed `" ".join(extraction["skills"]["explicit"] + extraction["skills"]["inferred"] + extraction["domain_keywords"])` vs embed `" ".join(job_profile["required_skills"] + job_profile["preferred_skills"])`.

---

## GitHub Enrichment (`M2-F03`)

```
GET https://api.github.com/users/{handle}
GET https://api.github.com/users/{handle}/repos?sort=pushed&per_page=10
```

Extract per repo: `language`, `pushed_at` (commit recency), `stargazers_count`, `has_readme` (from `GET /repos/{owner}/{repo}/readme` → 200 or 404).

Stored as `github_enrichment`:
```json
{
  "username": "...",
  "public_repos": 24,
  "top_languages": ["Python", "TypeScript"],
  "most_recent_push": "2026-07-10",
  "repos": [
    {"name": "...", "language": "Python", "stars": 12,
     "pushed_at": "2026-07-10", "has_readme": true}
  ]
}
```

On GitHub 404 or rate-limit (`429`): log warning, set `github_enrichment = NULL`, continue.

---

## `candidate_profiles` Upsert Shape

```python
INSERT INTO candidate_profiles (
  org_id, candidate_id, job_assessment_id,
  skill_matrix, experience_matrix, leadership_level_estimate,
  strengths, risk_flags,
  parsing_confidence, field_confidence,
  match_score, github_enrichment
) VALUES (...)
ON CONFLICT (candidate_id, job_assessment_id) DO UPDATE SET ...
```

`skill_matrix` = `{"explicit": [...], "inferred": [...], "tech_used": [...]}` from agent output.
`experience_matrix` = `{"employment_history": [...], "career_timeline": {...}}`.
`leadership_level_estimate` = derived from `leadership_indicators.max_team_size`:
  - NULL/0 → "IC", 1-4 → "Team Lead", 5-15 → "Manager", 16-50 → "Director", >50 → "VP-equiv".
`strengths` / `risk_flags` = `[]` at M2 stage (populated by M3).

---

## Error Handling Summary

| Scenario | Response |
|---|---|
| Unsupported file type | `422` before S3 upload |
| S3 upload failure | `502` |
| Extracted text < 50 chars | `422` "resume too short to parse" |
| File > 5 MB or parse > 8 s | `202 Accepted` + asyncio background |
| Agent API error | Log + continue; `parsing_confidence = NULL` in row |
| GitHub 404 / rate-limit | Skip; `github_enrichment = NULL` |
| Embedding API error | Skip; `match_score = NULL` |
| `job_profile` is NULL on job_assessment | Use `required_skills`/`preferred_skills` arrays directly for match |

---

## Tests

```
services/ingestion-service/tests/
  conftest.py              — async DB session, moto S3 mock, sample PDF/DOCX/txt fixtures,
                             mock Anthropic + OpenAI clients
  test_upload.py           — PDF/DOCX/txt accepted; unsupported type → 422
  test_parsers.py          — extract_text per format; < 50 chars → ValueError
  test_analyze_sync.py     — full pipeline (mocked agent + embeddings):
                               assert candidate_profiles row written,
                               field_confidence populated for all 10 fields,
                               match_score between 0 and 1
  test_analyze_async.py    — >5 MB fixture → 202; GET polling → completed
  test_github.py           — mock GitHub API happy path; 404 → NULL enrichment
  test_agent_error.py      — Anthropic raises → parsing_confidence NULL; no exception raised

agents/resume_analysis/tests/
  test_agent.py            — mock anthropic client returns tool_use block;
                             assert output shape matches tool definition;
                             assert non-fatal on APIError
```

---

## `pyproject.toml` additions for ingestion-service

```toml
dependencies = [
    "fastapi>=0.111",
    "uvicorn[standard]>=0.29",
    "pypdf>=4.0",
    "python-docx>=1.1",
    "httpx>=0.27",
    "boto3>=1.34",
    "anthropic>=0.28",
    "sqlalchemy[asyncio]>=2.0",
    "psycopg[binary]>=3.1",
    "pgvector>=0.3",
    "openai>=1.30",
    "pydantic-settings>=2.0",
    "numpy>=1.26",
]
```

---

## Exit Criteria (M2)

- [ ] `POST /upload` accepts PDF, DOCX, plain text; rejects other types with `422`
- [ ] `POST /analyze` with a PDF resume produces a `candidate_profiles` row with all 10 `field_confidence` keys populated
- [ ] `match_score` between 0 and 1 is written for every successful analysis
- [ ] A resume > 5 MB returns `202`; `GET /analyze/{ids}` eventually returns the completed profile
- [ ] GitHub URL present → `github_enrichment` populated with `top_languages` and `most_recent_push`
- [ ] Agent API error → row written with `parsing_confidence = NULL`; endpoint still returns `200`
- [ ] All tests pass (`pytest`)
