"""CrewAI single-agent copilot for Phase 1/2: read + write (proposals)."""

from __future__ import annotations

import logging
from typing import Any

from app.agent.llm import get_llm
from app.agent.tools.read_tools import build_read_tools
from app.agent.tools.registry import ToolRunContext
from app.agent.tools.write_tools import build_write_tools
from app.domain.schemas import VendorContext

logger = logging.getLogger(__name__)

COPILOT_BACKSTORY = """\
You are the Vendor Portal Copilot for a single vendor in a multi-tenant sports/
gaming platform. You answer factual questions about this vendor's users, games,
memberships, trials, and revenue using READ tools only.

For write/mutation requests (extend trial, change plan, suspend user, update dates):
- You do NOT execute changes directly.
- You CREATE A PROPOSAL using the appropriate propose_* tool.
- The proposal includes a clear BEFORE/AFTER preview.
- The vendor must APPROVE the proposal via the portal UI (not you) before execution.
- Explain clearly: "This creates a pending proposal. No data is changed until you approve it."

Hard rules:
- You serve ONLY the authenticated vendor. Never claim data for other vendors.
- Prefer tools over guessing. If data is missing, say so clearly.
- Do not invent user ids, revenue numbers, or membership dates.
- For "today" or relative dates, rely on tools which use the vendor timezone.
- Refuse out-of-scope asks (other vendors, secrets, bulk deletes, raw SQL).
- If the user asks to change data and you don't have a matching propose_* tool, say it's not supported yet.
"""

TOOL_USE_GUIDANCE = """\
When the user asks a question:
1. Use READ tools (list_trial_users, get_revenue, search_users, get_user, get_membership, list_games, get_vendor_summary) for factual queries.
2. If the user wants to CHANGE data, use the matching PROPOSE tool:
   - "extend trial" / "add days to trial" → propose_extend_trial
   - "change plan" / "upgrade/downgrade" → propose_change_plan
   - "suspend user" / "ban user" → propose_suspend_user
   - "update membership dates" / "set start/end" → propose_update_membership_dates
3. After calling a propose_* tool, you will receive a proposal_id, preview, and expiry.
   Explain the preview to the user and state clearly: "This is PENDING approval. No data has been changed."
4. Do not claim success until the proposal status is "executed" (which happens after vendor approval, outside this chat).
"""


async def run_copilot_turn(
    *,
    user_message: str,
    ctx: VendorContext,
    history: list[dict[str, str]] | None = None,
    session_id: str | None = None,
    message_id: str | None = None,
    db=None,
) -> dict[str, Any]:
    """Run one agent turn and return text + UI blocks + tool traces."""
    run_ctx = ToolRunContext()
    read_tools = build_read_tools(ctx, run_ctx, db=db)
    write_tools = build_write_tools(ctx, run_ctx, session_id=session_id, message_id=message_id, db=db)
    all_tools = read_tools + write_tools
    llm = get_llm()

    from crewai import Agent, Crew, Process, Task

    history_text = _format_history(history or [])

    agent = Agent(
        role="Vendor Portal Copilot",
        goal=(
            f"Answer portal questions accurately for vendor '{ctx.vendor_name}' "
            f"({ctx.vendor_id}) using tools. Timezone: {ctx.timezone}. "
            f"For write requests, create proposals — never mutate directly."
        ),
        backstory=COPILOT_BACKSTORY + "\n\n" + TOOL_USE_GUIDANCE,
        llm=llm,
        tools=all_tools,
        verbose=False,
        allow_delegation=False,
        max_iter=6,
    )

    task = Task(
        description=(
            f"Vendor context: vendor_id={ctx.vendor_id}, name={ctx.vendor_name}, "
            f"timezone={ctx.timezone}, role={ctx.role}.\n\n"
            f"Recent conversation:\n{history_text or '(none)'}\n\n"
            f"User message:\n{user_message}\n\n"
            "Use tools as needed, then give a clear, concise answer. "
            "If you used a propose_* tool, explain the preview and state that approval is required."
        ),
        expected_output=(
            "A natural-language answer grounded in tool results. "
            "If tools returned tables, summarize key rows. "
            "If a propose_* tool was called, include the proposal_id and preview summary, "
            "and state that approval is required before execution."
        ),
        agent=agent,
    )

    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
        memory=False,
    )

    logger.info(
        "copilot_turn_start vendor_id=%s session_role=%s write_tools=%d",
        ctx.vendor_id,
        ctx.role,
        len(write_tools),
    )
    # Use kickoff_async since we're in an async context
    result = await crew.kickoff_async()
    text = _result_to_text(result)

    return {
        "text": text,
        "blocks": list(run_ctx.blocks),
        "tool_traces": list(run_ctx.traces),
        "raw": result,
    }


def _format_history(history: list[dict[str, str]], *, max_turns: int = 6) -> str:
    if not history:
        return ""
    lines: list[str] = []
    for turn in history[-max_turns:]:
        role = turn.get("role", "user")
        content = (turn.get("content") or "").strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _result_to_text(result: Any) -> str:
    if result is None:
        return "I could not produce an answer."
    if isinstance(result, str):
        return result.strip() or "I could not produce an answer."
    # CrewAI CrewOutput
    for attr in ("raw", "output", "result"):
        if hasattr(result, attr):
            val = getattr(result, attr)
            if isinstance(val, str) and val.strip():
                return val.strip()
    text = str(result).strip()
    return text or "I could not produce an answer."