from __future__ import annotations

import base64
import hashlib
import hmac
import os
from typing import Any

import requests
from dotenv import load_dotenv


load_dotenv()

LINE_REPLY_ENDPOINT = (
    "https://api.line.me/v2/bot/message/reply"
)


class LineConfigurationError(Exception):
    """LINE 環境變數設定不完整。"""


class LineApiError(Exception):
    """LINE Messaging API 呼叫失敗。"""


def get_line_settings(
    require_access_token: bool = False,
) -> dict[str, str]:
    channel_secret = os.getenv(
        "LINE_CHANNEL_SECRET",
        "",
    ).strip()

    access_token = os.getenv(
        "LINE_CHANNEL_ACCESS_TOKEN",
        "",
    ).strip()

    if not channel_secret:
        raise LineConfigurationError(
            "LINE_CHANNEL_SECRET 尚未設定。"
        )

    if require_access_token and not access_token:
        raise LineConfigurationError(
            "LINE_CHANNEL_ACCESS_TOKEN 尚未設定。"
        )

    return {
        "channel_secret": channel_secret,
        "access_token": access_token,
    }


def line_config_status() -> dict[str, bool]:
    return {
        "channel_secret_configured": bool(
            os.getenv(
                "LINE_CHANNEL_SECRET",
                "",
            ).strip()
        ),
        "access_token_configured": bool(
            os.getenv(
                "LINE_CHANNEL_ACCESS_TOKEN",
                "",
            ).strip()
        ),
        "reporter_hash_secret_configured": bool(
            os.getenv(
                "REPORTER_HASH_SECRET",
                "",
            ).strip()
        ),
    }


def make_webhook_signature(
    raw_body: bytes,
    channel_secret: str,
) -> str:
    digest = hmac.new(
        channel_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).digest()

    return base64.b64encode(
        digest
    ).decode("ascii")


def verify_webhook_signature(
    raw_body: bytes,
    signature: str | None,
    channel_secret: str | None = None,
) -> bool:
    if not signature:
        return False

    if channel_secret is None:
        settings = get_line_settings()
        channel_secret = settings["channel_secret"]

    expected_signature = make_webhook_signature(
        raw_body,
        channel_secret,
    )

    return hmac.compare_digest(
        expected_signature,
        signature,
    )


def reply_message(
    reply_token: str,
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    if not reply_token:
        raise ValueError("reply_token 不可為空。")

    if not 1 <= len(messages) <= 5:
        raise ValueError(
            "一次 LINE reply 必須包含 1 至 5 則訊息。"
        )

    settings = get_line_settings(
        require_access_token=True,
    )

    response = requests.post(
        LINE_REPLY_ENDPOINT,
        headers={
            "Authorization": (
                "Bearer "
                + settings["access_token"]
            ),
        },
        json={
            "replyToken": reply_token,
            "messages": messages,
        },
        timeout=15,
    )

    if response.status_code >= 400:
        raise LineApiError(
            "LINE reply API 失敗："
            + response.text[:500]
        )

    if not response.content:
        return {}

    return response.json()


def text_message(
    text: str,
    quick_reply_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    message: dict[str, Any] = {
        "type": "text",
        "text": text,
    }

    if quick_reply_items:
        message["quickReply"] = {
            "items": quick_reply_items,
        }

    return message


def quick_reply_postback(
    label: str,
    data: str,
    display_text: str | None = None,
) -> dict[str, Any]:
    action: dict[str, Any] = {
        "type": "postback",
        "label": label,
        "data": data,
    }

    if display_text:
        action["displayText"] = display_text

    return {
        "type": "action",
        "action": action,
    }


def quick_reply_message(
    label: str,
    text: str,
) -> dict[str, Any]:
    return {
        "type": "action",
        "action": {
            "type": "message",
            "label": label,
            "text": text,
        },
    }


def quick_reply_location(
    label: str = "傳送目前位置",
) -> dict[str, Any]:
    return {
        "type": "action",
        "action": {
            "type": "location",
            "label": label,
        },
    }