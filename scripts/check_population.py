from pathlib import Path
import pandas as pd


csv_path = Path("data/raw/population/opendata11504M030.csv")


def read_csv_with_fallback(path):
    """
    嘗試用幾種常見編碼讀 CSV。

    台灣政府開放資料常見：
    - utf-8
    - utf-8-sig
    - big5
    - cp950

    如果第一個讀不進去，就換下一個。
    """
    encodings = ["utf-8-sig", "utf-8", "big5", "cp950"]

    last_error = None

    for encoding in encodings:
        try:
            df = pd.read_csv(path, encoding=encoding)
            print(f"成功使用編碼：{encoding}")
            return df
        except Exception as e:
            last_error = e
            print(f"使用 {encoding} 失敗：{e}")

    raise last_error


print("=== 1. 檢查檔案是否存在 ===")
print("路徑：", csv_path)

if not csv_path.exists():
    raise FileNotFoundError(f"找不到檔案：{csv_path}")

print("檔案存在，可以繼續。")


print("\n=== 2. 讀取人口 CSV ===")
df = read_csv_with_fallback(csv_path)

print("讀取成功。")


print("\n=== 3. 基本資訊 ===")
print("資料筆數：", len(df))
print("欄位數量：", len(df.columns))


print("\n=== 4. 欄位名稱 ===")
print(df.columns.tolist())


print("\n=== 5. 前 10 筆資料 ===")
print(df.head(10))


print("\n=== 6. 每個欄位的資料型態 ===")
print(df.dtypes)


print("\n=== 7. 每個欄位的空值數量 ===")
print(df.isna().sum())