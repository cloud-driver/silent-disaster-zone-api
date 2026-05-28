from pathlib import Path
import geopandas as gpd


input_path = Path("data/processed/villages_hualien_with_flood.geojson")

output_geojson_path = Path("data/processed/villages_hualien_with_flood_final.geojson")
output_csv_path = Path("data/processed/villages_hualien_with_flood_final.csv")


def minmax_normalize(series):
    series = series.fillna(0).astype(float)

    min_value = series.min()
    max_value = series.max()

    if max_value == min_value:
        return series * 0

    return ((series - min_value) / (max_value - min_value)).clip(0, 1)


print("=== 1. 讀取村里 + 淹水特徵資料 ===")

gdf = gpd.read_file(input_path)

print("資料筆數：", len(gdf))
print("CRS：", gdf.crs)
print("欄位：", gdf.columns.tolist())


print("\n=== 2. 檢查必要欄位 ===")

required_columns = [
    "village_id",
    "county_name",
    "town_name",
    "village_name",
    "population_total",
    "elderly_ratio",
    "village_area_m2",
    "flood_area_m2",
    "flood_area_ratio",
    "flood_weighted_score",
    "flood_risk",
    "max_flood_class",
    "geometry",
]

missing_columns = [col for col in required_columns if col not in gdf.columns]

if missing_columns:
    raise ValueError(f"缺少必要欄位：{missing_columns}")

print("必要欄位都有，可以繼續。")


print("\n=== 3. 建立淹水模型欄位 ===")

# 原本的 flood_risk 保留成 raw，代表「面積加權暴露比例」
gdf["flood_risk_raw"] = gdf["flood_risk"].fillna(0).astype(float)

# 相對化後給後面的總風險模型使用
gdf["flood_risk_model"] = minmax_normalize(gdf["flood_risk_raw"])

# 是否有淹水潛勢交集
gdf["has_flood_potential"] = (gdf["flood_area_m2"].fillna(0) > 0).astype(int)

# 最大淹水等級轉成 0~1，保留當輔助欄位
gdf["max_flood_class_score"] = (
    gdf["max_flood_class"].fillna(0).astype(float) / 5
).clip(0, 1)


print("flood_risk_raw 統計：")
print(gdf["flood_risk_raw"].describe())

print("\nflood_risk_model 統計：")
print(gdf["flood_risk_model"].describe())


print("\n=== 4. 品質檢查 ===")

print("村里數：", len(gdf))
print("有淹水潛勢村里數：", int(gdf["has_flood_potential"].sum()))
print("無淹水潛勢村里數：", int((gdf["has_flood_potential"] == 0).sum()))
print("flood_risk_raw 缺失數：", gdf["flood_risk_raw"].isna().sum())
print("flood_risk_model 缺失數：", gdf["flood_risk_model"].isna().sum())
print("geometry 無效數：", int((~gdf.geometry.is_valid).sum()))
print("geometry 空值數：", int(gdf.geometry.is_empty.sum()))


print("\n淹水模型風險最高前 10 個村里：")
print(
    gdf[
        [
            "village_id",
            "county_name",
            "town_name",
            "village_name",
            "flood_area_ratio",
            "flood_risk_raw",
            "flood_risk_model",
            "max_flood_class",
            "max_flood_class_score",
        ]
    ]
    .sort_values("flood_risk_model", ascending=False)
    .head(10)
    .to_string(index=False)
)


print("\n=== 5. 輸出 final 檔案 ===")

output_geojson_path.parent.mkdir(parents=True, exist_ok=True)

gdf.to_file(output_geojson_path, driver="GeoJSON")

gdf.drop(columns=["geometry"]).to_csv(
    output_csv_path,
    index=False,
    encoding="utf-8-sig"
)

print("完成：", output_geojson_path)
print("完成：", output_csv_path)