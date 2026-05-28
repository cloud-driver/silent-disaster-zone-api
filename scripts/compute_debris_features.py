from pathlib import Path
import geopandas as gpd
import pandas as pd


villages_path = Path("data/processed/villages_hualien_with_flood_final.geojson")
debris_path = Path("data/processed/debris_area_hualien.geojson")

output_features_path = Path("data/processed/debris_features_hualien.csv")
output_geojson_path = Path("data/processed/villages_hualien_with_flood_debris.geojson")
output_csv_path = Path("data/processed/villages_hualien_with_flood_debris.csv")


def minmax_normalize(series):
    series = series.fillna(0).astype(float)

    min_value = series.min()
    max_value = series.max()

    if max_value == min_value:
        return series * 0

    return ((series - min_value) / (max_value - min_value)).clip(0, 1)


print("=== 1. 讀取村里主表與土石流圖層 ===")

villages = gpd.read_file(villages_path)
debris = gpd.read_file(debris_path)

print("村里筆數：", len(villages))
print("土石流 polygon 筆數：", len(debris))
print("村里 CRS：", villages.crs)
print("土石流 CRS：", debris.crs)


print("\n=== 2. 檢查必要欄位 ===")

village_required = [
    "village_id",
    "county_name",
    "town_name",
    "village_name",
    "population_total",
    "elderly_ratio",
    "flood_risk_raw",
    "flood_risk_model",
    "geometry",
]

debris_required = [
    "debris_id",
    "total_residents_exposed",
    "geometry",
]

missing_village = [col for col in village_required if col not in villages.columns]
missing_debris = [col for col in debris_required if col not in debris.columns]

if missing_village:
    raise ValueError(f"村里資料缺少欄位：{missing_village}")

if missing_debris:
    raise ValueError(f"土石流資料缺少欄位：{missing_debris}")

if villages.crs is None:
    raise ValueError("村里資料缺 CRS，不能繼續。")

if debris.crs is None:
    raise ValueError("土石流資料缺 CRS，不能繼續。")

print("必要欄位都有，可以繼續。")


print("\n=== 3. 轉成 EPSG:3826 計算面積 ===")

villages_m = villages.to_crs(epsg=3826)
debris_m = debris.to_crs(epsg=3826)

villages_m["village_area_m2"] = villages_m.geometry.area

print("村里面積最小值 m2：", villages_m["village_area_m2"].min())
print("村里面積最大值 m2：", villages_m["village_area_m2"].max())


print("\n=== 4. 做空間交集 intersection ===")

village_layer = villages_m[
    [
        "village_id",
        "county_name",
        "town_name",
        "village_name",
        "village_area_m2",
        "geometry",
    ]
].copy()

debris_layer = debris_m[
    [
        "debris_id",
        "total_residents_exposed",
        "geometry",
    ]
].copy()

debris_layer["total_residents_exposed"] = pd.to_numeric(
    debris_layer["total_residents_exposed"],
    errors="coerce"
).fillna(0)

intersection = gpd.overlay(
    village_layer,
    debris_layer,
    how="intersection",
    keep_geom_type=True
)

print("交集圖斑數：", len(intersection))

if len(intersection) == 0:
    raise ValueError("村里與土石流圖層沒有任何交集，請檢查 CRS 或資料範圍。")


print("\n=== 5. 計算交集面積 ===")

intersection["intersect_area_m2"] = intersection.geometry.area

print("交集面積總和 m2：", intersection["intersect_area_m2"].sum())


print("\n=== 6. 聚合到村里層級 ===")

debris_features = (
    intersection
    .groupby("village_id")
    .agg(
        debris_area_m2=("intersect_area_m2", "sum"),
        debris_polygon_count=("debris_id", "count"),
        max_total_residents_exposed=("total_residents_exposed", "max"),
        sum_total_residents_exposed=("total_residents_exposed", "sum"),
    )
    .reset_index()
)

village_area = villages_m[
    [
        "village_id",
        "village_area_m2",
    ]
].copy()

debris_features = village_area.merge(
    debris_features,
    on="village_id",
    how="left"
)

fill_zero_cols = [
    "debris_area_m2",
    "debris_polygon_count",
    "max_total_residents_exposed",
    "sum_total_residents_exposed",
]

for col in fill_zero_cols:
    debris_features[col] = debris_features[col].fillna(0)


print("\n=== 7. 計算 debris_area_ratio / debris_risk ===")

debris_features["debris_area_ratio"] = (
    debris_features["debris_area_m2"] / debris_features["village_area_m2"]
)

# 原始風險：面積暴露比例
debris_features["debris_risk_raw"] = debris_features["debris_area_ratio"].clip(0, 1)

# 模型風險：花蓮內部相對分數
debris_features["debris_risk_model"] = minmax_normalize(
    debris_features["debris_risk_raw"]
)

debris_features["has_debris_potential"] = (
    debris_features["debris_area_m2"] > 0
).astype(int)


over_area_count = (debris_features["debris_area_ratio"] > 1.05).sum()

print("debris_area_ratio > 1.05 的村里數：", over_area_count)

if over_area_count > 0:
    print("\n警告：有村里的 debris_area_ratio 超過 1，可能代表土石流 polygon 有重疊。")
    print(
        debris_features[debris_features["debris_area_ratio"] > 1.05]
        .sort_values("debris_area_ratio", ascending=False)
        .head(10)
        .to_string(index=False)
    )


print("\n=== 8. 合併回村里主表 ===")

output = villages.merge(
    debris_features[
        [
            "village_id",
            "debris_area_m2",
            "debris_polygon_count",
            "max_total_residents_exposed",
            "sum_total_residents_exposed",
            "debris_area_ratio",
            "debris_risk_raw",
            "debris_risk_model",
            "has_debris_potential",
        ]
    ],
    on="village_id",
    how="left"
)

check_cols = [
    "debris_area_m2",
    "debris_polygon_count",
    "max_total_residents_exposed",
    "sum_total_residents_exposed",
    "debris_area_ratio",
    "debris_risk_raw",
    "debris_risk_model",
    "has_debris_potential",
]

for col in check_cols:
    output[col] = output[col].fillna(0)


print("\n=== 9. 結果摘要 ===")

print("村里總數：", len(output))
print("有土石流潛勢交集的村里數：", int((output["debris_area_m2"] > 0).sum()))
print("沒有土石流潛勢交集的村里數：", int((output["debris_area_m2"] == 0).sum()))

print("\ndebris_risk_raw 統計：")
print(output["debris_risk_raw"].describe())

print("\ndebris_risk_model 統計：")
print(output["debris_risk_model"].describe())

print("\n土石流模型風險最高前 10 個村里：")
print(
    output[
        [
            "village_id",
            "county_name",
            "town_name",
            "village_name",
            "debris_area_ratio",
            "debris_risk_raw",
            "debris_risk_model",
            "debris_polygon_count",
            "max_total_residents_exposed",
        ]
    ]
    .sort_values("debris_risk_model", ascending=False)
    .head(10)
    .to_string(index=False)
)


print("\n=== 10. 輸出資料 ===")

output_features_path.parent.mkdir(parents=True, exist_ok=True)

debris_features.to_csv(
    output_features_path,
    index=False,
    encoding="utf-8-sig"
)

output.to_file(output_geojson_path, driver="GeoJSON")

output.drop(columns=["geometry"]).to_csv(
    output_csv_path,
    index=False,
    encoding="utf-8-sig"
)

print("完成：", output_features_path)
print("完成：", output_geojson_path)
print("完成：", output_csv_path)