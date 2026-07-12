"""Gemini LLM wiring for CrewAI agents.

Phase 1 uses CrewAI's native ``LLM`` (litellm-backed), which is what the
installed CrewAI version accepts for the ``Agent(llm=...)`` argument. The
model id follows the ``gemini/<model-id>`` convention so litellm routes to
Google's Gemini API using ``GEMINI_API_KEY``.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.config import Settings, get_settings


@lru_cache
def get_llm(settings: Settings | None = None) -> Any:
    """Return a CrewAI ``LLM`` bound to Gemini Flash-Lite.

    Cached per process. Call ``get_llm.cache_clear()`` in tests if settings change.
    """
    settings = settings or get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured. Set it in the environment or .env file."
        )

    from crewai import LLM

    return LLM(
        model=f"gemini/{settings.gemini_model}",
        api_key=settings.gemini_api_key,
        temperature=settings.gemini_temperature,
        max_tokens=settings.gemini_max_output_tokens,
    )
