from pathlib import Path
import geopandas as gpd


shp_path = Path("data/raw/village_boundary/VILLAGE_NLSC_1150407.shp")

print("=== 1. 檢查檔案是否存在 ===")
print("路徑：", shp_path)

if not shp_path.exists():
    raise FileNotFoundError(f"找不到檔案：{shp_path}")

print("檔案存在，可以繼續。")


print("\n=== 2. 讀取 Shapefile ===")
gdf = gpd.read_file(shp_path)

print("讀取成功。")


print("\n=== 3. 檢查基本資訊 ===")
print("資料筆數：", len(gdf))
print("座標系統 CRS：", gdf.crs)


print("\n=== 4. 檢查欄位名稱 ===")
print(gdf.columns.tolist())


print("\n=== 5. 看前 5 筆資料 ===")
print(gdf.head())