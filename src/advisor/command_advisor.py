from __future__ import annotations

import json
from typing import Any

from src.advisor.command_plan import build_command_plan
from src.advisor.ollama_client import (
    OllamaError,
    chat_with_ollama,
    get_ollama_settings,
)


NARRATIVE_SCHEMA = {
    "type": "object",
    "properties": {
        "situation_summary": {
            "type": "string",
        },
        "recommended_focus": {
            "type": "string",
        },
        "cautions": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
    },
    "required": [
        "situation_summary",
        "recommended_focus",
        "cautions",
    ],
    "additionalProperties": False,
}


def build_prompts(
    command_plan: dict[str, Any],
) -> tuple[str, str]:
    system_prompt = """
你是防災資訊摘要助手，不是指揮官、政府機關或災害應變中心。

你的工作是依照提供的 command_plan，
將既有的規則式排序整理成中性、保守、可供人工閱讀的繁體中文 briefing。

嚴格限制：
1. 不得新增 command_plan 中不存在的村里。
2. 不得變更 P1、P2、P3 優先順序。
3. 不得把 P3 描述為緊急處置、指揮命令或立即災害事件。
4. 不得使用「本指揮部」、「指揮命令」、「下令」、「應立即撤離」等語句。
5. 不得宣稱災害已發生。
6. 不得發布撤離、封路、停班停課或其他官方強制命令。
7. 不得把 pending 民眾回報視為已驗證事實。
8. 必須清楚反映 operational_posture：
   - routine_monitoring：日常監測與下一輪確認候選。
   - heightened_monitoring：提高確認與交叉查證優先度。
   - priority_verification：優先人工確認與巡查。
9. 必須輸出符合指定 JSON schema 的 JSON。
10. verified_incident_queue 是已完成人工查證的民眾回報摘要，
    必須和 priority_queue 分開描述。
11. 已驗證回報不等於官方災害宣告，也不得轉換為強制命令。
12. operational_posture 若為 verified_incident_priority_review，
    代表需要優先人員研判，不代表自動派遣或官方命令。
""".strip()

    user_prompt = (
        "請將以下 command plan 轉成結構化指揮 briefing：\n\n"
        + json.dumps(
            command_plan,
            ensure_ascii=False,
            indent=2,
        )
    )

    return system_prompt, user_prompt


def parse_narrative(
    content: str,
) -> dict[str, Any]:
    payload = json.loads(content)

    if not isinstance(payload, dict):
        raise ValueError("AI 回應不是 JSON object。")

    situation_summary = payload.get(
        "situation_summary"
    )

    recommended_focus = payload.get(
        "recommended_focus"
    )

    cautions = payload.get("cautions")

    if not isinstance(situation_summary, str):
        raise ValueError(
            "AI 回應缺少 situation_summary。"
        )

    if not isinstance(recommended_focus, str):
        raise ValueError(
            "AI 回應缺少 recommended_focus。"
        )

    if not isinstance(cautions, list):
        raise ValueError(
            "AI 回應缺少 cautions。"
        )

    cleaned_cautions = [
        str(item).strip()
        for item in cautions
        if str(item).strip()
    ][:5]

    return {
        "situation_summary": situation_summary.strip(),
        "recommended_focus": recommended_focus.strip(),
        "cautions": cleaned_cautions,
    }


def generate_command_advice(
    *,
    records: list[dict[str, Any]],
    dataset_metadata: dict[str, Any],
    report_summary: dict[str, Any],
    verified_incidents: list[dict[str, Any]] | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    command_plan = build_command_plan(
        records=records,
        dataset_metadata=dataset_metadata,
        report_summary=report_summary,
        verified_incidents=verified_incidents or [],
        limit=limit,
    )

    system_prompt, user_prompt = build_prompts(
        command_plan
    )

    settings = get_ollama_settings()

    try:
        result = chat_with_ollama(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.1,
            response_format=NARRATIVE_SCHEMA,
        )

        narrative = parse_narrative(
            result["content"]
        )

        return {
            "advisor_status": "available",
            "model": result["model"],
            "base_url": result["base_url"],
            "command_plan": command_plan,
            "narrative": narrative,
            "fallback_message": None,
        }

    except (OllamaError, ValueError, json.JSONDecodeError) as error:
        return {
            "advisor_status": "fallback",
            "model": settings["model"],
            "base_url": settings["base_url"],
            "command_plan": command_plan,
            "narrative": None,
            "fallback_message": (
                "AI 敘述暫時不可用，請直接依據 "
                "command_plan 的 priority_queue 執行人工確認。"
            ),
            "error": str(error),
        }