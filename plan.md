# Vendor Portal AI Copilot — Architecture Plan

**Stack (locked)**

| Layer | Choice |
|---|---|
| API | **FastAPI** (Python) |
| Agents | **CrewAI** (orchestration) |
| Tooling / utilities | **LangChain** where required (tools, prompts, output parsers, Gemini LLM wrapper) |
| LLM | **Google Gemini 3.1 Flash-Lite** — model id: `gemini-3.1-flash-lite` |
| Auth to model | `GEMINI_API_KEY` (Google AI Studio / Gemini API) |
| Data (v1) | Mock schema (SQLite / in-memory) behind repository ports |

---

## 1. Goal

Build an **AI copilot** inside the vendor portal that:

| Capability | Examples | Access model |
|---|---|---|
| **Read (Q&A)** | “What is revenue of today?”, “List trial users of badminton game” | Immediate, scoped to the logged-in vendor |
| **Write (mutations)** | “Update this user’s membership date”, “Increase free trial for this user” | **Proposed only** → vendor **approves** → then executed |

The system must be **safe by default**: the model never mutates production data on its own. All side effects go through a human-in-the-loop approval gate.

---

## 2. Design principles

1. **Tool-calling over free-form SQL** — CrewAI agents use typed tools; they never write raw SQL or hit the DB directly.
2. **Read vs write separation** — Read tools run immediately. Write tools only create **pending action proposals**.
3. **Vendor isolation** — Every query and mutation is filtered by `vendor_id` from the authenticated session (never from the LLM).
4. **Least privilege** — Tools expose only fields and operations the vendor is allowed to see/change.
5. **Auditability** — Every intent, proposal, approval, and execution is logged.
6. **Idempotency** — Mutations carry idempotency keys so double-approve / retries are safe.
7. **Mock-first** — Start with SQLite mock schema; swap the repository layer for real APIs later.
8. **FastAPI owns HTTP; CrewAI owns reasoning** — Keep the agent runtime behind a service interface so routes stay thin.

---

## 3. High-level architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Vendor Portal (Web UI)                               │
│  ┌──────────────┐  ┌────────────────────┐  ┌─────────────────────────────┐ │
│  │ Chat panel   │  │ Approval cards     │  │ Result tables / charts      │ │
│  │ (SSE stream) │  │ (Approve / Reject) │  │ (tool results rendered)     │ │
│  └──────┬───────┘  └─────────┬──────────┘  └─────────────────────────────┘ │
└─────────┼────────────────────┼──────────────────────────────────────────────┘
          │ HTTPS + JWT        │ POST /v1/copilot/proposals/{id}/decide
          ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FastAPI Application (Python)                              │
│  Auth middleware · rate limits · correlation IDs · OpenAPI                   │
│  Routes: /v1/copilot/*  ·  /v1/health                                        │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          ▼                         ▼                         ▼
┌──────────────────┐   ┌────────────────────┐   ┌──────────────────────────┐
│  Chat Service    │   │  Approval Service  │   │  Domain Repositories     │
│  sessions,       │   │  proposals CRUD    │   │  users, games, revenue,  │
│  history, SSE    │   │  approve / reject  │   │  memberships (mock →    │
│                  │   │  execute on approve│   │   real Vendor API later) │
└────────┬─────────┘   └─────────┬──────────┘   └────────────┬─────────────┘
         │                       │                           │
         ▼                       │                           │
┌────────────────────────────────────────┐                   │
│  Agent Runtime (CrewAI)                │                   │
│  ┌──────────────────────────────────┐  │                   │
│  │ Copilot Crew                     │  │                   │
│  │  • Intent / Router Agent         │  │                   │
│  │  • Data Analyst Agent (reads)    │  │                   │
│  │  • Action Planner Agent (writes) │  │                   │
│  └──────────────────────────────────┘  │                   │
│  LLM: gemini-3.1-flash-lite            │                   │
│  Tools: LangChain @tool / CrewAI tools │───────────────────┘
│  Context: vendor_id, role, session_id  │
└────────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────┐
│  Google Gemini API                     │
│  GEMINI_API_KEY                        │
│  model = gemini-3.1-flash-lite         │
└────────────────────────────────────────┘
```

### Component responsibilities

| Component | Responsibility |
|---|---|
| **FastAPI** | HTTP, auth, validation (Pydantic), SSE streaming, OpenAPI docs |
| **Chat Service** | Sessions, message persistence, invoke agent, stream tokens/events |
| **CrewAI Agent Runtime** | Multi-agent crew, task planning, tool selection loop |
| **LangChain** | Tool definitions, Gemini chat model binding, optional parsers / memory helpers |
| **Tool Layer** | Typed tools: validate input, enforce vendor scope, call repositories |
| **Approval Service** | Persist proposals, state machine, execute on vendor approve |
| **Domain Repos** | Mock (v1) or real vendor APIs for users, memberships, revenue, games |
| **Audit Log** | Immutable record of tool use, proposals, decisions, mutations |

---

## 4. Why this stack split

| Concern | Framework | Why |
|---|---|---|
| HTTP API, auth, SSE | **FastAPI** | Async-friendly, first-class Pydantic, OpenAPI |
| Multi-step agent workflow | **CrewAI** | Agents + tasks + crew process; clear roles (router / analyst / action planner) |
| Tools, LLM client, parsers | **LangChain** | Mature Gemini integration (`ChatGoogleGenerativeAI` / community wrappers), `@tool`, structured output |
| Inference | **Gemini 3.1 Flash-Lite** | Low latency, cost-efficient, tool-capable; good fit for high-volume copilot turns |

**Rule of thumb**

- Prefer **CrewAI** for “who does what” (agents, tasks, process).
- Prefer **LangChain** for “how tools and the model are wired” (tool schemas, LLM instance, optional chain helpers).
- Prefer **plain Python services** for approvals, repos, and audit — no agent needed after human approve.

---

## 5. Request flows

### 5.1 Read flow (immediate)

```
User: "list trial users of badminton game"
  → FastAPI Auth: attach vendor_id, role, vendor_user_id
  → Chat Service persists user message
  → CrewAI Copilot Crew kicks off
       Intent Agent  → classify: READ
       Data Analyst  → tool: list_trial_users(game_slug="badminton")
       Repo filters WHERE vendor_id = session.vendor_id
  → Structured result + natural language answer
  → SSE stream to UI (tokens / final blocks)
```

No approval step. Fully tenant-scoped.

### 5.2 Write flow (approve-then-execute)

```
User: "increase free trial of user u_123 by 7 days"
  → Crew: Intent → WRITE_PROPOSE
  → Action Planner Agent selects propose_extend_trial(...)
  → Tool does NOT mutate; creates ActionProposal:
       { status: pending, action_type, payload, preview, expires_at }
  → UI shows Approval Card
  → Vendor clicks Approve (authenticated FastAPI endpoint — not the LLM)
  → Approval Service:
       1. Re-validate (exists, vendor scope, policy)
       2. Execute via domain service (idempotent)
       3. status = executed | failed
  → Optional: append system/assistant message into chat thread
```

### 5.3 Proposal state machine

```
                ┌──────────┐
     create ──► │ pending  │
                └────┬─────┘
         approve /   │   \ reject / expire / cancel
                     ▼
              ┌────────────┐
              │  approved  │  (brief transitional)
              └─────┬──────┘
                    │ execute
           ┌────────┴────────┐
           ▼                 ▼
     ┌──────────┐      ┌──────────┐
     │ executed │      │  failed  │
     └──────────┘      └──────────┘

  Also terminal: rejected | expired | cancelled
```

Rules:
- Only `pending` can be approved or rejected.
- Execution is **server-side only** after a valid approve API call from an authorized vendor user.
- Proposals **expire** (e.g. 15–30 minutes).
- Re-validation on approve catches races (user deleted, membership already changed).
- The LLM / CrewAI **cannot** call the approve endpoint.

---

## 6. CrewAI design

### 6.1 Agents

| Agent | Goal | Tools |
|---|---|---|
| **Intent Router** | Classify user message → `read` \| `write_propose` \| `clarify` \| `refuse`; extract entities | None or light helpers (list_games) |
| **Data Analyst** | Answer factual questions with vendor-scoped data | All **read** tools |
| **Action Planner** | Draft safe mutation proposals with clear previews | All **propose_write** tools |
| **Response Composer** *(optional, can merge into analyst/planner)* | Produce final user-facing text + UI blocks JSON | None |

For v1, a **2–3 agent crew** is enough:

1. Router (or single agent with strong system prompt if latency matters)
2. Specialist (Analyst **or** Action Planner based on intent)
3. Optional composer

**Latency note:** Gemini 3.1 Flash-Lite is optimized for low latency. Prefer a **sequential process** with minimal agents for interactive chat; expand to multi-agent only when accuracy needs it.

### 6.2 Crew process

```python
# Conceptual — not production code
crew = Crew(
    agents=[intent_router, data_analyst, action_planner],
    tasks=[route_task, execute_task],
    process=Process.sequential,  # v1
    verbose=True,
    memory=False,  # use our chat_messages store instead
)
```

**Session context** injected into every task:

```python
VendorContext(
    vendor_id=...,
    vendor_user_id=...,
    role=...,          # owner | admin | support | viewer
    session_id=...,
    timezone=...,      # for "today" revenue
)
```

### 6.3 Single-agent fallback (MVP)

If multi-agent overhead is too high for chat UX:

```
One Copilot Agent
  role: "Vendor Portal Copilot"
  tools: read_* + propose_*
  LLM: gemini-3.1-flash-lite
  system: safety rules + tool policy
```

Ship single-agent first if needed; keep the same tool layer so graduating to a Crew is a thin change.

---

## 7. Gemini integration

### 7.1 Model

| Setting | Value |
|---|---|
| Display name | Gemini 3.1 Flash-Lite |
| Model ID | `gemini-3.1-flash-lite` |
| Provider | Google Gemini API (AI Studio key) |
| Env var | `GEMINI_API_KEY` |

### 7.2 Wiring options

**Preferred path for this project**

1. Create LangChain Gemini chat model bound to `gemini-3.1-flash-lite`.
2. Pass that LLM into CrewAI agents (`llm=` parameter).
3. Register tools as CrewAI tools (wrapping LangChain tools or pure Python callables).

```python
# Conceptual wiring
from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    google_api_key=settings.gemini_api_key,
    temperature=0.2,  # low for factual portal ops
)

# CrewAI agent
agent = Agent(
    role="Vendor Data Analyst",
    goal="Answer vendor-scoped questions accurately using tools",
    backstory="...",
    llm=llm,
    tools=read_tools,
    verbose=True,
)
```

### 7.3 Config (settings)

```env
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-3.1-flash-lite
GEMINI_TEMPERATURE=0.2
GEMINI_MAX_OUTPUT_TOKENS=2048
```

Use Pydantic `Settings` in FastAPI (`pydantic-settings`). Never log the API key.

### 7.4 Tool calling notes

- Keep tool JSON schemas small and explicit (better for Flash-Lite reliability).
- Cap max tool rounds per turn (e.g. 5) to avoid loops.
- On tool failure, return structured error strings the agent can recover from — do not raise uncaught into the HTTP layer.

---

## 8. Mock data schema

Initial domain model (SQLite or Postgres). Production maps 1:1 to existing vendor APIs later.

### 8.1 Core entities

```sql
vendors (
  id            TEXT PRIMARY KEY,          -- e.g. v_acme
  name          TEXT NOT NULL,
  timezone      TEXT NOT NULL DEFAULT 'UTC',
  created_at    TIMESTAMPTZ NOT NULL
)

vendor_users (
  id            TEXT PRIMARY KEY,
  vendor_id     TEXT NOT NULL REFERENCES vendors(id),
  email         TEXT NOT NULL,
  role          TEXT NOT NULL,             -- owner | admin | support | viewer
  created_at    TIMESTAMPTZ NOT NULL
)

games (
  id            TEXT PRIMARY KEY,
  vendor_id     TEXT NOT NULL REFERENCES vendors(id),
  slug          TEXT NOT NULL,             -- badminton, cricket, ...
  name          TEXT NOT NULL,
  UNIQUE (vendor_id, slug)
)

app_users (
  id            TEXT PRIMARY KEY,          -- e.g. u_123
  vendor_id     TEXT NOT NULL REFERENCES vendors(id),
  email         TEXT,
  display_name  TEXT,
  status        TEXT NOT NULL,             -- active | suspended | deleted
  created_at    TIMESTAMPTZ NOT NULL
)

memberships (
  id            TEXT PRIMARY KEY,
  vendor_id     TEXT NOT NULL,
  user_id       TEXT NOT NULL REFERENCES app_users(id),
  game_id       TEXT NOT NULL REFERENCES games(id),
  plan          TEXT NOT NULL,             -- free | trial | basic | pro
  starts_at     TIMESTAMPTZ NOT NULL,
  ends_at       TIMESTAMPTZ,
  trial_ends_at TIMESTAMPTZ,
  status        TEXT NOT NULL,             -- active | expired | cancelled
  UNIQUE (vendor_id, user_id, game_id)
)

revenue_daily (
  id            TEXT PRIMARY KEY,
  vendor_id     TEXT NOT NULL,
  game_id       TEXT,                      -- null = all games
  day           DATE NOT NULL,
  currency      TEXT NOT NULL DEFAULT 'USD',
  gross_cents   BIGINT NOT NULL,
  refunds_cents BIGINT NOT NULL DEFAULT 0,
  net_cents     BIGINT NOT NULL,
  UNIQUE (vendor_id, game_id, day, currency)
)

chat_sessions (
  id            TEXT PRIMARY KEY,
  vendor_id     TEXT NOT NULL,
  vendor_user_id TEXT NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL
)

chat_messages (
  id            TEXT PRIMARY KEY,
  session_id    TEXT NOT NULL REFERENCES chat_sessions(id),
  role          TEXT NOT NULL,             -- user | assistant | tool | system
  content       JSONB NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL
)

action_proposals (
  id              TEXT PRIMARY KEY,
  vendor_id       TEXT NOT NULL,
  session_id      TEXT,
  message_id      TEXT,
  proposed_by     TEXT NOT NULL,
  action_type     TEXT NOT NULL,
  payload         JSONB NOT NULL,
  preview         JSONB NOT NULL,
  status          TEXT NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE,
  expires_at      TIMESTAMPTZ NOT NULL,
  decided_by      TEXT,
  decided_at      TIMESTAMPTZ,
  execution_result JSONB,
  created_at      TIMESTAMPTZ NOT NULL
)

audit_events (
  id            TEXT PRIMARY KEY,
  vendor_id     TEXT NOT NULL,
  actor_id      TEXT,
  event_type    TEXT NOT NULL,
  entity_type   TEXT,
  entity_id     TEXT,
  metadata      JSONB NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL
)
```

### 8.2 Sample seed

```
vendors:        v_acme ("Acme Sports")
games:          badminton, cricket
app_users:      u_alice (trial badminton), u_bob (pro cricket)
revenue_daily:  today / yesterday for badminton & cricket
```

---

## 9. Tool catalog

Tools are the **only** way agents touch data. Each tool: name, description, JSON schema, mode (`read` | `propose_write`), required roles.

### 9.1 Read tools

| Tool | Purpose | Key args |
|---|---|---|
| `get_revenue` | Revenue for a day/range | `day` or `from`/`to`, optional `game_slug` |
| `list_trial_users` | Users currently on trial | `game_slug?`, `limit`, `cursor` |
| `search_users` | Find users by email/name/id | `query`, `limit` |
| `get_user` | User profile + memberships | `user_id` |
| `get_membership` | Single membership detail | `user_id`, `game_slug` |
| `list_games` | Vendor’s games | — |
| `get_vendor_summary` | High-level KPIs | optional `day` |

All read tools:
- Inject `vendor_id` from `VendorContext` (ignore model-supplied tenant ids).
- Cap result size (pagination + max rows).
- Return structured JSON; agent narrates for the user.

### 9.2 Write tools (proposal-only)

| Tool | Purpose | Payload sketch |
|---|---|---|
| `propose_extend_trial` | Add N days to trial | `user_id`, `game_slug`, `extra_days` |
| `propose_update_membership_dates` | Set start/end | `user_id`, `game_slug`, `starts_at?`, `ends_at?` |
| `propose_change_plan` | free/trial/basic/pro | `user_id`, `game_slug`, `new_plan` |
| `propose_suspend_user` | Suspend end-user | `user_id`, `reason` |

Each write tool:
1. Validates args (Pydantic).
2. Loads current state → builds **preview** (`before` / `after`).
3. Inserts `action_proposals` with `status=pending`.
4. Returns proposal id + preview to the agent (and UI).
5. **Never** writes to `memberships` / `app_users` directly.

### 9.3 Tool implementation pattern (Python)

```python
# Conceptual — LangChain tool wrapped for CrewAI
from langchain_core.tools import tool
from pydantic import BaseModel, Field

class ExtendTrialArgs(BaseModel):
    user_id: str
    game_slug: str
    extra_days: int = Field(ge=1, le=90)

def make_tools(ctx: VendorContext, repos, proposals) -> list:
    @tool("list_trial_users", args_schema=...)
    def list_trial_users(game_slug: str, limit: int = 20) -> str:
        rows = repos.memberships.list_trials(
            vendor_id=ctx.vendor_id, game_slug=game_slug, limit=limit
        )
        return json.dumps(rows)

    @tool("propose_extend_trial", args_schema=ExtendTrialArgs)
    def propose_extend_trial(user_id: str, game_slug: str, extra_days: int) -> str:
        # validate role, build preview, insert proposal — no mutation
        proposal = proposals.create_extend_trial(ctx, user_id, game_slug, extra_days)
        return json.dumps(proposal.to_public_dict())

    return [list_trial_users, propose_extend_trial, ...]
```

Factory pattern: tools close over `VendorContext` so agents cannot switch tenant.

---

## 10. FastAPI application design

### 10.1 Suggested project layout

```
HobbyFi/
  plan.md
  apps/
    copilot-api/
      pyproject.toml / requirements.txt
      app/
        main.py                 # FastAPI app factory
        config.py               # pydantic-settings
        deps.py                 # DI: db, ctx, services
        api/
          routes/
            health.py
            sessions.py
            chat.py             # POST message + SSE
            proposals.py        # list / decide
          middleware/
            auth.py
            request_id.py
        services/
          chat_service.py
          approval_service.py
          audit_service.py
        agent/
          crew.py               # CrewAI crew factory
          agents.py             # agent definitions
          tasks.py
          llm.py                # Gemini 3.1 Flash-Lite via LangChain
          tools/
            read_tools.py
            write_tools.py
            registry.py
        domain/
          models.py             # SQLAlchemy / SQLModel
          schemas.py            # Pydantic API schemas
          repos/
            users.py
            memberships.py
            revenue.py
            games.py
          seed.py
        db/
          session.py
          base.py
  packages/                     # optional later
  tests/
    test_tools_scoping.py
    test_approvals.py
    test_agent_golden.py
```

### 10.2 API surface

#### Copilot

| Method | Path | Description |
|---|---|---|
| `POST` | `/v1/copilot/sessions` | Create chat session |
| `GET` | `/v1/copilot/sessions/{id}/messages` | History |
| `POST` | `/v1/copilot/sessions/{id}/messages` | Send message (JSON response) |
| `POST` | `/v1/copilot/sessions/{id}/messages:stream` | SSE stream for assistant reply |

#### Approvals

| Method | Path | Description |
|---|---|---|
| `GET` | `/v1/copilot/proposals?status=pending` | List proposals |
| `GET` | `/v1/copilot/proposals/{id}` | Detail + preview |
| `POST` | `/v1/copilot/proposals/{id}/decide` | `{ "decision": "approve" \| "reject", "reason?" }` |

#### Ops

| Method | Path | Description |
|---|---|---|
| `GET` | `/v1/health` | Liveness |
| `GET` | `/v1/copilot/audit` | Vendor-scoped audit (admin roles) |

### 10.3 Streaming (SSE)

CrewAI runs are often non-streaming end-to-end. Practical v1 approach:

1. Stream **status events** while the crew runs (`routing`, `tool_start`, `tool_end`, `composing`).
2. Stream final **assistant text** (chunk if available; otherwise one `final` event).
3. Always emit structured **`blocks`** (tables, proposal cards) in a `result` event.

```text
event: status
data: {"phase": "tool_start", "tool": "list_trial_users"}

event: result
data: {"text": "...", "blocks": [{"type": "table", ...}]}

event: done
data: {"message_id": "m_..."}
```

Later: if token streaming is required, wrap Gemini streaming at the composer step only.

### 10.4 Auth

- JWT / portal session validated in FastAPI dependency.
- Builds `VendorContext` — **single source of truth** for tenancy.
- Roles gate tools and approve endpoint.

---

## 11. Agent orchestration (runtime sequence)

```
POST /messages
  → load history (last N turns)
  → build tools for VendorContext
  → build Crew (or single Agent) with gemini-3.1-flash-lite
  → crew.kickoff(inputs={user_message, history_summary, timezone})
  → collect:
       - assistant text
       - tool traces (for audit)
       - any new proposal ids
  → persist assistant message + blocks
  → return / SSE to client
```

### System / backstory essentials (all agents)

- You are the vendor portal copilot for **this vendor only**.
- Prefer tools over guessing. If data is missing, ask a clarifying question.
- Never claim a write succeeded until status is `executed`.
- When proposing writes, state clearly that **approval is required**.
- Do not invent user ids, revenue numbers, or membership dates.
- Refuse out-of-scope asks (other vendors, secrets, unrestricted bulk deletes).

### Structured assistant response

```json
{
  "text": "Here are the trial users for Badminton…",
  "blocks": [
    { "type": "table", "columns": ["user_id", "email", "trial_ends_at"], "rows": [...] },
    { "type": "proposal_card", "proposal_id": "ap_...", "summary": "...", "preview": {...} }
  ]
}
```

Use a Pydantic model + LangChain structured output / JSON mode on the final compose step when possible.

---

## 12. Security & tenancy

| Threat | Mitigation |
|---|---|
| Cross-vendor data leak | `vendor_id` only from auth → `VendorContext`; repos always filter |
| Prompt injection → unauthorized write | Writes only via proposals + separate authenticated approve API |
| Privilege escalation | Role checks on tools + approve endpoint |
| Stale proposal | Expiry + re-validation before execute |
| Replay / double execute | Unique `idempotency_key`; execute once |
| Over-broad bulk actions | Hard caps in v1 (one user per proposal) |
| API key leakage | Env-only secrets; never put key in prompts/logs |
| Tool loops / cost | Max iterations; rate limits per vendor_user; Flash-Lite cost controls |

**Critical rule:** Approve is a normal authenticated FastAPI route. CrewAI/Gemini cannot approve.

---

## 13. Python dependencies (indicative)

```text
fastapi
uvicorn[standard]
pydantic
pydantic-settings
sqlalchemy          # or sqlmodel
aiosqlite           # local mock
httpx
crewai
langchain
langchain-core
langchain-google-genai
google-generativeai   # if needed by provider stack
python-jose / PyJWT   # auth
sse-starlette         # SSE helpers
pytest
pytest-asyncio
```

Pin versions in `requirements.txt` / `uv.lock` / `poetry.lock` at implementation time.

---

## 14. Approval UX (product)

```
┌─────────────────────────────────────────────────────────┐
│ ⚠️ Action requires your approval                        │
│                                                         │
│ Extend free trial                                       │
│ User: Alice (u_alice) · Game: Badminton                 │
│ Trial ends: 2026-07-10 → 2026-07-17 (+7 days)           │
│                                                         │
│ Proposed by: you · Expires in 29 min                    │
│                                                         │
│        [ Reject ]              [ Approve ]              │
└─────────────────────────────────────────────────────────┘
```

After decision:
- **Executed:** confirmation + refreshed membership snippet.
- **Failed:** error reason + suggest new proposal.
- **Rejected / expired:** neutral status in thread.

---

## 15. Evaluation & quality

| Layer | Approach |
|---|---|
| Unit | Tool validation, vendor scoping, proposal state machine |
| Integration | Mock DB + FastAPI `TestClient` for chat + approve |
| Agent evals | Golden prompts → expected tool name + args |
| Security tests | Cross-vendor `user_id` → deny/empty |
| Approval tests | Expired / already-executed → reject |

Golden prompts:
1. Revenue today → `get_revenue` (vendor TZ).
2. Trial users badminton → `list_trial_users`.
3. Extend trial → `propose_extend_trial` only; no mutation until approve.
4. “Delete all users” → refuse / no tool.

---

## 16. Implementation phases

### Phase 0 — Foundation
- FastAPI app skeleton + settings (`GEMINI_API_KEY`, `GEMINI_MODEL=gemini-3.1-flash-lite`)
- Mock schema + seed (SQLAlchemy/SQLModel + SQLite)
- Auth stub → `VendorContext`
- Chat session + message tables
- Health endpoint

### Phase 1 — Read copilot (MVP)
- LangChain Gemini client (`gemini-3.1-flash-lite`)
- CrewAI single agent **or** small sequential crew
- 3–5 read tools
- `POST /messages` + optional SSE status events
- Vendor scoping tests

### Phase 2 — Write with approval
- `action_proposals` + decide API
- 2–3 `propose_*` tools + executor
- Approval cards contract in API response `blocks`
- Expiry job (APScheduler / asyncio background) + re-validation
- Full audit trail

### Phase 3 — Hardening
- Multi-agent crew (router + analyst + planner) if evals need it
- RBAC per tool
- Rate limits, idempotency polish
- Golden eval suite + prompt tuning for Flash-Lite
- Observability (structured logs, latency per phase)

### Phase 4 — Production integration
- Swap mock repos for real Vendor APIs
- Real portal JWT / SSO
- Bulk-safe ops only if product requires
- Optional multi-approver policy

---

## 17. Key decisions

| Decision | Choice | Rationale |
|---|---|---|
| Backend | **FastAPI** | Async Python, OpenAPI, fits agent stack |
| Agent framework | **CrewAI** | Clear multi-agent roles; tasks for read vs write paths |
| Tooling / LLM glue | **LangChain** | Gemini bindings, tool schemas, structured output |
| Model | **`gemini-3.1-flash-lite`** | Low latency + cost for interactive portal copilot |
| Model access | **`GEMINI_API_KEY`** | Simple Google AI Studio key for v1 |
| How agents access data | **Typed tools**, not text-to-SQL | Safer, auditable, RBAC-friendly |
| Writes | **Propose → approve → execute** | Human control; blocks injection-driven mutations |
| Tenancy | **Session-injected vendor_id** | Model cannot select another tenant |
| Response shape | **Text + UI blocks** | Tables / proposal cards without fragile markdown parsing |
| Data layer v1 | **Mock schema + repository ports** | Ship agent UX before real backend coupling |
| Crew complexity v1 | **Single agent OK; crew optional** | Prefer latency; expand agents when evals demand |
| Execution on approve | **Sync FastAPI service** (not CrewAI) | Deterministic mutations; no LLM in the execute path |

---

## 18. Open questions

1. **Roles:** Can `support` approve writes, or only `admin`/`owner`?
2. **Bulk actions:** Per-user proposals only in v1?
3. **Chat placement:** Drawer in existing portal vs dedicated page?
4. **Retention:** Chat + proposal retention for compliance?
5. **Timezone:** Always vendor timezone for “today”?
6. **Crew shape:** Start single-agent (faster) or full router+analyst+planner from day one?

---

## 19. Success metrics

- **Accuracy:** ≥ 90% on golden read eval set vs mock ground truth.
- **Safety:** 0 mutations without an explicit approve audit event.
- **Latency:** p50 end-to-end simple read &lt; 5–8s with Flash-Lite (tune agents down if slower).
- **Adoption:** WAU vendors; approval completion rate.
- **Trust:** Proposal reject rate (high may mean bad previews / wrong intent).

---

## 20. Concrete next steps

1. Scaffold `apps/copilot-api` (FastAPI + settings + health).
2. Add mock DB models, seed, repository interfaces.
3. Wire `llm.py` → `ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite")`.
4. Implement read tools + CrewAI agent + `/messages`.
5. Add `propose_extend_trial` + approve/reject + executor.
6. Golden tests for the three example prompts.

---

## Appendix A — Example end-to-end

**User:** “What is revenue of today?”

1. Crew/Agent → `get_revenue({ day: "2026-07-10" })`  
2. Assistant: “Today’s net revenue is **$1,285.00** …”

**User:** “List trial users of badminton game”

1. → `list_trial_users({ game_slug: "badminton" })`  
2. Text + table block.

**User:** “Increase free trial of u_alice by 7 days for badminton”

1. → `propose_extend_trial(...)` → proposal `ap_…` **pending**  
2. Card in UI; membership **not** changed.  
3. Vendor approves via FastAPI → executor updates `trial_ends_at` → `executed`.  
4. Chat: “Done. Alice’s Badminton trial now ends on 2026-07-17.”

---

## Appendix B — Non-goals (v1)

- Fully autonomous multi-step ops without approval  
- Cross-vendor analytics  
- Free-form SQL / code execution tools  
- Voice interface  
- Running mutations inside CrewAI after approval (execute is plain Python)  
- Replacing the entire vendor admin UI (copilot **augments** it)

---

## Appendix C — Environment checklist

```bash
# Required
export GEMINI_API_KEY=your_key_here
export GEMINI_MODEL=gemini-3.1-flash-lite

# Optional
export DATABASE_URL=sqlite+aiosqlite:///./copilot_mock.db
export LOG_LEVEL=INFO
export CORS_ORIGINS=http://localhost:3000
```

```bash
# Dev run
cd apps/copilot-api
uvicorn app.main:app --reload --port 8000
# Docs: http://localhost:8000/docs
```
