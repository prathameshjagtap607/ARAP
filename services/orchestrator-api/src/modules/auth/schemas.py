from uuid import UUID

from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str
    org_id: UUID


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginResponse(TokenResponse):
    refresh_token: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class CandidateTokenRequest(BaseModel):
    email: str
    org_id: UUID
    assessment_session_id: UUID


class CandidateTokenResponse(BaseModel):
    token: str


class CandidateVerifyRequest(BaseModel):
    token: str
    assessment_session_id: UUID


class ClientTokenRequest(BaseModel):
    email: str
    org_id: UUID
    report_share_id: UUID


class ClientTokenResponse(BaseModel):
    token: str


class ClientVerifyRequest(BaseModel):
    token: str
    report_share_id: UUID
