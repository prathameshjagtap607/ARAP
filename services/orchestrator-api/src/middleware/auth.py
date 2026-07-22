import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """Stub — auth logic added in auth session."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if not request.headers.get("Authorization"):
            logger.debug("Request without Authorization header: %s", request.url.path)
        return await call_next(request)
