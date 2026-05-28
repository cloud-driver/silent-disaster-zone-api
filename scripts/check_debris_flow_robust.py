from pathlib import Path
import geopandas as gpd


folder = Path("data/raw/debris_flow")

encodings = [
    "utf-8",
    "utf-8-sig",
    "big5",
    "cp950",
    "latin1",
]

print("=== 1. 搜尋所有 .shp 檔案 ===")

shp_files = sorted(folder.rglob("*.shp"))

print("找到 .shp 數量：", len(shp_files))

if len(shp_files) == 0:
    raise FileNotFoundError("找不到任何 .shp 檔案，請檢查 data/raw/debris_flow")


for shp_path in shp_files:
    print("\n================================================")
    print("檔案：", shp_path)
    print("大小 MB：", round(shp_path.stat().st_size / 1024 / 1024, 2))

    success = False
    last_error = None
    gdf = None
    used_encoding = None

    print("\n--- 嘗試不同 encoding 讀取 ---")

    for encoding in encodings:
        try:
            gdf = gpd.read_file(shp_path, encoding=encoding)
            used_encoding = encoding
            success = True
            print(f"成功使用 encoding：{encoding}")
            break
        except Exception as e:
            last_error = e
            print(f"{encoding} 失敗：{e}")

    if not success:
        print("\n讀取失敗。最後錯誤：")
        print(last_error)
        continue

    print("\n--- 讀取結果 ---")
    print("資料筆數：", len(gdf))
    print("CRS：", gdf.crs)
    print("使用 encoding：", used_encoding)
    print("欄位：", gdf.columns.tolist())

    print("\ngeometry 類型：")
    print(gdf.geometry.geom_type.value_counts())

    print("\nbounds：")
    print(gdf.total_bounds)

    print("\n前 5 筆屬性資料：")
    print(gdf.head(5).drop(columns="geometry", errors="ignore"))

    print("\n空值數量：")
    print(gdf.drop(columns="geometry", errors="ignore").isna().sum())

    print("\n無效 geometry 數量：", int((~gdf.geometry.is_valid).sum()))
    print("空 geometry 數量：", int(gdf.geometry.is_empty.sum()))

print("\n=== 檢查完成 ===")