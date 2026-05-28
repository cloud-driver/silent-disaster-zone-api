from pathlib import Path
import geopandas as gpd
import pandas as pd


villages_path = Path("data/processed/villages_hualien_population_final.geojson")
flood_path = Path("data/processed/flood_350mm_24hr_hualien_final.geojson")

output_features_path = Path("data/processed/flood_features_hualien.csv")
output_geojson_path = Path("data/processed/villages_hualien_with_flood.geojson")
output_csv_path = Path("data/processed/villages_hualien_with_flood.csv")


print("=== 1. 讀取村里主表與淹水圖斑 ===")

villages = gpd.read_file(villages_path)
flood = gpd.read_file(flood_path)

print("村里筆數：", len(villages))
print("淹水圖斑筆數：", len(flood))
print("村里 CRS：", villages.crs)
print("淹水 CRS：", flood.crs)


print("\n=== 2. 檢查必要欄位 ===")

village_required = [
    "village_id",
    "county_name",
    "town_name",
    "village_name",
    "geometry",
]

flood_required = [
    "flood_class",
    "flood_depth",
    "geometry",
]

missing_village = [col for col in village_required if col not in villages.columns]
missing_flood = [col for col in flood_required if col not in flood.columns]

if missing_village:
    raise ValueError(f"村里資料缺少欄位：{missing_village}")

if missing_flood:
    raise ValueError(f"淹水資料缺少欄位：{missing_flood}")

print("必要欄位都有，可以繼續。")


print("\n=== 3. 轉成 EPSG:3826 計算面積 ===")

# 注意：
# 面積不能直接用 EPSG:4326 算，因為經緯度單位是度，不是公尺。
# EPSG:3826 是台灣常用的 TWD97 / TM2，單位是公尺，比較適合算面積。
villages_m = villages.to_crs(epsg=3826)
flood_m = flood.to_crs(epsg=3826)

villages_m["village_area_m2"] = villages_m.geometry.area

print("村里面積最小值 m2：", villages_m["village_area_m2"].min())
print("村里面積最大值 m2：", villages_m["village_area_m2"].max())


print("\n=== 4. 做空間交集 intersection ===")

# 只保留必要欄位，避免 overlay 產生太多雜欄位
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

flood_layer = flood_m[
    [
        "flood_class",
        "flood_depth",
        "geometry",
    ]
].copy()

intersection = gpd.overlay(
    village_layer,
    flood_layer,
    how="intersection",
    keep_geom_type=True
)

print("交集圖斑數：", len(intersection))

if len(intersection) == 0:
    raise ValueError("村里與淹水圖斑沒有任何交集，請檢查 CRS 或資料範圍。")


print("\n=== 5. 計算每個交集區塊的面積與權重 ===")

intersection["intersect_area_m2"] = intersection.geometry.area

intersection["flood_class"] = pd.to_numeric(
    intersection["flood_class"],
    errors="coerce"
).fillna(0)

intersection["flood_weight"] = (intersection["flood_class"] / 5).clip(0, 1)

intersection["weighted_flood_area_m2"] = (
    intersection["intersect_area_m2"] * intersection["flood_weight"]
)

print("交集面積總和 m2：", intersection["intersect_area_m2"].sum())
print("加權淹水面積總和 m2：", intersection["weighted_flood_area_m2"].sum())


print("\n=== 6. 聚合到村里層級 ===")

flood_features = (
    intersection
    .groupby("village_id")
    .agg(
        flood_area_m2=("intersect_area_m2", "sum"),
        weighted_flood_area_m2=("weighted_flood_area_m2", "sum"),
        max_flood_class=("flood_class", "max"),
        flood_polygon_count=("flood_class", "count"),
    )
    .reset_index()
)

village_area = villages_m[
    [
        "village_id",
        "village_area_m2",
    ]
].copy()

flood_features = village_area.merge(
    flood_features,
    on="village_id",
    how="left"
)

fill_zero_cols = [
    "flood_area_m2",
    "weighted_flood_area_m2",
    "max_flood_class",
    "flood_polygon_count",
]

for col in fill_zero_cols:
    flood_features[col] = flood_features[col].fillna(0)


print("\n=== 7. 計算 flood_area_ratio / flood_risk ===")

flood_features["flood_area_ratio"] = (
    flood_features["flood_area_m2"] / flood_features["village_area_m2"]
)

flood_features["flood_weighted_score"] = (
    flood_features["weighted_flood_area_m2"] / flood_features["village_area_m2"]
)

# 如果圖斑有重疊，理論上可能超過 1，所以先 clip。
# 但我們也會印出來檢查。
flood_features["flood_risk"] = flood_features["flood_weighted_score"].clip(0, 1)

over_area_count = (flood_features["flood_area_ratio"] > 1.05).sum()
over_score_count = (flood_features["flood_weighted_score"] > 1.05).sum()

print("flood_area_ratio > 1.05 的村里數：", over_area_count)
print("flood_weighted_score > 1.05 的村里數：", over_score_count)

if over_area_count > 0:
    print("\n警告：有村里的 flood_area_ratio 超過 1，可能代表淹水圖斑有重疊。")
    print(
        flood_features[flood_features["flood_area_ratio"] > 1.05]
        .sort_values("flood_area_ratio", ascending=False)
        .head(10)
        .to_string(index=False)
    )


print("\n=== 8. 合併回村里主表 ===")

output = villages.merge(
    flood_features[
        [
            "village_id",
            "village_area_m2",
            "flood_area_m2",
            "weighted_flood_area_m2",
            "flood_area_ratio",
            "flood_weighted_score",
            "flood_risk",
            "max_flood_class",
            "flood_polygon_count",
        ]
    ],
    on="village_id",
    how="left"
)

check_cols = [
    "village_area_m2",
    "flood_area_m2",
    "weighted_flood_area_m2",
    "flood_area_ratio",
    "flood_weighted_score",
    "flood_risk",
    "max_flood_class",
    "flood_polygon_count",
]

for col in check_cols:
    output[col] = output[col].fillna(0)


print("\n=== 9. 結果摘要 ===")

print("村里總數：", len(output))
print("有淹水潛勢交集的村里數：", (output["flood_area_m2"] > 0).sum())
print("沒有淹水潛勢交集的村里數：", (output["flood_area_m2"] == 0).sum())

print("\nflood_risk 統計：")
print(output["flood_risk"].describe())

print("\n淹水風險最高前 10 個村里：")
print(
    output[
        [
            "village_id",
            "county_name",
            "town_name",
            "village_name",
            "flood_area_ratio",
            "flood_weighted_score",
            "flood_risk",
            "max_flood_class",
        ]
    ]
    .sort_values("flood_risk", ascending=False)
    .head(10)
    .to_string(index=False)
)


print("\n=== 10. 輸出資料 ===")

output_features_path.parent.mkdir(parents=True, exist_ok=True)

flood_features.to_csv(
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