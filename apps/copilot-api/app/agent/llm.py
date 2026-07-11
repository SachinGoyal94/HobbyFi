"""Gemini LLM wiring via LangChain for CrewAI agents."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.config import Settings, get_settings


@lru_cache
def get_llm(settings: Settings | None = None) -> Any:
    """Return a LangChain ChatGoogleGenerativeAI bound to Gemini Flash-Lite.

    Cached per process. Call ``get_llm.cache_clear()`` in tests if settings change.
    """
    settings = settings or get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured. Set it in the environment or .env file."
        )

    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
        temperature=settings.gemini_temperature,
        max_output_tokens=settings.gemini_max_output_tokens,
    )
