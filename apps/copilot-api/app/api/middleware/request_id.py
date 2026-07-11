"""Middleware that attaches a unique request-id header to every response."""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

HEADER_REQUEST_ID = "x-request-id"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Ensure every response carries an x-request-id header.

    If the client sends one we echo it; otherwise we generate a new UUID.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get(HEADER_REQUEST_ID) or str(uuid.uuid4())
        response = await call_next(request)
        response.headers[HEADER_REQUEST_ID] = request_id
        return response