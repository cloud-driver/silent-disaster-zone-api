from pathlib import Path
import json
import shutil
import pandas as pd
import geopandas as gpd
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT))

from src.scoring.silent_risk import apply_silent_risk_scoring

from src.runtime.run_manifest import (
    load_manifest,
    mark_scoring_complete,
)

BASE_INPUT_PATH = PROJECT_ROOT / "data" / "processed" / "villages_hualien_with_reports.geojson"
REALTIME_FEATURES_PATH = PROJECT_ROOT / "data" / "realtime" / "latest" / "realtime_features.csv"

VERIFIED_REPORT_FEATURES_PATH = (
    PROJECT_ROOT
    / "data"
    / "realtime"
    / "latest"
    / "verified_report_features.csv"
)

VERIFIED_INCIDENTS_PATH = (
    PROJECT_ROOT
    / "outputs"
    / "latest"
    / "verified_incidents.json"
)

OUTPUT_LATEST_DIR = PROJECT_ROOT / "outputs" / "latest"
OUTPUT_HISTORY_ROOT = PROJECT_ROOT / "outputs" / "history"


def get_active_run_id():
    manifest = load_manifest()

    if manifest is None:
        raise RuntimeError(
            "找不到 run_manifest.json，請先執行 realtime fetch。"
        )

    run_id = str(manifest.get("run_id", "")).strip()

    if not run_id:
        raise RuntimeError("run_manifest.json 缺少 run_id。")

    return run_id


def assign_level(score):
    if score >= 0.75:
        return "critical"
    if score >= 0.55:
        return "high"
    if score >= 0.35:
        return "medium"
    return "low"


def build_silent_reason(row):
    reasons = []

    if row["static_risk_score"] >= 0.35:
        reasons.append("靜態災害風險偏高")

    if row["sensor_gap_score"] >= 0.35:
        reasons.append("高風險但感測器覆蓋不足")

    if row["realtime_event_score"] >= 0.2:
        reasons.append("即時資料顯示道路/雨量/土石流相關事件")

    elif row["realtime_event_score"] > 0:
        reasons.append("即時資料有輕微異常訊號")

    if row["rainfall_realtime_score"] > 0:
        reasons.append("即時雨量觀測有反應")

    if row["landslide_realtime_score"] > 0:
        reasons.append("土石流雨量或警戒資料有反應")

    if row["road_realtime_score"] > 0:
        reasons.append("村里內或附近有即時路況事件")

    if row["report_count_6h"] == 0:
        reasons.append("近6小時無通報")

    if row["report_count_24h"] == 0:
        reasons.append("近24小時無通報")

    if row["report_count_6h"] > 0:
        reasons.append("近6小時已有通報，沉默風險降低")

    if len(reasons) == 0:
        reasons.append("目前沉默風險較低")

    return "；".join(reasons)


def make_json_serializable(value):
    import numpy as np
    import pandas as pd

    if value is None:
        return None

    try:
        is_na = pd.isna(value)
        if hasattr(is_na, "all"):
            if is_na.all():
                return None
        elif is_na:
            return None
    except Exception:
        pass

    if isinstance(value, np.ndarray):
        return value.tolist()

    if isinstance(value, (np.integer,)):
        return int(value)

    if isinstance(value, (np.floating,)):
        return float(value)

    if isinstance(value, pd.Timestamp):
        return value.isoformat()

    if isinstance(value, list):
        return [make_json_serializable(v) for v in value]

    if isinstance(value, dict):
        return {str(k): make_json_serializable(v) for k, v in value.items()}

    return value


print("=== 1. 讀取基礎主表與即時特徵 ===")

if not BASE_INPUT_PATH.exists():
    raise FileNotFoundError(f"找不到基礎主表：{BASE_INPUT_PATH}")

if not REALTIME_FEATURES_PATH.exists():
    raise FileNotFoundError(f"找不到即時特徵：{REALTIME_FEATURES_PATH}")

if not VERIFIED_REPORT_FEATURES_PATH.exists():
    raise FileNotFoundError(
        "找不到已驗證通報特徵："
        f"{VERIFIED_REPORT_FEATURES_PATH}"
    )

if not VERIFIED_INCIDENTS_PATH.exists():
    raise FileNotFoundError(
        "找不到已驗證事件 snapshot："
        f"{VERIFIED_INCIDENTS_PATH}"
    )

gdf = gpd.read_file(BASE_INPUT_PATH)

realtime = pd.read_csv(
    REALTIME_FEATURES_PATH,
    encoding="utf-8-sig",
    dtype={"village_id": str}
)
verified_reports = pd.read_csv(
    VERIFIED_REPORT_FEATURES_PATH,
    encoding="utf-8-sig",
    dtype={"village_id": str},
)
gdf["village_id"] = gdf["village_id"].astype(str)
realtime["village_id"] = realtime["village_id"].astype(str)

run_id = get_active_run_id()

print("基礎主表筆數：", len(gdf))
print("即時特徵筆數：", len(realtime))
print("run_id:", run_id)


print("\n=== 2. 合併即時特徵 ===")

realtime_cols = [
    "village_id",
    "rainfall_realtime_score",
    "landslide_realtime_score",
    "road_realtime_score",
    "realtime_event_score",
]

missing_realtime_cols = [c for c in realtime_cols if c not in realtime.columns]

if missing_realtime_cols:
    raise ValueError(f"即時特徵缺少欄位：{missing_realtime_cols}")

gdf = gdf.merge(
    realtime[realtime_cols],
    on="village_id",
    how="left",
)

for col in realtime_cols:
    if col != "village_id":
        gdf[col] = gdf[col].fillna(0).astype(float)

print("合併後筆數：", len(gdf))
print("realtime_event_score 最大值：", gdf["realtime_event_score"].max())

print("\n=== 3. 合併已驗證民眾通報特徵 ===")

report_feature_cols = [
    "village_id",
    "verified_report_count_6h",
    "verified_report_count_24h",
    "verified_report_severity_sum_6h",
    "verified_report_severity_sum_24h",
    "verified_report_max_severity_6h",
    "verified_report_max_severity_24h",
    "report_data_source",
    "report_feature_run_id",
    "report_feature_generated_at",
]

missing_report_cols = [
    column
    for column in report_feature_cols
    if column not in verified_reports.columns
]

if missing_report_cols:
    raise ValueError(
        "已驗證通報特徵缺少欄位："
        f"{missing_report_cols}"
    )

verified_reports["village_id"] = (
    verified_reports["village_id"].astype(str)
)

gdf = gdf.merge(
    verified_reports[report_feature_cols],
    on="village_id",
    how="left",
)

numeric_report_cols = [
    "verified_report_count_6h",
    "verified_report_count_24h",
    "verified_report_severity_sum_6h",
    "verified_report_severity_sum_24h",
    "verified_report_max_severity_6h",
    "verified_report_max_severity_24h",
]

for column in numeric_report_cols:
    gdf[column] = (
        gdf[column]
        .fillna(0)
        .astype(float)
    )

gdf["report_data_source"] = (
    gdf["report_data_source"]
    .fillna("verified_human_reviewed_reports")
)

gdf["report_feature_run_id"] = (
    gdf["report_feature_run_id"]
    .fillna(run_id)
)

gdf["report_feature_generated_at"] = (
    gdf["report_feature_generated_at"]
    .fillna("")
)

# Live pipeline 不再混用舊 mock reports。
gdf["report_count_6h"] = (
    gdf["verified_report_count_6h"]
)

gdf["report_count_24h"] = (
    gdf["verified_report_count_24h"]
)

print(
    "verified_report_count_24h 總數：",
    int(gdf["verified_report_count_24h"].sum()),
)

print("\n=== 3.5. 檢查必要欄位 ===")

required_columns = [
    "village_id",
    "county_name",
    "town_name",
    "village_name",
    "population_total",
    "elderly_ratio",
    "static_risk_score",
    "sensor_gap_score",
    "sensor_realtime_score",
    "realtime_event_score",
    "rainfall_realtime_score",
    "landslide_realtime_score",
    "road_realtime_score",
    "report_count_6h",
    "report_count_24h",
    "geometry",
]

missing = [c for c in required_columns if c not in gdf.columns]

if missing:
    raise ValueError(f"缺少必要欄位：{missing}")

print("必要欄位都有，可以繼續。")


print("\n=== 4. 計算即時版 base_risk_score ===")

numeric_cols = [
    "static_risk_score",
    "sensor_gap_score",
    "sensor_realtime_score",
    "realtime_event_score",
    "report_count_6h",
    "report_count_24h",
]

for col in numeric_cols:
    gdf[col] = gdf[col].fillna(0).astype(float)

print("\n=== 5. 使用共用公式計算即時沉默風險 ===")

gdf = apply_silent_risk_scoring(gdf)

gdf["silent_reason"] = gdf.apply(
    build_silent_reason,
    axis=1,
)

gdf["realtime_run_id"] = run_id

print("risk_evidence_score 統計：")
print(gdf["risk_evidence_score"].describe())

print("\nobservation_gap_score 統計：")
print(gdf["observation_gap_score"].describe())


print("silent_risk_score 統計：")
print(gdf["silent_risk_score"].describe())

print("\nsilent_risk_level 分布：")
print(gdf["silent_risk_level"].value_counts())


print("\n沉默風險最高前 20 個村里：")

top_cols = [
    "village_id",
    "county_name",
    "town_name",
    "village_name",
    "static_risk_score",
    "sensor_gap_score",
    "realtime_event_score",
    "report_count_6h",
    "report_count_24h",
    "base_risk_score",
    "silence_factor",
    "silent_risk_score",
    "silent_risk_level",
    "silent_reason",
]

print(
    gdf[top_cols]
    .sort_values("silent_risk_score", ascending=False)
    .head(20)
    .to_string(index=False)
)


print("\n=== 6. 輸出 latest 與 history ===")

history_dir = OUTPUT_HISTORY_ROOT / run_id
OUTPUT_LATEST_DIR.mkdir(parents=True, exist_ok=True)
history_dir.mkdir(parents=True, exist_ok=True)

latest_geojson = OUTPUT_LATEST_DIR / "silent_risk.geojson"
latest_csv = OUTPUT_LATEST_DIR / "silent_risk.csv"
latest_json = OUTPUT_LATEST_DIR / "silent_risk.json"

history_geojson = history_dir / "silent_risk.geojson"
history_csv = history_dir / "silent_risk.csv"
history_json = history_dir / "silent_risk.json"

gdf.to_file(latest_geojson, driver="GeoJSON")
gdf.to_file(history_geojson, driver="GeoJSON")

gdf.drop(columns=["geometry"]).to_csv(
    latest_csv,
    index=False,
    encoding="utf-8-sig",
)

gdf.drop(columns=["geometry"]).to_csv(
    history_csv,
    index=False,
    encoding="utf-8-sig",
)


json_columns = [
    "village_id",
    "county_name",
    "town_name",
    "village_name",
    "population_total",
    "elderly_ratio",
    "static_risk_score",
    "sensor_gap_score",
    "sensor_realtime_score",
    "rainfall_realtime_score",
    "landslide_realtime_score",
    "road_realtime_score",
    "realtime_event_score",
    "report_count_6h",
    "report_count_24h",
    "base_risk_score",
    "report_activity_score",
    "silence_factor",
    "silent_risk_score",
    "silent_risk_level",
    "silent_reason",
    "realtime_run_id",
    "verified_report_count_6h",
    "verified_report_count_24h",
    "verified_report_severity_sum_6h",
    "verified_report_severity_sum_24h",
    "verified_report_max_severity_6h",
    "verified_report_max_severity_24h",
    "report_data_source",
    "report_feature_run_id",
    "report_feature_generated_at",
    "risk_evidence_score",
    "observation_gap_score",
    "recent_report_score",
    "older_report_score",
    "silent_risk_rule_score",
    "silent_risk_nn_score",
    "scoring_mode",
    "model_status",
]

json_df = (
    gdf[json_columns]
    .sort_values("silent_risk_score", ascending=False)
    .copy()
)

records = []

for record in json_df.to_dict(orient="records"):
    records.append({
        key: make_json_serializable(value)
        for key, value in record.items()
    })

with open(latest_json, "w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)

with open(history_json, "w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)

print("完成：", latest_geojson)
print("完成：", latest_csv)
print("完成：", latest_json)
print("完成：", history_geojson)
print("完成：", history_csv)
print("完成：", history_json)

mark_scoring_complete(
    run_id=run_id,
    outputs={
        "silent_risk_json": str(
            latest_json.relative_to(PROJECT_ROOT)
        ),
        "silent_risk_csv": str(
            latest_csv.relative_to(PROJECT_ROOT)
        ),
        "silent_risk_geojson": str(
            latest_geojson.relative_to(PROJECT_ROOT)
        ),
        "verified_report_features_csv": str(
            VERIFIED_REPORT_FEATURES_PATH.relative_to(
                PROJECT_ROOT
            )
        ),
        "verified_incidents_json": str(
            VERIFIED_INCIDENTS_PATH.relative_to(
                PROJECT_ROOT
            )
        ),
    },
)

print("完成 manifest：outputs/latest/run_manifest.json")