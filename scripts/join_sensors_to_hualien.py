from pathlib import Path
import geopandas as gpd
import pandas as pd


villages_path = Path("data/processed/villages_hualien_static_risk.geojson")
sensors_path = Path("data/processed/sensors_standardized.geojson")

output_sensor_points_path = Path("data/processed/sensors_hualien_joined.geojson")
output_features_path = Path("data/processed/sensor_features_hualien.csv")
output_villages_path = Path("data/processed/villages_hualien_with_sensors.geojson")
output_villages_csv_path = Path("data/processed/villages_hualien_with_sensors.csv")


print("=== 1. 讀取花蓮村里與感測器資料 ===")

villages = gpd.read_file(villages_path)
sensors = gpd.read_file(sensors_path)

print("花蓮村里數：", len(villages))
print("感測器總數：", len(sensors))
print("村里 CRS：", villages.crs)
print("感測器 CRS：", sensors.crs)


print("\n=== 2. 空間 join：找出落在花蓮村里內的感測器 ===")

villages = villages.to_crs(epsg=4326)
sensors = sensors.to_crs(epsg=4326)

joined = gpd.sjoin(
    sensors,
    villages[["village_id", "county_name", "town_name", "village_name", "geometry"]],
    how="inner",
    predicate="within"
)

print("落在花蓮村里內的感測器筆數：", len(joined))

if len(joined) == 0:
    print("警告：沒有任何感測器落在花蓮村里內。這代表目前這批感測器資料對花蓮 MVP 幫助有限。")


print("\n感測器類型分布：")
if len(joined) > 0:
    print(joined["sensor_type"].value_counts())


print("\n=== 3. 依村里聚合感測器特徵 ===")

if len(joined) > 0:
    features = (
        joined
        .groupby("village_id")
        .agg(
            sensor_count=("datastream_id", "count"),
            flood_sensor_count=("sensor_type", lambda s: (s == "flood_depth").sum()),
            rainfall_sensor_count=("sensor_type", lambda s: (s == "rainfall").sum()),
            flow_sensor_count=("sensor_type", lambda s: (s == "flow").sum()),
            water_level_sensor_count=("sensor_type", lambda s: (s == "water_level").sum()),
            max_flood_depth_cm=("value", lambda x: x[joined.loc[x.index, "sensor_type"] == "flood_depth"].max() if (joined.loc[x.index, "sensor_type"] == "flood_depth").any() else 0),
            max_rainfall_mm=("value", lambda x: x[joined.loc[x.index, "sensor_type"] == "rainfall"].max() if (joined.loc[x.index, "sensor_type"] == "rainfall").any() else 0),
        )
        .reset_index()
    )
else:
    features = pd.DataFrame(columns=[
        "village_id",
        "sensor_count",
        "flood_sensor_count",
        "rainfall_sensor_count",
        "flow_sensor_count",
        "water_level_sensor_count",
        "max_flood_depth_cm",
        "max_rainfall_mm",
    ])


print("有感測器特徵的村里數：", len(features))


print("\n=== 4. 合併回村里主表 ===")

output = villages.merge(
    features,
    on="village_id",
    how="left"
)

fill_cols = [
    "sensor_count",
    "flood_sensor_count",
    "rainfall_sensor_count",
    "flow_sensor_count",
    "water_level_sensor_count",
    "max_flood_depth_cm",
    "max_rainfall_mm",
]

for col in fill_cols:
    output[col] = output[col].fillna(0)

# 第一版簡單做即時感測器分數
# 淹水深度 >= 30cm 視為高風險，30cm 以上壓到 1
output["flood_sensor_score"] = (output["max_flood_depth_cm"] / 30).clip(0, 1)

# 雨量這批資料若沒有花蓮站，這欄大多會是 0
# 10分鐘雨量 >= 10mm 暫視為高風險
output["rainfall_sensor_score"] = (output["max_rainfall_mm"] / 10).clip(0, 1)

output["sensor_realtime_score"] = (
    0.7 * output["flood_sensor_score"]
    + 0.3 * output["rainfall_sensor_score"]
).clip(0, 1)


print("\n=== 5. 結果摘要 ===")

print("村里總數：", len(output))
print("有任何感測器的村里數：", int((output["sensor_count"] > 0).sum()))
print("有淹水感測器的村里數：", int((output["flood_sensor_count"] > 0).sum()))
print("有雨量感測器的村里數：", int((output["rainfall_sensor_count"] > 0).sum()))

print("\nsensor_realtime_score 統計：")
print(output["sensor_realtime_score"].describe())

print("\n感測器即時分數最高前 15 個村里：")
print(
    output[
        [
            "village_id",
            "county_name",
            "town_name",
            "village_name",
            "sensor_count",
            "flood_sensor_count",
            "rainfall_sensor_count",
            "max_flood_depth_cm",
            "max_rainfall_mm",
            "sensor_realtime_score",
        ]
    ]
    .sort_values("sensor_realtime_score", ascending=False)
    .head(15)
    .to_string(index=False)
)


print("\n=== 6. 輸出資料 ===")

output_features_path.parent.mkdir(parents=True, exist_ok=True)

if len(joined) > 0:
    joined.to_file(output_sensor_points_path, driver="GeoJSON")

features.to_csv(
    output_features_path,
    index=False,
    encoding="utf-8-sig"
)

output.to_file(output_villages_path, driver="GeoJSON")

output.drop(columns=["geometry"]).to_csv(
    output_villages_csv_path,
    index=False,
    encoding="utf-8-sig"
)

print("完成：", output_features_path)
print("完成：", output_villages_path)
print("完成：", output_villages_csv_path)

if len(joined) > 0:
    print("完成：", output_sensor_points_path)