from __future__ import annotations

import os
from typing import Literal

from fastapi import (
    APIRouter,
    HTTPException,
    Request,
    status,
)
from pydantic import BaseModel, Field

from src.auth.store import (
    AuthConfigurationError,
    consume_login_attempt,
    issue_access_token,
    revoke_access_token,
    verify_login_credentials,
)


router = APIRouter(
    prefix="/auth",
    tags=["01 · Authentication"],
)


class LoginRequest(BaseModel):
    username: str = Field(
        ...,
        min_length=1,
        max_length=80,
        description=(
            "【必填】登入帳號。"
        ),
        examples=["api-admin"],
    )

    password: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description=(
            "【必填】登入密碼。"
        ),
        json_schema_extra={
            "writeOnly": True,
        },
    )


class LoginResponse(BaseModel):
    access_token: str = Field(
        description=(
            "唯一短效 Token。"
            "只會在登入成功時完整回傳一次。"
        ),
    )

    token_type: Literal["Bearer"] = Field(
        description=(
            "Authorization header 的驗證類型。"
        ),
    )

    expires_in: int = Field(
        description=(
            "Token 剩餘有效秒數。"
            "固定為 900 秒，即 15 分鐘。"
        ),
        examples=[900],
    )

    expires_at: str = Field(
        description=(
            "Token 到期時間，UTC ISO-8601 格式。"
        ),
    )


class SessionResponse(BaseModel):
    status: Literal["authenticated"]
    username: str
    issued_at: str
    expires_at: str
    expires_in: int


def resolve_client_ip(
    request: Request,
) -> str:
    trust_proxy_headers = os.getenv(
        "AUTH_TRUST_PROXY_HEADERS",
        "false",
    ).strip().lower() in {
        "1",
        "true",
        "yes",
    }

    if trust_proxy_headers:
        forwarded_for = request.headers.get(
            "X-Forwarded-For",
            "",
        ).strip()

        if forwarded_for:
            return forwarded_for.split(
                ",",
                maxsplit=1,
            )[0].strip()

    if request.client is not None:
        return request.client.host

    return "unknown"


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="【01-1】登入並取得 15 分鐘 Token",
)
def login(
    payload: LoginRequest,
    request: Request,
):
    client_ip = resolve_client_ip(request)

    try:
        allowed, retry_after = consume_login_attempt(
            client_ip
        )

    except AuthConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "同一 IP 一分鐘內最多可呼叫登入 API 5 次。"
            ),
            headers={
                "Retry-After": str(retry_after),
            },
        )

    try:
        credentials_valid = verify_login_credentials(
            payload.username,
            payload.password,
        )

    except AuthConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error

    if not credentials_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="帳號或密碼錯誤。",
        )

    return issue_access_token(payload.username)


@router.get(
    "/session",
    response_model=SessionResponse,
    summary="【01-2】查詢目前 Token 狀態",
)
def current_session(
    request: Request,
):
    session = getattr(
        request.state,
        "auth_session",
        None,
    )

    if not isinstance(session, dict):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未找到有效登入狀態。",
        )

    return {
        "status": "authenticated",
        **session,
    }


@router.post(
    "/logout",
    summary="【01-3】撤銷目前 Token",
)
def logout(
    request: Request,
):
    access_token = getattr(
        request.state,
        "access_token",
        "",
    )

    revoked = revoke_access_token(access_token)

    return {
        "status": "success",
        "revoked": revoked,
        "message": (
            "目前 Token 已撤銷，後續請重新登入。"
        ),
    }