from pathlib import Path
import geopandas as gpd


input_path = Path("data/processed/villages_hualien_with_sensors.geojson")

output_geojson_path = Path("data/processed/villages_hualien_with_sensor_gap.geojson")
output_csv_path = Path("data/processed/villages_hualien_with_sensor_gap.csv")


def assign_sensor_gap_level(row):
    if row["sensor_gap_score"] >= 0.75:
        return "critical"
    if row["sensor_gap_score"] >= 0.55:
        return "high"
    if row["sensor_gap_score"] >= 0.35:
        return "medium"
    return "low"


def build_sensor_gap_reason(row):
    reasons = []

    if row["has_any_sensor"] == 0:
        reasons.append("村里內無任何感測器覆蓋")
    elif row["has_flood_sensor"] == 0 and row["has_rainfall_sensor"] == 0:
        reasons.append("村里內缺少淹水與雨量感測器")
    elif row["has_flood_sensor"] == 0:
        reasons.append("村里內缺少淹水感測器")
    elif row["has_rainfall_sensor"] == 0:
        reasons.append("村里內缺少雨量感測器")
    else:
        reasons.append("村里內具基本感測器覆蓋")

    return reasons


print("=== 1. 讀取村里 + 感測器資料 ===")

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
    "static_risk_score",
    "static_risk_level",
    "sensor_count",
    "flood_sensor_count",
    "rainfall_sensor_count",
    "max_flood_depth_cm",
    "max_rainfall_mm",
    "sensor_realtime_score",
    "geometry",
]

missing_columns = [col for col in required_columns if col not in gdf.columns]

if missing_columns:
    raise ValueError(f"缺少必要欄位：{missing_columns}")

print("必要欄位都有，可以繼續。")


print("\n=== 3. 建立感測器覆蓋缺口欄位 ===")

gdf["has_any_sensor"] = (gdf["sensor_count"].fillna(0) > 0).astype(int)
gdf["has_flood_sensor"] = (
    gdf["flood_sensor_count"].fillna(0) > 0
).astype(int)
gdf["has_rainfall_sensor"] = (
    gdf["rainfall_sensor_count"].fillna(0) > 0
).astype(int)

# 感測器缺口只描述「觀測是否不足」，
# 不再直接使用 static_risk_score，避免重複放大靜態風險。
gdf["sensor_gap_score"] = (
    0.50 * (1 - gdf["has_any_sensor"])
    + 0.30 * (1 - gdf["has_flood_sensor"])
    + 0.20 * (1 - gdf["has_rainfall_sensor"])
).clip(0, 1)

# 水文相關觀測缺口，保留給後續分析使用。
gdf["hydro_sensor_gap_score"] = (
    0.60 * (1 - gdf["has_flood_sensor"])
    + 0.40 * (1 - gdf["has_rainfall_sensor"])
).clip(0, 1)

gdf["sensor_gap_level"] = gdf.apply(assign_sensor_gap_level, axis=1)
gdf["sensor_gap_reason"] = gdf.apply(build_sensor_gap_reason, axis=1)


print("\n=== 4. 結果摘要 ===")

print("村里總數：", len(gdf))
print("有任何感測器村里數：", int(gdf["has_any_sensor"].sum()))
print("無任何感測器村里數：", int((gdf["has_any_sensor"] == 0).sum()))
print("有淹水感測器村里數：", int(gdf["has_flood_sensor"].sum()))
print("有雨量感測器村里數：", int(gdf["has_rainfall_sensor"].sum()))

print("\nsensor_gap_score 統計：")
print(gdf["sensor_gap_score"].describe())

print("\nsensor_gap_level 分布：")
print(gdf["sensor_gap_level"].value_counts())


print("\n感測器缺口最高前 15 個村里：")
print(
    gdf[
        [
            "village_id",
            "county_name",
            "town_name",
            "village_name",
            "static_risk_score",
            "static_risk_level",
            "sensor_count",
            "flood_sensor_count",
            "rainfall_sensor_count",
            "sensor_gap_score",
            "sensor_gap_level",
        ]
    ]
    .sort_values("sensor_gap_score", ascending=False)
    .head(15)
    .to_string(index=False)
)


print("\n=== 5. 輸出資料 ===")

output_geojson_path.parent.mkdir(parents=True, exist_ok=True)

gdf.to_file(output_geojson_path, driver="GeoJSON")

gdf.drop(columns=["geometry"]).to_csv(
    output_csv_path,
    index=False,
    encoding="utf-8-sig"
)

print("完成：", output_geojson_path)
print("完成：", output_csv_path)