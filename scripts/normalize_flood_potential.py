from pathlib import Path
import geopandas as gpd


input_path = Path("data/raw/flood_potential/Flood_350mm_24HR.shp")

output_geojson_path = Path("data/processed/flood_350mm_24hr_hualien.geojson")
output_csv_path = Path("data/processed/flood_350mm_24hr_hualien.csv")

target_county = "花蓮縣"


def clean_text(value):
    return (
        str(value)
        .strip()
        .replace("　", "")
        .replace(" ", "")
        .replace("臺", "台")
    )


print("=== 1. 讀取淹水潛勢 Shapefile ===")

if not input_path.exists():
    raise FileNotFoundError(f"找不到檔案：{input_path}")

gdf = gpd.read_file(input_path)

print("原始資料筆數：", len(gdf))
print("原始 CRS：", gdf.crs)
print("原始欄位：", gdf.columns.tolist())
print("geometry 類型：")
print(gdf.geometry.geom_type.value_counts())


print("\n=== 2. 檢查必要欄位 ===")

required_columns = [
    "flood_dept",
    "Class",
    "CityName",
    "TownName",
    "geometry",
]

missing_columns = [col for col in required_columns if col not in gdf.columns]

if missing_columns:
    raise ValueError(f"缺少必要欄位：{missing_columns}")

if gdf.crs is None:
    raise ValueError("淹水資料缺 CRS，不能繼續處理。")

print("必要欄位都有，可以繼續。")


print("\n=== 3. 清理縣市與鄉鎮名稱 ===")

gdf["CityName"] = gdf["CityName"].apply(clean_text)
gdf["TownName"] = gdf["TownName"].apply(clean_text)

print("縣市列表：")
print(gdf["CityName"].value_counts().sort_index())


print("\n=== 4. 篩選花蓮縣 ===")

hualien = gdf[gdf["CityName"] == target_county].copy()

print(f"{target_county} 淹水圖斑數：", len(hualien))

if len(hualien) == 0:
    raise ValueError(f"找不到 {target_county} 的淹水潛勢資料，請檢查 CityName 欄位。")


print("\n=== 5. 標準化欄位 ===")

hualien = hualien.rename(
    columns={
        "flood_dept": "flood_depth",
        "Class": "flood_class",
        "CityName": "county_name",
        "TownName": "town_name",
    }
)

hualien["flood_depth"] = hualien["flood_depth"].astype(str).str.strip()
hualien["flood_class"] = hualien["flood_class"].astype(int)

hualien = hualien[
    [
        "county_name",
        "town_name",
        "flood_depth",
        "flood_class",
        "geometry",
    ]
]


print("整理後欄位：", hualien.columns.tolist())
print("淹水深度分類：")
print(hualien["flood_depth"].value_counts().sort_index())

print("淹水等級分類：")
print(hualien["flood_class"].value_counts().sort_index())


print("\n=== 6. 轉成 EPSG:4326，方便地圖展示 ===")

hualien_4326 = hualien.to_crs(epsg=4326)

print("轉換後 CRS：", hualien_4326.crs)
print("bounds：", hualien_4326.total_bounds)


print("\n=== 7. 輸出資料 ===")

output_geojson_path.parent.mkdir(parents=True, exist_ok=True)

hualien_4326.to_file(output_geojson_path, driver="GeoJSON")

hualien_4326.drop(columns=["geometry"]).to_csv(
    output_csv_path,
    index=False,
    encoding="utf-8-sig"
)

print("完成：", output_geojson_path)
print("完成：", output_csv_path)