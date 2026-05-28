from pathlib import Path
import json
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point


input_folder = Path("data/raw/sensors")

output_csv_path = Path("data/processed/sensors_standardized.csv")
output_geojson_path = Path("data/processed/sensors_standardized.geojson")


def infer_sensor_type(filename, row):
    text = f"{filename} {row.get('name', '')} {row.get('description', '')}"

    if "淹水" in text:
        return "flood_depth"
    if "雨量" in text:
        return "rainfall"
    if "流量" in text:
        return "flow"
    if "水位" in text:
        return "water_level"

    return "unknown"


def get_value_from_observations(row):
    observations = row.get("Observations")

    if not isinstance(observations, list) or len(observations) == 0:
        return None, None

    latest = observations[0]

    value = latest.get("result")
    observed_at = latest.get("phenomenonTime") or latest.get("resultTime")

    return value, observed_at


def get_coordinates(row):
    observed_area = row.get("observedArea")

    if isinstance(observed_area, dict):
        coords = observed_area.get("coordinates")
        if isinstance(coords, list) and len(coords) >= 2:
            return coords[0], coords[1]

    thing = row.get("Thing")

    if isinstance(thing, dict):
        locations = thing.get("Locations")
        if isinstance(locations, list) and len(locations) > 0:
            location = locations[0].get("location")
            if isinstance(location, dict):
                coords = location.get("coordinates")
                if isinstance(coords, list) and len(coords) >= 2:
                    return coords[0], coords[1]

    return None, None


def get_thing_properties(row):
    thing = row.get("Thing")

    if not isinstance(thing, dict):
        return {}

    properties = thing.get("properties")

    if isinstance(properties, dict):
        return properties

    return {}


def get_unit(row):
    unit = row.get("unitOfMeasurement")

    if isinstance(unit, dict):
        return unit.get("symbol") or unit.get("name")

    return None


def load_sensor_file(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    value = data.get("value")

    if not isinstance(value, list):
        print(f"跳過：{path.name}，原因：value 不是 list")
        return []

    rows = []

    for item in value:
        if not isinstance(item, dict):
            continue

        lon, lat = get_coordinates(item)
        latest_value, observed_at = get_value_from_observations(item)
        props = get_thing_properties(item)

        row = {
            "source_file": path.name,
            "datastream_id": item.get("@iot.id"),
            "sensor_type": infer_sensor_type(path.name, item),
            "datastream_name": item.get("name"),
            "sensor_name": props.get("stationName"),
            "station_id": props.get("stationID"),
            "station_code": props.get("stationCode"),
            "authority": props.get("authority"),
            "authority_type": props.get("authority_type"),
            "lon": lon,
            "lat": lat,
            "observed_at": observed_at,
            "value": latest_value,
            "unit": get_unit(item),
            "phenomenon_time_range": item.get("phenomenonTime"),
            "result_time_range": item.get("resultTime"),
            "observations_count": item.get("Observations@iot.count"),
        }

        rows.append(row)

    return rows


print("=== 1. 讀取 sensors 資料夾 ===")

files = sorted([
    p for p in input_folder.glob("*.json")
    if p.name != ".DS_Store"
])

print("JSON 檔案數：", len(files))

if len(files) == 0:
    raise FileNotFoundError("找不到任何 sensors JSON 檔案")


print("\n=== 2. 逐一解析 SensorThings Datastream ===")

all_rows = []

for file in files:
    rows = load_sensor_file(file)
    all_rows.extend(rows)
    print(f"{file.name}: 解析出 {len(rows)} 筆")


print("\n=== 3. 建立標準化表格 ===")

df = pd.DataFrame(all_rows)

print("總筆數：", len(df))
print("欄位：", df.columns.tolist())

if len(df) == 0:
    raise ValueError("沒有解析出任何感測器資料")


print("\n=== 4. 清理型態 ===")

df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
df["value"] = pd.to_numeric(df["value"], errors="coerce")
df["observations_count"] = pd.to_numeric(df["observations_count"], errors="coerce").fillna(0)

print("lon 缺失數：", df["lon"].isna().sum())
print("lat 缺失數：", df["lat"].isna().sum())
print("value 缺失數：", df["value"].isna().sum())
print("observed_at 缺失數：", df["observed_at"].isna().sum())


print("\n=== 5. 建立 GeoDataFrame ===")

valid_geo = df[df["lon"].notna() & df["lat"].notna()].copy()

gdf = gpd.GeoDataFrame(
    valid_geo,
    geometry=[Point(xy) for xy in zip(valid_geo["lon"], valid_geo["lat"])],
    crs="EPSG:4326"
)

print("有座標的感測器筆數：", len(gdf))
print("bounds：", gdf.total_bounds)

print("\n感測器類型分布：")
print(gdf["sensor_type"].value_counts())

print("\n單位分布：")
print(gdf["unit"].value_counts(dropna=False))


print("\n=== 6. 輸出標準化資料 ===")

output_csv_path.parent.mkdir(parents=True, exist_ok=True)

df.to_csv(
    output_csv_path,
    index=False,
    encoding="utf-8-sig"
)

gdf.to_file(output_geojson_path, driver="GeoJSON")

print("完成：", output_csv_path)
print("完成：", output_geojson_path)


print("\n=== 7. 前 20 筆標準化資料 ===")

print(
    gdf[
        [
            "source_file",
            "sensor_type",
            "sensor_name",
            "station_id",
            "lon",
            "lat",
            "observed_at",
            "value",
            "unit",
        ]
    ]
    .head(20)
    .to_string(index=False)
)