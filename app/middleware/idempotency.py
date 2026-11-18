"""Idempotency middleware: validates that Idempotency-Key is present on mutation routes."""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

_MUTATION_METHODS = {"POST", "PUT", "PATCH"}
_REQUIRED_PATHS_PREFIX = "/api/v1/broll/jobs"


class IdempotencyKeyMiddleware(BaseHTTPMiddleware):
    """
    Enforces that POST /api/v1/broll/jobs includes an Idempotency-Key header.
    The actual duplicate-detection logic lives in the router (needs DB access).
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if (
            request.method in _MUTATION_METHODS
            and request.url.path.startswith(_REQUIRED_PATHS_PREFIX)
        ):
            if not request.headers.get("Idempotency-Key"):
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": {
                            "code": "MISSING_INPUT",
                            "message": "The 'Idempotency-Key' header is required for this request.",
                            "retryable": False,
                            "details": {"header": "Idempotency-Key"},
                        }
                    },
                )
        return await call_next(request)
