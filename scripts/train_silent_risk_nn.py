from pathlib import Path
import json
import joblib
import numpy as np
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.neural_network import MLPRegressor
from sklearn.metrics import mean_absolute_error, r2_score


PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_CSV = PROJECT_ROOT / "outputs" / "latest" / "silent_risk.csv"
MODEL_DIR = PROJECT_ROOT / "models"
MODEL_PATH = MODEL_DIR / "silent_risk_mlp.joblib"
METADATA_PATH = MODEL_DIR / "silent_risk_mlp_metadata.json"


FEATURE_COLUMNS = [
    "static_risk_score",
    "sensor_gap_score",
    "sensor_realtime_score",
    "realtime_event_score",
    "rainfall_realtime_score",
    "landslide_realtime_score",
    "road_realtime_score",
    "report_count_6h",
    "report_count_24h",
    "elderly_ratio",
    "flood_risk_model",
    "debris_risk_model",
]


def compute_rule_label(df):
    """
    這是目前 MVP 的規則式標籤。
    神經網路第一版會先學會模仿它。

    注意：
    這不是現實世界 ground truth。
    這只是 pseudo-label。
    """
    base_risk_score = (
        0.45 * df["static_risk_score"]
        + 0.20 * df["sensor_gap_score"]
        + 0.15 * df["sensor_realtime_score"]
        + 0.20 * df["realtime_event_score"]
    ).clip(0, 1)

    has_report_6h = (df["report_count_6h"] > 0).astype(float)
    has_report_24h = (df["report_count_24h"] > 0).astype(float)

    report_activity_score = (
        0.7 * has_report_6h
        + 0.3 * has_report_24h
    ).clip(0, 1)

    silence_factor = (1 - report_activity_score).clip(0, 1)

    silent_risk_score = (
        base_risk_score * silence_factor
    ).clip(0, 1)

    return silent_risk_score


def create_training_scenarios(df, scenarios_per_village=80, random_seed=42):
    """
    目前只有 178 個村里，直接訓練太少。
    所以我們用每個村里的靜態特徵，產生多種即時情境：

    - 不同即時雨量
    - 不同路況事件
    - 不同通報數
    - 不同感測器異常

    再用既有規則公式產生 pseudo-label。
    """
    rng = np.random.default_rng(random_seed)

    rows = []

    for _, base_row in df.iterrows():
        for _ in range(scenarios_per_village):
            row = base_row.copy()

            # 靜態特徵保留原村里的狀態
            # 即時特徵則產生不同情境

            row["rainfall_realtime_score"] = rng.beta(1, 8)
            row["landslide_realtime_score"] = rng.beta(1, 10)

            # 路況通常大多數時間為 0，少數為 0.5 或 1
            row["road_realtime_score"] = rng.choice(
                [0.0, 0.5, 1.0],
                p=[0.82, 0.12, 0.06],
            )

            row["sensor_realtime_score"] = rng.choice(
                [0.0, 0.3, 0.7, 1.0],
                p=[0.88, 0.06, 0.04, 0.02],
            )

            row["realtime_event_score"] = (
                0.45 * row["rainfall_realtime_score"]
                + 0.35 * row["landslide_realtime_score"]
                + 0.20 * row["road_realtime_score"]
            )

            # 通報情境：大多數村里無通報，少數有 6h / 24h 通報
            report_case = rng.choice(
                ["none", "24h_only", "6h"],
                p=[0.78, 0.12, 0.10],
            )

            if report_case == "none":
                row["report_count_6h"] = 0
                row["report_count_24h"] = 0
            elif report_case == "24h_only":
                row["report_count_6h"] = 0
                row["report_count_24h"] = rng.integers(1, 4)
            else:
                row["report_count_6h"] = rng.integers(1, 3)
                row["report_count_24h"] = row["report_count_6h"] + rng.integers(0, 3)

            rows.append(row)

    scenario_df = pd.DataFrame(rows)

    scenario_df["target_silent_risk_score"] = compute_rule_label(scenario_df)

    return scenario_df


print("=== 1. 讀取目前 latest silent risk CSV ===")

if not INPUT_CSV.exists():
    raise FileNotFoundError(f"找不到檔案：{INPUT_CSV}")

df = pd.read_csv(INPUT_CSV, encoding="utf-8-sig", dtype={"village_id": str})

print("原始筆數：", len(df))
print("欄位數量：", len(df.columns))


print("\n=== 2. 檢查必要特徵欄位 ===")

for col in FEATURE_COLUMNS:
    if col not in df.columns:
        print(f"缺少欄位 {col}，補 0")
        df[col] = 0.0

for col in FEATURE_COLUMNS:
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

print("特徵欄位都有，可以繼續。")


print("\n=== 3. 建立訓練情境資料 ===")

train_df = create_training_scenarios(df)

print("訓練資料筆數：", len(train_df))
print("target 統計：")
print(train_df["target_silent_risk_score"].describe())


print("\n=== 4. 切分訓練 / 測試資料 ===")

X = train_df[FEATURE_COLUMNS].copy()
y = train_df["target_silent_risk_score"].copy()

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
)


print("X_train:", X_train.shape)
print("X_test:", X_test.shape)


print("\n=== 5. 訓練 MLPRegressor 神經網路 ===")

model = Pipeline(
    steps=[
        ("scaler", StandardScaler()),
        ("mlp", MLPRegressor(
            hidden_layer_sizes=(32, 16),
            activation="relu",
            solver="adam",
            alpha=0.001,
            learning_rate_init=0.001,
            max_iter=2000,
            early_stopping=True,
            random_state=42,
        )),
    ]
)

model.fit(X_train, y_train)


print("\n=== 6. 評估模型 ===")

pred = model.predict(X_test)
pred = np.clip(pred, 0, 1)

mae = mean_absolute_error(y_test, pred)
r2 = r2_score(y_test, pred)

print("MAE:", mae)
print("R2:", r2)

eval_df = X_test.copy()
eval_df["y_true"] = y_test.values
eval_df["y_pred"] = pred
eval_df["abs_error"] = (eval_df["y_true"] - eval_df["y_pred"]).abs()

print("\n誤差最大前 10 筆：")
print(
    eval_df
    .sort_values("abs_error", ascending=False)
    .head(10)
    .to_string(index=False)
)


print("\n=== 7. 儲存模型 ===")

MODEL_DIR.mkdir(parents=True, exist_ok=True)

payload = {
    "model": model,
    "feature_columns": FEATURE_COLUMNS,
}

joblib.dump(payload, MODEL_PATH)

metadata = {
    "model_type": "MLPRegressor",
    "label_type": "pseudo_label_from_rule_based_score",
    "feature_columns": FEATURE_COLUMNS,
    "training_rows": int(len(train_df)),
    "mae": float(mae),
    "r2": float(r2),
    "warning": "This model is trained on pseudo-labels generated by the rule-based MVP formula, not real disaster ground truth.",
}

with open(METADATA_PATH, "w", encoding="utf-8") as f:
    json.dump(metadata, f, ensure_ascii=False, indent=2)

print("完成：", MODEL_PATH)
print("完成：", METADATA_PATH)