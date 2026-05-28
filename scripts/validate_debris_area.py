from pathlib import Path
import geopandas as gpd


input_path = Path("data/processed/debris_area_hualien.geojson")


print("=== 1. 讀取花蓮土石流影響範圍資料 ===")

if not input_path.exists():
    raise FileNotFoundError(f"找不到檔案：{input_path}")

gdf = gpd.read_file(input_path)

print("資料筆數：", len(gdf))
print("CRS：", gdf.crs)
print("欄位：", gdf.columns.tolist())


print("\n=== 2. 檢查 geometry ===")

print("geometry 類型：")
print(gdf.geometry.geom_type.value_counts())

print("無效 geometry 數量：", int((~gdf.geometry.is_valid).sum()))
print("空 geometry 數量：", int(gdf.geometry.is_empty.sum()))


print("\n=== 3. 檢查 bounds ===")

print("bounds:", gdf.total_bounds)

minx, miny, maxx, maxy = gdf.total_bounds

if not (119 <= minx <= 123 and 21 <= miny <= 26 and 119 <= maxx <= 123 and 21 <= maxy <= 26):
    print("警告：bounds 看起來不像台灣 EPSG:4326 範圍，請檢查 CRS。")
else:
    print("bounds 看起來合理。")


print("\n=== 4. 欄位空值檢查 ===")

for col in gdf.drop(columns=["geometry"]).columns:
    null_count = gdf[col].isna().sum()
    empty_count = (gdf[col].astype(str).str.strip() == "").sum()
    print(f"{col}: null={null_count}, empty={empty_count}")


print("\n=== 5. 前 10 筆資料 ===")

print(gdf.drop(columns=["geometry"]).head(10).to_string(index=False))


print("\n=== 檢查完成 ===")