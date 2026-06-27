from __future__ import annotations

from typing import Any

from src.advisor.incident_plan import (
    build_verified_incident_queue,
)


def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        if value is None:
            return default

        return float(value)

    except (TypeError, ValueError):
        return default


def safe_int(
    value: Any,
    default: int = 0,
) -> int:
    try:
        if value is None:
            return default

        return int(value)

    except (TypeError, ValueError):
        return default


def village_label(
    record: dict[str, Any],
) -> str:
    county = str(
        record.get("county_name", "")
    ).strip()

    town = str(
        record.get("town_name", "")
    ).strip()

    village = str(
        record.get("village_name", "")
    ).strip()

    return "".join([
        county,
        town,
        village,
    ]) or str(
        record.get("village_id", "未知區域")
    )


def priority_level(
    score: float,
) -> str:
    if score >= 0.55:
        return "P1"

    if score >= 0.35:
        return "P2"

    return "P3"

def determine_operational_posture(
    priority_queue: list[dict[str, Any]],
    verified_incident_queue: list[dict[str, Any]],
) -> str:
    incident_priorities = {
        item.get("priority")
        for item in verified_incident_queue
    }

    if "I1" in incident_priorities:
        return "verified_incident_priority_review"

    if verified_incident_queue:
        return "verified_incident_review"

    priorities = {
        item.get("priority")
        for item in priority_queue
    }

    if "P1" in priorities:
        return "priority_verification"

    if "P2" in priorities:
        return "heightened_monitoring"

    return "routine_monitoring"


def build_evidence(
    record: dict[str, Any],
) -> list[str]:
    evidence = []

    static_risk = safe_float(
        record.get("static_risk_score")
    )

    sensor_gap = safe_float(
        record.get("sensor_gap_score")
    )

    realtime_event = safe_float(
        record.get("realtime_event_score")
    )

    report_6h = safe_int(
        record.get("report_count_6h")
    )

    report_24h = safe_int(
        record.get("report_count_24h")
    )

    if static_risk >= 0.35:
        evidence.append("靜態災害與脆弱度風險偏高")

    if sensor_gap >= 0.50:
        evidence.append("觀測缺口偏高，現場資訊不足")

    if realtime_event > 0:
        evidence.append("存在即時雨量、路況或警戒事件訊號")

    if report_6h == 0:
        evidence.append("近 6 小時無系統通報，需主動確認")

    if report_24h > 0:
        evidence.append(
            f"系統記錄近 24 小時 {report_24h} 筆通報"
        )

    if not evidence:
        evidence.append("目前可用證據有限，建議持續觀察")

    return evidence


def build_actions(
    record: dict[str, Any],
) -> list[str]:
    actions = [
        "優先聯繫里長、防災幹部或既有聯絡網確認現況。",
        "比對村里風險分數、即時資料與既有通報是否一致。",
    ]

    sensor_gap = safe_float(
        record.get("sensor_gap_score")
    )

    realtime_event = safe_float(
        record.get("realtime_event_score")
    )

    elderly_ratio = safe_float(
        record.get("elderly_ratio")
    )

    report_6h = safe_int(
        record.get("report_count_6h")
    )

    if sensor_gap >= 0.50:
        actions.append(
            "安排具定位能力的巡查或替代觀測方式，補足感測器缺口。"
        )

    if realtime_event > 0:
        actions.append(
            "查核即時事件來源的時間、位置與影響範圍。"
        )

    if elderly_ratio >= 0.20:
        actions.append(
            "確認高齡或脆弱住戶的聯絡與關懷名單是否可用。"
        )

    if report_6h > 0:
        actions.append(
            "確認既有通報是否已完成人工查證，避免重複派遣。"
        )
    else:
        actions.append(
            "將此區列入下一輪主動確認與巡查排序。"
        )

    return actions


def build_limitations(
    dataset_metadata: dict[str, Any],
    report_summary: dict[str, Any],
) -> list[str]:
    limitations = [
        "本計畫僅提供人工確認與巡查優先順序，不代表災害已發生。",
        "不得直接作為撤離、封路或其他官方強制命令依據。",
    ]

    data_mode = dataset_metadata.get("data_mode")
    freshness = dataset_metadata.get("freshness")

    if data_mode != "live":
        limitations.append(
            "目前資料不是即時 live 資料，需先確認資料生成時間。"
        )

    if freshness in {"stale", "expired"}:
        limitations.append(
            "即時資料可能過期，應先刷新資料或人工交叉確認。"
        )

    if dataset_metadata.get("has_source_issues"):
        limitations.append(
            "至少一個外部資料來源抓取失敗或被略過。"
        )

    if report_summary.get("pending", 0) > 0:
        limitations.append(
            "尚有未驗證的民眾回報，暫時不得直接納入正式風險排序。"
        )

    return limitations


def build_command_plan(
    records: list[dict[str, Any]],
    dataset_metadata: dict[str, Any],
    report_summary: dict[str, Any],
    verified_incidents: list[dict[str, Any]] | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    sorted_records = sorted(
        [
            record
            for record in records
            if isinstance(record, dict)
        ],
        key=lambda record: safe_float(
            record.get("silent_risk_score")
        ),
        reverse=True,
    )

    selected_records = sorted_records[:limit]

    priority_queue = []

    for record in selected_records:
        score = safe_float(
            record.get("silent_risk_score")
        )

        priority_queue.append(
            {
                "priority": priority_level(score),
                "village_id": record.get("village_id"),
                "village_label": village_label(record),
                "silent_risk_score": round(score, 4),
                "silent_risk_level": record.get(
                    "silent_risk_level"
                ),
                "evidence": build_evidence(record),
                "recommended_actions": build_actions(record),
                "needs_human_confirmation": True,
            }
        )

    verified_incident_queue = (
        build_verified_incident_queue(
            verified_incidents or [],
            limit=limit,
        )
    )

    return {
        "plan_version": "1.0",
        "decision_scope": "decision_support_only",
        "operational_posture": determine_operational_posture(
            priority_queue,
            verified_incident_queue,
        ),
        "dataset": {
            "data_mode": dataset_metadata.get("data_mode"),
            "verification": dataset_metadata.get(
                "verification"
            ),
            "freshness": dataset_metadata.get("freshness"),
            "generated_at": dataset_metadata.get(
                "generated_at"
            ),
            "has_source_issues": dataset_metadata.get(
                "has_source_issues"
            ),
        },
        "report_intake": report_summary,
        "priority_queue": priority_queue,
        "verified_incident_queue": verified_incident_queue,
        "limitations": build_limitations(
            dataset_metadata,
            report_summary,
        ),
    }