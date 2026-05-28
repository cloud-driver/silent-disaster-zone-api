from pathlib import Path
import json
import shutil
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point


PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_ROOT = PROJECT_ROOT / "data" / "realtime" / "raw"
PROCESSED_ROOT = PROJECT_ROOT / "data" / "realtime" / "processed"
LATEST_ROOT = PROJECT_ROOT / "data" / "realtime" / "latest"

VILLAGES_PATH = PROJECT_ROOT / "data" / "processed" / "villages_hualien_static_risk.geojson"


def latest_json(source_name):
    folder = RAW_ROOT / source_name
    files = sorted(folder.glob("*.json"))
    if not files:
        return None
    return files[-1]


def get_run_id_from_path(path):
    return path.stem


def clean_text(value):
    return (
        str(value)
        .strip()
        .replace("　", "")
        .replace(" ", "")
        .replace("臺", "台")
    )


def safe_float(value):
    try:
        if value in [None, "", "-", "None"]:
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def find_nested_value(obj, candidate_keys):
    """
    在巢狀 dict/list 裡面找第一個符合 key 的值。
    用來處理 CWA GeoInfo 欄位名稱不穩的情況。
    """
    if isinstance(obj, dict):
        for key in candidate_keys:
            if key in obj:
                return obj[key]

        for value in obj.values():
            found = find_nested_value(value, candidate_keys)
            if found is not None:
                return found

    elif isinstance(obj, list):
        for item in obj:
            found = find_nested_value(item, candidate_keys)
            if found is not None:
                return found

    return None


def normalize_cwa_rain(path, run_id):
    print("\n=== normalize cwa_rain ===")

    if path is None:
        print("沒有 cwa_rain snapshot")
        return gpd.GeoDataFrame(columns=["source", "run_id", "lon", "lat", "rain_1h", "geometry"], crs="EPSG:4326")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    stations = data.get("records", {}).get("Station", [])

    rows = []

    for station in stations:
        geo = station.get("GeoInfo", {})
        rain = station.get("RainfallElement", {})
        obs = station.get("ObsTime", {})

        lon = find_nested_value(geo, [
            "StationLongitude",
            "Longitude",
            "lon",
            "lng",
            "X",
        ])

        lat = find_nested_value(geo, [
            "StationLatitude",
            "Latitude",
            "lat",
            "Y",
        ])

        # CWA 雨量欄位不同資料版本可能叫法不同，所以多抓幾種
        rain_10min = find_nested_value(rain, [
            "Past10Min",
            "Past10MIN",
            "Now",
        ])

        rain_1h = find_nested_value(rain, [
            "Past1hr",
            "Past1Hr",
            "Past1H",
            "HourRainfall",
        ])

        rain_3h = find_nested_value(rain, [
            "Past3hr",
            "Past3Hr",
        ])

        observed_at = find_nested_value(obs, [
            "DateTime",
            "ObsTime",
            "Time",
        ])

        lon = safe_float(lon)
        lat = safe_float(lat)

        if lon == 0 or lat == 0:
            continue

        rows.append({
            "source": "cwa_rain",
            "run_id": run_id,
            "station_id": station.get("StationId"),
            "station_name": station.get("StationName"),
            "observed_at": observed_at,
            "lon": lon,
            "lat": lat,
            "rain_10min": safe_float(rain_10min),
            "rain_1h": safe_float(rain_1h),
            "rain_3h": safe_float(rain_3h),
        })

    df = pd.DataFrame(rows)

    if len(df) == 0:
        print("cwa_rain 解析後 0 筆")
        return gpd.GeoDataFrame(columns=["source", "run_id", "lon", "lat", "rain_1h", "geometry"], crs="EPSG:4326")

    gdf = gpd.GeoDataFrame(
        df,
        geometry=[Point(xy) for xy in zip(df["lon"], df["lat"])],
        crs="EPSG:4326",
    )

    print("CWA 雨量測站筆數：", len(gdf))
    print("bounds:", gdf.total_bounds)
    print("rain_1h 統計：")
    print(gdf["rain_1h"].describe())

    return gdf


def normalize_ardswc_alert(path, run_id):
    print("\n=== normalize ardswc_alert ===")

    if path is None:
        print("沒有 ardswc_alert snapshot")
        return pd.DataFrame(columns=["county_name", "town_name", "village_name", "landslide_alert_score"])

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    rows = []

    if not isinstance(data, list):
        print("ardswc_alert 不是 list")
        return pd.DataFrame(columns=["county_name", "town_name", "village_name", "landslide_alert_score"])

    for item in data:
        county = clean_text(item.get("County"))
        town = clean_text(item.get("Town"))
        vill = clean_text(item.get("Vill"))
        level = str(item.get("AlertLevel", "")).strip().lower()

        # 過濾欄位說明列
        if county in ["縣市", "none", "nan", ""]:
            continue

        score = 0.0
        if level == "y":
            score = 0.6
        elif level == "r":
            score = 1.0

        rows.append({
            "county_name": county,
            "town_name": town,
            "village_name": vill,
            "alert_level": level,
            "landslide_alert_score": score,
            "last_update": item.get("LastUpdateDate"),
        })

    df = pd.DataFrame(rows)

    print("ARDSWC 警戒有效筆數：", len(df))

    return df


def normalize_ardswc_debris_rain(path, run_id):
    print("\n=== normalize ardswc_debris_rain ===")

    if path is None:
        print("沒有 ardswc_debris_rain snapshot")
        return pd.DataFrame(columns=["county_name", "town_name", "village_name", "debris_rain_score"])

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    rows = []

    if not isinstance(data, list):
        print("ardswc_debris_rain 不是 list")
        return pd.DataFrame(columns=["county_name", "town_name", "village_name", "debris_rain_score"])

    for item in data:
        county = clean_text(item.get("County"))
        town = clean_text(item.get("Town"))
        vill = clean_text(item.get("Vill"))

        alert_value = safe_float(item.get("AlertValue"))
        rain1 = safe_float(item.get("STRT1"))
        rain2 = safe_float(item.get("STRT2"))

        if county in ["縣市", "none", "nan", ""]:
            continue

        current_ref_rain = max(rain1, rain2)

        if alert_value > 0:
            rain_ratio = current_ref_rain / alert_value
        else:
            rain_ratio = 0

        rows.append({
            "county_name": county,
            "town_name": town,
            "village_name": vill,
            "debris_no": item.get("DebrisNO"),
            "alert_value": alert_value,
            "current_ref_rain": current_ref_rain,
            "debris_rain_ratio": rain_ratio,
            "debris_rain_score": min(max(rain_ratio, 0), 1),
        })

    df = pd.DataFrame(rows)

    print("ARDSWC 土石流雨量筆數：", len(df))

    return df


def normalize_road_traffic(path, run_id):
    print("\n=== normalize road_traffic ===")

    if path is None:
        print("沒有 road_traffic snapshot")
        return gpd.GeoDataFrame(columns=["source", "run_id", "lon", "lat", "road_event_score", "geometry"], crs="EPSG:4326")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    records = data.get("result", [])

    rows = []

    for item in records:
        lon = safe_float(item.get("x1"))
        lat = safe_float(item.get("y1"))

        if lon == 0 or lat == 0:
            continue

        roadtype = str(item.get("roadtype", "")).strip()
        comment = str(item.get("comment", "")).strip()
        area_name = str(item.get("areaNm", "")).strip()

        score = 0.2

        high_keywords = ["封閉", "中斷", "坍方", "落石", "積水", "災害", "管制"]
        medium_keywords = ["事故", "施工", "壅塞"]

        text = roadtype + " " + comment

        if any(k in text for k in high_keywords):
            score = 1.0
        elif any(k in text for k in medium_keywords):
            score = 0.5

        rows.append({
            "source": "road_traffic",
            "run_id": run_id,
            "uid": item.get("UID"),
            "area_name": area_name,
            "roadtype": roadtype,
            "road": item.get("road"),
            "comment": comment,
            "happendate": item.get("happendate"),
            "happentime": item.get("happentime"),
            "lon": lon,
            "lat": lat,
            "road_event_score": score,
        })

    df = pd.DataFrame(rows)

    if len(df) == 0:
        print("road_traffic 解析後 0 筆")
        return gpd.GeoDataFrame(columns=["source", "run_id", "lon", "lat", "road_event_score", "geometry"], crs="EPSG:4326")

    gdf = gpd.GeoDataFrame(
        df,
        geometry=[Point(xy) for xy in zip(df["lon"], df["lat"])],
        crs="EPSG:4326",
    )

    print("警廣路況筆數：", len(gdf))
    print("bounds:", gdf.total_bounds)

    return gdf


def join_points_to_villages(point_gdf, villages, value_columns, prefix):
    if len(point_gdf) == 0:
        return pd.DataFrame({"village_id": villages["village_id"]})

    joined = gpd.sjoin(
        point_gdf.to_crs(epsg=4326),
        villages[["village_id", "county_name", "town_name", "village_name", "geometry"]].to_crs(epsg=4326),
        how="inner",
        predicate="within",
    )

    print(f"{prefix} 落在花蓮村里內筆數：", len(joined))

    if len(joined) == 0:
        return pd.DataFrame({"village_id": villages["village_id"]})

    agg_dict = {}

    for col in value_columns:
        agg_dict[f"{prefix}_{col}_max"] = (col, "max")
        agg_dict[f"{prefix}_{col}_mean"] = (col, "mean")

    agg_dict[f"{prefix}_count"] = ("village_id", "count")

    features = (
        joined
        .groupby("village_id")
        .agg(**agg_dict)
        .reset_index()
    )

    return features


print("=== Normalize realtime sources ===")

latest_paths = {
    "cwa_rain": latest_json("cwa_rain"),
    "ardswc_alert": latest_json("ardswc_alert"),
    "ardswc_debris_rain": latest_json("ardswc_debris_rain"),
    "road_traffic": latest_json("road_traffic"),
}

available_run_ids = [
    get_run_id_from_path(p)
    for p in latest_paths.values()
    if p is not None
]

if not available_run_ids:
    raise RuntimeError("找不到任何 realtime raw snapshot")

run_id = sorted(available_run_ids)[-1]

print("使用 run_id:", run_id)

output_dir = PROCESSED_ROOT / run_id
output_dir.mkdir(parents=True, exist_ok=True)
LATEST_ROOT.mkdir(parents=True, exist_ok=True)

villages = gpd.read_file(VILLAGES_PATH).to_crs(epsg=4326)
villages["county_name_clean"] = villages["county_name"].apply(clean_text)
villages["town_name_clean"] = villages["town_name"].apply(clean_text)
villages["village_name_clean"] = villages["village_name"].apply(clean_text)

print("花蓮村里數：", len(villages))


# 1. CWA rain
cwa_gdf = normalize_cwa_rain(latest_paths["cwa_rain"], run_id)
cwa_features = join_points_to_villages(
    cwa_gdf,
    villages,
    value_columns=["rain_10min", "rain_1h", "rain_3h"],
    prefix="cwa_rain"
)


# 2. road traffic
road_gdf = normalize_road_traffic(latest_paths["road_traffic"], run_id)
road_features = join_points_to_villages(
    road_gdf,
    villages,
    value_columns=["road_event_score"],
    prefix="road"
)


# 3. ARDSWC alert by names
alert_df = normalize_ardswc_alert(latest_paths["ardswc_alert"], run_id)

if len(alert_df) > 0:
    alert_df["county_name_clean"] = alert_df["county_name"].apply(clean_text)
    alert_df["town_name_clean"] = alert_df["town_name"].apply(clean_text)
    alert_df["village_name_clean"] = alert_df["village_name"].apply(clean_text)

    alert_features = (
        villages[["village_id", "county_name_clean", "town_name_clean", "village_name_clean"]]
        .merge(
            alert_df,
            on=["county_name_clean", "town_name_clean", "village_name_clean"],
            how="left",
        )
        .groupby("village_id")
        .agg(
            landslide_alert_score=("landslide_alert_score", "max"),
        )
        .reset_index()
    )
else:
    alert_features = pd.DataFrame({"village_id": villages["village_id"], "landslide_alert_score": 0})


# 4. ARDSWC debris rain by names
debris_rain_df = normalize_ardswc_debris_rain(latest_paths["ardswc_debris_rain"], run_id)

if len(debris_rain_df) > 0:
    debris_rain_df["county_name_clean"] = debris_rain_df["county_name"].apply(clean_text)
    debris_rain_df["town_name_clean"] = debris_rain_df["town_name"].apply(clean_text)
    debris_rain_df["village_name_clean"] = debris_rain_df["village_name"].apply(clean_text)

    debris_rain_features = (
        villages[["village_id", "county_name_clean", "town_name_clean", "village_name_clean"]]
        .merge(
            debris_rain_df,
            on=["county_name_clean", "town_name_clean", "village_name_clean"],
            how="left",
        )
        .groupby("village_id")
        .agg(
            debris_rain_score=("debris_rain_score", "max"),
            debris_rain_ratio=("debris_rain_ratio", "max"),
            debris_rain_count=("debris_no", "count"),
        )
        .reset_index()
    )
else:
    debris_rain_features = pd.DataFrame({
        "village_id": villages["village_id"],
        "debris_rain_score": 0,
        "debris_rain_ratio": 0,
        "debris_rain_count": 0,
    })


# 5. Merge all features
features = villages[[
    "village_id",
    "county_name",
    "town_name",
    "village_name",
]].copy()

for df in [
    cwa_features,
    road_features,
    alert_features,
    debris_rain_features,
]:
    features = features.merge(df, on="village_id", how="left")

features = features.fillna(0)


# 6. Create final realtime score
features["rainfall_realtime_score"] = (
    features.get("cwa_rain_rain_1h_max", 0) / 40
).clip(0, 1)

features["road_realtime_score"] = (
    features.get("road_road_event_score_max", 0)
).clip(0, 1)

features["landslide_realtime_score"] = (
    0.6 * features["landslide_alert_score"].astype(float)
    + 0.4 * features["debris_rain_score"].astype(float)
).clip(0, 1)

features["realtime_event_score"] = (
    0.45 * features["rainfall_realtime_score"]
    + 0.35 * features["landslide_realtime_score"]
    + 0.20 * features["road_realtime_score"]
).clip(0, 1)


print("\n=== realtime feature summary ===")
print("村里數：", len(features))

for col in [
    "rainfall_realtime_score",
    "landslide_realtime_score",
    "road_realtime_score",
    "realtime_event_score",
]:
    print(f"\n{col} 統計：")
    print(features[col].describe())

print("\nrealtime_event_score 最高前 15：")
print(
    features[[
        "village_id",
        "county_name",
        "town_name",
        "village_name",
        "rainfall_realtime_score",
        "landslide_realtime_score",
        "road_realtime_score",
        "realtime_event_score",
    ]]
    .sort_values("realtime_event_score", ascending=False)
    .head(15)
    .to_string(index=False)
)


# 7. Save outputs
features.to_csv(output_dir / "realtime_features.csv", index=False, encoding="utf-8-sig")
features.to_csv(LATEST_ROOT / "realtime_features.csv", index=False, encoding="utf-8-sig")

if len(cwa_gdf) > 0:
    cwa_gdf.to_file(output_dir / "cwa_rain_points.geojson", driver="GeoJSON")

if len(road_gdf) > 0:
    road_gdf.to_file(output_dir / "road_traffic_points.geojson", driver="GeoJSON")

shutil.copyfile(output_dir / "realtime_features.csv", LATEST_ROOT / "realtime_features.csv")

print("\n完成：", output_dir / "realtime_features.csv")
print("完成：", LATEST_ROOT / "realtime_features.csv")