from __future__ import annotations

import os
from typing import Any
from urllib.parse import parse_qs

from src.line_bot.client import (
    quick_reply_location,
    quick_reply_message,
    quick_reply_postback,
    text_message,
)
from src.line_bot.store import (
    clear_line_session,
    get_line_session,
    save_line_session,
)
from src.reports.store import (
    create_report,
    hash_reporter_id,
)


CATEGORIES = {
    "flooding": "積淹水",
    "landslide": "土石／落石",
    "road_blocked": "道路中斷",
    "trapped_people": "受困／需協助",
    "power_or_comms": "停電／通訊異常",
    "other": "其他",
}

SEVERITIES = {
    "1": "輕微",
    "2": "中度",
    "3": "嚴重",
}

START_COMMANDS = {
    "災情回報",
    "回報災情",
    "開始回報",
}


def start_menu() -> list[dict[str, Any]]:
    return [
        text_message(
            "這裡是災情回報入口。\n\n"
            "回報會先進入「待人工查證」，"
            "不會直接被視為已確認災情，"
            "也不會直接觸發官方命令。\n\n"
            "若有人員立即危險，請優先使用緊急服務。",
            quick_reply_items=[
                quick_reply_message(
                    "開始災情回報",
                    "災情回報",
                ),
            ],
        )
    ]


def category_prompt() -> list[dict[str, Any]]:
    items = []

    for key, label in CATEGORIES.items():
        items.append(
            quick_reply_postback(
                label=label,
                data=(
                    "flow=report"
                    "&action=category"
                    f"&value={key}"
                ),
                display_text=label,
            )
        )

    items.append(
        quick_reply_message(
            "取消",
            "取消",
        )
    )

    return [
        text_message(
            "請選擇災情類型：",
            quick_reply_items=items,
        )
    ]


def severity_prompt() -> list[dict[str, Any]]:
    items = []

    for key, label in SEVERITIES.items():
        items.append(
            quick_reply_postback(
                label=f"{key}｜{label}",
                data=(
                    "flow=report"
                    "&action=severity"
                    f"&value={key}"
                ),
                display_text=f"{key}｜{label}",
            )
        )

    items.append(
        quick_reply_message(
            "取消",
            "取消",
        )
    )

    return [
        text_message(
            "請選擇你觀察到的嚴重程度：\n"
            "1＝輕微、2＝中度、3＝嚴重",
            quick_reply_items=items,
        )
    ]


def location_prompt() -> list[dict[str, Any]]:
    return [
        text_message(
            "請使用下方按鈕傳送災情位置。",
            quick_reply_items=[
                quick_reply_location(),
                quick_reply_message(
                    "取消",
                    "取消",
                ),
            ],
        )
    ]


def description_prompt() -> list[dict[str, Any]]:
    return [
        text_message(
            "請用文字簡述現況，例如：\n"
            "「道路邊坡有落石，汽車暫時無法通行」\n\n"
            "請勿提供身分證號、住址、電話等敏感個資。",
            quick_reply_items=[
                quick_reply_message(
                    "取消",
                    "取消",
                ),
            ],
        )
    ]


def confirmation_prompt(
    draft: dict[str, Any],
) -> list[dict[str, Any]]:
    category = CATEGORIES.get(
        str(draft.get("category", "")),
        "未指定",
    )

    severity = SEVERITIES.get(
        str(draft.get("severity", "")),
        "未指定",
    )

    location_label = (
        str(draft.get("location_label", ""))
        .strip()
        or "已收到定位座標"
    )

    description = str(
        draft.get("description", "")
    ).strip()

    summary = (
        "請確認回報內容：\n\n"
        f"類型：{category}\n"
        f"嚴重程度：{severity}\n"
        f"位置：{location_label}\n"
        f"描述：{description}\n\n"
        "送出後將以「待人工查證」保存，"
        "不會直接被當成已確認災情。"
    )

    return [
        text_message(
            summary,
            quick_reply_items=[
                quick_reply_postback(
                    label="確認送出",
                    data=(
                        "flow=report"
                        "&action=confirm"
                    ),
                    display_text="確認送出災情回報",
                ),
                quick_reply_postback(
                    label="取消",
                    data=(
                        "flow=report"
                        "&action=cancel"
                    ),
                    display_text="取消災情回報",
                ),
            ],
        )
    ]


def reminder_for_step(
    step: str,
    draft: dict[str, Any],
) -> list[dict[str, Any]]:
    if step == "awaiting_category":
        return category_prompt()

    if step == "awaiting_severity":
        return severity_prompt()

    if step == "awaiting_location":
        return location_prompt()

    if step == "awaiting_description":
        return description_prompt()

    if step == "awaiting_confirm":
        return confirmation_prompt(draft)

    return start_menu()


def cancel_report(
    reporter_hash: str,
    db_path: str | None = None,
) -> list[dict[str, Any]]:
    clear_line_session(
        reporter_hash,
        db_path=db_path,
    )

    return [
        text_message(
            "已取消本次災情回報。",
            quick_reply_items=[
                quick_reply_message(
                    "重新開始",
                    "災情回報",
                ),
            ],
        )
    ]


def handle_text_message(
    reporter_hash: str,
    text: str,
    db_path: str | None = None,
) -> list[dict[str, Any]]:
    text = text.strip()

    if text == "取消":
        return cancel_report(
            reporter_hash,
            db_path=db_path,
        )

    session = get_line_session(
        reporter_hash,
        db_path=db_path,
    )

    step = session["step"]
    draft = session["draft"]

    if text in START_COMMANDS:
        save_line_session(
            reporter_hash,
            "awaiting_category",
            {},
            db_path=db_path,
        )

        return category_prompt()

    if step == "awaiting_description":
        if len(text) < 3:
            return [
                text_message(
                    "描述至少需要 3 個字，請再補充現況。"
                )
            ]

        if len(text) > 1000:
            return [
                text_message(
                    "描述超過 1000 字，請縮短後重新傳送。"
                )
            ]

        draft["description"] = text

        save_line_session(
            reporter_hash,
            "awaiting_confirm",
            draft,
            db_path=db_path,
        )

        return confirmation_prompt(draft)

    return reminder_for_step(step, draft)


def handle_location_message(
    reporter_hash: str,
    message: dict[str, Any],
    db_path: str | None = None,
) -> list[dict[str, Any]]:
    session = get_line_session(
        reporter_hash,
        db_path=db_path,
    )

    if session["step"] != "awaiting_location":
        return [
            text_message(
                "請先輸入「災情回報」開始新的回報流程。"
            )
        ]

    try:
        latitude = float(message["latitude"])
        longitude = float(message["longitude"])
    except (
        KeyError,
        TypeError,
        ValueError,
    ):
        return [
            text_message(
                "位置資料不完整，請重新使用定位按鈕傳送位置。"
            )
        ]

    if not -90 <= latitude <= 90:
        return [
            text_message("緯度資料無效，請重新傳送位置。")
        ]

    if not -180 <= longitude <= 180:
        return [
            text_message("經度資料無效，請重新傳送位置。")
        ]

    title = str(
        message.get("title", "")
    ).strip()

    address = str(
        message.get("address", "")
    ).strip()

    location_label = " ".join(
        item
        for item in [title, address]
        if item
    )

    draft = session["draft"]
    draft["latitude"] = latitude
    draft["longitude"] = longitude
    draft["location_label"] = location_label

    save_line_session(
        reporter_hash,
        "awaiting_description",
        draft,
        db_path=db_path,
    )

    return description_prompt()


def handle_postback(
    reporter_hash: str,
    data: str,
    webhook_event_id: str,
    db_path: str | None = None,
) -> list[dict[str, Any]]:
    payload = parse_qs(
        data,
        keep_blank_values=True,
    )

    if payload.get("flow", [""])[0] != "report":
        return start_menu()

    action = payload.get("action", [""])[0]
    value = payload.get("value", [""])[0]

    session = get_line_session(
        reporter_hash,
        db_path=db_path,
    )

    draft = session["draft"]

    if action == "cancel":
        return cancel_report(
            reporter_hash,
            db_path=db_path,
        )

    if action == "category":
        if value not in CATEGORIES:
            return category_prompt()

        draft = {
            "category": value,
        }

        save_line_session(
            reporter_hash,
            "awaiting_severity",
            draft,
            db_path=db_path,
        )

        return severity_prompt()

    if action == "severity":
        if value not in SEVERITIES:
            return severity_prompt()

        if "category" not in draft:
            return category_prompt()

        draft["severity"] = int(value)

        save_line_session(
            reporter_hash,
            "awaiting_location",
            draft,
            db_path=db_path,
        )

        return location_prompt()

    if action == "confirm":
        required_fields = {
            "category",
            "severity",
            "latitude",
            "longitude",
            "description",
        }

        if not required_fields.issubset(
            draft.keys()
        ):
            return start_menu()

        external_event_id = (
            f"line:{webhook_event_id}"
            if webhook_event_id
            else None
        )

        report, created = create_report(
            source="line",
            reporter_hash=reporter_hash,
            category=str(draft["category"]),
            severity=int(draft["severity"]),
            description=str(draft["description"]),
            latitude=float(draft["latitude"]),
            longitude=float(draft["longitude"]),
            location_label=str(
                draft.get("location_label", "")
            ),
            external_event_id=external_event_id,
            db_path=db_path,
        )

        clear_line_session(
            reporter_hash,
            db_path=db_path,
        )

        if created:
            return [
                text_message(
                    "已收到你的回報。\n\n"
                    f"回報編號：{report['report_id']}\n"
                    "目前狀態：待人工查證\n\n"
                    "此回報不代表災情已被官方確認。"
                )
            ]

        return [
            text_message(
                "這筆回報先前已收到，"
                "目前仍維持待人工查證狀態。"
            )
        ]

    return reminder_for_step(
        session["step"],
        draft,
    )


def handle_line_event(
    event: dict[str, Any],
    db_path: str | None = None,
    reporter_hash_secret: str | None = None,
) -> list[dict[str, Any]]:
    source = event.get("source", {})

    if not isinstance(source, dict):
        return []

    if source.get("type") != "user":
        return [
            text_message(
                "為保護回報隱私，"
                "請在與本帳號的一對一聊天中進行災情回報。"
            )
        ]

    user_id = str(
        source.get("userId", "")
    ).strip()

    if not user_id:
        return []

    reporter_hash_secret = (
        reporter_hash_secret
        or os.getenv(
            "REPORTER_HASH_SECRET",
            "",
        ).strip()
    )

    reporter_hash = hash_reporter_id(
        user_id,
        reporter_hash_secret,
    )

    event_type = event.get("type")

    if event_type == "follow":
        clear_line_session(
            reporter_hash,
            db_path=db_path,
        )

        return start_menu()

    if event_type == "postback":
        postback = event.get("postback", {})

        if not isinstance(postback, dict):
            return start_menu()

        return handle_postback(
            reporter_hash=reporter_hash,
            data=str(postback.get("data", "")),
            webhook_event_id=str(
                event.get("webhookEventId", "")
            ),
            db_path=db_path,
        )

    if event_type != "message":
        return []

    message = event.get("message", {})

    if not isinstance(message, dict):
        return []

    message_type = message.get("type")

    if message_type == "text":
        return handle_text_message(
            reporter_hash=reporter_hash,
            text=str(message.get("text", "")),
            db_path=db_path,
        )

    if message_type == "location":
        return handle_location_message(
            reporter_hash=reporter_hash,
            message=message,
            db_path=db_path,
        )

    return [
        text_message(
            "目前回報 MVP 支援文字與位置資訊。\n"
            "請輸入「災情回報」重新開始。"
        )
    ]