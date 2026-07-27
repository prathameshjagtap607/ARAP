# Auth + RBAC Design — ARAP Orchestrator API
**Date:** 2026-07-22
**PRD refs:** Section 4, Section 15
**Task:** TASK-000 (Phase 0 — auth session)
**Module scope:** `services/orchestrator-api/src/modules/auth` ONLY

---

## 1. Overview

Four identity types share one JWT-based auth system with strict scope enforcement:

| Identity | Auth method | JWT scope claim | Refresh token |
|---|---|---|---|
| Admin | bcrypt password | `role: "admin"` | Yes (Redis) |
| User | bcrypt password | `role: "user"` | Yes (Redis) |
| Candidate | magic-link or OTP | `assessment_session_id` | No |
| Client | magic-link or OTP | `report_share_id` | No |

Role and scope claims are extracted from the JWT payload only — never from the request body.

Email delivery of magic-link / OTP tokens is **out of scope** for this module. The token is returned to the caller; M5 (test-delivery session) handles email sending.

---

## 2. File Layout

```
services/orchestrator-api/src/modules/auth/
├── __init__.py
├── router.py          # FastAPI routes for all 4 login flows + refresh + logout
├── schemas.py         # Pydantic request/response models
├── service.py         # Business logic: verify credentials, issue tokens, audit
├── token.py           # JWT encode/decode; refresh token Redis CRUD
└── dependencies.py    # Composable Depends(): require_user, require_admin,
                       #   require_candidate_scope, require_client_scope
```

`src/middleware/auth.py` — existing stub — is filled with one responsibility:
decode bearer JWT → set `request.state.claims: TokenClaims | None`.

`src/middleware/rbac.py` — existing stub — is **deleted**. RBAC is enforced
exclusively through `Depends()` in `dependencies.py`.

---

## 3. New Package Dependencies

Add to `pyproject.toml` `[project.dependencies]`:

```
PyJWT>=2.8
passlib[bcrypt]>=1.7.4
redis>=5.0
```

---

## 4. Config Additions (`src/config.py`)

```python
JWT_SECRET_KEY: str                          # required; no default
JWT_ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
REFRESH_TOKEN_EXPIRE_DAYS: int = 7
LOGIN_TOKEN_EXPIRE_MINUTES: int = 15         # magic-link / OTP TTL
REDIS_URL: str = "redis://localhost:6379/0"
```

`JWT_SECRET_KEY` is added to `.env.example` and must be set in production.

---

## 5. JWT Token Payloads

**Admin / User access token:**
```json
{
  "sub": "<user_id (UUID)>",
  "role": "admin | user",
  "org_id": "<org_id (UUID)>",
  "type": "access",
  "exp": "<unix timestamp>"
}
```

**Candidate access token (scoped):**
```json
{
  "sub": "<candidate_id (UUID)>",
  "role": "candidate",
  "org_id": "<org_id (UUID)>",
  "assessment_session_id": "<UUID>",
  "type": "access",
  "exp": "<unix timestamp>"
}
```

**Client access token (scoped):**
```json
{
  "sub": "<client_id (UUID)>",
  "role": "client",
  "org_id": "<org_id (UUID)>",
  "report_share_id": "<UUID>",
  "type": "access",
  "exp": "<unix timestamp>"
}
```

**Refresh token (Admin / User only):**
Opaque 32-byte URL-safe random string. Stored in Redis as:
- key: `refresh:{sha256_hex_of_token}`
- value: JSON `{"user_id": "...", "org_id": "...", "role": "..."}`
- TTL: `REFRESH_TOKEN_EXPIRE_DAYS * 86400` seconds

Candidates and Clients have no refresh token. Their scoped JWT covers a single
assessment session or report share event.

---

## 6. API Routes

All routes are mounted at `/auth` prefix in `main.py`.

### 6.1 Admin / User — Password Login

```
POST /auth/login
Request:  { email: str, password: str, org_id: UUID }
Response: { access_token: str, refresh_token: str, token_type: "bearer" }
Errors:   401 — invalid credentials; 401 — account not found
Audit:    user_login (success) | login_failed (failure)
```

### 6.2 Token Refresh (Admin / User only)

```
POST /auth/refresh
Request:  { refresh_token: str }
Response: { access_token: str, refresh_token: str, token_type: "bearer" }
Behavior: old refresh token deleted from Redis; new pair issued (rotation)
Errors:   401 — token not found or expired
Audit:    token_refresh
```

### 6.3 Logout

```
POST /auth/logout
Auth:     Bearer token required
Behavior: deletes refresh token from Redis if Admin/User; no-op for Candidate/Client
Audit:    logout
```

### 6.4 Candidate — Request Token

```
POST /auth/candidate/request-token
Request:  { email: str, org_id: UUID, assessment_session_id: UUID }
Guards:   assessment_session must exist + belong to a candidate with that email
          in that org; session must not be in status "expired" or "completed"
Behavior: generate secrets.token_urlsafe(32); store sha256 hash in
          candidates.login_token_hash; store expiry in login_token_expires_at
Response: { token: str }   ← raw token; caller delivers to candidate's email
Audit:    candidate_token_requested
```

### 6.5 Candidate — Verify Token

```
POST /auth/candidate/verify-token
Request:  { token: str, assessment_session_id: UUID }
Guards:   sha256(token) matches login_token_hash AND now < login_token_expires_at
          assessment_session.candidate_id == candidate.id
Behavior: clear login_token_hash + login_token_expires_at (single-use)
          issue scoped access JWT with assessment_session_id claim
Response: { access_token: str, token_type: "bearer" }
Errors:   401 — token invalid or expired; 403 — session/candidate mismatch
Audit:    candidate_login (success) | login_failed (failure)
```

### 6.6 Client — Request Token

```
POST /auth/client/request-token
Request:  { email: str, org_id: UUID, report_share_id: UUID }
Guards:   report_share must exist + belong to a client with that email in that org;
          report_share.revoked_at IS NULL; report_share.expires_at > now (if set)
Behavior: generate token; store hash in clients.login_token_hash + expiry
Response: { token: str }
Audit:    client_token_requested
```

### 6.7 Client — Verify Token

```
POST /auth/client/verify-token
Request:  { token: str, report_share_id: UUID }
Guards:   hash match + not expired; report_share.client_id == client.id
Behavior: single-use clear; issue scoped access JWT with report_share_id claim
Response: { access_token: str, token_type: "bearer" }
Errors:   401 — token invalid or expired; 403 — share/client mismatch
Audit:    client_login (success) | login_failed (failure)
```

---

## 7. AuthMiddleware (src/middleware/auth.py)

Replaces the current stub. Single responsibility:

1. Extract `Authorization: Bearer <token>` header.
2. Decode JWT using `JWT_SECRET_KEY` + `JWT_ALGORITHM`.
3. On success: set `request.state.claims = TokenClaims(...)`.
4. On failure (missing header, expired, invalid): set `request.state.claims = None`.
5. Always call `await call_next(request)` — do NOT reject here. Route-level
   `Depends()` raises 401/403 when claims are absent or insufficient.

---

## 8. RBAC Dependencies (src/modules/auth/dependencies.py)

```python
TokenClaims   # dataclass: sub, role, org_id, type,
              #   assessment_session_id (opt), report_share_id (opt)

get_claims(request) -> TokenClaims
    # raises 401 if request.state.claims is None

require_user(claims) -> TokenClaims
    # raises 403 if role not in ("user", "admin")

require_admin(claims) -> TokenClaims
    # raises 403 if role != "admin"
    # admin routes may omit org_id filter — this is the only exception

require_candidate_scope(session_id: UUID, claims) -> TokenClaims
    # raises 403 if role != "candidate"
    # raises 403 if claims.assessment_session_id != session_id

require_client_scope(share_id: UUID, claims) -> TokenClaims
    # raises 403 if role != "client"
    # raises 403 if claims.report_share_id != share_id
```

Every route in every module declares exactly one of these as `Depends()`.
No RBAC logic anywhere else.

---

## 9. Tenant Isolation

Every database query in the auth module (and all future modules) must filter
`WHERE org_id = claims.org_id`. The one exception: routes guarded by
`require_admin` may query across orgs — this exception is explicit and
documented at the route level, never implicit.

---

## 10. Audit Logging

Every auth event writes to `audit_logs`. Actual column names: `action`,
`entity_type`, `entity_id`, `log_metadata` (JSONB), `actor_id` (UUID NOT NULL),
`org_id` (UUID NOT NULL).

**RLS requirement:** service must `SET LOCAL app.current_org_id = '<org_id>'`
inside the transaction before every INSERT to `audit_logs`, or the row is
silently dropped by RLS.

For anonymous failures (actor unknown), `actor_id` is set to the nil UUID
(`00000000-0000-0000-0000-000000000000`); the attempted email is stored in
`log_metadata`.

| action | entity_type | entity_id | actor_id | log_metadata |
|---|---|---|---|---|
| `user_login` | `user` | user.id | user.id | `{}` |
| `login_failed` | `user` | nil UUID | nil UUID | `{"email": "..."}` |
| `candidate_token_requested` | `assessment_session` | session.id | candidate.id | `{}` |
| `candidate_login` | `assessment_session` | session.id | candidate.id | `{}` |
| `client_token_requested` | `report_share` | share.id | client.id | `{}` |
| `client_login` | `report_share` | share.id | client.id | `{}` |
| `login_failed` | `candidate` / `client` | nil UUID | nil UUID | `{"email": "..."}` |
| `token_refresh` | `user` | user.id | user.id | `{}` |
| `logout` | `user` / `candidate` / `client` | actor.id | actor.id | `{}` |

Failures always logged even when the actor cannot be identified.

---

## 11. Error Handling

| Condition | HTTP status |
|---|---|
| Missing or malformed bearer token | 401 |
| Expired access token | 401 |
| Wrong password | 401 (no hint about which field is wrong) |
| Magic-link / OTP token expired or already used | 401 |
| Candidate JWT accessing a different assessment_session | 403 |
| Client JWT accessing a different report_share | 403 |
| Insufficient role (e.g. User accessing admin route) | 403 |
| Revoked or expired report_share | 401 |

Error response shape: `{ "detail": "<message>" }` — FastAPI default.

---

## 12. Test Plan

### 12.1 Unit tests (`tests/auth/`)

- `token.py`: encode/decode round-trip for each role type; expired token raises;
  wrong algorithm raises
- `service.py`: bcrypt verify pass/fail; token hash store + clear; single-use
  enforcement (second verify call → 401)

### 12.2 Integration tests (httpx TestClient + real test DB)

- Flow 1: POST /auth/login → valid credentials → access + refresh returned
- Flow 1: POST /auth/login → wrong password → 401 + audit row logged
- Flow 2 + 3: request-token → verify-token → access JWT returned; second
  verify of same token → 401
- Flow 4: POST /auth/refresh → new pair issued; old refresh token invalid
- POST /auth/logout → refresh token deleted from Redis

### 12.3 Scope isolation (exit criterion)

Issue candidate JWT for session A. Attempt GET on a route that calls
`require_candidate_scope(session_id=B)` → assert HTTP 403. This test is
the primary exit-criterion verification per TASK-000.

### 12.4 Audit coverage

After each integration test flow, assert exactly one `audit_logs` row with
correct `event`, `actor_id`, and `status`.

---

## 13. Out of Scope (this module)

- Email delivery of magic-link / OTP → M5 (test-delivery session)
- Rate limiting on login endpoints → already stubbed in `RateLimitMiddleware`
- Frontend token storage / refresh logic → frontend sessions
- Password reset flow → not in PRD Phase 0
