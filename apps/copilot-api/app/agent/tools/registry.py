"""Shared run context for tool traces and UI blocks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolRunContext:
    """Collected during a single agent turn for audit + UI blocks."""

    traces: list[dict[str, Any]] = field(default_factory=list)
    blocks: list[dict[str, Any]] = field(default_factory=list)

    def record(
        self,
        tool: str,
        args: dict[str, Any],
        result: Any,
        *,
        block: dict[str, Any] | None = None,
    ) -> None:
        self.traces.append({"tool": tool, "args": args, "result": result})
        if block is not None:
            self.blocks.append(block)
