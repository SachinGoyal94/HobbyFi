# HobbyFi Vendor Portal AI Copilot — Specification

**Version:** 1.0  
**Date:** 2025-07-12  
**Status:** Phases 0–3 Complete, Phase 4 Planned

---

## 1. Purpose

Build an AI copilot embedded in a vendor portal that allows vendor staff to:
- **Read** — Ask factual questions about their users, games, revenue, memberships
- **Write** — Propose changes (extend trial, change plan, suspend user, update dates) that require human approval before execution

**Safety Principle:** The LLM never mutates data. All writes go through a propose → approve → execute flow with authenticated human decision.

---

## 2. Tech Stack

| Layer | Technology | Version/Purpose |
|-------|------------|-----------------|
| API Framework | FastAPI | Async, OpenAPI, Pydantic |
| Agent Runtime | CrewAI | Multi-agent orchestration |
| LLM Client | LangChain + Google GenAI | Tool calling, structured output |
| Model | Gemini 3.1 Flash-Lite | Low latency, cost-efficient |
| Database | SQLite + SQLAlchemy (async) | Mock schema, repo pattern |
| Auth (v0) | Header stubs | `x-vendor-id`, `x-vendor-user-id`, `x-vendor-role` |
| Observability | Structured JSON logs | Correlation IDs, phase timers |
| Testing | pytest + httpx | 85 tests, mock agent runner |

---

## 3. Architecture

### 3.1 High-Level Components

```
┌─────────────────┐     HTTPS + Headers      ┌─────────────────────────────────┐
│  Vendor Portal  │◄─────────────────────────►│        FastAPI App              │
│     (React)     │     SSE + JSON           │  • Auth Middleware (headers)    │
└─────────────────┘                          │  • Rate Limiting (30/min, 200/hr)│
                                             │  • Routes (/v1/copilot/*)       │
                    ┌────────────────────────┼────────────────────────┐         │
                    ▼                        ▼                        ▼         ▼
            ┌───────────────┐        ┌───────────────┐        ┌───────────────┐
            │ Agent Runtime │        │ Domain Svcs   │        │ Repositories  │
            │  (CrewAI)     │        │ • ChatService │        │ (SQLAlchemy)  │
            │ • 4 Agents    │        │ • ApprovalSvc │        │ • Users       │
            │ • 11 Tools    │        │ • AuditSvc    │        │ • Games       │
            │ • LLM         │        │ • ExpiryTask  │        │ • Memberships │
            └───────┬───────┘        └───────┬───────┘        │ • Revenue     │
                    │                        │                └───────────────┘
            ┌───────┴───────┐                │
            │   4-Agent     │                │
            │   Pipeline    │                │
            ├───────────────┤                │
            │ Router        │                │
            │ Analyst       │◄─── 7 Read     │
            │ Planner       │◄─── 4 Propose  │
            │ Composer      │     Tools      │
            └───────────────┘                │
                    │                        │
                    ▼                        ▼
            ┌───────────────┐        ┌───────────────┐
            │   Gemini      │        │    SQLite     │
            │   3.1 Flash   │        │   (mock DB)   │
            └───────────────┘        └───────────────┘
```

### 3.2 Key Components

| Layer | Technology | Purpose |
|-------|------------|---------|
| API | FastAPI | HTTP, validation, SSE, OpenAPI, CORS |
| Auth | Header stubs (Phase 0–3) → JWT/OIDC (Phase 4) | `x-vendor-id`, `x-vendor-user-id`, `x-vendor-role` → `VendorContext` |
| Agent Runtime | CrewAI | 4-agent sequential pipeline with tool calling |
| LLM | Google Gemini 3.1 Flash-Lite | Low latency, tool-capable, structured output |
| Read Tools (7) | CrewAI BaseTool + Pydantic | Vendor-scoped, typed, RBAC-gated |
| Propose Tools (4) | CrewAI BaseTool + Pydantic | Create pending proposals with before/after preview |
| RBAC | Role-based gating | Read: all roles; Write: owner/admin/support; Approve: owner/admin/support |
| Data | SQLAlchemy + aiosqlite (async) | Repository pattern, vendor-scoped queries |
| Observability | Structured JSON logs | Correlation IDs, phase timers, rate-limit headers |
| Streaming | SSE (Server-Sent Events) | Phase status → result → done events |
| Write Safety | Propose → Approve → Execute | LLM never mutates; human decision on `/decide` endpoint |

### 3.3 4-Agent Pipeline (CrewAI)

| Agent | Role | Tools | Output |
|-------|------|-------|--------|
| **Intent Router** | Classify intent: `read` \| `write_propose` \| `clarify` \| `refuse` | None | JSON `{intent, reason}` |
| **Data Analyst** | Answer factual queries using 7 read tools | `list_games`, `list_trial_users`, `get_revenue`, `search_users`, `get_user`, `get_membership`, `get_vendor_summary` | Grounded answer + UI blocks (table/kpi) |
| **Action Planner** | Create proposals via 4 propose tools | `propose_extend_trial`, `propose_change_plan`, `propose_suspend_user`, `propose_update_membership_dates` | Proposal card with preview + expiry |
| **Response Composer** | Format final answer from specialist output | None | JSON `{text, blocks[], tool_traces[]}` |

### 3.4 Request Flow (Read)

```
POST /v1/copilot/sessions/{id}/messages
    │
    ▼
Auth Middleware → VendorContext (vendor_id, user_id, role, timezone)
    │
    ▼
Rate Limiter (30/min, 200/hr per vendor_user)
    │
    ▼
ChatService.handle_user_message()
    │
    ├── Persist user message
    ├── Load recent history
    ├── Build tools for vendor_context
    ├── Run Copilot Crew (Router → Analyst → Composer)
    │       │
    │       ├── Router: classify intent (read/write/clarify/refuse)
    │       ├── Analyst: invoke read tools (vendor-scoped)
    │       └── Composer: format {text, blocks[], tool_traces[]}
    │
    ├── Persist assistant message + audit event
    └── Return ChatTurnResponse (or SSE stream)
```

### 3.5 Request Flow (Write)

```
User: "Extend trial for u_alice by 7 days"
    │
    ▼
Router → intent: write_propose
    │
    ▼
Action Planner → propose_extend_trial(user_id="u_alice", game_slug="badminton", extra_days=7)
    │
    ├── Validate args + RBAC (role must be owner/admin/support)
    ├── Load current membership → build preview {before, after}
    ├── INSERT action_proposal (status=pending, expires_at=now+30min)
    ├── INSERT audit_event (proposal.create)
    └── Return {proposal_id, preview, "PENDING approval"}
    │
    ▼
UI shows Approval Card
    │
    ▼
Human clicks Approve → POST /v1/copilot/proposals/{id}/decide
    │
    ▼
ApprovalService.decide_proposal()
    │
    ├── Re-validate (exists, vendor-scoped, not expired, not decided)
    ├── Re-load current state (race check)
    ├── Execute mutation (UPDATE membership)
    ├── UPDATE proposal (status=executed, execution_result)
    ├── INSERT audit_event (proposal.execute)
    └── Return {status: executed}
```

### 3.6 Security Model

#### 3.6.1 Authentication (Phase 0 → 4)

| Phase | Mechanism |
|-------|-----------|
| 0–3 | Header stubs: `x-vendor-id`, `x-vendor-user-id`, `x-vendor-role` |
| 4 | JWT/OIDC from portal IdP (Auth0, Azure AD, Keycloak) |

#### 3.6.2 Authorization (RBAC)

| Action | Allowed Roles |
|--------|---------------|
| Read tools (all) | `owner`, `admin`, `support`, `viewer` |
| Propose tools | `owner`, `admin`, `support` |
| Approve/Reject | `owner`, `admin`, `support` |
| Audit log | `owner`, `admin`, `support` |
| Re-seed | `owner`, `admin` |

#### 3.6.3 Tenancy

- `vendor_id` **only** from authenticated context (never from LLM)
- Every repository query filters `WHERE vendor_id = :ctx_vendor_id`
- Cross-vendor access → 404 (not 403, to avoid enumeration)

#### 3.6.4 Write Safety

| Control | Implementation |
|---------|----------------|
| LLM cannot mutate | Propose tools only create proposals |
| Human-in-the-loop | Approve endpoint is authenticated FastAPI route |
| Re-validation | On approve: re-check existence, vendor scope, policy |
| Idempotency | Unique `idempotency_key` per proposal |
| Expiry | Proposals auto-expire (configurable, default 30 min) |
| Audit trail | Every tool call, proposal, decision, execution logged |

### 3.7 Observability

#### 3.7.1 Structured Logging

```json
{
  "timestamp": "2025-07-12T10:30:00.123Z",
  "level": "INFO",
  "logger": "app.http",
  "message": "Request completed",
  "correlation_id": "abc123",
  "vendor_id": "v_acme",
  "vendor_user_id": "vu_admin",
  "method": "POST",
  "path": "/v1/copilot/sessions/cs_123/messages",
  "status_code": 201,
  "duration_ms": 1450,
  "phases": {
    "auth": 5,
    "rate_limit": 1,
    "agent_routing": 120,
    "tool_execution": 850,
    "composition": 300,
    "persistence": 170
  }
}
```

#### 3.7.2 Rate Limit Headers

```
X-RateLimit-Limit-Minute: 30
X-RateLimit-Remaining-Minute: 28
X-RateLimit-Reset-Minute: 1720785600
X-RateLimit-Limit-Hour: 200
X-RateLimit-Remaining-Hour: 195
X-RateLimit-Reset-Hour: 1720789200
```

#### 3.7.3 Response Headers

```
X-Request-ID: req_abc123
X-Correlation-ID: corr_xyz789
X-Response-Time-MS: 1450
```

#### 3.7.4 SSE Event Format

```
event: status
data: {"phase": "routing"}

event: status
data: {"phase": "running"}

event: result
data: {"text": "Revenue is $1,285.00", "blocks": [{"type": "kpi", ...}], "user_message_id": "m_1", "assistant_message_id": "m_2"}

event: done
data: {"message_id": "m_2", "session_id": "cs_123"}
```

---

## 4. Data Model

### 4.1 Core Tables

```sql
-- Vendors (tenants)
vendors (
  id TEXT PRIMARY KEY,           -- v_acme
  name TEXT NOT NULL,            -- Acme Sports
  timezone TEXT NOT NULL,        -- Asia/Kolkata
  created_at TIMESTAMPTZ NOT NULL
)

-- Vendor staff (authenticated users)
vendor_users (
  id TEXT PRIMARY KEY,           -- vu_admin
  vendor_id TEXT REFERENCES vendors(id),
  email TEXT NOT NULL,
  role TEXT NOT NULL,            -- owner | admin | support | viewer
  created_at TIMESTAMPTZ NOT NULL
)

-- Games offered by vendor
games (
  id TEXT PRIMARY KEY,           -- g_badminton
  vendor_id TEXT REFERENCES vendors(id),
  slug TEXT NOT NULL,            -- badminton
  name TEXT NOT NULL,            -- Badminton
  UNIQUE (vendor_id, slug)
)

-- End users (players)
app_users (
  id TEXT PRIMARY KEY,           -- u_alice
  vendor_id TEXT REFERENCES vendors(id),
  email TEXT,
  display_name TEXT,
  status TEXT NOT NULL,          -- active | suspended | churned | deleted
  created_at TIMESTAMPTZ NOT NULL
)

-- User's membership in a game
memberships (
  id TEXT PRIMARY KEY,           -- m_alice_badminton
  vendor_id TEXT,
  user_id TEXT REFERENCES app_users(id),
  game_id TEXT REFERENCES games(id),
  plan TEXT NOT NULL,            -- free | trial | basic | pro
  starts_at TIMESTAMPTZ NOT NULL,
  ends_at TIMESTAMPTZ,
  trial_ends_at TIMESTAMPTZ,
  status TEXT NOT NULL,          -- active | expired | cancelled
  UNIQUE (vendor_id, user_id, game_id)
)

-- Daily revenue per game
revenue_daily (
  id TEXT PRIMARY KEY,
  vendor_id TEXT,
  game_id TEXT,                  -- NULL = all games
  day DATE NOT NULL,
  currency TEXT NOT NULL DEFAULT 'USD',
  gross_cents BIGINT NOT NULL,
  refunds_cents BIGINT NOT NULL DEFAULT 0,
  net_cents BIGINT NOT NULL,
  UNIQUE (vendor_id, game_id, day, currency)
)

-- Chat sessions
chat_sessions (
  id TEXT PRIMARY KEY,           -- cs_...
  vendor_id TEXT,
  vendor_user_id TEXT,
  created_at TIMESTAMPTZ NOT NULL
)

-- Chat messages
chat_messages (
  id TEXT PRIMARY KEY,           -- m_...
  session_id TEXT REFERENCES chat_sessions(id),
  role TEXT NOT NULL,            -- user | assistant | tool | system
  content JSONB NOT NULL,        -- {text, blocks[], tool_traces[]}
  created_at TIMESTAMPTZ NOT NULL
)

-- Action proposals (write path)
action_proposals (
  id TEXT PRIMARY KEY,           -- ap_...
  vendor_id TEXT,
  session_id TEXT,
  message_id TEXT,
  proposed_by TEXT,              -- vendor_user_id
  action_type TEXT NOT NULL,     -- extend_trial | change_plan | suspend_user | update_membership_dates
  payload JSONB NOT NULL,
  preview JSONB NOT NULL,        -- {before, after}
  status TEXT NOT NULL,          -- pending | approved | rejected | executed | failed | expired
  idempotency_key TEXT UNIQUE,
  expires_at TIMESTAMPTZ NOT NULL,
  decided_by TEXT,
  decided_at TIMESTAMPTZ,
  execution_result JSONB,
  created_at TIMESTAMPTZ NOT NULL
)

-- Immutable audit log
audit_events (
  id TEXT PRIMARY KEY,
  vendor_id TEXT,
  actor_id TEXT,
  event_type TEXT NOT NULL,      -- proposal.create | proposal.decide | proposal.execute | copilot.turn
  entity_type TEXT,
  entity_id TEXT,
  metadata JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
)
```

---

## 5. Tool Catalog

### 5.1 Read Tools (Data Analyst)

| Tool | Description | Args | Returns |
|------|-------------|------|---------|
| `get_revenue` | Revenue for day/range | `day?`, `from?`, `to?`, `game_slug?` | `{found, gross, refunds, net, currency, rows[]}` |
| `list_trial_users` | Users on trial | `game_slug?`, `limit`, `cursor` | `{count, trial_users[{user_id, email, display_name, trial_ends_at, game_slug}]}` |
| `search_users` | Find by email/name/id | `query`, `limit` | `{count, users[{id, email, display_name, status}]}` |
| `get_user` | Profile + memberships | `user_id` | `{found, user{id, email, display_name, status, memberships[]}}` |
| `get_membership` | Single membership | `user_id`, `game_slug` | `{found, membership{plan, starts_at, ends_at, trial_ends_at, status, game_slug}}` |
| `list_games` | Vendor's games | — | `{games[{id, slug, name}]}` |
| `get_vendor_summary` | KPIs | `day?` | `{game_count, active_users, active_trials, revenue_today, revenue_yesterday}` |

### 5.2 Propose Tools (Action Planner)

| Tool | Description | Args | Creates Proposal |
|------|-------------|------|------------------|
| `propose_extend_trial` | Add days to trial | `user_id`, `game_slug`, `extra_days (1-90)` | ✅ |
| `propose_change_plan` | Change plan tier | `user_id`, `game_slug`, `new_plan (free|trial|basic|pro)` | ✅ |
| `propose_suspend_user` | Suspend end-user | `user_id`, `reason` | ✅ |
| `propose_update_membership_dates` | Set start/end | `user_id`, `game_slug`, `starts_at?`, `ends_at?` | ✅ |

**All propose tools:**
- Never mutate data
- Build `{before, after}` preview
- Insert `action_proposals` row with `status=pending`
- Return proposal_id + preview + expiry

---

## 6. API Reference

### 6.1 Copilot Chat

| Method | Path | Auth | Body | Response |
|--------|------|------|------|----------|
| `POST` | `/v1/copilot/sessions` | Headers | `{}` | `ChatSessionResponse` |
| `GET` | `/v1/copilot/sessions/{id}` | Headers | — | `ChatSessionResponse` |
| `GET` | `/v1/copilot/sessions/{id}/messages` | Headers | — | `ChatMessageListResponse` |
| `POST` | `/v1/copilot/sessions/{id}/messages` | Headers | `ChatMessageCreate` | `ChatTurnResponse` |
| `POST` | `/v1/copilot/sessions/{id}/messages:stream` | Headers | `ChatMessageCreate` | SSE Stream |

**Headers:** `x-vendor-id`, `x-vendor-user-id`, `x-vendor-role`

### 6.2 Approvals

| Method | Path | Auth | Body | Response |
|--------|------|------|------|----------|
| `GET` | `/v1/copilot/proposals` | Headers + RBAC | Query: `status?` | `ProposalListResponse` |
| `GET` | `/v1/copilot/proposals/{id}` | Headers | — | `ActionProposalResponse` |
| `POST` | `/v1/copilot/proposals/{id}/decide` | Headers + `require_role(owner,admin,support)` | `ProposalDecisionRequest` | `ActionProposalResponse` |

### 6.3 Ops

| Method | Path | Auth | Response |
|--------|------|------|----------|
| `GET` | `/v1/health` | — | `{status, app, database, gemini_configured, version}` |
| `GET` | `/v1/copilot/audit` | Headers + `require_role(admin,support)` | `AuditListResponse` |
| `POST` | `/v1/admin/seed` | Headers + `require_role(admin)` | `{counts}` |

---

## 7. Security Model

### 7.1 Authentication (Phase 0 → 4)
| Phase | Mechanism |
|-------|-----------|
| 0–3 | Header stubs: `x-vendor-id`, `x-vendor-user-id`, `x-vendor-role` |
| 4 | JWT/OIDC from portal IdP (Auth0, Azure AD, Keycloak) |

### 7.2 Authorization (RBAC)

| Action | Allowed Roles |
|--------|---------------|
| Read tools (all) | `owner`, `admin`, `support`, `viewer` |
| Propose tools | `owner`, `admin`, `support` |
| Approve/Reject | `owner`, `admin`, `support` |
| Audit log | `owner`, `admin`, `support` |
| Re-seed | `owner`, `admin` |

### 7.3 Tenancy
- `vendor_id` **only** from authenticated context (never from LLM)
- Every repository query filters `WHERE vendor_id = :ctx_vendor_id`
- Cross-vendor access → 404 (not 403, to avoid enumeration)

### 7.4 Write Safety
| Control | Implementation |
|---------|----------------|
| LLM cannot mutate | Propose tools only create proposals |
| Human-in-the-loop | Approve endpoint is authenticated FastAPI route |
| Re-validation | On approve: re-check existence, vendor scope, policy |
| Idempotency | Unique `idempotency_key` per proposal |
| Expiry | Proposals auto-expire (configurable, default 15 min) |
| Audit trail | Every tool call, proposal, decision, execution logged |

---

## 8. Observability

### 8.1 Structured Logging
```json
{
  "timestamp": "2025-07-12T10:30:00.123Z",
  "level": "INFO",
  "logger": "app.http",
  "message": "Request completed",
  "correlation_id": "abc123",
  "vendor_id": "v_acme",
  "vendor_user_id": "vu_admin",
  "method": "POST",
  "path": "/v1/copilot/sessions/cs_123/messages",
  "status_code": 201,
  "duration_ms": 1450,
  "phases": {
    "auth": 5,
    "rate_limit": 1,
    "agent_routing": 120,
    "tool_execution": 850,
    "composition": 300,
    "persistence": 170
  }
}
```

### 8.2 Rate Limit Headers
```
X-RateLimit-Limit-Minute: 30
X-RateLimit-Remaining-Minute: 28
X-RateLimit-Reset-Minute: 1720785600
X-RateLimit-Limit-Hour: 200
X-RateLimit-Remaining-Hour: 195
X-RateLimit-Reset-Hour: 1720789200
```

### 8.3 Response Headers
```
X-Request-ID: req_abc123
X-Correlation-ID: corr_xyz789
X-Response-Time-MS: 1450
```

---

## 9. Testing Strategy

| Layer | Tool | Coverage |
|-------|------|----------|
| Unit | pytest | Tool validation, RBAC, proposal state machine |
| Integration | pytest + httpx + ASGITransport | Full API flows, vendor scoping, approval flow |
| Agent Eval | Golden eval suite (42 cases) | Intent routing, tool selection, output quality |
| Security | pytest | Cross-vendor 404, role gates, rate limits |

**Test Count:** 85 (12 Phase 0 + 19 Phase 1 + 22 Phase 2 + 32 Phase 3)

---

## 10. Deployment

### 10.1 Requirements
- Python 3.12+
- `GEMINI_API_KEY` environment variable
- SQLite file (dev) or PostgreSQL (prod)

### 10.2 Environment Variables
```bash
GEMINI_API_KEY=...
DATABASE_URL=sqlite+aiosqlite:///./copilot.db  # or postgresql+asyncpg://...
APP_ENV=development
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
PROPOSAL_TTL_MINUTES=15
```

### 10.3 Run
```bash
cd apps/copilot-api
uvicorn app.main:app --reload --port 8000
# → http://localhost:8000/docs
```

---

## 11. Future Work (Phase 4)

| Item | Description |
|------|-------------|
| Real Vendor APIs | Swap SQLite repos for HTTP clients to vendor backend |
| JWT/OIDC Auth | Replace header stubs with token validation |
| Bulk Operations | `propose_bulk_*` tools with stricter RBAC (owner only) |
| Multi-Approver | Require 2 approvals for sensitive actions |
| Retention Policy | Auto-archive chat/proposals after N days |
| Portal UI | React/Vue components for chat + approval cards |

---

## 12. Appendix

### 12.1 Example Proposal Payloads

**Extend Trial:**
```json
{
  "action_type": "extend_trial",
  "payload": {
    "user_id": "u_alice",
    "game_slug": "badminton",
    "extra_days": 7,
    "current_trial_ends_at": "2025-07-16T10:30:00Z",
    "new_trial_ends_at": "2025-07-23T10:30:00Z"
  },
  "preview": {
    "before": {"trial_ends_at": "2025-07-16T10:30:00Z"},
    "after": {"trial_ends_at": "2025-07-23T10:30:00Z"}
  }
}
```

**Change Plan:**
```json
{
  "action_type": "change_plan",
  "payload": {
    "user_id": "u_bob",
    "game_slug": "cricket",
    "new_plan": "basic",
    "current_plan": "pro"
  },
  "preview": {
    "before": {"plan": "pro"},
    "after": {"plan": "basic"}
  }
}
```

### 12.2 SSE Event Format

```
event: status
data: {"phase": "routing"}

event: status
data: {"phase": "running"}

event: result
data: {"text": "Revenue is $1,285.00", "blocks": [{"type": "kpi", ...}], "user_message_id": "m_1", "assistant_message_id": "m_2"}

event: done
data: {"message_id": "m_2", "session_id": "cs_123"}
```

---

**End of Specification**