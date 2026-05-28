from pathlib import Path
import geopandas as gpd


input_path = Path("data/interim/villages.geojson")
output_path = Path("data/processed/villages_standardized.geojson")


def clean_name(value):
    """
    清理中文地名：
    - 去掉前後空白
    - 把全形空白移除
    - 把「臺」統一成「台」

    這是為了避免後面 join 人口資料時，
    因為「臺北市」和「台北市」這種差異導致接不起來。
    """
    return (
        str(value)
        .strip()
        .replace("　", "")
        .replace(" ", "")
        .replace("臺", "台")
    )


print("=== 1. 讀取 villages.geojson ===")

if not input_path.exists():
    raise FileNotFoundError(f"找不到檔案：{input_path}")

gdf = gpd.read_file(input_path)

print("讀取成功")
print("資料筆數：", len(gdf))
print("原始欄位：", gdf.columns.tolist())
print("CRS：", gdf.crs)


print("\n=== 2. 檢查必要欄位 ===")

required_columns = [
    "VILLCODE",
    "COUNTYNAME",
    "TOWNNAME",
    "VILLNAME",
    "geometry",
]

missing_columns = [col for col in required_columns if col not in gdf.columns]

if missing_columns:
    raise ValueError(f"缺少必要欄位：{missing_columns}")

print("必要欄位都有，可以繼續。")


print("\n=== 3. 重新命名欄位 ===")

gdf = gdf.rename(
    columns={
        "VILLCODE": "village_id",
        "COUNTYNAME": "county_name",
        "TOWNNAME": "town_name",
        "VILLNAME": "village_name",
    }
)


print("\n=== 4. 清理文字欄位 ===")

gdf["village_id"] = gdf["village_id"].astype(str).str.strip()
gdf["county_name"] = gdf["county_name"].apply(clean_name)
gdf["town_name"] = gdf["town_name"].apply(clean_name)
gdf["village_name"] = gdf["village_name"].apply(clean_name)


print("\n=== 5. 只保留後面會用的欄位 ===")

gdf = gdf[
    [
        "village_id",
        "county_name",
        "town_name",
        "village_name",
        "geometry",
    ]
]

print("整理後欄位：", gdf.columns.tolist())
print("前 5 筆：")
print(gdf.head())


print("\n=== 6. 輸出標準化 GeoJSON ===")

output_path.parent.mkdir(parents=True, exist_ok=True)
gdf.to_file(output_path, driver="GeoJSON")

print("完成：", output_path)