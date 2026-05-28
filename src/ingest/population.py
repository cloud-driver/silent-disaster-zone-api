# src/ingest/population.py

import pandas as pd

def load_population(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path, encoding="utf-8")
    print("人口資料欄位：", df.columns.tolist())
    return df

def normalize_population(df: pd.DataFrame) -> pd.DataFrame:
    # 你要依實際欄位調整
    possible_age_cols = ["age", "年齡", "性別年齡"]
    possible_pop_cols = ["population", "人口數", "人數"]

    age_col = next((c for c in possible_age_cols if c in df.columns), None)
    pop_col = next((c for c in possible_pop_cols if c in df.columns), None)

    if age_col is None or pop_col is None:
        raise ValueError("找不到年齡或人口數欄位，請先檢查 CSV 欄位")

    # 假設已經有 county_name, town_name, village_name
    key_cols = ["county_name", "town_name", "village_name"]
    for c in key_cols:
        if c not in df.columns:
            raise ValueError(f"人口資料缺欄位：{c}")

    df[pop_col] = pd.to_numeric(df[pop_col], errors="coerce").fillna(0)

    # 年齡欄位要依實際格式清理
    df["age_num"] = pd.to_numeric(df[age_col], errors="coerce")

    total = (
        df.groupby(key_cols)[pop_col]
        .sum()
        .reset_index()
        .rename(columns={pop_col: "population_total"})
    )

    elderly = (
        df[df["age_num"] >= 65]
        .groupby(key_cols)[pop_col]
        .sum()
        .reset_index()
        .rename(columns={pop_col: "elderly_population"})
    )

    result = total.merge(elderly, on=key_cols, how="left")
    result["elderly_population"] = result["elderly_population"].fillna(0)
    result["elderly_ratio"] = result["elderly_population"] / result["population_total"].replace(0, 1)

    result["village_id"] = (
        result["county_name"].astype(str)
        + "_"
        + result["town_name"].astype(str)
        + "_"
        + result["village_name"].astype(str)
    )

    return result