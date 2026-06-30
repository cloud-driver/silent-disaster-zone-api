#!/usr/bin/env python3
"""Seed clearly-labeled mock disaster reports for a local recording/demo.

This script is for LOCAL DEMO / RECORDING ONLY.
It creates a small, internally consistent mix of:
- verified reports -> appear in /incidents/verified and the command plan;
- pending reports  -> appear in /reports/pending but do NOT affect formal scoring;
- one rejected report -> demonstrates the review boundary.

It only removes records whose external_event_id begins with ``recording-demo-``
unless --clear-all-reports is explicitly supplied.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import geopandas as gpd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.reports.analytics import build_verified_report_analytics
from src.reports.store import (
    create_report,
    get_connection,
    get_report_summary,
    init_db,
    list_verified_reports,
    review_report,
)

VILLAGES_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "villages_hualien_with_reports.geojson"
)
FEATURE_OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "realtime"
    / "latest"
    / "verified_report_features.csv"
)
INCIDENT_OUTPUT_PATH = (
    PROJECT_ROOT
    / "outputs"
    / "latest"
    / "verified_incidents.json"
)
HISTORY_ROOT = PROJECT_ROOT / "outputs" / "history"
MANIFEST_PATH = PROJECT_ROOT / "outputs" / "latest" / "run_manifest.json"
DEMO_PREFIX = "recording-demo-"

# The script tries these villages first, then safely falls back to other village
# geometries in the local dataset if a name is unavailable.
PREFERRED_VILLAGES = [
    ("光復鄉", "大安村"),
    ("鳳林鎮", "鳳仁里"),
    ("玉里鎮", "啟模里"),
    ("玉里鎮", "泰昌里"),
    ("瑞穗鄉", "瑞北村"),
]

# A deliberate mix for recording:
# - 3 verified: one I1 and two I2 incidents
# - 3 pending: visible to human review but excluded from formal features
# - 1 rejected: preserves the audit boundary
SCENARIOS = [
    {
        "key": "001",
        "status": "verified",
        "source": "line",
        "category": "trapped_people",
        "severity": 3,
        "description": "【模擬資料】住戶回報兩名行動不便者暫時受困，需由值勤人員進一步查證。",
        "reviewer_note": "【模擬審核】已由在地聯絡人回覆需優先確認，列入事件研判隊列。",
    },
    {
        "key": "002",
        "status": "verified",
        "source": "line",
        "category": "road_blocked",
        "severity": 2,
        "description": "【模擬資料】聯外道路疑似有落石與土砂堆積，通行受影響。",
        "reviewer_note": "【模擬審核】資訊來源與現地聯絡網一致，需確認替代動線。",
    },
    {
        "key": "003",
        "status": "verified",
        "source": "manual",
        "category": "flooding",
        "severity": 2,
        "description": "【模擬資料】低窪路段出現積淹水，機車通行困難。",
        "reviewer_note": "【模擬審核】已由巡查回覆確認，持續觀察水位變化。",
    },
    {
        "key": "004",
        "status": "pending",
        "source": "line",
        "category": "power_or_comms",
        "severity": 2,
        "description": "【模擬資料】居民回報局部停電與行動網路不穩，尚待交叉確認。",
    },
    {
        "key": "005",
        "status": "pending",
        "source": "line",
        "category": "landslide",
        "severity": 2,
        "description": "【模擬資料】山邊道路旁疑似有零星落石，尚未完成現地查核。",
    },
    {
        "key": "006",
        "status": "pending",
        "source": "api",
        "category": "flooding",
        "severity": 1,
        "description": "【模擬資料】回報路旁排水不及，是否積水仍待確認。",
    },
    {
        "key": "007",
        "status": "rejected",
        "source": "line",
        "category": "other",
        "severity": 1,
        "description": "【模擬資料】重複且資訊不足的回報，用於展示 rejected 審核結果。",
        "reviewer_note": "【模擬審核】與既有回報重複，且沒有可用位置描述。",
    },
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="建立錄影用模擬災情回報與已驗證事件 snapshot。"
    )
    parser.add_argument(
        "--clear-all-reports",
        action="store_true",
        help=(
            "危險：清空本機 disaster_reports 資料表後再建立模擬資料。"
            "僅限錄影用本機環境。"
        ),
    )
    parser.add_argument(
        "--keep-existing-demo",
        action="store_true",
        help="不移除既有 recording-demo-* 資料；通常不建議使用。",
    )
    return parser.parse_args()


def clear_reports(*, clear_all: bool, keep_existing_demo: bool) -> int:
    """Clear only our seeded reports by default; clear all only with opt-in."""
    init_db()
    connection = get_connection()

    try:
        if clear_all:
            cursor = connection.execute("DELETE FROM disaster_reports")
        elif keep_existing_demo:
            return 0
        else:
            cursor = connection.execute(
                """
                DELETE FROM disaster_reports
                WHERE external_event_id LIKE ?
                """,
                (f"{DEMO_PREFIX}%",),
            )

        connection.commit()
        return int(cursor.rowcount or 0)
    finally:
        connection.close()


def require_villages() -> gpd.GeoDataFrame:
    if not VILLAGES_PATH.exists():
        raise FileNotFoundError(
            "找不到村里圖資："
            f"{VILLAGES_PATH}\n"
            "請先確認 data/processed/villages_hualien_with_reports.geojson 存在。"
        )

    villages = gpd.read_file(VILLAGES_PATH)
    required = {"village_id", "county_name", "town_name", "village_name", "geometry"}
    missing = required - set(villages.columns)

    if missing:
        raise ValueError(f"村里圖資缺少欄位：{sorted(missing)}")

    if villages.crs is None:
        raise ValueError("村里圖資缺少 CRS。")

    if villages.empty:
        raise ValueError("村里圖資為空。")

    # representative_point is guaranteed to lie inside each polygon and is safer
    # than an unprojected centroid for spatial matching in report analytics.
    projected = villages.to_crs(epsg=3857).copy()
    points = projected.geometry.representative_point()
    points_4326 = gpd.GeoSeries(points, crs="EPSG:3857").to_crs(epsg=4326)

    villages = villages.to_crs(epsg=4326).copy()
    villages["_demo_point"] = points_4326.values
    return villages


def choose_demo_villages(villages: gpd.GeoDataFrame, count: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()

    normalized = villages.copy()
    for column in ("county_name", "town_name", "village_name", "village_id"):
        normalized[column] = normalized[column].astype(str).str.strip()

    for town_name, village_name in PREFERRED_VILLAGES:
        matches = normalized[
            (normalized["town_name"] == town_name)
            & (normalized["village_name"] == village_name)
        ]

        if matches.empty:
            continue

        row = matches.sort_values("village_id", kind="stable").iloc[0]
        village_id = str(row["village_id"])
        if village_id not in selected_ids:
            selected.append(row.to_dict())
            selected_ids.add(village_id)

        if len(selected) >= count:
            return selected

    for _, row in normalized.sort_values("village_id", kind="stable").iterrows():
        village_id = str(row["village_id"])
        if village_id in selected_ids:
            continue

        selected.append(row.to_dict())
        selected_ids.add(village_id)

        if len(selected) >= count:
            return selected

    if len(selected) < count:
        raise RuntimeError("可用村里數量不足，無法建立完整模擬情境。")

    return selected


def village_location(row: dict[str, Any]) -> tuple[float, float, str]:
    point = row.get("_demo_point")
    if point is None:
        raise ValueError("村里缺少代表點。")

    label = "".join(
        [
            str(row.get("county_name", "")).strip(),
            str(row.get("town_name", "")).strip(),
            str(row.get("village_name", "")).strip(),
        ]
    )

    return float(point.y), float(point.x), label


def create_seeded_reports(villages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seeded: list[dict[str, Any]] = []

    for index, scenario in enumerate(SCENARIOS):
        village = villages[index % len(villages)]
        latitude, longitude, location_label = village_location(village)
        external_event_id = f"{DEMO_PREFIX}{scenario['key']}"

        report, created = create_report(
            source=scenario["source"],
            reporter_hash=f"recording-demo-reporter-{scenario['key']}",
            category=scenario["category"],
            severity=scenario["severity"],
            description=scenario["description"],
            latitude=latitude,
            longitude=longitude,
            location_label=location_label,
            external_event_id=external_event_id,
        )

        if scenario["status"] in {"verified", "rejected"} and report["status"] == "pending":
            report = review_report(
                report_id=report["report_id"],
                decision=scenario["status"],
                reviewer_id="recording-demo-admin",
                reviewer_note=scenario.get("reviewer_note", "【模擬審核】錄影展示資料。"),
            )

        seeded.append(
            {
                "report_id": report["report_id"],
                "created": created,
                "status": report["status"],
                "category": report["category"],
                "severity": report["severity"],
                "location_label": report.get("location_label"),
            }
        )

    return seeded


def current_run_id() -> str:
    if MANIFEST_PATH.exists():
        try:
            payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
            run_id = str(payload.get("run_id", "")).strip()
            if run_id:
                return run_id
        except (OSError, json.JSONDecodeError):
            pass

    return "recording_demo_" + datetime.now().strftime("%Y%m%d_%H%M%S")


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def build_incident_snapshot(villages: gpd.GeoDataFrame) -> dict[str, Any]:
    run_id = current_run_id()
    generated_at = now_iso()
    reports = list_verified_reports()

    features, incidents, summary = build_verified_report_analytics(
        villages,
        reports,
        analysis_time=generated_at,
        run_id=run_id,
        generated_at=generated_at,
    )

    FEATURE_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(
        FEATURE_OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    payload = {
        "schema_version": "1.0",
        "run_id": run_id,
        "generated_at": generated_at,
        "data_mode": "recording_mock",
        "report_data_source": "recording_demo_human_reviewed_reports",
        "summary": summary,
        "count": len(incidents),
        "data": incidents,
    }

    write_json_atomic(INCIDENT_OUTPUT_PATH, payload)
    write_json_atomic(
        HISTORY_ROOT / run_id / "verified_incidents.json",
        payload,
    )

    return payload


def main() -> None:
    args = parse_args()

    if args.clear_all_reports:
        print("[警告] 將清空本機 disaster_reports 資料表。")

    removed = clear_reports(
        clear_all=args.clear_all_reports,
        keep_existing_demo=args.keep_existing_demo,
    )
    villages = require_villages()
    chosen = choose_demo_villages(villages, count=len(SCENARIOS))
    seeded = create_seeded_reports(chosen)
    snapshot = build_incident_snapshot(villages)
    summary = get_report_summary()

    print("\n=== 錄影用模擬資料已建立 ===")
    print(f"移除既有資料筆數：{removed}")
    print(f"建立／重用通報筆數：{len(seeded)}")
    print("通報統計：", json.dumps(summary, ensure_ascii=False))
    print(
        "事件 snapshot：",
        f"{INCIDENT_OUTPUT_PATH.relative_to(PROJECT_ROOT)}",
    )
    print("已驗證事件數：", snapshot["count"])
    print("\n錄影情境：")
    print("- verified：1 筆 I1 受困事件、2 筆 I2 道路／積淹水事件")
    print("- pending：3 筆待人工查證回報")
    print("- rejected：1 筆拒絕回報")
    print("\n若未修改後端程式，不必重啟 FastAPI；回到前端按『同步 API 資料』即可。")
    print("若 /advisor/command 仍回傳 500，請先修正 main.py 的 load_verified_incident_snapshot 匯入。")


if __name__ == "__main__":
    main()
