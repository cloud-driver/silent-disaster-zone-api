from pathlib import Path
import pandas as pd


input_path = Path("data/raw/population/opendata11504M030.csv")
output_path = Path("data/processed/population_standardized.csv")


def read_csv_with_fallback(path):
    encodings = ["utf-8-sig", "utf-8", "big5", "cp950"]

    last_error = None

    for encoding in encodings:
        try:
            df = pd.read_csv(
                path,
                encoding=encoding,
                dtype={"區域別代碼": str}
            )
            print(f"成功使用編碼：{encoding}")
            return df
        except Exception as e:
            last_error = e
            print(f"使用 {encoding} 失敗：{e}")

    raise last_error


def clean_text(value):
    return (
        str(value)
        .strip()
        .replace("　", "")
        .replace(" ", "")
        .replace("臺", "台")
    )


print("=== 1. 讀取人口資料 ===")

if not input_path.exists():
    raise FileNotFoundError(f"找不到檔案：{input_path}")

df = read_csv_with_fallback(input_path)

print("資料筆數：", len(df))
print("欄位數量：", len(df.columns))


print("\n=== 2. 檢查必要欄位 ===")

required_columns = [
    "區域別代碼",
    "區域別",
    "村里",
    "戶數",
    "人口數",
]

missing_columns = [col for col in required_columns if col not in df.columns]

if missing_columns:
    raise ValueError(f"缺少必要欄位：{missing_columns}")

print("必要欄位都有，可以繼續。")


print("\n=== 3. 找出 65 歲以上欄位 ===")

elderly_columns = []

for age in range(65, 100):
    elderly_columns.append(f"{age}歲-男")
    elderly_columns.append(f"{age}歲-女")

elderly_columns.append("100歲以上-男")
elderly_columns.append("100歲以上-女")

missing_elderly_columns = [col for col in elderly_columns if col not in df.columns]

if missing_elderly_columns:
    raise ValueError(f"缺少高齡人口欄位：{missing_elderly_columns}")

print("65歲以上欄位數量：", len(elderly_columns))
print("前幾個高齡欄位：", elderly_columns[:6])
print("最後幾個高齡欄位：", elderly_columns[-6:])


print("\n=== 4. 整理欄位與計算高齡人口 ===")

numeric_columns = ["戶數", "人口數"] + elderly_columns

for col in numeric_columns:
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

result = pd.DataFrame()

result["village_id"] = df["區域別代碼"].astype(str).str.strip()
result["region_name"] = df["區域別"].apply(clean_text)
result["village_name_population"] = df["村里"].apply(clean_text)
result["household_count"] = df["戶數"].astype(int)
result["population_total"] = df["人口數"].astype(int)
result["elderly_population"] = df[elderly_columns].sum(axis=1).astype(int)

result["elderly_ratio"] = (
    result["elderly_population"] / result["population_total"].replace(0, pd.NA)
).fillna(0)


print("整理後欄位：", result.columns.tolist())
print("前 10 筆：")
print(result.head(10))


print("\n=== 5. 基本品質檢查 ===")

print("village_id 空值數：", result["village_id"].isna().sum())
print("village_id 重複數：", result["village_id"].duplicated().sum())
print("人口數為 0 的筆數：", (result["population_total"] == 0).sum())

print("elderly_ratio 最小值：", result["elderly_ratio"].min())
print("elderly_ratio 最大值：", result["elderly_ratio"].max())

if result["village_id"].duplicated().sum() > 0:
    print("重複的 village_id：")
    print(result[result["village_id"].duplicated(keep=False)].sort_values("village_id"))


print("\n=== 6. 輸出標準化人口資料 ===")

output_path.parent.mkdir(parents=True, exist_ok=True)

result.to_csv(
    output_path,
    index=False,
    encoding="utf-8-sig"
)

print("完成：", output_path)