import logging
import uuid

import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.modules.auth.dependencies import TokenClaims
from src.modules.auth.token import decode_access_token

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request.state.claims = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                payload = decode_access_token(token)
                request.state.claims = TokenClaims(
                    sub=payload["sub"],
                    role=payload["role"],
                    org_id=uuid.UUID(payload["org_id"]),
                    type=payload.get("type", "access"),
                    assessment_session_id=(
                        uuid.UUID(payload["assessment_session_id"])
                        if "assessment_session_id" in payload
                        else None
                    ),
                    report_share_id=(
                        uuid.UUID(payload["report_share_id"])
                        if "report_share_id" in payload
                        else None
                    ),
                )
            except (jwt.PyJWTError, KeyError, ValueError) as e:
                logger.debug("JWT decode failed: %s", e)
        return await call_next(request)
