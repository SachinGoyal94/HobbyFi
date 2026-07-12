"""Structured logging and observability utilities.

Provides correlation IDs, structured JSON logs, and per-phase latency tracking.
"""

from __future__ import annotations

import contextvars
import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


# ── Correlation ID management ────────────────────────────────────────────────

_correlation_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)
_request_start_time: contextvars.ContextVar[float | None] = contextvars.ContextVar(
    "request_start_time", default=None
)


def get_correlation_id() -> str:
    """Get or generate the correlation ID for the current context."""
    cid = _correlation_id.get()
    if cid is None:
        cid = str(uuid.uuid4())[:8]
        _correlation_id.set(cid)
    return cid


def set_correlation_id(cid: str) -> None:
    """Set the correlation ID for the current context."""
    _correlation_id.set(cid)


def clear_correlation_id() -> None:
    """Clear the correlation ID from the current context."""
    _correlation_id.set(None)


def get_request_start_time() -> float:
    """Get the request start time for the current context."""
    start = _request_start_time.get()
    if start is None:
        start = time.time()
        _request_start_time.set(start)
    return start


def set_request_start_time(start: float) -> None:
    """Set the request start time for the current context."""
    _request_start_time.set(start)


# ── Structured logging ───────────────────────────────────────────────────────

class StructuredFormatter(logging.Formatter):
    """JSON formatter that includes correlation ID and timing."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": get_correlation_id(),
        }

        # Add extra fields from record
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "name", "pathname", "process", "processName",
                "relativeCreated", "thread", "threadName", "exc_info",
                "exc_text", "stack_info"
            }:
                log_entry[key] = value

        # Add elapsed time if available
        start = _request_start_time.get()
        if start is not None:
            log_entry["elapsed_ms"] = round((time.time() - start) * 1000, 2)

        # Handle exceptions
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


def setup_structured_logging(level: str = "INFO") -> None:
    """Configure structured JSON logging for the application."""
    # Clear existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    # Set level
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Create handler with structured formatter
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredFormatter())
    root_logger.addHandler(handler)

    # Reduce noise from noisy libraries
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


# ── Per-phase latency tracking ──────────────────────────────────────────────

class PhaseTimer:
    """Context manager for timing a phase of request processing."""

    def __init__(self, phase_name: str, logger: logging.Logger | None = None, **extra):
        self.phase_name = phase_name
        self.logger = logger or logging.getLogger("app.phases")
        self.extra = extra
        self.start_time = 0.0

    def __enter__(self) -> PhaseTimer:
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        elapsed = (time.perf_counter() - self.start_time) * 1000
        self.logger.info(
            f"Phase completed: {self.phase_name}",
            extra={
                "phase": self.phase_name,
                "duration_ms": round(elapsed, 2),
                **self.extra,
            },
        )


def phase_timer(phase_name: str, logger: logging.Logger | None = None, **extra) -> PhaseTimer:
    """Create a phase timer context manager."""
    return PhaseTimer(phase_name, logger, **extra)


# ── HTTP Middleware for correlation IDs and request timing ──────────────────

class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to add correlation IDs and log request/response info."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Generate or extract correlation ID
        correlation_id = request.headers.get("x-correlation-id") or str(uuid.uuid4())[:8]
        set_correlation_id(correlation_id)

        # Record start time
        start_time = time.time()
        set_request_start_time(start_time)

        # Log request
        logger = logging.getLogger("app.http")
        logger.info(
            "Request started",
            extra={
                "method": request.method,
                "path": request.url.path,
                "query": str(request.url.query) if request.url.query else None,
                "client": request.client.host if request.client else None,
            },
        )

        # Process request
        try:
            response = await call_next(request)
        except Exception as exc:
            elapsed = (time.time() - start_time) * 1000
            logger.exception(
                "Request failed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(elapsed, 2),
                    "error": str(exc),
                },
            )
            raise

        # Log response
        elapsed = (time.time() - start_time) * 1000
        logger.info(
            "Request completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(elapsed, 2),
            },
        )

        # Add correlation ID to response headers
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Response-Time-MS"] = str(round(elapsed, 2))

        # Clean up context
        clear_correlation_id()

        return response


# ── Helper functions for structured logging ──────────────────────────────────

def log_phase_start(phase: str, logger: logging.Logger | None = None, **extra) -> float:
    """Log the start of a phase and return the start time."""
    logger = logger or logging.getLogger("app.phases")
    start = time.perf_counter()
    logger.info(
        f"Phase started: {phase}",
        extra={"phase": phase, "event": "start", **extra},
    )
    return start


def log_phase_end(
    phase: str,
    start_time: float,
    logger: logging.Logger | None = None,
    success: bool = True,
    **extra,
) -> float:
    """Log the end of a phase and return the elapsed time in ms."""
    logger = logger or logging.getLogger("app.phases")
    elapsed = (time.perf_counter() - start_time) * 1000
    logger.info(
        f"Phase {'completed' if success else 'failed'}: {phase}",
        extra={
            "phase": phase,
            "duration_ms": round(elapsed, 2),
            "success": success,
            "event": "end",
            **extra,
        },
    )
    return elapsed


# ── Agent phase timing helpers ──────────────────────────────────────────────

def log_agent_phase(phase: str, vendor_id: str, **extra) -> float:
    """Log the start of an agent processing phase."""
    return log_phase_start(f"agent.{phase}", logging.getLogger("app.agent"), vendor_id=vendor_id, **extra)


def log_agent_phase_end(
    phase: str,
    vendor_id: str,
    start_time: float,
    success: bool = True,
    **extra,
) -> float:
    """Log the end of an agent processing phase."""
    return log_phase_end(f"agent.{phase}", start_time, logging.getLogger("app.agent"), success=success, vendor_id=vendor_id, **extra)