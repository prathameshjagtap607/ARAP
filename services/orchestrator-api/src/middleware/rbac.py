from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RBACMiddleware(BaseHTTPMiddleware):
    """Stub — role extraction and enforcement added in auth session."""

    async def dispatch(self, request: Request, call_next) -> Response:
        return await call_next(request)
