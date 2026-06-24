from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.reports.analytics import (
    build_verified_report_analytics,
)
from src.reports.store import list_verified_reports
from src.runtime.run_manifest import (
    load_manifest,
    now_iso,
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

HISTORY_ROOT = (
    PROJECT_ROOT
    / "outputs"
    / "history"
)


def write_json_atomic(
    path: Path,
    payload: dict,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = path.with_suffix(
        path.suffix + ".tmp"
    )

    with open(
        temporary_path,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            payload,
            file,
            ensure_ascii=False,
            indent=2,
        )

    temporary_path.replace(path)


def write_csv_atomic(
    path: Path,
    frame,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = path.with_suffix(
        path.suffix + ".tmp"
    )

    frame.to_csv(
        temporary_path,
        index=False,
        encoding="utf-8-sig",
    )

    temporary_path.replace(path)


print("=== 建立已驗證民眾通報特徵 ===")

manifest = load_manifest()

if manifest is None:
    raise RuntimeError(
        "找不到 run_manifest.json，請先執行 realtime fetch。"
    )

run_id = str(manifest.get("run_id", "")).strip()

if not run_id:
    raise RuntimeError("run_manifest.json 缺少 run_id。")

if not VILLAGES_PATH.exists():
    raise FileNotFoundError(
        f"找不到村里圖資：{VILLAGES_PATH}"
    )

generated_at = now_iso()

villages = gpd.read_file(VILLAGES_PATH)
verified_reports = list_verified_reports()

features, incidents, summary = (
    build_verified_report_analytics(
        villages,
        verified_reports,
        run_id=run_id,
        generated_at=generated_at,
    )
)

history_dir = HISTORY_ROOT / run_id
history_incident_path = (
    history_dir
    / "verified_incidents.json"
)

write_csv_atomic(
    FEATURE_OUTPUT_PATH,
    features,
)

payload = {
    "schema_version": "1.0",
    "run_id": run_id,
    "generated_at": generated_at,
    "data_mode": "live",
    "report_data_source": (
        "verified_human_reviewed_reports"
    ),
    "summary": summary,
    "count": len(incidents),
    "data": incidents,
}

write_json_atomic(
    INCIDENT_OUTPUT_PATH,
    payload,
)

write_json_atomic(
    history_incident_path,
    payload,
)

print("run_id:", run_id)
print("資料庫 verified 通報總數：", len(verified_reports))
print("本輪可用通報數：", summary["eligible_recent_report_count"])
print("成功對應村里數：", summary["matched_report_count"])
print("輸出：", FEATURE_OUTPUT_PATH)
print("輸出：", INCIDENT_OUTPUT_PATH)