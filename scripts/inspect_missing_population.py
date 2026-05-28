from pathlib import Path
import geopandas as gpd
import pandas as pd


merged_path = Path("data/processed/villages_hualien_with_population.geojson")
villages_path = Path("data/processed/villages_hualien.geojson")
population_path = Path("data/processed/population_standardized.csv")

print("=== 1. 讀取合併後資料 ===")

merged = gpd.read_file(merged_path)

missing = merged[merged["population_total"].isna()].copy()

print("沒接到人口資料的筆數：", len(missing))

print("\n=== 2. 沒接到人口資料的完整欄位 ===")
print(missing.drop(columns=["geometry"]).to_string(index=False))


print("\n=== 3. 檢查這些 village_id 是否存在於人口資料 ===")

population = pd.read_csv(
    population_path,
    encoding="utf-8-sig",
    dtype={"village_id": str}
)

for village_id in missing["village_id"]:
    found = population[population["village_id"] == village_id]
    print(f"\n查詢 village_id = {village_id}")
    print("人口資料中筆數：", len(found))

    if len(found) > 0:
        print(found.to_string(index=False))


print("\n=== 4. 檢查 village_name 是 nan 的村里界資料 ===")

villages = gpd.read_file(villages_path)

nan_name = villages[
    villages["village_name"].astype(str).str.lower().isin(["nan", "none", ""])
].copy()

print("村里名稱異常筆數：", len(nan_name))

if len(nan_name) > 0:
    print(nan_name.drop(columns=["geometry"]).to_string(index=False))


print("\n=== 檢查完成 ===")