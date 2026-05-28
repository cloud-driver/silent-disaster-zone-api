from pathlib import Path
import geopandas as gpd
import pandas as pd


villages_path = Path("data/processed/villages_hualien.geojson")
population_path = Path("data/processed/population_standardized.csv")

output_geojson_path = Path("data/processed/villages_hualien_with_population.geojson")
output_csv_path = Path("data/processed/villages_hualien_with_population.csv")


print("=== 1. 讀取花蓮村里資料 ===")

villages = gpd.read_file(villages_path)
villages["village_id"] = villages["village_id"].astype(str).str.strip()

print("花蓮村里數：", len(villages))
print("村里欄位：", villages.columns.tolist())


print("\n=== 2. 讀取標準化人口資料 ===")

population = pd.read_csv(
    population_path,
    encoding="utf-8-sig",
    dtype={"village_id": str}
)

population["village_id"] = population["village_id"].astype(str).str.strip()

print("人口資料筆數：", len(population))
print("人口欄位：", population.columns.tolist())


print("\n=== 3. 用 village_id 合併 ===")

merged = villages.merge(
    population[
        [
            "village_id",
            "region_name",
            "village_name_population",
            "household_count",
            "population_total",
            "elderly_population",
            "elderly_ratio",
        ]
    ],
    on="village_id",
    how="left"
)

print("合併後筆數：", len(merged))


print("\n=== 4. 檢查有沒有花蓮村里沒接到人口資料 ===")

missing_population = merged[merged["population_total"].isna()].copy()

print("沒接到人口資料的村里數：", len(missing_population))

if len(missing_population) > 0:
    print("沒接到的村里：")
    print(missing_population[
        ["village_id", "county_name", "town_name", "village_name"]
    ].to_string(index=False))


print("\n=== 5. 檢查接到的人口資料是否合理 ===")

matched = merged[merged["population_total"].notna()].copy()

print("成功接到人口資料的村里數：", len(matched))

if len(matched) > 0:
    print("花蓮總人口：", int(matched["population_total"].sum()))
    print("花蓮 65 歲以上人口：", int(matched["elderly_population"].sum()))
    print("平均高齡比例：", matched["elderly_ratio"].mean())

    print("\n高齡比例最高前 10 個村里：")
    print(
        matched[
            [
                "village_id",
                "county_name",
                "town_name",
                "village_name",
                "population_total",
                "elderly_population",
                "elderly_ratio",
            ]
        ]
        .sort_values("elderly_ratio", ascending=False)
        .head(10)
        .to_string(index=False)
    )


print("\n=== 6. 輸出合併結果 ===")

merged.to_file(output_geojson_path, driver="GeoJSON")

merged.drop(columns=["geometry"]).to_csv(
    output_csv_path,
    index=False,
    encoding="utf-8-sig"
)

print("完成：", output_geojson_path)
print("完成：", output_csv_path)