from pathlib import Path
import json
import geopandas as gpd


input_path = Path("data/processed/villages_hualien_with_reports.geojson")

output_dir = Path("outputs")
output_geojson_path = output_dir / "silent_risk.geojson"
output_csv_path = output_dir / "silent_risk.csv"
output_json_path = output_dir / "silent_risk.json"


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


print("\n=== 3. 補齊數值欄位 ===")

numeric_cols = [
    "static_risk_score",
    "sensor_gap_score",
    "sensor_realtime_score",
    "report_count_6h",
    "report_count_24h",
]

for col in numeric_cols:
    gdf[col] = gdf[col].fillna(0).astype(float)


print("\n=== 4. 計算 base_risk_score ===")

gdf["base_risk_score"] = (
    0.55 * gdf["static_risk_score"]
    + 0.25 * gdf["sensor_gap_score"]
    + 0.20 * gdf["sensor_realtime_score"]
).clip(0, 1)

print("base_risk_score 統計：")
print(gdf["base_risk_score"].describe())


print("\n=== 5. 計算通報活動與沉默係數 ===")

gdf["has_report_6h"] = (gdf["report_count_6h"] > 0).astype(int)
gdf["has_report_24h"] = (gdf["report_count_24h"] > 0).astype(int)

gdf["report_activity_score"] = (
    0.7 * gdf["has_report_6h"]
    + 0.3 * gdf["has_report_24h"]
).clip(0, 1)

gdf["silence_factor"] = (1 - gdf["report_activity_score"]).clip(0, 1)

gdf["silent_risk_score"] = (
    gdf["base_risk_score"] * gdf["silence_factor"]
).clip(0, 1)

gdf["silent_risk_level"] = gdf["silent_risk_score"].apply(assign_level)
gdf["silent_reason"] = gdf.apply(build_silent_reason, axis=1)


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
    "report_activity_score",
    "silence_factor",
    "silent_risk_score",
    "silent_risk_level",
    "silent_reason",
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