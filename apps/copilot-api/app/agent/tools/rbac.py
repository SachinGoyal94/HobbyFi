"""Role-Based Access Control for agent tools.

Defines which roles can invoke which tools. Enforced at tool execution time
via the VendorContext.role field. The LLM cannot bypass this — it's server-side.
"""

from __future__ import annotations

from app.domain.schemas import Role

# ─── Tool permission map ──────────────────────────────────────────────────────
# tool_name -> set of roles allowed to call it
# Roles: owner | admin | support | viewer

READ_TOOL_PERMISSIONS: dict[str, set[Role]] = {
    "list_games": {"owner", "admin", "support", "viewer"},
    "list_trial_users": {"owner", "admin", "support", "viewer"},
    "get_revenue": {"owner", "admin", "support", "viewer"},
    "search_users": {"owner", "admin", "support", "viewer"},
    "get_user": {"owner", "admin", "support", "viewer"},
    "get_membership": {"owner", "admin", "support", "viewer"},
    "get_vendor_summary": {"owner", "admin", "support", "viewer"},
}

WRITE_TOOL_PERMISSIONS: dict[str, set[Role]] = {
    "propose_extend_trial": {"owner", "admin"},          # support cannot propose trial extensions
    "propose_update_membership_dates": {"owner", "admin"},
    "propose_change_plan": {"owner", "admin"},           # support cannot change plans
    "propose_suspend_user": {"owner", "admin"},          # support cannot suspend
}

ALL_TOOL_PERMISSIONS: dict[str, set[Role]] = {
    **READ_TOOL_PERMISSIONS,
    **WRITE_TOOL_PERMISSIONS,
}


def check_tool_permission(tool_name: str, role: Role) -> bool:
    """Return True if the role is allowed to call this tool."""
    allowed = ALL_TOOL_PERMISSIONS.get(tool_name)
    if allowed is None:
        # Unknown tool — deny by default
        return False
    return role in allowed


def get_allowed_tools(role: Role) -> list[str]:
    """Return list of tool names this role can call."""
    return [name for name, roles in ALL_TOOL_PERMISSIONS.items() if role in roles]