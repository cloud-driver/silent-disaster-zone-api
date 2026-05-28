from pathlib import Path
import json
import pandas as pd


folder = Path("data/raw/sensors")


def find_candidate_tables(obj, path="root", results=None, max_depth=5):
    """
    從 JSON 裡找「看起來像表格」的 list[dict]。

    很多 API JSON 不一定長這樣：
    [
      {...},
      {...}
    ]

    它可能長這樣：
    {
      "result": {
        "records": [
          {...},
          {...}
        ]
      }
    }

    所以我們遞迴往下找 list of dict。
    """
    if results is None:
        results = []

    if max_depth < 0:
        return results

    if isinstance(obj, list):
        if len(obj) > 0 and isinstance(obj[0], dict):
            results.append((path, obj))
        else:
            # 如果是 list 裡面包其他東西，也繼續看前幾個
            for i, item in enumerate(obj[:3]):
                find_candidate_tables(item, f"{path}[{i}]", results, max_depth - 1)

    elif isinstance(obj, dict):
        for key, value in obj.items():
            find_candidate_tables(value, f"{path}.{key}", results, max_depth - 1)

    return results


def print_dataframe_preview(df):
    print("資料筆數：", len(df))
    print("欄位數量：", len(df.columns))
    print("欄位：")
    print(df.columns.tolist())

    print("\n前 5 筆：")
    print(df.head(5).to_string(index=False))

    print("\n空值數量前 20 欄：")
    print(df.isna().sum().head(20))

    possible_lon_cols = [
        "lon", "lng", "longitude", "Longitude", "經度", "TWD97Lon", "WGS84Lon",
        "stationLon", "StationLon", "locationLon"
    ]

    possible_lat_cols = [
        "lat", "latitude", "Latitude", "緯度", "TWD97Lat", "WGS84Lat",
        "stationLat", "StationLat", "locationLat"
    ]

    possible_time_cols = [
        "time", "Time", "datetime", "DateTime", "obsTime", "ObsTime",
        "觀測時間", "資料時間", "updateTime"
    ]

    possible_value_cols = [
        "value", "Value", "雨量", "水位", "流量", "淹水深度",
        "rain", "rainfall", "waterLevel", "WaterLevel", "flow", "Flow"
    ]

    lon_found = [c for c in possible_lon_cols if c in df.columns]
    lat_found = [c for c in possible_lat_cols if c in df.columns]
    time_found = [c for c in possible_time_cols if c in df.columns]
    value_found = [c for c in possible_value_cols if c in df.columns]

    print("\n可能的經度欄位：", lon_found)
    print("可能的緯度欄位：", lat_found)
    print("可能的時間欄位：", time_found)
    print("可能的數值欄位：", value_found)


print("=== 1. 檢查 sensors 資料夾 ===")

if not folder.exists():
    raise FileNotFoundError(f"找不到資料夾：{folder}")

files = sorted([p for p in folder.rglob("*") if p.is_file() and p.name != ".DS_Store"])

print("資料夾：", folder)
print("檔案數量：", len(files))

if len(files) == 0:
    raise FileNotFoundError("data/raw/sensors 是空的，請先把感測器資料放進去。")


print("\n=== 2. 列出檔案 ===")

for file in files:
    size_mb = file.stat().st_size / 1024 / 1024
    print(f"{file}  ({size_mb:.2f} MB)")


print("\n=== 3. 逐一檢查檔案 ===")

for file in files:
    suffix = file.suffix.lower()

    print("\n================================================")
    print("檔案：", file)
    print("副檔名：", suffix)

    if suffix == ".json":
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)

            print("JSON 讀取成功")
            print("最外層型態：", type(data))

            if isinstance(data, dict):
                print("最外層 keys：", list(data.keys())[:30])

            tables = find_candidate_tables(data)

            print("找到候選表格數量：", len(tables))

            if len(tables) == 0:
                print("找不到 list[dict] 結構，請手動檢查 JSON。")
                continue

            # 選資料筆數最多的 list[dict]
            tables = sorted(tables, key=lambda x: len(x[1]), reverse=True)
            best_path, best_rows = tables[0]

            print("選用候選表格路徑：", best_path)
            print("候選表格筆數：", len(best_rows))

            df = pd.DataFrame(best_rows)
            print_dataframe_preview(df)

        except Exception as e:
            print("JSON 讀取失敗：", e)

    elif suffix == ".csv":
        success = False
        last_error = None

        for encoding in ["utf-8-sig", "utf-8", "big5", "cp950"]:
            try:
                df = pd.read_csv(file, encoding=encoding)
                print(f"CSV 讀取成功，encoding={encoding}")
                print_dataframe_preview(df)
                success = True
                break
            except Exception as e:
                last_error = e

        if not success:
            print("CSV 讀取失敗：", last_error)

    else:
        print("暫時不處理這種檔案格式。")


print("\n=== 檢查完成 ===")