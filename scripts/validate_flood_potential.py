from pathlib import Path
import geopandas as gpd


input_path = Path("data/processed/flood_350mm_24hr_hualien_final.geojson")


print("=== 1. 讀取花蓮淹水潛勢資料 ===")

if not input_path.exists():
    raise FileNotFoundError(f"找不到檔案：{input_path}")

gdf = gpd.read_file(input_path)

print("資料筆數：", len(gdf))
print("CRS：", gdf.crs)
print("欄位：", gdf.columns.tolist())


print("\n=== 2. 檢查 geometry ===")

print("geometry 類型：")
print(gdf.geometry.geom_type.value_counts())

print("無效 geometry 數量：", (~gdf.geometry.is_valid).sum())
print("空 geometry 數量：", gdf.geometry.is_empty.sum())


print("\n=== 3. 檢查欄位空值 ===")

check_columns = [
    "county_name",
    "town_name",
    "flood_depth",
    "flood_class",
]

for col in check_columns:
    null_count = gdf[col].isna().sum()
    empty_count = (gdf[col].astype(str).str.strip() == "").sum()
    print(f"{col}: null={null_count}, empty={empty_count}")


print("\n=== 4. 檢查鄉鎮分布 ===")

print(gdf["town_name"].value_counts().sort_index())


print("\n=== 5. 檢查淹水深度與等級 ===")

print("flood_depth：")
print(gdf["flood_depth"].value_counts().sort_index())

print("\nflood_class：")
print(gdf["flood_class"].value_counts().sort_index())


print("\n=== 6. 簡單檢查 bounds 是否在台灣附近 ===")

print("bounds:", gdf.total_bounds)

minx, miny, maxx, maxy = gdf.total_bounds

if not (119 <= minx <= 123 and 21 <= miny <= 26 and 119 <= maxx <= 123 and 21 <= maxy <= 26):
    print("警告：bounds 看起來不太像 EPSG:4326 的台灣範圍，請檢查 CRS。")
else:
    print("bounds 看起來合理。")


print("\n=== 檢查完成 ===")