from pathlib import Path
import json
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point


villages_path = Path("data/processed/villages_hualien_with_sensor_gap.geojson")
reports_path = Path("data/raw/reports/reports_mock.json")

output_reports_geojson_path = Path("data/processed/reports_hualien_joined.geojson")
output_features_path = Path("data/processed/report_features_hualien.csv")
output_villages_path = Path("data/processed/villages_hualien_with_reports.geojson")
output_villages_csv_path = Path("data/processed/villages_hualien_with_reports.csv")


# 這裡先固定 MVP 的分析時間。
# 之後正式版可以改成 datetime.now(tz=...)
analysis_time = pd.Timestamp("2026-05-17T16:00:00+08:00")


print("=== 1. 讀取村里主表與通報資料 ===")

villages = gpd.read_file(villages_path)

with open(reports_path, "r", encoding="utf-8") as f:
    reports_data = json.load(f)

reports_df = pd.DataFrame(reports_data)

print("村里數：", len(villages))
print("通報筆數：", len(reports_df))


print("\n=== 2. 整理通報資料型態 ===")

reports_df["lon"] = pd.to_numeric(reports_df["lon"], errors="coerce")
reports_df["lat"] = pd.to_numeric(reports_df["lat"], errors="coerce")
reports_df["severity"] = pd.to_numeric(reports_df["severity"], errors="coerce").fillna(1)
reports_df["created_at"] = pd.to_datetime(reports_df["created_at"], errors="coerce")

reports_df = reports_df[
    reports_df["lon"].notna()
    & reports_df["lat"].notna()
    & reports_df["created_at"].notna()
].copy()

reports_gdf = gpd.GeoDataFrame(
    reports_df,
    geometry=[Point(xy) for xy in zip(reports_df["lon"], reports_df["lat"])],
    crs="EPSG:4326"
)

print("有效通報筆數：", len(reports_gdf))


print("\n=== 3. 空間 join：通報點落在哪個村里 ===")

villages = villages.to_crs(epsg=4326)
reports_gdf = reports_gdf.to_crs(epsg=4326)

joined = gpd.sjoin(
    reports_gdf,
    villages[["village_id", "county_name", "town_name", "village_name", "geometry"]],
    how="inner",
    predicate="within"
)

print("落在花蓮村里內的通報筆數：", len(joined))

if len(joined) > 0:
    print(joined[
        [
            "report_id",
            "report_type",
            "severity",
            "created_at",
            "county_name",
            "town_name",
            "village_name",
        ]
    ].to_string(index=False))


print("\n=== 4. 計算 6h / 24h 通報數 ===")

if len(joined) > 0:
    joined["hours_before_analysis"] = (
        analysis_time - joined["created_at"]
    ).dt.total_seconds() / 3600

    recent_6h = joined[
        (joined["hours_before_analysis"] >= 0)
        & (joined["hours_before_analysis"] <= 6)
    ].copy()

    recent_24h = joined[
        (joined["hours_before_analysis"] >= 0)
        & (joined["hours_before_analysis"] <= 24)
    ].copy()

    features_6h = (
        recent_6h
        .groupby("village_id")
        .agg(
            report_count_6h=("report_id", "count"),
            report_severity_sum_6h=("severity", "sum"),
            max_report_severity_6h=("severity", "max"),
        )
        .reset_index()
    )

    features_24h = (
        recent_24h
        .groupby("village_id")
        .agg(
            report_count_24h=("report_id", "count"),
            report_severity_sum_24h=("severity", "sum"),
            max_report_severity_24h=("severity", "max"),
        )
        .reset_index()
    )

    report_features = features_24h.merge(
        features_6h,
        on="village_id",
        how="outer"
    )
else:
    report_features = pd.DataFrame(columns=[
        "village_id",
        "report_count_24h",
        "report_severity_sum_24h",
        "max_report_severity_24h",
        "report_count_6h",
        "report_severity_sum_6h",
        "max_report_severity_6h",
    ])


print("有通報特徵的村里數：", len(report_features))


print("\n=== 5. 合併回村里主表 ===")

output = villages.merge(
    report_features,
    on="village_id",
    how="left"
)

fill_cols = [
    "report_count_6h",
    "report_severity_sum_6h",
    "max_report_severity_6h",
    "report_count_24h",
    "report_severity_sum_24h",
    "max_report_severity_24h",
]

for col in fill_cols:
    output[col] = output[col].fillna(0)


print("\n=== 6. 結果摘要 ===")

print("村里總數：", len(output))
print("近 6 小時有通報村里數：", int((output["report_count_6h"] > 0).sum()))
print("近 24 小時有通報村里數：", int((output["report_count_24h"] > 0).sum()))

print("\n通報數最高村里：")
print(
    output[
        [
            "village_id",
            "county_name",
            "town_name",
            "village_name",
            "report_count_6h",
            "report_count_24h",
            "static_risk_score",
            "sensor_gap_score",
        ]
    ]
    .sort_values(["report_count_6h", "report_count_24h"], ascending=False)
    .head(10)
    .to_string(index=False)
)


print("\n=== 7. 輸出資料 ===")

output_reports_geojson_path.parent.mkdir(parents=True, exist_ok=True)

if len(joined) > 0:
    joined.to_file(output_reports_geojson_path, driver="GeoJSON")

report_features.to_csv(
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
    print("完成：", output_reports_geojson_path)