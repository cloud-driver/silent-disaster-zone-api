from pathlib import Path
import geopandas as gpd


input_path = Path("data/processed/villages_hualien_with_flood_debris.geojson")

output_geojson_path = Path("data/processed/villages_hualien_static_risk.geojson")
output_csv_path = Path("data/processed/villages_hualien_static_risk.csv")


def minmax_normalize(series):
    series = series.fillna(0).astype(float)

    min_value = series.min()
    max_value = series.max()

    if max_value == min_value:
        return series * 0

    return ((series - min_value) / (max_value - min_value)).clip(0, 1)


def assign_level(score):
    if score >= 0.75:
        return "critical"
    if score >= 0.55:
        return "high"
    if score >= 0.35:
        return "medium"
    return "low"


def build_static_reason(row):
    reasons = []

    if row["flood_risk_model"] >= 0.5:
        reasons.append("淹水潛勢相對偏高")

    if row["debris_risk_model"] >= 0.5:
        reasons.append("土石流影響範圍相對偏高")

    if row["elderly_ratio"] >= 0.30:
        reasons.append("高齡人口比例偏高")

    if row["has_flood_potential"] == 1:
        reasons.append("村里內有淹水潛勢區")

    if row["has_debris_potential"] == 1:
        reasons.append("村里內有土石流影響範圍")

    if len(reasons) == 0:
        reasons.append("目前靜態風險因子較低")

    return reasons


print("=== 1. 讀取村里 + 淹水 + 土石流主表 ===")

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
    "elderly_population",
    "elderly_ratio",
    "flood_risk_raw",
    "flood_risk_model",
    "has_flood_potential",
    "debris_risk_raw",
    "debris_risk_model",
    "has_debris_potential",
    "geometry",
]

missing_columns = [col for col in required_columns if col not in gdf.columns]

if missing_columns:
    raise ValueError(f"缺少必要欄位：{missing_columns}")

if gdf.crs is None:
    raise ValueError("資料缺 CRS，不能繼續。")

print("必要欄位都有，可以繼續。")


print("\n=== 3. 建立 vulnerability_score ===")

gdf["vulnerability_score"] = minmax_normalize(gdf["elderly_ratio"])

print("elderly_ratio 統計：")
print(gdf["elderly_ratio"].describe())

print("\nvulnerability_score 統計：")
print(gdf["vulnerability_score"].describe())


print("\n=== 4. 建立 hazard_score 與 static_risk_score ===")

gdf["hazard_score"] = (
    0.6 * gdf["flood_risk_model"].fillna(0).astype(float)
    + 0.4 * gdf["debris_risk_model"].fillna(0).astype(float)
).clip(0, 1)

gdf["static_risk_score"] = (
    0.75 * gdf["hazard_score"]
    + 0.25 * gdf["vulnerability_score"]
).clip(0, 1)

gdf["static_risk_level"] = gdf["static_risk_score"].apply(assign_level)
gdf["static_reason"] = gdf.apply(build_static_reason, axis=1)


print("hazard_score 統計：")
print(gdf["hazard_score"].describe())

print("\nstatic_risk_score 統計：")
print(gdf["static_risk_score"].describe())

print("\nstatic_risk_level 分布：")
print(gdf["static_risk_level"].value_counts())


print("\n=== 5. 品質檢查 ===")

check_columns = [
    "vulnerability_score",
    "hazard_score",
    "static_risk_score",
    "static_risk_level",
]

for col in check_columns:
    print(f"{col} 缺失數：", gdf[col].isna().sum())

print("geometry 無效數：", int((~gdf.geometry.is_valid).sum()))
print("geometry 空值數：", int(gdf.geometry.is_empty.sum()))


print("\n靜態風險最高前 15 個村里：")
print(
    gdf[
        [
            "village_id",
            "county_name",
            "town_name",
            "village_name",
            "elderly_ratio",
            "flood_risk_model",
            "debris_risk_model",
            "vulnerability_score",
            "hazard_score",
            "static_risk_score",
            "static_risk_level",
        ]
    ]
    .sort_values("static_risk_score", ascending=False)
    .head(15)
    .to_string(index=False)
)


print("\n=== 6. 輸出資料 ===")

output_geojson_path.parent.mkdir(parents=True, exist_ok=True)

gdf.to_file(output_geojson_path, driver="GeoJSON")

gdf.drop(columns=["geometry"]).to_csv(
    output_csv_path,
    index=False,
    encoding="utf-8-sig"
)

print("完成：", output_geojson_path)
print("完成：", output_csv_path)