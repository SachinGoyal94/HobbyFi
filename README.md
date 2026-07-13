# HobbyFi Vendor Portal AI Copilot

> **An AI-powered copilot for vendor portal operators — read data, propose changes, get approval, execute safely.**

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com)
[![CrewAI](https://img.shields.io/badge/CrewAI-0.70+-orange.svg)](https://crewai.com)
[![Tests](https://img.shields.io/badge/Tests-85%20passing-brightgreen.svg)]()

---

## What It Does

| Capability | Example | Safety Model |
|------------|---------|--------------|
| **Read (Q&A)** | "What's today's revenue for badminton?" | Immediate, vendor-scoped |
| **Read (Tables)** | "List trial users expiring this week" | Structured blocks + text |
| **Write (Propose)** | "Extend Alice's trial by 7 days" | Creates **pending proposal** |
| **Approve/Reject** | Vendor clicks Approve in UI | Server-side execution, audited |

**Core Principle:** The LLM **never mutates data directly**. All writes go through a human-in-the-loop approval gate.

---

## Quick Start

```bash
# 1. Clone & enter
cd apps/copilot-api

# 2. Install deps (uv recommended)
uv pip install -e .

# 3. Configure
cp .env.example .env
# Edit .env → add GEMINI_API_KEY from Google AI Studio

# 4. Run
uvicorn app.main:app --reload --port 8000

# 5. Explore
open http://localhost:8000/docs
```

### Try the API

```bash
# 1. Create a session
curl -X POST http://localhost:8000/v1/copilot/sessions \
  -H "x-vendor-id: v_acme" \
  -H "x-vendor-user-id: vu_admin" \
  -H "x-vendor-role: admin" \
  -H "Content-Type: application/json" \
  -d '{}'

# 2. Ask a question (replace SESSION_ID)
curl -X POST http://localhost:8000/v1/copilot/sessions/SESSION_ID/messages \
  -H "x-vendor-id: v_acme" \
  -H "x-vendor-user-id: vu_admin" \
  -H "x-vendor-role: admin" \
  -H "Content-Type: application/json" \
  -d '{"content": "What is today revenue?"}'

# 3. Propose a change
curl -X POST http://localhost:8000/v1/copilot/sessions/SESSION_ID/messages \
  -H "x-vendor-id: v_acme" \
  -H "x-vendor-user-id: vu_admin" \
  -H "x-vendor-role: admin" \
  -H "Content-Type: application/json" \
  -d '{"content": "Extend trial for u_alice on badminton by 7 days"}'

# 4. Approve the proposal (copy proposal_id from response)
curl -X POST http://localhost:8000/v1/copilot/proposals/ap_xxx/decide \
  -H "x-vendor-id: v_acme" \
  -H "x-vendor-user-id: vu_admin" \
  -H "x-vendor-role: admin" \
  -H "Content-Type: application/json" \
  -d '{"decision": "approve"}'
```

---

## Architecture

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

### Key Components

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

### 4-Agent Pipeline (CrewAI)

| Agent | Role | Tools | Output |
|-------|------|-------|--------|
| **Intent Router** | Classify intent: `read` \| `write_propose` \| `clarify` \| `refuse` | None | JSON `{intent, reason}` |
| **Data Analyst** | Answer factual queries using 7 read tools | `list_games`, `list_trial_users`, `get_revenue`, `search_users`, `get_user`, `get_membership`, `get_vendor_summary` | Grounded answer + UI blocks (table/kpi) |
| **Action Planner** | Create proposals via 4 propose tools | `propose_extend_trial`, `propose_change_plan`, `propose_suspend_user`, `propose_update_membership_dates` | Proposal card with preview + expiry |
| **Response Composer** | Format final answer from specialist output | None | JSON `{text, blocks[], tool_traces[]}` |

### Data Flow: Read Query

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
    │       ├── Router: classify intent
    │       ├── Analyst: invoke read tools (vendor-scoped)
    │       └── Composer: format {text, blocks[], tool_traces[]}
    │
    ├── Persist assistant message + audit event
    └── Return ChatTurnResponse (or SSE stream)
```

### Data Flow: Write Proposal

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
    ├── INSERT action_proposal (status=pending, expires_at=now+15min)
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

### Security Model

| Layer | Mechanism |
|-------|-----------|
| **Authentication** | Header stubs (Phase 0–3) → JWT/OIDC (Phase 4) |
| **Authorization** | Role-based: read=all, write=owner/admin/support, approve=owner/admin/support |
| **Tenancy** | `vendor_id` only from auth context; all repos filter `WHERE vendor_id = :ctx_vendor_id` |
| **Cross-vendor** | Returns 404 (not 403) to avoid enumeration |
| **Write Safety** | Propose tools only create proposals; execution only in authenticated FastAPI route |
| **Idempotency** | Unique `idempotency_key` per proposal |
| **Expiry** | Proposals auto-expire (configurable, default 30 min) |
| **Audit Trail** | Immutable log: tool calls, proposals, decisions, executions |

---

## Demo Data (Seeded Automatically)

| Entity | Count | Notes |
|--------|-------|-------|
| Vendors | 2 | Acme Sports (demo), Beta Games Co (tenancy test) |
| Vendor Users | 6 | 3 roles each: owner/admin/support/viewer |
| Games | 3 + 3 | Badminton, Cricket, Football / Tennis, Squash, Pickleball |
| End Users | 13 + 3 | Varied states: active, trial, suspended, churned |
| Memberships | 20+ | All plan types, trial expirations for demos |
| Revenue | 30 days × 4 games | Realistic daily variation |

---

## Test Suite

```bash
# All tests (85)
pytest tests/ -v

# By phase
pytest tests/test_phase0.py -v           # Foundation
pytest tests/test_phase1_chat.py -v      # Chat API + SSE
pytest tests/test_phase1_tools.py -v     # Read tools + scoping
pytest tests/test_phase2_approvals.py -v # Propose→Approve→Execute
pytest tests/test_phase3_golden_eval.py -v # 42 golden cases
```

### Golden Evaluation (Phase 3)

| Category | Cases | Validates |
|----------|-------|-----------|
| Read | 8 | Tool selection, output structure |
| Write Propose | 4 | Preview cards, pending status |
| Clarify | 2 | Missing params → ask, no proposal |
| Refuse | 4 | Cross-vendor, bulk delete, SQL, secrets blocked |

---

## Project Structure

```
HobbyFi/
├── SPEC.md                 # Machine-readable spec
├── README.md               # This file
├── apps/
│   └── copilot-api/
│       ├── pyproject.toml
│       ├── .env.example
│       └── app/
│           ├── main.py                 # FastAPI factory
│           ├── config.py               # Pydantic Settings
│           ├── deps.py                 # Auth, DB, role deps
│           ├── observability.py        # JSON logs, correlation IDs, phase timing
│           ├── api/
│           │   ├── middleware/
│           │   │   ├── request_id.py
│           │   │   └── rate_limiter.py
│           │   └── routes/
│           │       ├── health.py
│           │       ├── sessions.py
│           │       └── proposals.py
│           ├── services/
│           │   ├── chat_service.py
│           │   ├── approval_service.py
│           │   └── proposal_expiry.py
│           ├── agent/
│           │   ├── crew.py             # 4-agent pipeline
│           │   ├── llm.py              # Gemini wrapper
│           │   └── tools/
│           │       ├── read_tools.py   # 7 read tools
│           │       ├── write_tools.py  # 4 propose tools
│           │       ├── rbac.py         # Role gates
│           │       └── registry.py     # ToolRunContext
│           └── domain/
│               ├── models.py           # SQLAlchemy
│               ├── schemas.py          # Pydantic API
│               ├── seed.py             # Rich mock data
│               └── repos/
│                   ├── users.py
│                   ├── memberships.py
│                   ├── revenue.py
│                   └── games.py
└── tests/
    ├── conftest.py
    ├── test_phase0.py
    ├── test_phase1_chat.py
    ├── test_phase1_tools.py
    ├── test_phase2_approvals.py
    └── test_phase3_golden_eval.py
```

---

## Configuration

`.env` file:

```bash
# Required
GEMINI_API_KEY=your_google_ai_studio_key
GEMINI_MODEL=gemini-3.1-flash-lite
GEMINI_TEMPERATURE=0.2
GEMINI_MAX_OUTPUT_TOKENS=2048

# Optional
DATABASE_URL=sqlite+aiosqlite:///./copilot_mock.db
APP_ENV=development
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
PROPOSAL_TTL_MINUTES=15
```

---

## API Reference

### Copilot Chat

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/v1/copilot/sessions` | ✅ | Create session |
| `GET` | `/v1/copilot/sessions/{id}` | ✅ | Get session |
| `GET` | `/v1/copilot/sessions/{id}/messages` | ✅ | List messages |
| `POST` | `/v1/copilot/sessions/{id}/messages` | ✅ | Send message (JSON) |
| `POST` | `/v1/copilot/sessions/{id}/messages:stream` | ✅ | SSE stream |

### Approvals

| Method | Path | Auth | Roles | Description |
|--------|------|------|-------|-------------|
| `GET` | `/v1/copilot/proposals?status=pending` | ✅ | all | List proposals |
| `GET` | `/v1/copilot/proposals/{id}` | ✅ | all | Get proposal + preview |
| `POST` | `/v1/copilot/proposals/{id}/decide` | ✅ | owner, admin, support | Approve/Reject |

### Ops

| Method | Path | Auth | Roles | Description |
|--------|------|------|-------|-------------|
| `GET` | `/v1/health` | ❌ | — | Liveness |
| `GET` | `/v1/copilot/audit` | ✅ | admin, support | Audit log |
| `POST` | `/v1/admin/seed` | ✅ | admin | Re-seed mock data |

---

## Security Model

| Layer | Mechanism |
|-------|-----------|
| **Authentication** | Header stub (Phase 0) → JWT/OIDC (Phase 4) |
| **Authorization** | Role-based: read = all, write = owner/admin/support |
| **Tenancy** | `vendor_id` from auth context only; all repos filter by it |
| **Write Safety** | Propose → Approve → Execute (separate endpoint, not LLM) |
| **Idempotency** | Unique `idempotency_key` per proposal |
| **Expiry** | Proposals auto-expire (default 15 min) |
| **Audit** | Immutable log of every tool call, proposal, decision, execution |

---

## Observability

- **Structured JSON logs** with `correlation_id`, `vendor_id`, `elapsed_ms`
- **Phase timers** for: routing, tool execution, composition
- **Rate limit headers** on every response
- **Request ID** on every response

---

## Roadmap

| Phase | Focus | Status |
|-------|-------|--------|
| 0 | Foundation (FastAPI, DB, Auth stub, Seed) | ✅ |
| 1 | Read Copilot (Agent + 7 tools + SSE) | ✅ |
| 2 | Write with Approval (4 propose tools + executor) | ✅ |
| 3 | Hardening (Multi-agent, RBAC, Rate limits, Golden evals, Observability) | ✅ |
| 4 | Production Integration (Real APIs, JWT/SSO, Bulk ops, Multi-approver) | ⏳ |

---

## License

MIT — see [LICENSE](LICENSE) for details.