from pathlib import Path
import geopandas as gpd


input_path = Path("data/processed/villages_hualien_with_population.geojson")

output_geojson_path = Path("data/processed/villages_hualien_population_final.geojson")
output_csv_path = Path("data/processed/villages_hualien_population_final.csv")
excluded_csv_path = Path("data/processed/villages_hualien_population_excluded.csv")


print("=== 1. 讀取花蓮村里 + 人口資料 ===")

gdf = gpd.read_file(input_path)

print("原始筆數：", len(gdf))


print("\n=== 2. 標記不可用資料 ===")

invalid_name_mask = (
    gdf["village_name"].astype(str).str.lower().isin(["nan", "none", ""])
)

missing_population_mask = gdf["population_total"].isna()

exclude_mask = invalid_name_mask | missing_population_mask

excluded = gdf[exclude_mask].copy()
valid = gdf[~exclude_mask].copy()

print("排除筆數：", len(excluded))
print("保留筆數：", len(valid))


if len(excluded) > 0:
    print("\n被排除的資料：")
    print(
        excluded[
            [
                "village_id",
                "county_name",
                "town_name",
                "village_name",
                "population_total",
                "elderly_ratio",
            ]
        ].to_string(index=False)
    )


print("\n=== 3. 修正資料型態 ===")

int_columns = [
    "household_count",
    "population_total",
    "elderly_population",
]

for col in int_columns:
    valid[col] = valid[col].astype(int)

valid["elderly_ratio"] = valid["elderly_ratio"].astype(float)


print("\n=== 4. 最終品質檢查 ===")

print("最終村里數：", len(valid))
print("village_id 重複數：", valid["village_id"].duplicated().sum())
print("人口缺失數：", valid["population_total"].isna().sum())
print("村里名稱異常數：", valid["village_name"].astype(str).str.lower().isin(["nan", "none", ""]).sum())
print("總人口：", int(valid["population_total"].sum()))
print("65歲以上人口：", int(valid["elderly_population"].sum()))
print("平均高齡比例：", valid["elderly_ratio"].mean())


print("\n=== 5. 輸出最終資料 ===")

valid.to_file(output_geojson_path, driver="GeoJSON")

valid.drop(columns=["geometry"]).to_csv(
    output_csv_path,
    index=False,
    encoding="utf-8-sig"
)

excluded.drop(columns=["geometry"]).to_csv(
    excluded_csv_path,
    index=False,
    encoding="utf-8-sig"
)

print("完成：", output_geojson_path)
print("完成：", output_csv_path)
print("完成：", excluded_csv_path)