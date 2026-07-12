"""Rate limiting for copilot API endpoints."""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.domain.schemas import VendorContext
from app.deps import get_vendor_context


@dataclass
class RateLimitConfig:
    requests_per_minute: int = 30
    requests_per_hour: int = 200
    burst_allowance: int = 5  # extra requests allowed in short burst


# In-memory store (replace with Redis in production)
# Key: vendor_user_id, Value: list of timestamps
_request_log: dict[str, list[float]] = defaultdict(list)


def _clean_old_entries(user_id: str, window_seconds: int) -> None:
    """Remove timestamps older than window_seconds."""
    cutoff = time.time() - window_seconds
    _request_log[user_id] = [ts for ts in _request_log[user_id] if ts > cutoff]


def check_rate_limit(
    vendor_context: VendorContext,
    config: RateLimitConfig = RateLimitConfig(),
) -> tuple[bool, dict[str, int]]:
    """
    Check if request is within rate limits.
    Returns (allowed, headers_dict).
    """
    user_id = vendor_context.vendor_user_id
    now = time.time()

    # Clean old entries
    _clean_old_entries(user_id, 3600)  # 1 hour window

    # Count requests in windows
    minute_ago = now - 60
    hour_ago = now - 3600

    minute_count = sum(1 for ts in _request_log[user_id] if ts > minute_ago)
    hour_count = sum(1 for ts in _request_log[user_id] if ts > hour_ago)

    # Check limits
    if minute_count >= config.requests_per_minute + config.burst_allowance:
        return False, {
            "X-RateLimit-Limit-Minute": config.requests_per_minute,
            "X-RateLimit-Remaining-Minute": 0,
            "X-RateLimit-Reset-Minute": int(now + 60),
            "X-RateLimit-Limit-Hour": config.requests_per_hour,
            "X-RateLimit-Remaining-Hour": max(0, config.requests_per_hour - hour_count),
            "X-RateLimit-Reset-Hour": int(now + 3600),
        }

    if hour_count >= config.requests_per_hour:
        return False, {
            "X-RateLimit-Limit-Minute": config.requests_per_minute,
            "X-RateLimit-Remaining-Minute": max(0, config.requests_per_minute - minute_count),
            "X-RateLimit-Reset-Minute": int(now + 60),
            "X-RateLimit-Limit-Hour": config.requests_per_hour,
            "X-RateLimit-Remaining-Hour": 0,
            "X-RateLimit-Reset-Hour": int(now + 3600),
        }

    # Record this request
    _request_log[user_id].append(now)

    return True, {
        "X-RateLimit-Limit-Minute": config.requests_per_minute,
        "X-RateLimit-Remaining-Minute": max(0, config.requests_per_minute - minute_count - 1),
        "X-RateLimit-Reset-Minute": int(now + 60),
        "X-RateLimit-Limit-Hour": config.requests_per_hour,
        "X-RateLimit-Remaining-Hour": max(0, config.requests_per_hour - hour_count - 1),
        "X-RateLimit-Reset-Hour": int(now + 3600),
    }


async def rate_limit_dependency(
    request: Request,
    vendor_context: VendorContext = Depends(get_vendor_context),
) -> dict[str, int]:
    """
    FastAPI dependency that enforces rate limits.
    Adds rate limit headers to response.
    """
    # vendor_context is injected by get_vendor_context which sets request.state.vendor_context
    ctx = vendor_context
    if not ctx:
        # No auth context - skip rate limiting (auth will fail anyway)
        return {}

    allowed, headers = check_rate_limit(ctx)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please slow down.",
            headers=headers,
        )

    # Store headers in request state for response middleware
    request.state.rate_limit_headers = headers
    return headers


async def add_rate_limit_headers(request: Request, call_next):
    """Middleware to add rate limit headers to all responses."""
    response = await call_next(request)
    headers = getattr(request.state, "rate_limit_headers", {})
    for key, value in headers.items():
        response.headers[key] = str(value)
    return response


# For testing: reset rate limit state
def reset_rate_limits() -> None:
    """Clear all rate limit tracking (test helper)."""
    _request_log.clear()