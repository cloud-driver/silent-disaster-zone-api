from pathlib import Path
import json
import pandas as pd
import geopandas as gpd


folder = Path("data/raw/flood_potential")

print("=== 1. 檢查資料夾是否存在 ===")

if not folder.exists():
    raise FileNotFoundError(f"找不到資料夾：{folder}")

files = sorted([p for p in folder.iterdir() if p.is_file()])

print("資料夾：", folder)
print("檔案數量：", len(files))

if len(files) == 0:
    raise FileNotFoundError("flood_potential 資料夾是空的，請先把淹水潛勢資料放進來。")


print("\n=== 2. 列出檔案 ===")

for file in files:
    size_mb = file.stat().st_size / 1024 / 1024
    print(f"{file.name}  ({size_mb:.2f} MB)")


print("\n=== 3. 嘗試判斷每個檔案格式 ===")

for file in files:
    suffix = file.suffix.lower()
    print("\n--------------------------------")
    print("檔案：", file.name)
    print("副檔名：", suffix)

    if suffix in [".shp", ".geojson", ".json", ".kml"]:
        try:
            gdf = gpd.read_file(file)

            print("可用 geopandas 讀取：是")
            print("資料筆數：", len(gdf))
            print("CRS：", gdf.crs)
            print("欄位：", gdf.columns.tolist())
            print("geometry 類型：")
            print(gdf.geometry.geom_type.value_counts())

            print("範圍 bounds：")
            print(gdf.total_bounds)

            print("前 3 筆：")
            print(gdf.head(3).drop(columns="geometry", errors="ignore"))

        except Exception as e:
            print("可用 geopandas 讀取：否")
            print("錯誤：", e)

            if suffix == ".json":
                try:
                    with open(file, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    print("JSON 可讀取：是")
                    print("JSON 最外層型態：", type(data))

                    if isinstance(data, dict):
                        print("JSON keys：", list(data.keys())[:20])

                        if "type" in data:
                            print("JSON type：", data["type"])

                        if "features" in data:
                            print("features 數量：", len(data["features"]))

                    elif isinstance(data, list):
                        print("list 長度：", len(data))
                        print("第一筆：", data[0] if len(data) > 0 else None)

                except Exception as json_error:
                    print("JSON 也無法讀取：", json_error)

    elif suffix == ".csv":
        try:
            df = pd.read_csv(file, encoding="utf-8-sig")
            print("可用 pandas 讀取：是")
            print("資料筆數：", len(df))
            print("欄位數量：", len(df.columns))
            print("欄位：", df.columns.tolist())
            print("前 3 筆：")
            print(df.head(3))

        except Exception as e:
            print("utf-8-sig 讀取失敗，改試 big5/cp950")

            for enc in ["big5", "cp950", "utf-8"]:
                try:
                    df = pd.read_csv(file, encoding=enc)
                    print(f"成功使用編碼：{enc}")
                    print("資料筆數：", len(df))
                    print("欄位：", df.columns.tolist())
                    print("前 3 筆：")
                    print(df.head(3))
                    break
                except Exception as e2:
                    print(f"{enc} 失敗：", e2)

    else:
        print("暫時不處理這種副檔名。")


print("\n=== 檢查完成 ===")