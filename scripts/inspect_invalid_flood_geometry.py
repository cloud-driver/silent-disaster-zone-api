from pathlib import Path
import geopandas as gpd
from shapely.validation import explain_validity


input_path = Path("data/processed/flood_350mm_24hr_hualien.geojson")

print("=== 1. 讀取花蓮淹水潛勢資料 ===")

gdf = gpd.read_file(input_path)

print("資料筆數：", len(gdf))
print("CRS：", gdf.crs)


print("\n=== 2. 找出無效 geometry ===")

invalid = gdf[~gdf.geometry.is_valid].copy()

print("無效 geometry 數量：", len(invalid))

if len(invalid) > 0:
    print("\n前 10 筆無效 geometry：")

    for idx, row in invalid.head(10).iterrows():
        print("--------------------------------")
        print("index:", idx)
        print("town_name:", row["town_name"])
        print("flood_depth:", row["flood_depth"])
        print("flood_class:", row["flood_class"])
        print("原因:", explain_validity(row.geometry))


print("\n=== 檢查完成 ===")