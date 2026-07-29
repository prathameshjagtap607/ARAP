# M11 Analytics — Design Spec

**Date:** 2026-07-29
**Task:** TASK-005 (Phase 5, M11)
**PRD ref:** Section 16, M11 F01–F05
**Status:** Approved — ready for implementation planning

---

## Scope

Five analytics features on top of existing session/report data:

| Feature | ID | Description |
|---|---|---|
| Score Trends | F01 | Average scores over time, by dept/skill/role |
| Hiring Funnel | F02 | Invited → completed → hired conversion, by dept/role |
| Question & Difficulty Analytics | F03 | Category distribution, difficulty mix, category-coverage vs verdict correlation |
| Candidate Benchmarking | F04 | Percentile ranking vs all org candidates for same role |
| Skill Trend (stub) | F05 | Top/weakest skill trends; predictive model is v2+ (PRD §17) |

Out of scope: predictive on-the-job success model (v2+), cross-org admin views (M12), ATS integrations.

---

## Architecture

**Approach:** One backend module (`analytics`), five dedicated endpoint groups, each with its own Redis cache key. Frontend: tabbed single-page layout, tabs lazy-load on activation.

---

## 1. Data Model

### Existing tables used (no schema changes)

| Table | Fields consumed |
|---|---|
| `assessment_sessions` | `status`, `org_id`, `job_assessment_id`, `candidate_id`, `invited_at`, `started_at`, `completed_at` |
| `hiring_reports` | `score_rollup` (JSONB: `overall`, `composite_scores`), `verdict`, `org_id`, `session_id` |
| `job_assessments` | `department`, `title`, `difficulty_level`, `role_family`, `org_id` |
| `session_questions` | `category`, `difficulty`, `evaluation` (JSONB), `org_id` |
| `question_sets` | `session_id` (joins questions to sessions) |

### New table: `skill_trend_snapshots` (F05 stub)

Weekly aggregated snapshot per org/role/dept/competency. Populated by a background job (v2+). Empty at launch — UI shows "no data yet" state.

```sql
CREATE TABLE skill_trend_snapshots (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id        uuid NOT NULL REFERENCES orgs(id),
    week_start    date NOT NULL,
    role_family   text,
    department    text,
    competency    text NOT NULL,
    avg_score     numeric(4,2) NOT NULL,
    sample_count  int NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_skill_trend_snapshots_org_week
    ON skill_trend_snapshots (org_id, week_start DESC);
```

One Alembic migration for this table. No migration needed for F01–F04.

---

## 2. Backend Module

### File layout

```
services/orchestrator-api/src/modules/analytics/
  __init__.py
  router.py      # five route groups, registered in main.py
  service.py     # raw SQL aggregations (SQLAlchemy text())
  schemas.py     # Pydantic response models
  cache.py       # Redis get/set/invalidate helpers
```

### API routes

All routes:
- Require authenticated HR or Admin user
- Scope to `current_user.org_id` — no cross-org access
- Check Redis cache first; fall through to SQL on miss; write result to cache

| Method | Path | Query params |
|---|---|---|
| GET | `/analytics/score-trends` | `dept`, `role`, `from_date`, `to_date`, `granularity` (week\|month, default week) |
| GET | `/analytics/funnel` | `dept`, `role`, `from_date`, `to_date` |
| GET | `/analytics/questions` | `job_assessment_id`, `from_date`, `to_date` |
| GET | `/analytics/benchmarks/{session_id}` | — |
| GET | `/analytics/skill-trends` | `dept`, `role`, `from_date`, `to_date` |

### Cache strategy

- Key pattern: `analytics:{org_id}:{feature}:{sha256(params)[:8]}`
- TTL: 300 seconds (5 minutes)
- Invalidation: on new `HiringReport` INSERT, call `invalidate_org_analytics(org_id)` — deletes all `analytics:{org_id}:*` keys via Redis `SCAN` + `DEL`
- Hook point: end of `reports/service.py` report creation (one call, non-blocking)

### SQL aggregations

**F01 — Score Trends**

Two queries in service.py (overall + per-competency) merged in Python:

```sql
-- Query 1: overall avg per period
SELECT
    DATE_TRUNC(:granularity, s.completed_at) AS period,
    AVG((r.score_rollup->>'overall')::numeric) AS avg_overall,
    COUNT(*) AS session_count
FROM assessment_sessions s
JOIN hiring_reports r ON r.session_id = s.id
JOIN job_assessments j ON j.id = s.job_assessment_id
WHERE s.org_id = :org_id
  AND s.status = 'completed'
  AND (:dept IS NULL OR j.department = :dept)
  AND (:role IS NULL OR j.title = :role)
  AND s.completed_at BETWEEN :from_date AND :to_date
GROUP BY 1
ORDER BY 1;

-- Query 2: per-competency avg per period (lateral expand then re-aggregate)
SELECT
    DATE_TRUNC(:granularity, s.completed_at) AS period,
    comp.key AS competency,
    AVG(comp.value::numeric) AS avg_score
FROM assessment_sessions s
JOIN hiring_reports r ON r.session_id = s.id
JOIN job_assessments j ON j.id = s.job_assessment_id,
LATERAL jsonb_each_text(r.score_rollup->'composite_scores') AS comp(key, value)
WHERE s.org_id = :org_id
  AND s.status = 'completed'
  AND (:dept IS NULL OR j.department = :dept)
  AND (:role IS NULL OR j.title = :role)
  AND s.completed_at BETWEEN :from_date AND :to_date
GROUP BY 1, 2
ORDER BY 1, 2;
```

Service merges results: for each period row from Query 1, attach `avg_by_competency` dict built from Query 2 rows for that period.

**F02 — Hiring Funnel**
```sql
SELECT
    COALESCE(j.department, 'Unknown') AS department,
    j.title AS role,
    COUNT(*) FILTER (WHERE s.status IN ('invited','in_progress','completed','expired')) AS total_invited,
    COUNT(*) FILTER (WHERE s.status = 'completed') AS completed,
    COUNT(*) FILTER (WHERE r.verdict IN ('hire','strong_hire')) AS hired
FROM assessment_sessions s
JOIN job_assessments j ON j.id = s.job_assessment_id
LEFT JOIN hiring_reports r ON r.session_id = s.id
WHERE s.org_id = :org_id
  AND (:dept IS NULL OR j.department = :dept)
  AND (:role IS NULL OR j.title = :role)
  AND s.invited_at BETWEEN :from_date AND :to_date
GROUP BY 1, 2
ORDER BY total_invited DESC
```

**F03 — Question & Difficulty Analytics**
```sql
SELECT
    sq.category,
    sq.difficulty,
    COUNT(*) AS question_count,
    AVG(CASE sq.difficulty
        WHEN 'easy'   THEN 1
        WHEN 'medium' THEN 2
        WHEN 'hard'   THEN 3
        WHEN 'expert' THEN 4
    END) AS avg_difficulty_num,
    AVG((r.score_rollup->>'overall')::numeric) AS avg_verdict_score
FROM session_questions sq
JOIN question_sets qs ON qs.id = sq.question_set_id
JOIN assessment_sessions s ON s.id = qs.session_id
JOIN hiring_reports r ON r.session_id = s.id
WHERE sq.org_id = :org_id
  AND (:job_assessment_id IS NULL OR s.job_assessment_id = :job_assessment_id)
  AND s.completed_at BETWEEN :from_date AND :to_date
GROUP BY 1, 2
ORDER BY 1, 2
```

**F04 — Candidate Benchmarking**
```sql
WITH ranked AS (
    SELECT
        s.id AS session_id,
        (r.score_rollup->>'overall')::numeric AS overall_score,
        PERCENT_RANK() OVER (ORDER BY (r.score_rollup->>'overall')::numeric) AS percentile,
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY (r.score_rollup->>'overall')::numeric)
            OVER () AS p25,
        PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY (r.score_rollup->>'overall')::numeric)
            OVER () AS p50,
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY (r.score_rollup->>'overall')::numeric)
            OVER () AS p75
    FROM assessment_sessions s
    JOIN hiring_reports r ON r.session_id = s.id
    WHERE s.org_id = :org_id
      AND s.job_assessment_id = (
          SELECT job_assessment_id FROM assessment_sessions WHERE id = :session_id
      )
      AND s.status = 'completed'
)
SELECT * FROM ranked WHERE session_id = :session_id
```

**F05 — Skill Trends**
```sql
SELECT week_start, competency, avg_score, sample_count
FROM skill_trend_snapshots
WHERE org_id = :org_id
  AND (:dept IS NULL OR department = :dept)
  AND (:role IS NULL OR role_family = :role)
  AND week_start BETWEEN :from_date AND :to_date
ORDER BY week_start, competency
```
Returns empty array when table has no rows — frontend shows "no trend data yet" state.

### Pydantic response shapes (schemas.py)

```python
class ScoreTrendPoint(BaseModel):
    period: datetime
    avg_overall: float
    avg_by_competency: dict[str, float]
    session_count: int

class ScoreTrendsResponse(BaseModel):
    data: list[ScoreTrendPoint]
    filters_applied: dict

class FunnelRow(BaseModel):
    department: str
    role: str
    total_invited: int
    completed: int
    hired: int
    completion_rate: float   # computed: completed/total_invited
    hire_rate: float         # computed: hired/completed

class FunnelResponse(BaseModel):
    rows: list[FunnelRow]
    totals: FunnelRow

class QuestionCategoryRow(BaseModel):
    category: str
    difficulty: str
    question_count: int
    avg_difficulty_num: float
    avg_verdict_score: float | None

class QuestionAnalyticsResponse(BaseModel):
    rows: list[QuestionCategoryRow]

class BenchmarkResponse(BaseModel):
    session_id: uuid.UUID
    overall_score: float
    percentile: float        # 0.0–1.0
    p25: float
    p50: float
    p75: float
    peer_count: int

class SkillTrendPoint(BaseModel):
    week_start: date
    competency: str
    avg_score: float
    sample_count: int

class SkillTrendsResponse(BaseModel):
    data: list[SkillTrendPoint]
    has_data: bool
```

---

## 3. Frontend

### File layout

```
apps/console-web/src/app/(console)/analytics/
  page.tsx                    # tab shell; replaces placeholder
  _components/
    ScoreTrends.tsx           # F01
    HiringFunnel.tsx          # F02
    QuestionAnalytics.tsx     # F03
    Benchmarking.tsx          # F04
    SkillTrends.tsx           # F05
  _lib/
    api.ts                    # typed fetch wrappers, 5 functions
    types.ts                  # TS interfaces matching Pydantic schemas
```

### Tab layout (page.tsx)

Five tabs: Score Trends | Hiring Funnel | Question Analytics | Benchmarking | Skill Trends.
Each tab mounts its component on first activation (lazy). No tab pre-fetches — avoids 5 parallel queries on page load.

### Per-component summary

| Component | Chart type | Filters |
|---|---|---|
| ScoreTrends | LineChart (Recharts) — overall + togglable per-competency lines | dept, role, date range, granularity |
| HiringFunnel | Stacked BarChart (dept/role on x-axis) + conversion % labels | dept, role, date range |
| QuestionAnalytics | PieChart (category dist) + BarChart (difficulty by category) | job_assessment_id, date range |
| Benchmarking | Search field → session lookup → horizontal percentile bar + p25/p50/p75 markers | — (session_id driven) |
| SkillTrends | LineChart per competency; empty-state card when `has_data=false` | dept, role, date range |

All components reuse `ChartCard`, `FilterBar`, `SummaryCard` from `components/dashboard/`.

### Shared patterns

- Skeleton loader while fetching (existing CSS pattern from M10)
- Empty-state card: "No data available for the selected filters"
- Error boundary: "Failed to load — retry" link
- All API calls pass `Authorization: Bearer <token>` via existing `AuthContext`

---

## 4. Registration

`main.py`: add `from src.modules.analytics.router import router as analytics_router` and `app.include_router(analytics_router)`.

---

## 5. Open Questions (carried from PRD §18)

- **#5 Human calibration set size** — the >75% inter-rater agreement metric is not yet sourceable; F03 surfaces category coverage vs verdict correlation but does NOT claim calibration validity. Flag in UI tooltip.
- **F05 predictive signal** — stub only. Background snapshot job and ML model are PRD §17 v2 work. Table schema is forward-compatible.

---

## Exit Criteria

- [ ] All four funnel/trend views (F01–F04) load from real session data with correct org scoping
- [ ] Benchmarking returns correct percentile for a completed session
- [ ] Expensive aggregates cached; dashboard tab load < 2s on second request
- [ ] F05 renders "no data yet" state gracefully
- [ ] `skill_trend_snapshots` table exists in DB (Alembic migration applied)
