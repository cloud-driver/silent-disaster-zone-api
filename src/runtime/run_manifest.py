from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LATEST_MANIFEST_PATH = (
    PROJECT_ROOT
    / "outputs"
    / "latest"
    / "run_manifest.json"
)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def create_manifest(
    run_id: str,
    source_names: Iterable[str],
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "run_id": run_id,
        "data_mode": "live",
        "pipeline_status": "fetching",
        "created_at": now_iso(),
        "fetch_completed_at": None,
        "generated_at": None,
        "outputs": {},
        "sources": {
            source_name: {
                "status": "pending",
                "fetched_at": None,
                "raw_path": None,
                "message": None,
            }
            for source_name in source_names
        },
    }


def update_source(
    manifest: dict[str, Any],
    source_name: str,
    status: str,
    raw_path: str | None = None,
    message: str | None = None,
) -> None:
    source = manifest["sources"].setdefault(
        source_name,
        {},
    )

    source.update(
        {
            "status": status,
            "fetched_at": now_iso(),
            "raw_path": raw_path,
            "message": message,
        }
    )


def mark_fetch_complete(manifest: dict[str, Any]) -> None:
    manifest["pipeline_status"] = "fetch_completed"
    manifest["fetch_completed_at"] = now_iso()


def write_manifest(manifest: dict[str, Any]) -> None:
    LATEST_MANIFEST_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = LATEST_MANIFEST_PATH.with_suffix(".tmp")

    with open(temporary_path, "w", encoding="utf-8") as file:
        json.dump(
            manifest,
            file,
            ensure_ascii=False,
            indent=2,
        )

    temporary_path.replace(LATEST_MANIFEST_PATH)


def load_manifest() -> dict[str, Any] | None:
    if not LATEST_MANIFEST_PATH.exists():
        return None

    with open(LATEST_MANIFEST_PATH, "r", encoding="utf-8") as file:
        manifest = json.load(file)

    if not isinstance(manifest, dict):
        raise ValueError("run_manifest.json 格式錯誤。")

    return manifest


def mark_scoring_complete(
    run_id: str,
    outputs: dict[str, str],
) -> dict[str, Any]:
    manifest = load_manifest()

    if manifest is None:
        raise RuntimeError(
            "找不到 run_manifest.json，請先執行 "
            "scripts/fetch_realtime_sources.py。"
        )

    if manifest.get("run_id") != run_id:
        raise RuntimeError(
            "目前 manifest 的 run_id 與計分資料 run_id 不一致。"
        )

    manifest["pipeline_status"] = "scoring_completed"
    manifest["generated_at"] = now_iso()
    manifest["outputs"] = outputs

    write_manifest(manifest)

    return manifest

def write_batch_manifest(
    outputs: dict[str, str],
) -> dict[str, Any]:
    generated_at = now_iso()

    manifest = {
        "schema_version": "1.0",
        "run_id": (
            "batch_"
            + datetime.now().strftime("%Y%m%d_%H%M%S")
        ),
        "data_mode": "batch",
        "pipeline_status": "scoring_completed",
        "created_at": generated_at,
        "fetch_completed_at": None,
        "generated_at": generated_at,
        "outputs": outputs,
        "sources": {},
        "notes": [
            "資料由完整批次 pipeline 產生，並非即時抓取。",
        ],
    }

    write_manifest(manifest)

    return manifest