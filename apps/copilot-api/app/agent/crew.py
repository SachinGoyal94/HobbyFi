"""CrewAI single-agent copilot for Phase 1 read Q&A."""

from __future__ import annotations

import logging
from typing import Any

from app.agent.llm import get_llm
from app.agent.tools.read_tools import build_read_tools
from app.agent.tools.registry import ToolRunContext
from app.domain.schemas import VendorContext

logger = logging.getLogger(__name__)

COPILOT_BACKSTORY = """\
You are the Vendor Portal Copilot for a single vendor in a multi-tenant sports/
gaming platform. You answer factual questions about this vendor's users, games,
memberships, trials, and revenue using tools only.

Hard rules:
- You serve ONLY the authenticated vendor. Never claim data for other vendors.
- Prefer tools over guessing. If data is missing, say so clearly.
- Do not invent user ids, revenue numbers, or membership dates.
- Do not perform or claim any write/mutation. Phase 1 is read-only.
  If the user asks to change data (extend trial, suspend user, change plan),
  explain that write actions require approval and are not available yet.
- Refuse out-of-scope asks (other vendors, secrets, bulk deletes, raw SQL).
- When presenting numbers, use the tool results (cents may include dollar fields).
- For "today" or relative dates, rely on tools which use the vendor timezone.
"""


def run_copilot_turn(
    *,
    user_message: str,
    ctx: VendorContext,
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Run one agent turn and return text + UI blocks + tool traces.

    Returns:
        {
          "text": str,
          "blocks": list[dict],
          "tool_traces": list[dict],
          "raw": Any,
        }
    """
    run_ctx = ToolRunContext()
    tools = build_read_tools(ctx, run_ctx)
    llm = get_llm()

    from crewai import Agent, Crew, Process, Task

    history_text = _format_history(history or [])
    agent = Agent(
        role="Vendor Portal Copilot",
        goal=(
            f"Answer portal questions accurately for vendor '{ctx.vendor_name}' "
            f"({ctx.vendor_id}) using read tools. Timezone: {ctx.timezone}."
        ),
        backstory=COPILOT_BACKSTORY,
        llm=llm,
        tools=tools,
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
            "Use tools as needed, then give a clear, concise answer for the "
            "vendor user. Do not invent facts."
        ),
        expected_output=(
            "A natural-language answer grounded in tool results. "
            "If tools returned tables of data, summarize the key rows. "
            "If nothing was found, say so."
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
        "copilot_turn_start vendor_id=%s session_role=%s",
        ctx.vendor_id,
        ctx.role,
    )
    result = crew.kickoff()
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
