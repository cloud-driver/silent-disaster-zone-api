from __future__ import annotations

import json
import logging

from fastapi import (
    APIRouter,
    Header,
    HTTPException,
    Request,
)

from src.line_bot.client import (
    LineConfigurationError,
    line_config_status,
    reply_message,
    verify_webhook_signature,
)
from src.line_bot.flow import handle_line_event
from src.line_bot.store import (
    claim_webhook_event,
    complete_webhook_event,
    init_line_storage,
    release_webhook_event,
)


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/line",
    tags=["line"],
)

init_line_storage()


@router.get("/health")
def line_health():
    config = line_config_status()

    return {
        "status": (
            "ok"
            if all(config.values())
            else "degraded"
        ),
        "webhook_path": "/line/webhook",
        "config": config,
    }


@router.post("/webhook")
async def line_webhook(
    request: Request,
    x_line_signature: str | None = Header(
        default=None,
        alias="X-Line-Signature",
    ),
):
    raw_body = await request.body()

    try:
        signature_valid = verify_webhook_signature(
            raw_body,
            x_line_signature,
        )

    except LineConfigurationError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error

    if not signature_valid:
        raise HTTPException(
            status_code=400,
            detail="LINE webhook signature 驗證失敗。",
        )

    try:
        payload = json.loads(
            raw_body.decode("utf-8")
        )

    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as error:
        raise HTTPException(
            status_code=400,
            detail="LINE webhook JSON 格式錯誤。",
        ) from error

    events = payload.get("events", [])

    if not isinstance(events, list):
        raise HTTPException(
            status_code=400,
            detail="LINE webhook events 格式錯誤。",
        )

    processed_events = 0
    ignored_duplicates = 0

    for event in events:
        if not isinstance(event, dict):
            continue

        webhook_event_id = str(
            event.get("webhookEventId", "")
        ).strip()

        if webhook_event_id:
            claimed = claim_webhook_event(
                webhook_event_id
            )

            if not claimed:
                ignored_duplicates += 1
                continue

        try:
            messages = handle_line_event(event)

            reply_token = str(
                event.get("replyToken", "")
            ).strip()

            if messages and reply_token:
                reply_message(
                    reply_token,
                    messages,
                )

            if webhook_event_id:
                complete_webhook_event(
                    webhook_event_id
                )

            processed_events += 1

        except Exception as error:
            if webhook_event_id:
                release_webhook_event(
                    webhook_event_id
                )

            logger.exception(
                "LINE webhook event processing failed."
            )

            raise HTTPException(
                status_code=500,
                detail=(
                    "LINE webhook event 處理失敗。"
                ),
            ) from error

    return {
        "status": "ok",
        "processed_events": processed_events,
        "ignored_duplicates": ignored_duplicates,
    }