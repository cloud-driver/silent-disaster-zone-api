from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.reports import require_report_admin_key


PROJECT_ROOT = Path(__file__).resolve().parents[2]

INCIDENT_PATH = (
    PROJECT_ROOT
    / "outputs"
    / "latest"
    / "verified_incidents.json"
)

router = APIRouter(
    prefix="/incidents",
    tags=["incidents"],
)


def load_verified_incident_snapshot() -> dict[str, Any]:
    if not INCIDENT_PATH.exists():
        return {
            "available": False,
            "run_id": None,
            "generated_at": None,
            "summary": {},
            "data": [],
        }

    with open(
        INCIDENT_PATH,
        "r",
        encoding="utf-8",
    ) as file:
        payload = json.load(file)

    if not isinstance(payload, dict):
        raise ValueError(
            "verified_incidents.json 格式錯誤。"
        )

    data = payload.get("data", [])

    if not isinstance(data, list):
        raise ValueError(
            "verified_incidents.json 的 data 必須是 list。"
        )

    return {
        "available": True,
        "run_id": payload.get("run_id"),
        "generated_at": payload.get("generated_at"),
        "summary": payload.get("summary", {}),
        "data": data,
    }


@router.get("/verified")
def get_verified_incidents(
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    _: None = Depends(require_report_admin_key),
):
    snapshot = load_verified_incident_snapshot()

    if not snapshot["available"]:
        raise HTTPException(
            status_code=404,
            detail=(
                "找不到已驗證事件 snapshot，"
                "請先執行 realtime pipeline。"
            ),
        )

    data = snapshot["data"][:limit]

    return {
        "meta": {
            "run_id": snapshot["run_id"],
            "generated_at": snapshot["generated_at"],
            "summary": snapshot["summary"],
        },
        "count": len(data),
        "data": data,
    }