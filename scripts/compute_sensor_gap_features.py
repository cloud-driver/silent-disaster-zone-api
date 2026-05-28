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

    if row["sensor_count"] == 0 and row["static_risk_score"] >= 0.35:
        reasons.append("靜態風險偏高但村里內無感測器覆蓋")

    if row["sensor_count"] > 0:
        reasons.append("村里內已有感測器覆蓋")

    if row["flood_sensor_count"] > 0 and row["max_flood_depth_cm"] == 0:
        reasons.append("淹水感測器目前未偵測到積淹水")

    if row["rainfall_sensor_count"] == 0:
        reasons.append("目前未取得村里內雨量感測器資料")

    if len(reasons) == 0:
        reasons.append("感測器覆蓋缺口較低")

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
gdf["has_flood_sensor"] = (gdf["flood_sensor_count"].fillna(0) > 0).astype(int)
gdf["has_rainfall_sensor"] = (gdf["rainfall_sensor_count"].fillna(0) > 0).astype(int)

# 感測器缺口：靜態風險越高，且沒有感測器，缺口越高
gdf["sensor_gap_score"] = (
    gdf["static_risk_score"].fillna(0) * (1 - gdf["has_any_sensor"])
).clip(0, 1)

# 另一個更嚴格版本：沒有淹水感測器也沒有雨量感測器
gdf["hydro_sensor_gap_score"] = (
    gdf["static_risk_score"].fillna(0)
    * (1 - ((gdf["has_flood_sensor"] | gdf["has_rainfall_sensor"]).astype(int)))
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