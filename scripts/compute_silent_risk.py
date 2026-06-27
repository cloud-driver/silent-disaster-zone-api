from pathlib import Path
import json
import sys

import geopandas as gpd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.scoring.silent_risk import apply_silent_risk_scoring
from src.runtime.run_manifest import write_batch_manifest


input_path = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "villages_hualien_with_reports.geojson"
)

output_dir = PROJECT_ROOT / "outputs" / "latest"
output_geojson_path = output_dir / "silent_risk.geojson"
output_csv_path = output_dir / "silent_risk.csv"
output_json_path = output_dir / "silent_risk.json"


def build_silent_reason(row):
    reasons = []

    if row["static_risk_score"] >= 0.35:
        reasons.append("靜態災害風險偏高")

    if row["sensor_gap_score"] >= 0.35:
        reasons.append("高風險但感測器覆蓋不足")

    if row["sensor_realtime_score"] > 0:
        reasons.append("即時感測器出現異常值")

    if row["report_count_6h"] == 0:
        reasons.append("近6小時無通報")

    if row["report_count_24h"] == 0:
        reasons.append("近24小時無通報")

    if row["report_count_6h"] > 0:
        reasons.append("近6小時已有通報，沉默風險降低")

    if len(reasons) == 0:
        reasons.append("目前沉默風險較低")

    return "；".join(reasons)


print("=== 1. 讀取村里 + 通報主表 ===")

gdf = gpd.read_file(input_path)

print("資料筆數：", len(gdf))
print("CRS：", gdf.crs)
print("欄位數量：", len(gdf.columns))


print("\n=== 2. 檢查必要欄位 ===")

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
    "report_count_6h",
    "report_count_24h",
    "geometry",
]

missing_columns = [col for col in required_columns if col not in gdf.columns]

if missing_columns:
    raise ValueError(f"缺少必要欄位：{missing_columns}")

print("必要欄位都有，可以繼續。")


print("\n=== 3. 使用共用公式計算批次沉默風險 ===")

gdf = apply_silent_risk_scoring(gdf)

# 批次 pipeline 不應假裝是即時資料。
gdf["realtime_run_id"] = "batch_static"

gdf["silent_reason"] = gdf.apply(
    build_silent_reason,
    axis=1,
)

print("report_activity_score 統計：")
print(gdf["report_activity_score"].describe())

print("\nsilence_factor 統計：")
print(gdf["silence_factor"].describe())

print("\nsilent_risk_score 統計：")
print(gdf["silent_risk_score"].describe())

print("\nsilent_risk_level 分布：")
print(gdf["silent_risk_level"].value_counts())


print("\n=== 6. 沉默風險最高前 20 個村里 ===")

top_cols = [
    "village_id",
    "county_name",
    "town_name",
    "village_name",
    "static_risk_score",
    "sensor_gap_score",
    "sensor_realtime_score",
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


print("\n=== 7. 輸出結果 ===")

output_dir.mkdir(parents=True, exist_ok=True)

gdf.to_file(output_geojson_path, driver="GeoJSON")

gdf.drop(columns=["geometry"]).to_csv(
    output_csv_path,
    index=False,
    encoding="utf-8-sig"
)

def make_json_serializable(value):
    """
    把 pandas / numpy / GeoPandas 裡面 JSON 不認得的型態，
    轉成一般 Python 型態。
    """
    import pandas as pd
    import numpy as np

    if value is None:
        return None

    if pd.isna(value).all() if hasattr(pd.isna(value), "all") else pd.isna(value):
        return None

    if isinstance(value, np.ndarray):
        return value.tolist()

    if isinstance(value, (np.integer,)):
        return int(value)

    if isinstance(value, (np.floating,)):
        return float(value)

    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()

    if isinstance(value, list):
        return [
            make_json_serializable(v)
            for v in value
        ]

    if isinstance(value, dict):
        return {
            str(k): make_json_serializable(v)
            for k, v in value.items()
        }

    return value


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
    "report_count_6h",
    "report_count_24h",
    "base_risk_score",
    "silent_risk_score",
    "silent_risk_level",
    "silent_reason",
    "risk_evidence_score",
    "observation_gap_score",
    "recent_report_score",
    "older_report_score",
    "report_activity_score",
    "silence_factor",
    "silent_risk_rule_score",
    "silent_risk_nn_score",
    "scoring_mode",
    "model_status",
    "realtime_run_id",
]

json_df = (
    gdf[json_columns]
    .sort_values("silent_risk_score", ascending=False)
    .copy()
)

json_records = []

for record in json_df.to_dict(orient="records"):
    clean_record = {
        key: make_json_serializable(value)
        for key, value in record.items()
    }
    json_records.append(clean_record)

with open(output_json_path, "w", encoding="utf-8") as f:
    json.dump(json_records, f, ensure_ascii=False, indent=2)

print("完成：", output_geojson_path)
print("完成：", output_csv_path)
print("完成：", output_json_path)

write_batch_manifest(
    outputs={
        "silent_risk_json": str(
            output_json_path.relative_to(PROJECT_ROOT)
        ),
        "silent_risk_csv": str(
            output_csv_path.relative_to(PROJECT_ROOT)
        ),
        "silent_risk_geojson": str(
            output_geojson_path.relative_to(PROJECT_ROOT)
        ),
    },
)

print("完成 manifest：outputs/latest/run_manifest.json")