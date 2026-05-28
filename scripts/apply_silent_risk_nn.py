from pathlib import Path
import json
import joblib
import numpy as np
import pandas as pd
import geopandas as gpd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

MODEL_PATH = PROJECT_ROOT / "models" / "silent_risk_mlp.joblib"

INPUT_GEOJSON = PROJECT_ROOT / "outputs" / "latest" / "silent_risk.geojson"

OUTPUT_LATEST_DIR = PROJECT_ROOT / "outputs" / "latest"
OUTPUT_HISTORY_ROOT = PROJECT_ROOT / "outputs" / "history"


def assign_level(score):
    if score >= 0.75:
        return "critical"
    if score >= 0.55:
        return "high"
    if score >= 0.35:
        return "medium"
    return "low"


def build_nn_reason(row):
    reasons = []

    if row["silent_risk_nn_score"] >= row["silent_risk_rule_score"]:
        reasons.append("神經網路模型判定沉默風險不低於規則分數")
    else:
        reasons.append("神經網路模型判定沉默風險低於規則分數")

    if row["static_risk_score"] >= 0.35:
        reasons.append("靜態災害風險偏高")

    if row["sensor_gap_score"] >= 0.35:
        reasons.append("感測器覆蓋缺口偏高")

    if row["realtime_event_score"] > 0:
        reasons.append("即時資料有事件訊號")

    if row["report_count_6h"] == 0:
        reasons.append("近6小時無通報")

    if row["report_count_24h"] == 0:
        reasons.append("近24小時無通報")

    if row["report_count_6h"] > 0:
        reasons.append("近6小時已有通報，沉默風險降低")

    return "；".join(reasons)


def make_json_serializable(value):
    if value is None:
        return None

    try:
        is_na = pd.isna(value)
        if hasattr(is_na, "all"):
            if is_na.all():
                return None
        elif is_na:
            return None
    except Exception:
        pass

    if isinstance(value, np.ndarray):
        return value.tolist()

    if isinstance(value, (np.integer,)):
        return int(value)

    if isinstance(value, (np.floating,)):
        return float(value)

    if isinstance(value, pd.Timestamp):
        return value.isoformat()

    if isinstance(value, list):
        return [make_json_serializable(v) for v in value]

    if isinstance(value, dict):
        return {
            str(k): make_json_serializable(v)
            for k, v in value.items()
        }

    return value


def get_run_id(gdf):
    if "realtime_run_id" in gdf.columns and len(gdf) > 0:
        value = str(gdf["realtime_run_id"].iloc[0])
        if value and value != "nan":
            return value

    return "manual"


print("=== 1. 讀取模型與 latest silent risk ===")

if not MODEL_PATH.exists():
    raise FileNotFoundError(f"找不到模型：{MODEL_PATH}，請先執行 train_silent_risk_nn.py")

if not INPUT_GEOJSON.exists():
    raise FileNotFoundError(f"找不到輸入：{INPUT_GEOJSON}")

payload = joblib.load(MODEL_PATH)

model = payload["model"]
feature_columns = payload["feature_columns"]

gdf = gpd.read_file(INPUT_GEOJSON)

print("資料筆數：", len(gdf))
print("模型特徵：", feature_columns)


print("\n=== 2. 準備特徵 ===")

for col in feature_columns:
    if col not in gdf.columns:
        print(f"缺少欄位 {col}，補 0")
        gdf[col] = 0.0

for col in feature_columns:
    gdf[col] = pd.to_numeric(gdf[col], errors="coerce").fillna(0)

X = gdf[feature_columns].copy()


print("\n=== 3. 神經網路推論 ===")

pred = model.predict(X)
pred = np.clip(pred, 0, 1)

# 保留原本規則分數，避免丟失可解釋基準
gdf["silent_risk_rule_score"] = gdf["silent_risk_score"].fillna(0).astype(float)

gdf["silent_risk_nn_score"] = pred.astype(float)

# 第一版先真正替換成神經網路分數
gdf["silent_risk_score"] = gdf["silent_risk_nn_score"]

gdf["silent_risk_level"] = gdf["silent_risk_score"].apply(assign_level)
gdf["silent_reason"] = gdf.apply(build_nn_reason, axis=1)

print("silent_risk_rule_score 統計：")
print(gdf["silent_risk_rule_score"].describe())

print("\nsilent_risk_nn_score 統計：")
print(gdf["silent_risk_nn_score"].describe())

print("\nNN 與 rule 差異統計：")
gdf["nn_minus_rule"] = gdf["silent_risk_nn_score"] - gdf["silent_risk_rule_score"]
print(gdf["nn_minus_rule"].describe())

print("\n神經網路沉默風險最高前 20：")
print(
    gdf[
        [
            "village_id",
            "county_name",
            "town_name",
            "village_name",
            "static_risk_score",
            "sensor_gap_score",
            "realtime_event_score",
            "report_count_6h",
            "report_count_24h",
            "silent_risk_rule_score",
            "silent_risk_nn_score",
            "silent_risk_level",
        ]
    ]
    .sort_values("silent_risk_nn_score", ascending=False)
    .head(20)
    .to_string(index=False)
)


print("\n=== 4. 輸出 latest 與 history ===")

run_id = get_run_id(gdf)

history_dir = OUTPUT_HISTORY_ROOT / run_id

OUTPUT_LATEST_DIR.mkdir(parents=True, exist_ok=True)
history_dir.mkdir(parents=True, exist_ok=True)

latest_geojson = OUTPUT_LATEST_DIR / "silent_risk.geojson"
latest_csv = OUTPUT_LATEST_DIR / "silent_risk.csv"
latest_json = OUTPUT_LATEST_DIR / "silent_risk.json"

history_geojson = history_dir / "silent_risk_nn.geojson"
history_csv = history_dir / "silent_risk_nn.csv"
history_json = history_dir / "silent_risk_nn.json"

gdf.to_file(latest_geojson, driver="GeoJSON")
gdf.to_file(history_geojson, driver="GeoJSON")

gdf.drop(columns=["geometry"]).to_csv(
    latest_csv,
    index=False,
    encoding="utf-8-sig",
)

gdf.drop(columns=["geometry"]).to_csv(
    history_csv,
    index=False,
    encoding="utf-8-sig",
)


json_columns = [
    "village_id",
    "county_name",
    "town_name",
    "village_name",
    "population_total",
    "elderly_ratio",
    "static_risk_score",
    "sensor_gap_score",
    "sensor_realtime_score",
    "rainfall_realtime_score",
    "landslide_realtime_score",
    "road_realtime_score",
    "realtime_event_score",
    "report_count_6h",
    "report_count_24h",
    "base_risk_score",
    "report_activity_score",
    "silence_factor",
    "silent_risk_rule_score",
    "silent_risk_nn_score",
    "silent_risk_score",
    "silent_risk_level",
    "silent_reason",
    "realtime_run_id",
]

json_df = (
    gdf[json_columns]
    .sort_values("silent_risk_score", ascending=False)
    .copy()
)

records = []

for record in json_df.to_dict(orient="records"):
    records.append({
        key: make_json_serializable(value)
        for key, value in record.items()
    })

with open(latest_json, "w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)

with open(history_json, "w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)

print("完成：", latest_geojson)
print("完成：", latest_csv)
print("完成：", latest_json)
print("完成：", history_geojson)
print("完成：", history_csv)
print("完成：", history_json)