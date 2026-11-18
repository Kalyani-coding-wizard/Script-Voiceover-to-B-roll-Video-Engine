"""X-Correlation-Id middleware: injects / propagates the header on every request."""
from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

HEADER = "X-Correlation-Id"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    - If the incoming request already carries an X-Correlation-Id, keep it.
    - Otherwise generate a new UUID4.
    - Attach the value to request.state.correlation_id for use in logs.
    - Always echo it back in the response headers.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = request.headers.get(HEADER) or str(uuid.uuid4())
        request.state.correlation_id = correlation_id

        response: Response = await call_next(request)
        response.headers[HEADER] = correlation_id
        return response
