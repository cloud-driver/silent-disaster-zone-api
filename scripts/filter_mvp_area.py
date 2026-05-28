from pathlib import Path
import geopandas as gpd


input_path = Path("data/processed/villages_standardized.geojson")
output_geojson_path = Path("data/processed/villages_hualien.geojson")
output_csv_path = Path("data/processed/villages_hualien.csv")

target_county = "花蓮縣"


print("=== 1. 讀取標準化村里資料 ===")

gdf = gpd.read_file(input_path)

print("全臺村里數：", len(gdf))


print("\n=== 2. 篩選 MVP 範圍 ===")

mvp_gdf = gdf[gdf["county_name"] == target_county].copy()

print(f"{target_county} 村里數：", len(mvp_gdf))

if len(mvp_gdf) == 0:
    raise ValueError(f"找不到 {target_county}，請檢查 county_name 是否一致")


print("\n=== 3. 輸出 GeoJSON ===")

output_geojson_path.parent.mkdir(parents=True, exist_ok=True)
mvp_gdf.to_file(output_geojson_path, driver="GeoJSON")

print("完成：", output_geojson_path)


print("\n=== 4. 輸出 CSV 方便人工檢查 ===")

mvp_gdf.drop(columns=["geometry"]).to_csv(
    output_csv_path,
    index=False,
    encoding="utf-8-sig"
)

print("完成：", output_csv_path)


print("\n=== 5. 前 10 筆 ===")

print(mvp_gdf[
    ["village_id", "county_name", "town_name", "village_name"]
].head(10))