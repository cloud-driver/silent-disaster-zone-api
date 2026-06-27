from __future__ import annotations

from typing import Any, Iterable

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point


CATEGORY_LABELS = {
    "flooding": "積淹水",
    "landslide": "土石／落石",
    "road_blocked": "道路中斷",
    "trapped_people": "受困／需協助",
    "power_or_comms": "停電／通訊異常",
    "other": "其他",
}

FEATURE_COLUMNS = [
    "verified_report_count_6h",
    "verified_report_count_24h",
    "verified_report_severity_sum_6h",
    "verified_report_severity_sum_24h",
    "verified_report_max_severity_6h",
    "verified_report_max_severity_24h",
]


def to_utc_timestamp(value: Any) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)

    if pd.isna(timestamp):
        raise ValueError("時間格式無效。")

    if timestamp.tzinfo is None:
        return timestamp.tz_localize("UTC")

    return timestamp.tz_convert("UTC")


def incident_priority(
    category: str,
    severity: int,
) -> str:
    if category == "trapped_people" or severity >= 3:
        return "I1"

    if severity >= 2:
        return "I2"

    if category in {
        "flooding",
        "landslide",
        "road_blocked",
    }:
        return "I2"

    return "I3"


def incident_actions(
    category: str,
) -> list[str]:
    actions = [
        "確認人工查證紀錄、回報時間與現場狀況是否仍有效。",
        "將此事件與同區域即時資料及既有通報交叉比對。",
    ]

    if category == "trapped_people":
        actions.append(
            "優先確認受困資訊是否持續存在，並依既有應變程序轉交人員研判。"
        )

    elif category == "road_blocked":
        actions.append(
            "確認道路阻斷位置、替代動線與是否需要現場查核。"
        )

    elif category == "landslide":
        actions.append(
            "確認落石或邊坡影響範圍，並比對降雨與警戒資料。"
        )

    elif category == "flooding":
        actions.append(
            "確認積淹水位置、深度變化與通行影響。"
        )

    return actions


def village_label(
    row: dict[str, Any],
) -> str:
    return "".join(
        [
            str(row.get("county_name", "")).strip(),
            str(row.get("town_name", "")).strip(),
            str(row.get("village_name", "")).strip(),
        ]
    ) or str(row.get("village_id", "未知區域"))


def build_empty_features(
    villages: gpd.GeoDataFrame,
    run_id: str,
    generated_at: str,
) -> pd.DataFrame:
    if "village_id" not in villages.columns:
        raise ValueError("村里資料缺少 village_id。")

    features = pd.DataFrame(
        {
            "village_id": villages["village_id"]
            .astype(str)
            .drop_duplicates()
        }
    )

    for column in FEATURE_COLUMNS:
        features[column] = 0

    features["report_data_source"] = (
        "verified_human_reviewed_reports"
    )
    features["report_feature_run_id"] = run_id
    features["report_feature_generated_at"] = generated_at

    return features


def build_verified_report_analytics(
    villages: gpd.GeoDataFrame,
    reports: Iterable[dict[str, Any]],
    *,
    analysis_time: Any = None,
    run_id: str,
    generated_at: str,
) -> tuple[pd.DataFrame, list[dict[str, Any]], dict[str, Any]]:
    if villages.crs is None:
        raise ValueError("村里圖資缺少 CRS。")

    if analysis_time is None:
        analysis_timestamp = pd.Timestamp.now(tz="UTC")
    else:
        analysis_timestamp = to_utc_timestamp(analysis_time)

    features = build_empty_features(
        villages,
        run_id=run_id,
        generated_at=generated_at,
    )

    metadata = {
        "analysis_time": analysis_timestamp.isoformat(),
        "verified_report_total": 0,
        "eligible_recent_report_count": 0,
        "matched_report_count": 0,
        "outside_analysis_area_count": 0,
        "ignored_old_or_future_count": 0,
        "ignored_missing_location_or_time_count": 0,
    }

    report_rows = list(reports)

    if not report_rows:
        return features, [], metadata

    reports_df = pd.DataFrame(report_rows)

    required_columns = [
        "report_id",
        "status",
        "category",
        "severity",
        "created_at",
        "latitude",
        "longitude",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in reports_df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"verified report 資料缺少欄位：{missing_columns}"
        )

    reports_df["status"] = (
        reports_df["status"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    verified = reports_df[
        reports_df["status"] == "verified"
    ].copy()

    metadata["verified_report_total"] = len(verified)

    if verified.empty:
        return features, [], metadata

    verified["severity"] = pd.to_numeric(
        verified["severity"],
        errors="coerce",
    )

    verified["latitude"] = pd.to_numeric(
        verified["latitude"],
        errors="coerce",
    )

    verified["longitude"] = pd.to_numeric(
        verified["longitude"],
        errors="coerce",
    )

    verified["created_at"] = pd.to_datetime(
        verified["created_at"],
        errors="coerce",
        utc=True,
    )

    valid_location_and_time = verified[
        verified["severity"].notna()
        & verified["latitude"].notna()
        & verified["longitude"].notna()
        & verified["created_at"].notna()
    ].copy()

    metadata["ignored_missing_location_or_time_count"] = (
        len(verified) - len(valid_location_and_time)
    )

    window_start = analysis_timestamp - pd.Timedelta(hours=24)

    recent = valid_location_and_time[
        (valid_location_and_time["created_at"] >= window_start)
        & (
            valid_location_and_time["created_at"]
            <= analysis_timestamp
        )
    ].copy()

    metadata["ignored_old_or_future_count"] = (
        len(valid_location_and_time) - len(recent)
    )

    metadata["eligible_recent_report_count"] = len(recent)

    if recent.empty:
        return features, [], metadata

    villages_4326 = villages.to_crs(epsg=4326).copy()

    village_columns = [
        "village_id",
        "county_name",
        "town_name",
        "village_name",
        "geometry",
    ]

    villages_4326 = villages_4326[village_columns].copy()
    villages_4326["village_id"] = (
        villages_4326["village_id"].astype(str)
    )

    reports_gdf = gpd.GeoDataFrame(
        recent,
        geometry=[
            Point(longitude, latitude)
            for longitude, latitude in zip(
                recent["longitude"],
                recent["latitude"],
            )
        ],
        crs="EPSG:4326",
    )

    joined = gpd.sjoin(
        reports_gdf,
        villages_4326,
        how="left",
        predicate="intersects",
    )

    joined["_village_sort"] = (
        joined["village_id"]
        .fillna("")
        .astype(str)
    )

    joined = (
        joined.sort_values(
            ["report_id", "_village_sort"],
            kind="stable",
        )
        .drop_duplicates(
            subset=["report_id"],
            keep="first",
        )
        .drop(columns=["_village_sort"])
    )

    matched = joined[
        joined["village_id"].notna()
    ].copy()

    matched["village_id"] = (
        matched["village_id"].astype(str)
    )

    metadata["matched_report_count"] = len(matched)
    metadata["outside_analysis_area_count"] = (
        len(recent) - len(matched)
    )

    if matched.empty:
        return features, [], metadata

    six_hour_start = (
        analysis_timestamp - pd.Timedelta(hours=6)
    )

    recent_6h = matched[
        matched["created_at"] >= six_hour_start
    ].copy()

    aggregated_24h = (
        matched.groupby("village_id")
        .agg(
            verified_report_count_24h=(
                "report_id",
                "nunique",
            ),
            verified_report_severity_sum_24h=(
                "severity",
                "sum",
            ),
            verified_report_max_severity_24h=(
                "severity",
                "max",
            ),
        )
        .reset_index()
    )

    if recent_6h.empty:
        aggregated_6h = pd.DataFrame(
            columns=[
                "village_id",
                "verified_report_count_6h",
                "verified_report_severity_sum_6h",
                "verified_report_max_severity_6h",
            ]
        )
    else:
        aggregated_6h = (
            recent_6h.groupby("village_id")
            .agg(
                verified_report_count_6h=(
                    "report_id",
                    "nunique",
                ),
                verified_report_severity_sum_6h=(
                    "severity",
                    "sum",
                ),
                verified_report_max_severity_6h=(
                    "severity",
                    "max",
                ),
            )
            .reset_index()
        )

    features = features.merge(
        aggregated_24h,
        on="village_id",
        how="left",
        suffixes=("", "_new"),
    )

    features = features.merge(
        aggregated_6h,
        on="village_id",
        how="left",
        suffixes=("", "_new"),
    )

    for column in FEATURE_COLUMNS:
        replacement_column = f"{column}_new"

        if replacement_column in features.columns:
            features[column] = features[
                replacement_column
            ].combine_first(features[column])

            features = features.drop(
                columns=[replacement_column]
            )

        features[column] = pd.to_numeric(
            features[column],
            errors="coerce",
        ).fillna(0).astype(int)

    counts_by_village = (
        features.set_index("village_id")
        ["verified_report_count_24h"]
        .to_dict()
    )

    matched["_priority_rank"] = matched.apply(
        lambda row: {
            "I1": 1,
            "I2": 2,
            "I3": 3,
        }[
            incident_priority(
                str(row["category"]),
                int(row["severity"]),
            )
        ],
        axis=1,
    )

    matched = matched.sort_values(
        [
            "_priority_rank",
            "severity",
            "created_at",
        ],
        ascending=[True, False, False],
        kind="stable",
    )

    incidents = []

    for _, row in matched.iterrows():
        severity = int(row["severity"])
        category = str(row["category"])
        village_id = str(row["village_id"])

        incidents.append(
            {
                "incident_id": str(row["report_id"]),
                "incident_priority": incident_priority(
                    category,
                    severity,
                ),
                "village_id": village_id,
                "village_label": village_label(row),
                "category": category,
                "category_label": CATEGORY_LABELS.get(
                    category,
                    category,
                ),
                "severity": severity,
                "reported_at": row["created_at"].isoformat(),
                "reviewed_at": (
                    str(row.get("reviewed_at", "")).strip()
                    or None
                ),
                "village_verified_report_count_24h": int(
                    counts_by_village.get(village_id, 0)
                ),
                "recommended_actions": incident_actions(
                    category
                ),
                "needs_human_confirmation": True,
            }
        )

    return features, incidents, metadata