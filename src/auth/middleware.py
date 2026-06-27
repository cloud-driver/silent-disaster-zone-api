from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from src.auth.store import (
    ExpiredAccessTokenError,
    InvalidAccessTokenError,
    validate_access_token,
)


PUBLIC_PATHS = {
    "/auth/login",
    "/health",
    "/advisor/health",
    "/line/health",
    "/line/webhook",
    "/docs",
    "/docs/",
    "/redoc",
    "/redoc/",
    "/openapi.json",
}


def unauthorized_response(
    detail: str,
) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={
            "detail": detail,
        },
        headers={
            "WWW-Authenticate": "Bearer",
        },
    )


async def access_token_middleware(
    request: Request,
    call_next,
):
    path = request.url.path

    if (
        request.method == "OPTIONS"
        or path in PUBLIC_PATHS
    ):
        return await call_next(request)

    authorization = request.headers.get(
        "Authorization",
        "",
    ).strip()

    scheme, separator, access_token = (
        authorization.partition(" ")
    )

    if (
        not separator
        or scheme.lower() != "bearer"
        or not access_token.strip()
    ):
        return unauthorized_response(
            "缺少 Authorization: Bearer <access_token>。"
        )

    try:
        session = validate_access_token(access_token)

    except ExpiredAccessTokenError:
        return unauthorized_response(
            "Access token 已過期，請重新登入。"
        )

    except InvalidAccessTokenError:
        return unauthorized_response(
            "Access token 無效或已撤銷。"
        )

    request.state.access_token = access_token
    request.state.auth_session = session

    return await call_next(request)