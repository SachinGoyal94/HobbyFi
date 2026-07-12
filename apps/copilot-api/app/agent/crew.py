"""CrewAI multi-agent copilot (Phase 3): Intent Router → Specialist → Composer."""

from __future__ import annotations

import logging
from typing import Any, Literal

from app.agent.llm import get_llm
from app.agent.tools.read_tools import build_read_tools
from app.agent.tools.registry import ToolRunContext
from app.agent.tools.write_tools import build_write_tools
from app.domain.schemas import VendorContext

logger = logging.getLogger(__name__)

# ── System prompts ────────────────────────────────────────────────────────────

ROUTER_SYSTEM = """\
You are the Intent Router for a vendor portal copilot.

Classify the user's message into exactly ONE of these intents:
- "read"          : factual question about users, games, trials, revenue, memberships
- "write_propose" : request to change data (extend trial, change plan, suspend user, update dates)
- "clarify"       : ambiguous, missing details, or follow-up that needs disambiguation
- "refuse"        : out of scope (other vendors, secrets, bulk ops, raw SQL, cross-tenant)

Return ONLY a JSON object: {"intent": "<one of the four>", "reason": "<brief>"}
"""

DATA_ANALYST_SYSTEM = """\
You are the Data Analyst for a single vendor in a multi-tenant sports/gaming platform.

You have READ-ONLY access via these tools:
- list_games
- list_trial_users
- get_revenue
- search_users
- get_user
- get_membership
- get_vendor_summary

Rules:
- Answer ONLY the authenticated vendor's questions (vendor_id from context).
- Use tools for ALL factual queries — never guess or invent numbers.
- For "today" / relative dates, rely on tools (they use vendor timezone).
- If data is missing, say so clearly.
- Output concise, grounded answers with key figures.
- Do NOT create proposals or mutate data.
"""

ACTION_PLANNER_SYSTEM = """\
You are the Action Planner for a single vendor in a multi-tenant sports/gaming platform.

You create PROPOSALS for write requests using these tools:
- propose_extend_trial(user_id, game_slug, extra_days)
- propose_change_plan(user_id, game_slug, new_plan)
- propose_suspend_user(user_id, reason)
- propose_update_membership_dates(user_id, game_slug, starts_at?, ends_at?)

Rules:
- You do NOT execute changes directly. Each tool creates a pending ActionProposal.
- The proposal includes a BEFORE/AFTER preview and expires (typically 15 min).
- The vendor must APPROVE via the portal UI (not you) before execution.
- Always explain the preview and state: "This is PENDING approval. No data has been changed."
- If the user lacks details (which user, which game, how many days), ask for clarification — do NOT guess.
- Only one propose_* tool per turn. If multiple changes needed, handle sequentially.
"""

COMPOSER_SYSTEM = """\
You are the Response Composer. Your job is to produce the final user-facing answer.

Input: tool results from Data Analyst or Action Planner (provided in task description).
Output: A single JSON object with keys:
  - "text": natural-language answer (concise, grounded in tool results)
  - "blocks": array of UI blocks (table, kpi, proposal_card) — pass through from tool results
  - "tool_traces": array of tool traces — pass through from tool results

Rules:
- Summarize key numbers from tables/KPIs into the text.
- If a proposal was created, include its proposal_id, preview, expiry, and the required approval notice.
- Do not add information not present in tool results.
- Keep text concise and vendor-friendly.
"""


# ── Agent builders ────────────────────────────────────────────────────────────

def _build_router_agent():
    from crewai import Agent
    llm = get_llm()
    return Agent(
        role="Intent Router",
        goal="Classify user message into read | write_propose | clarify | refuse",
        backstory=ROUTER_SYSTEM,
        llm=llm,
        tools=[],
        verbose=False,
        allow_delegation=False,
        max_iter=1,
    )


def _build_data_analyst_agent(ctx: VendorContext, run_ctx: ToolRunContext, db=None):
    from crewai import Agent
    llm = get_llm()
    tools = build_read_tools(ctx, run_ctx, db=db)
    return Agent(
        role="Data Analyst",
        goal=(
            f"Answer factual questions for vendor '{ctx.vendor_name}' ({ctx.vendor_id}) "
            f"using read tools. Timezone: {ctx.timezone}."
        ),
        backstory=DATA_ANALYST_SYSTEM,
        llm=llm,
        tools=tools,
        verbose=False,
        allow_delegation=False,
        max_iter=5,
    )


def _build_action_planner_agent(ctx: VendorContext, run_ctx: ToolRunContext, db=None, session_id=None, message_id=None):
    from crewai import Agent
    llm = get_llm()
    tools = build_write_tools(ctx, run_ctx, session_id=session_id, message_id=message_id, db=db)
    return Agent(
        role="Action Planner",
        goal=(
            f"Create safe, auditable proposals for vendor '{ctx.vendor_name}' "
            f"({ctx.vendor_id}) using propose_* tools."
        ),
        backstory=ACTION_PLANNER_SYSTEM,
        llm=llm,
        tools=tools,
        verbose=False,
        allow_delegation=False,
        max_iter=3,
    )


def _build_composer_agent():
    from crewai import Agent
    llm = get_llm()
    return Agent(
        role="Response Composer",
        goal="Produce final user-facing answer from tool results.",
        backstory=COMPOSER_SYSTEM,
        llm=llm,
        tools=[],
        verbose=False,
        allow_delegation=False,
        max_iter=1,
    )


# ── Pipeline ────────────────────────────────────────────────────────────────

async def run_copilot_turn(
    *,
    user_message: str,
    ctx: VendorContext,
    history: list[dict[str, str]] | None = None,
    session_id: str | None = None,
    message_id: str | None = None,
    db=None,
) -> dict[str, Any]:
    """Run the 4-agent sequential pipeline: Router → Specialist → Composer."""
    run_ctx = ToolRunContext()

    # 1) Intent Router
    router_agent = _build_router_agent()
    from crewai import Crew, Process, Task

    router_task = Task(
        description=f"Classify this user message:\n\n{user_message}",
        expected_output='JSON: {"intent": "read|write_propose|clarify|refuse", "reason": "..."}',
        agent=router_agent,
    )
    router_crew = Crew(agents=[router_agent], tasks=[router_task], process=Process.sequential, verbose=False, memory=False)
    router_result = await router_crew.kickoff_async()

    import json
    try:
        router_out = json.loads(_extract_text(router_result))
        intent = router_out.get("intent", "clarify")
    except Exception:
        intent = "clarify"

    logger.info("intent_classified vendor_id=%s intent=%s", ctx.vendor_id, intent)

    # 2) Specialist
    specialist_output = {}
    blocks = []
    traces = []

    if intent == "read":
        analyst = _build_data_analyst_agent(ctx, run_ctx, db=db)
        analyst_task = Task(
            description=(
                f"Vendor context: vendor_id={ctx.vendor_id}, name={ctx.vendor_name}, "
                f"timezone={ctx.timezone}, role={ctx.role}.\n\n"
                f"User message:\n{user_message}\n\n"
                "Use read tools to answer. Return concise answer with data."
            ),
            expected_output="Answer grounded in tool results. Include key figures.",
            agent=analyst,
        )
        analyst_crew = Crew(agents=[analyst], tasks=[analyst_task], process=Process.sequential, verbose=False, memory=False)
        analyst_result = await analyst_crew.kickoff_async()
        specialist_output["text"] = _extract_text(analyst_result)

    elif intent == "write_propose":
        planner = _build_action_planner_agent(ctx, run_ctx, db=db, session_id=session_id, message_id=message_id)
        planner_task = Task(
            description=(
                f"Vendor context: vendor_id={ctx.vendor_id}, name={ctx.vendor_name}, "
                f"timezone={ctx.timezone}, role={ctx.role}.\n\n"
                f"User message:\n{user_message}\n\n"
                "Create the appropriate proposal using propose_* tool. "
                "If details missing (user_id, game_slug, days, plan), ask for clarification."
            ),
            expected_output="Proposal created with preview. State clearly that approval is required.",
            agent=planner,
        )
        planner_crew = Crew(agents=[planner], tasks=[planner_task], process=Process.sequential, verbose=False, memory=False)
        planner_result = await planner_crew.kickoff_async()
        specialist_output["text"] = _extract_text(planner_result)

    elif intent == "clarify":
        specialist_output["text"] = "I need a bit more information to help. Could you clarify which user, game, or what specific change you'd like?"
    else:  # refuse
        specialist_output["text"] = "I can't help with that. I only answer questions and create proposals for your vendor's data."

    # Collect tool outputs from run_ctx
    blocks = list(run_ctx.blocks)
    traces = list(run_ctx.traces)

    # 3) Composer
    composer = _build_composer_agent()
    composer_task = Task(
        description=(
            f"Original user message:\n{user_message}\n\n"
            f"Specialist output:\n{specialist_output.get('text', '')}\n\n"
            f"Tool blocks:\n{json.dumps(blocks, default=str)}\n\n"
            f"Tool traces:\n{json.dumps(traces, default=str)}"
        ),
        expected_output=(
            'JSON: {"text": "...", "blocks": [...], "tool_traces": [...]}'
        ),
        agent=composer,
    )
    composer_crew = Crew(agents=[composer], tasks=[composer_task], process=Process.sequential, verbose=False, memory=False)
    composer_result = await composer_crew.kickoff_async()

    # Parse composer output
    try:
        final = json.loads(_extract_text(composer_result))
        text = final.get("text", specialist_output.get("text", ""))
        final_blocks = final.get("blocks", blocks)
        final_traces = final.get("tool_traces", traces)
    except Exception:
        text = specialist_output.get("text", _extract_text(composer_result))
        final_blocks = blocks
        final_traces = traces

    return {
        "text": text,
        "blocks": final_blocks,
        "tool_traces": final_traces,
        "raw": {"router": router_result, "specialist": specialist_output, "composer": composer_result},
    }


def _extract_text(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result.strip()
    for attr in ("raw", "output", "result"):
        if hasattr(result, attr):
            val = getattr(result, attr)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return str(result).strip()