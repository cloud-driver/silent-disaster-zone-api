from pathlib import Path
import geopandas as gpd


input_path = Path("data/processed/villages_standardized.geojson")

print("=== 1. 讀取標準化村里資料 ===")

if not input_path.exists():
    raise FileNotFoundError(f"找不到檔案：{input_path}")

gdf = gpd.read_file(input_path)

print("資料筆數：", len(gdf))
print("欄位：", gdf.columns.tolist())
print("CRS：", gdf.crs)


print("\n=== 2. 檢查空值 ===")

check_columns = [
    "village_id",
    "county_name",
    "town_name",
    "village_name",
]

for col in check_columns:
    null_count = gdf[col].isna().sum()
    empty_count = (gdf[col].astype(str).str.strip() == "").sum()
    print(f"{col}: null={null_count}, empty={empty_count}")


print("\n=== 3. 檢查 village_id 是否重複 ===")

duplicate_count = gdf["village_id"].duplicated().sum()

print("重複 village_id 數量：", duplicate_count)

if duplicate_count > 0:
    print("重複的 village_id：")
    print(gdf[gdf["village_id"].duplicated(keep=False)][
        ["village_id", "county_name", "town_name", "village_name"]
    ].sort_values("village_id"))


print("\n=== 4. 檢查 geometry 是否有效 ===")

invalid_count = (~gdf.geometry.is_valid).sum()
empty_geometry_count = gdf.geometry.is_empty.sum()

print("無效 geometry 數量：", invalid_count)
print("空 geometry 數量：", empty_geometry_count)


print("\n=== 5. 檢查縣市列表 ===")

print(gdf["county_name"].value_counts().sort_index())


print("\n=== 檢查完成 ===")