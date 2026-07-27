from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Stub — token-bucket rate limiting added post-Phase 0."""

    async def dispatch(self, request: Request, call_next) -> Response:
        return await call_next(request)
