# Demo Script — HobbyFi Vendor Portal AI Copilot

## Prerequisites

```bash
# 1. Install dependencies
cd apps/copilot-api
pip install -r requirements.txt

# 2. Set Gemini API key (required for real agent; tests use mock)
export GEMINI_API_KEY="your-gemini-key"

# 3. Start server
uvicorn app.main:app --reload --port 8000
# → http://localhost:8000/docs
```

---

## Demo Flow 1: Read Query → Table Block (2 min)

**Scenario**: Vendor wants today's revenue breakdown.

### Via API (curl)

```bash
# 1. Create session
curl -X POST http://localhost:8000/v1/copilot/sessions \
  -H "x-vendor-id: v_acme" \
  -H "x-vendor-user-id: vu_admin" \
  -H "x-vendor-role: admin" \
  -H "Content-Type: application/json" \
  -d '{}'

# Response: {"id": "cs_abc123", "vendor_id": "v_acme", ...}

# 2. Ask question
curl -X POST http://localhost:8000/v1/copilot/sessions/cs_abc123/messages \
  -H "x-vendor-id: v_acme" \
  -H "x-vendor-user-id: vu_admin" \
  -H "x-vendor-role: admin" \
  -H "Content-Type: application/json" \
  -d '{"content": "What is today revenue for badminton?"}'

# Response includes:
# {
#   "assistant_message": {
#     "content": {
#       "text": "Today's Badminton revenue is $440.00 (gross $450.00, refunds $10.00).",
#       "blocks": [
#         {"type": "kpi", "title": "Badminton Revenue", "value": "440.00", "currency": "USD"},
#         {"type": "table", "columns": ["game", "gross", "refunds", "net"], "rows": [...]}
#       ],
#       "tool_traces": [{"tool": "get_revenue", "args": {"game_slug": "badminton"}, "result": {...}}]
#     }
#   }
# }
```

### Via SSE Stream (for UI)

```bash
curl -N http://localhost:8000/v1/copilot/sessions/cs_abc123/messages:stream \
  -H "x-vendor-id: v_acme" \
  -H "x-vendor-user-id: vu_admin" \
  -H "x-vendor-role: admin" \
  -H "Content-Type: application/json" \
  -d '{"content": "List trial users of badminton"}'

# SSE Events:
# event: status
# data: {"phase": "routing"}
#
# event: status
# data: {"phase": "running"}
#
# event: result
# data: {"text": "Found 2 trial users...", "blocks": [{"type": "table", ...}], "user_message_id": "m_...", "assistant_message_id": "m_..."}
#
# event: done
# data: {"message_id": "m_...", "session_id": "cs_abc123"}
```

---

## Demo Flow 2: Propose → Approve → Execute (3 min)

**Scenario**: Vendor wants to extend Alice's badminton trial by 7 days.

### Step 1: Propose (LLM creates proposal card)

```bash
curl -X POST http://localhost:8000/v1/copilot/sessions/cs_abc123/messages \
  -H "x-vendor-id: v_acme" -H "x-vendor-user-id: vu_admin" -H "x-vendor-role: admin" \
  -H "Content-Type: application/json" \
  -d '{"content": "Extend free trial for u_alice on badminton by 7 days"}'

# Response includes proposal_card block:
# {
#   "type": "proposal_card",
#   "proposal_id": "ap_xyz789",
#   "action_type": "extend_trial",
#   "status": "pending",
#   "preview": {
#     "before": {"trial_ends_at": "2025-07-16T10:30:00"},
#     "after": {"trial_ends_at": "2025-07-23T10:30:00"}
#   },
#   "expires_at": "2025-07-12T11:15:00Z"
# }
```

### Step 2: List Pending Proposals

```bash
curl http://localhost:8000/v1/copilot/proposals?status=pending \
  -H "x-vendor-id: v_acme" -H "x-vendor-user-id: vu_admin" -H "x-vendor-role: admin"
```

### Step 3: Approve (human action — not LLM)

```bash
curl -X POST http://localhost:8000/v1/copilot/proposals/ap_xyz789/decide \
  -H "x-vendor-id: v_acme" -H "x-vendor-user-id: vu_admin" -H "x-vendor-role: admin" \
  -H "Content-Type: application/json" \
  -d '{"decision": "approve", "reason": "Customer requested extension"}'

# Response: {"status": "executed", "execution_result": {"ok": true, "message": "Trial extended for u_alice on badminton to 2025-07-23T10:30:00Z"}}
```

### Step 4: Verify Mutation

```bash
curl -X POST http://localhost:8000/v1/copilot/sessions/cs_abc123/messages \
  -H "x-vendor-id: v_acme" -H "x-vendor-user-id: vu_admin" -H "x-vendor-role: admin" \
  -H "Content-Type: application/json" \
  -d '{"content": "Show membership for u_alice on badminton"}'

# Response shows: trial_ends_at = 2025-07-23T10:30:00Z (extended by 7 days)
```

---

## Demo Flow 3: Safety Gates (1 min each)

### Gate 1: Role-Based Write Access

```bash
# Viewer tries to approve → 403 Forbidden
curl -X POST http://localhost:8000/v1/copilot/proposals/ap_xyz789/decide \
  -H "x-vendor-id: v_acme" -H "x-vendor-user-id: vu_viewer" -H "x-vendor-role: viewer" \
  -H "Content-Type: application/json" -d '{"decision": "approve"}'

# Response: 403 {"detail": "Role 'viewer' not permitted. Required: ['owner', 'admin', 'support']"}
```

### Gate 2: Cross-Vendor Isolation

```bash
# Beta vendor tries to see Acme's proposal → 404
curl http://localhost:8000/v1/copilot/proposals/ap_xyz789 \
  -H "x-vendor-id: v_beta" -H "x-vendor-user-id: vu_beta_admin" -H "x-vendor-role: admin"

# Response: 404 {"detail": "Proposal not found"}
```

### Gate 3: Reject Leaves Data Unchanged

```bash
# Create proposal
curl -X POST .../messages -d '{"content": "Suspend u_carol"}'
# Get proposal_id

# Reject
curl -X POST .../proposals/ap_xxx/decide -d '{"decision": "reject", "reason": "Wrong user"}'

# Verify u_carol still active
curl -X POST .../messages -d '{"content": "Show u_carol membership"}'
# → status: "active" (unchanged)
```

### Gate 4: Rate Limiting

```bash
# Rapid fire 35 requests → 429 Too Many Requests
for i in {1..35}; do curl -s -o /dev/null -w "%{http_code}\n" ...; done
# Response headers: X-RateLimit-Limit-Minute: 30, X-RateLimit-Remaining-Minute: 0
```

---

## Demo Flow 4: Audit Trail (30 sec)

```bash
curl http://localhost:8000/v1/copilot/audit \
  -H "x-vendor-id: v_acme" -H "x-vendor-user-id: vu_admin" -H "x-vendor-role: admin"

# Response:
# {
#   "events": [
#     {"event_type": "proposal.create", "entity_type": "action_proposal", "entity_id": "ap_xyz789", "metadata": {"action_type": "extend_trial"}},
#     {"event_type": "proposal.decide", "entity_type": "action_proposal", "entity_id": "ap_xyz789", "metadata": {"decision": "approve", "decided_by": "vu_admin"}},
#     {"event_type": "proposal.execute", "entity_type": "action_proposal", "entity_id": "ap_xyz789", "metadata": {"ok": true}},
#     {"event_type": "copilot.turn", "entity_type": "chat_session", "entity_id": "cs_abc123", "metadata": {"tools": ["get_revenue"]}}
#   ]
# }
```

---

## Quick Reference: Test Users & Data

| Vendor | User ID | Role | Email |
|--------|---------|------|-------|
| Acme Sports | `vu_admin` | admin | admin@acme.example |
| Acme Sports | `vu_support` | support | support@acme.example |
| Acme Sports | `vu_viewer` | viewer | viewer@acme.example |
| Beta Games | `vu_beta_admin` | admin | admin@beta.example |

| End User | Game | Plan | Trial Ends |
|----------|------|------|------------|
| `u_alice` | badminton | trial | +4 days (extend demo) |
| `u_carol` | badminton | trial | +13 days |
| `u_bob` | cricket | pro | — |
| `u_dave` | cricket | basic | expired |
| `u_beta_eve` | tennis | trial | +7 days |

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `GEMINI_API_KEY not set` | `export GEMINI_API_KEY=...` (tests use mock, not required) |
| `429 Too Many Requests` | Wait 60s or use different `x-vendor-user-id` |
| `Proposal not found` | Check vendor_id matches proposal's vendor |
| `Role 'viewer' not permitted` | Use `x-vendor-role: admin` for approve/reject |
| SSE stream hangs | Ensure `-N` flag (no buffer) in curl |

---

## Architecture Diagram (Mermaid)

```mermaid
graph TB
    subgraph Portal[Vendor Portal UI]
        Chat[Chat Panel<br/>SSE Stream]
        Approve[Approval Cards<br/>Approve/Reject]
        Tables[Result Tables<br/>Tool Blocks]
    end

    subgraph API[FastAPI App]
        Auth[Auth Middleware<br/>Headers → VendorContext]
        Rate[Rate Limit<br/>30/min, 200/hr]
        Routes[Routes<br/>/v1/copilot/*]
        ChatSvc[Chat Service<br/>Sessions + Messages]
        ApprovalSvc[Approval Service<br/>Propose → Decide → Execute]
        AuditSvc[Audit Service<br/>Immutable Events]
    end

    subgraph Agent[CrewAI Runtime]
        Router[Intent Router<br/>read|write|clarify|refuse]
        Analyst[Data Analyst<br/>7 Read Tools]
        Planner[Action Planner<br/>4 Propose Tools]
        Composer[Response Composer<br/>Text + Blocks]
        LLM[(Gemini 3.1 Flash-Lite)]
    end

    subgraph Data[SQLite + SQLAlchemy]
        Users[app_users]
        Games[games]
        Memberships[memberships]
        Revenue[revenue_daily]
        Sessions[chat_sessions]
        Messages[chat_messages]
        Proposals[action_proposals]
        Audit[audit_events]
    end

    Portal -->|HTTPS + Headers| API
    API --> Auth
    Auth --> Rate
    Rate --> Routes
    Routes --> ChatSvc
    Routes --> ApprovalSvc
    ChatSvc --> Agent
    ApprovalSvc --> Data
    ChatSvc --> Data
    AuditSvc --> Data
    Agent --> LLM
    Router -->|read| Analyst
    Router -->|write| Planner
    Analyst --> Composer
    Planner --> Composer
    Composer -->|SSE| Chat
```

---

## Running Tests

```bash
# All tests (85)
python -m pytest tests/ -v

# Specific phases
python -m pytest tests/test_phase0.py -v
python -m pytest tests/test_phase1_chat.py tests/test_phase1_tools.py -v
python -m pytest tests/test_phase2_approvals.py -v
python -m pytest tests/test_phase3_golden_eval.py -v
```