from __future__ import annotations

import pandas as pd


def assign_level(score: float) -> str:
    if score >= 0.75:
        return "critical"
    if score >= 0.55:
        return "high"
    if score >= 0.35:
        return "medium"
    return "low"


def _ensure_numeric(
    frame: pd.DataFrame,
    column: str,
    default: float = 0.0,
) -> None:
    if column not in frame.columns:
        frame[column] = default

    frame[column] = (
        pd.to_numeric(frame[column], errors="coerce")
        .fillna(default)
        .astype(float)
    )


def apply_silent_risk_scoring(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    """
    沉默災區正式計分公式。

    此函式同時供：
    1. 批次資料 pipeline 使用
    2. 即時資料 pipeline 使用
    3. 未來背景排程使用

    使用同一套公式，避免不同資料路徑得到不同排名。
    """
    scored = frame.copy()

    required_columns = [
        "static_risk_score",
        "sensor_gap_score",
        "report_count_6h",
        "report_count_24h",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in scored.columns
    ]

    if missing_columns:
        raise ValueError(
            f"缺少沉默風險計分必要欄位：{missing_columns}"
        )

    numeric_columns = [
        "static_risk_score",
        "sensor_gap_score",
        "sensor_realtime_score",
        "realtime_event_score",
        "report_count_6h",
        "report_count_24h",
    ]

    for column in numeric_columns:
        _ensure_numeric(scored, column)

    # 24 小時通報量不應小於 6 小時通報量。
    scored["report_count_24h"] = scored[
        ["report_count_6h", "report_count_24h"]
    ].max(axis=1)

    # 通報活動改採連續分數。
    # 一筆通報只能降低風險，不能使沉默風險歸零。
    scored["recent_report_score"] = (
        scored["report_count_6h"] / 3
    ).clip(0, 1)

    scored["older_report_score"] = (
        (
            scored["report_count_24h"]
            - scored["report_count_6h"]
        ).clip(lower=0) / 6
    ).clip(0, 1)

    scored["report_activity_score"] = (
        0.70 * scored["recent_report_score"]
        + 0.30 * scored["older_report_score"]
    ).clip(0, 1)

    scored["silence_factor"] = (
        1 - scored["report_activity_score"]
    ).clip(0, 1)

    # 風險證據：地區風險、感測異常、即時事件。
    scored["risk_evidence_score"] = (
        0.55 * scored["static_risk_score"]
        + 0.20 * scored["sensor_realtime_score"]
        + 0.25 * scored["realtime_event_score"]
    ).clip(0, 1)

    # 觀測缺口只描述資料不足，不重複計入靜態災害風險。
    scored["observation_gap_score"] = (
        scored["sensor_gap_score"]
    ).clip(0, 1)

    # 保留舊欄位，避免既有 API Client 壞掉。
    scored["base_risk_score"] = scored["risk_evidence_score"]

    # 正式沉默風險。
    scored["silent_risk_score"] = (
        scored["risk_evidence_score"]
        * (
            0.50
            + 0.50 * scored["observation_gap_score"]
        )
        * scored["silence_factor"]
    ).clip(0, 1)

    scored["silent_risk_rule_score"] = (
        scored["silent_risk_score"]
    )

    # 批次版沒有跑 NN 時，保留固定欄位形狀。
    scored["silent_risk_nn_score"] = None
    scored["scoring_mode"] = "rule_based_mvp"
    scored["model_status"] = "not_applied"

    scored["silent_risk_level"] = scored[
        "silent_risk_score"
    ].apply(assign_level)

    return scored