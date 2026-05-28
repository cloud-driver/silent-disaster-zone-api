from pathlib import Path
import geopandas as gpd


folder = Path("data/raw/debris_flow")

print("=== 1. 檢查資料夾是否存在 ===")

if not folder.exists():
    raise FileNotFoundError(f"找不到資料夾：{folder}")

files = sorted([p for p in folder.iterdir() if p.is_file()])

print("資料夾：", folder)
print("檔案數量：", len(files))

if len(files) == 0:
    raise FileNotFoundError("debris_flow 資料夾是空的，請先把土石流資料放進來。")


print("\n=== 2. 列出檔案 ===")

for file in files:
    size_mb = file.stat().st_size / 1024 / 1024
    print(f"{file.name}  ({size_mb:.2f} MB)")


print("\n=== 3. 嘗試讀取可用的空間資料 ===")

for file in files:
    suffix = file.suffix.lower()

    if suffix not in [".shp", ".geojson", ".json", ".kml"]:
        continue

    print("\n--------------------------------")
    print("檔案：", file.name)
    print("副檔名：", suffix)

    try:
        gdf = gpd.read_file(file)

        print("可用 geopandas 讀取：是")
        print("資料筆數：", len(gdf))
        print("CRS：", gdf.crs)
        print("欄位：", gdf.columns.tolist())

        print("geometry 類型：")
        print(gdf.geometry.geom_type.value_counts())

        print("bounds：")
        print(gdf.total_bounds)

        print("前 5 筆屬性資料：")
        print(gdf.head(5).drop(columns="geometry", errors="ignore"))

        print("\n空值數量：")
        print(gdf.drop(columns="geometry", errors="ignore").isna().sum())

    except Exception as e:
        print("可用 geopandas 讀取：否")
        print("錯誤：", e)


print("\n=== 檢查完成 ===")