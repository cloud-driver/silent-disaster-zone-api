from __future__ import annotations

from typing import Any


PRIORITY_RANK = {
    "I1": 1,
    "I2": 2,
    "I3": 3,
}


def priority_rank(
    priority: str,
) -> int:
    return PRIORITY_RANK.get(priority, 99)


def incident_actions(
    categories: list[str],
) -> list[str]:
    actions = [
        "確認人工查證紀錄與事件時間是否仍有效。",
        "將已驗證回報與即時資料及周邊通報交叉比對。",
    ]

    if "trapped_people" in categories:
        actions.append(
            "優先確認受困資訊是否持續存在，並依既有程序轉交人員研判。"
        )

    if "road_blocked" in categories:
        actions.append(
            "確認道路阻斷位置、替代動線與現場查核需求。"
        )

    if "landslide" in categories:
        actions.append(
            "比對邊坡、落石與降雨相關資料，確認影響範圍。"
        )

    if "flooding" in categories:
        actions.append(
            "確認積淹水位置、通行影響與變化趨勢。"
        )

    return actions


def build_verified_incident_queue(
    incidents: list[dict[str, Any]],
    limit: int = 5,
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}

    for incident in incidents:
        if not isinstance(incident, dict):
            continue

        village_id = str(
            incident.get("village_id", "")
        ).strip()

        if not village_id:
            continue

        priority = str(
            incident.get("incident_priority", "I3")
        ).strip()

        severity = int(
            incident.get("severity", 0) or 0
        )

        group = grouped.setdefault(
            village_id,
            {
                "village_id": village_id,
                "village_label": incident.get(
                    "village_label",
                    village_id,
                ),
                "priorities": [],
                "categories": [],
                "incident_count": 0,
                "max_severity": 0,
                "latest_reported_at": None,
            },
        )

        group["priorities"].append(priority)

        category = str(
            incident.get("category", "")
        ).strip()

        if category:
            group["categories"].append(category)

        group["incident_count"] += 1
        group["max_severity"] = max(
            group["max_severity"],
            severity,
        )

        reported_at = incident.get("reported_at")

        if (
            reported_at
            and (
                group["latest_reported_at"] is None
                or str(reported_at)
                > str(group["latest_reported_at"])
            )
        ):
            group["latest_reported_at"] = reported_at

    queue = []

    for group in grouped.values():
        priority = min(
            group["priorities"],
            key=priority_rank,
        )

        categories = sorted(set(group["categories"]))

        queue.append(
            {
                "priority": priority,
                "village_id": group["village_id"],
                "village_label": group["village_label"],
                "verified_incident_count": (
                    group["incident_count"]
                ),
                "max_severity": group["max_severity"],
                "categories": categories,
                "latest_reported_at": (
                    group["latest_reported_at"]
                ),
                "recommended_actions": incident_actions(
                    categories
                ),
                "needs_human_confirmation": True,
            }
        )

    return sorted(
        queue,
        key=lambda item: (
            priority_rank(item["priority"]),
            -item["max_severity"],
            -item["verified_incident_count"],
        ),
    )[:limit]