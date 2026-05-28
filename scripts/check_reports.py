from pathlib import Path
import json
import pandas as pd


input_path = Path("data/raw/reports/reports_mock.json")


print("=== 1. 讀取通報資料 ===")

if not input_path.exists():
    raise FileNotFoundError(f"找不到檔案：{input_path}")

with open(input_path, "r", encoding="utf-8") as f:
    data = json.load(f)

if not isinstance(data, list):
    raise ValueError("通報資料最外層應該是 list")

df = pd.DataFrame(data)

print("通報筆數：", len(df))
print("欄位：", df.columns.tolist())
print(df.to_string(index=False))


print("\n=== 2. 檢查必要欄位 ===")

required_columns = [
    "report_id",
    "source",
    "report_type",
    "severity",
    "created_at",
    "lon",
    "lat",
    "description",
]

missing_columns = [col for col in required_columns if col not in df.columns]

if missing_columns:
    raise ValueError(f"缺少必要欄位：{missing_columns}")

print("必要欄位都有，可以繼續。")


print("\n=== 3. 檢查資料型態 ===")

df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
df["severity"] = pd.to_numeric(df["severity"], errors="coerce")
df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")

print("lon 缺失數：", df["lon"].isna().sum())
print("lat 缺失數：", df["lat"].isna().sum())
print("severity 缺失數：", df["severity"].isna().sum())
print("created_at 缺失數：", df["created_at"].isna().sum())


print("\n=== 4. 檢查座標範圍 ===")

print("lon min/max:", df["lon"].min(), df["lon"].max())
print("lat min/max:", df["lat"].min(), df["lat"].max())

print("\n=== 檢查完成 ===")