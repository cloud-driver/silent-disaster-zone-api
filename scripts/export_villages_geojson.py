from pathlib import Path
import geopandas as gpd


input_path = Path("data/raw/village_boundary/VILLAGE_NLSC_1150407.shp")
output_path = Path("data/interim/villages.geojson")

print("=== 1. 讀取村里界 Shapefile ===")
gdf = gpd.read_file(input_path)

print("原始 CRS：", gdf.crs)

if gdf.crs is None:
    raise ValueError("這份 Shapefile 沒有 CRS。請檢查是否有 .prj 檔。")


print("\n=== 2. 轉成 EPSG:4326 ===")
gdf = gdf.to_crs(epsg=4326)

print("轉換後 CRS：", gdf.crs)


print("\n=== 3. 建立輸出資料夾 ===")
output_path.parent.mkdir(parents=True, exist_ok=True)


print("\n=== 4. 輸出 GeoJSON ===")
gdf.to_file(output_path, driver="GeoJSON")

print("完成：", output_path)