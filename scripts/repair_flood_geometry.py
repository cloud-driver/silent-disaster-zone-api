from pathlib import Path
import geopandas as gpd


input_path = Path("data/processed/flood_350mm_24hr_hualien.geojson")

output_geojson_path = Path("data/processed/flood_350mm_24hr_hualien_final.geojson")
output_csv_path = Path("data/processed/flood_350mm_24hr_hualien_final.csv")


def repair_geometry(geometry):
    """
    修復無效 geometry。

    優先使用 make_valid。
    如果環境不支援，就用 buffer(0)。
    """
    if geometry is None or geometry.is_empty:
        return geometry

    if geometry.is_valid:
        return geometry

    try:
        from shapely.validation import make_valid
        return make_valid(geometry)
    except Exception:
        return geometry.buffer(0)


print("=== 1. 讀取花蓮淹水潛勢資料 ===")

gdf = gpd.read_file(input_path)

print("原始筆數：", len(gdf))
print("原始 CRS：", gdf.crs)
print("修復前無效 geometry 數量：", (~gdf.geometry.is_valid).sum())


print("\n=== 2. 修復 geometry ===")

gdf["geometry"] = gdf["geometry"].apply(repair_geometry)

print("修復後無效 geometry 數量：", (~gdf.geometry.is_valid).sum())
print("修復後空 geometry 數量：", gdf.geometry.is_empty.sum())


print("\n=== 3. explode MultiGeometry ===")

# make_valid 有時候會產生 GeometryCollection。
# explode 可以把混合幾何拆開，讓後面比較好處理。
gdf = gdf.explode(index_parts=False).reset_index(drop=True)

print("explode 後筆數：", len(gdf))
print("explode 後 geometry 類型：")
print(gdf.geometry.geom_type.value_counts())


print("\n=== 4. 只保留 Polygon / MultiPolygon ===")

allowed_types = ["Polygon", "MultiPolygon"]

before_count = len(gdf)

gdf = gdf[gdf.geometry.geom_type.isin(allowed_types)].copy()

after_count = len(gdf)

print("過濾前筆數：", before_count)
print("過濾後筆數：", after_count)
print("被排除筆數：", before_count - after_count)


print("\n=== 5. 最終檢查 ===")

print("最終無效 geometry 數量：", (~gdf.geometry.is_valid).sum())
print("最終空 geometry 數量：", gdf.geometry.is_empty.sum())
print("最終 CRS：", gdf.crs)
print("最終 bounds：", gdf.total_bounds)

print("淹水深度分類：")
print(gdf["flood_depth"].value_counts().sort_index())

print("淹水等級分類：")
print(gdf["flood_class"].value_counts().sort_index())


print("\n=== 6. 輸出修復後資料 ===")

output_geojson_path.parent.mkdir(parents=True, exist_ok=True)

gdf.to_file(output_geojson_path, driver="GeoJSON")

gdf.drop(columns=["geometry"]).to_csv(
    output_csv_path,
    index=False,
    encoding="utf-8-sig"
)

print("完成：", output_geojson_path)
print("完成：", output_csv_path)