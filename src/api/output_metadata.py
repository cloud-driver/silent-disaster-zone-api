from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

OUTPUT_JSON = PROJECT_ROOT / "outputs" / "latest" / "silent_risk.json"
OUTPUT_GEOJSON = (
    PROJECT_ROOT
    / "outputs"
    / "latest"
    / "silent_risk.geojson"
)

SAMPLE_JSON = (
    PROJECT_ROOT
    / "sample_outputs"
    / "silent_risk_sample.json"
)

SAMPLE_GEOJSON = (
    PROJECT_ROOT
    / "sample_outputs"
    / "silent_risk_sample.geojson"
)

MANIFEST_PATH = (
    PROJECT_ROOT
    / "outputs"
    / "latest"
    / "run_manifest.json"
)


def get_available_json_path() -> Path | None:
    if OUTPUT_JSON.exists():
        return OUTPUT_JSON

    if SAMPLE_JSON.exists():
        return SAMPLE_JSON

    return None


def get_available_geojson_path() -> Path | None:
    if OUTPUT_GEOJSON.exists():
        return OUTPUT_GEOJSON

    if SAMPLE_GEOJSON.exists():
        return SAMPLE_GEOJSON

    return None


def _load_manifest_safely() -> dict[str, Any] | None:
    if not MANIFEST_PATH.exists():
        return None

    try:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as file:
            manifest = json.load(file)
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(manifest, dict):
        return None

    return manifest


def _parse_age_seconds(
    timestamp: Any,
) -> int | None:
    if not isinstance(timestamp, str) or not timestamp.strip():
        return None

    try:
        parsed = datetime.fromisoformat(
            timestamp.replace("Z", "+00:00")
        )
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)

    return max(
        0,
        int(
            (
                now
                - parsed.astimezone(timezone.utc)
            ).total_seconds()
        ),
    )


def _get_freshness(
    data_mode: str,
    age_seconds: int | None,
) -> str:
    if data_mode == "sample":
        return "sample_data"

    if data_mode == "batch":
        return "not_realtime"

    if data_mode != "live":
        return "unknown"

    if age_seconds is None:
        return "unknown"

    if age_seconds <= 30 * 60:
        return "fresh"

    if age_seconds <= 6 * 60 * 60:
        return "stale"

    return "expired"


def _sanitize_sources(
    manifest: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    if manifest is None:
        return {}

    raw_sources = manifest.get("sources", {})

    if not isinstance(raw_sources, dict):
        return {}

    clean_sources = {}

    for source_name, source_info in raw_sources.items():
        if not isinstance(source_info, dict):
            continue

        clean_sources[str(source_name)] = {
            "status": source_info.get("status", "unknown"),
            "fetched_at": source_info.get("fetched_at"),
        }

    return clean_sources


def _single_record_value(
    records: list[dict[str, Any]],
    field_name: str,
) -> str | None:
    values = sorted(
        {
            str(record[field_name])
            for record in records
            if isinstance(record, dict)
            and record.get(field_name) not in {None, ""}
        }
    )

    if not values:
        return None

    if len(values) == 1:
        return values[0]

    return "mixed"


def build_dataset_metadata(
    records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    active_json_path = get_available_json_path()

    if active_json_path is None:
        return {
            "availability": "missing",
            "data_mode": "missing",
            "verification": "missing",
            "pipeline_status": "missing",
            "record_count": 0,
        }

    active_json_relative = str(
        active_json_path.relative_to(PROJECT_ROOT)
    )

    if active_json_path == SAMPLE_JSON:
        metadata = {
            "availability": "ready",
            "data_mode": "sample",
            "verification": "static_sample",
            "pipeline_status": "sample_only",
            "run_id": None,
            "generated_at": None,
            "generated_age_seconds": None,
            "freshness": "sample_data",
            "active_json": active_json_relative,
            "source_status": {},
            "has_source_issues": False,
        }
    else:
        manifest = _load_manifest_safely()

        data_mode = "unverified"
        verification = "unverified"
        pipeline_status = "unverified_output"
        run_id = None
        generated_at = None
        source_status = {}

        if manifest is not None:
            declared_mode = manifest.get("data_mode")
            declared_status = manifest.get("pipeline_status")

            if (
                declared_mode in {"live", "batch"}
                and declared_status == "scoring_completed"
            ):
                data_mode = declared_mode
                verification = "verified"

            pipeline_status = declared_status
            run_id = manifest.get("run_id")
            generated_at = manifest.get("generated_at")
            source_status = _sanitize_sources(manifest)

        generated_age_seconds = _parse_age_seconds(
            generated_at
        )

        metadata = {
            "availability": "ready",
            "data_mode": data_mode,
            "verification": verification,
            "pipeline_status": pipeline_status,
            "run_id": run_id,
            "generated_at": generated_at,
            "generated_age_seconds": generated_age_seconds,
            "freshness": _get_freshness(
                data_mode,
                generated_age_seconds,
            ),
            "active_json": active_json_relative,
            "source_status": source_status,
            "has_source_issues": any(
                source.get("status")
                in {"failed", "skipped"}
                for source in source_status.values()
            ),
        }

    if records is not None:
        metadata["record_count"] = len(records)
        metadata["scoring_mode"] = _single_record_value(
            records,
            "scoring_mode",
        )
        metadata["model_status"] = _single_record_value(
            records,
            "model_status",
        )

    return metadata