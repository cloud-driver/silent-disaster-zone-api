from __future__ import annotations

import os
import secrets
from typing import Literal

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
)
from pydantic import BaseModel, Field

from src.reports.store import (
    get_report_summary,
    init_db,
    list_reports,
    review_report,
)


router = APIRouter(
    prefix="/reports",
    tags=["reports"],
)

init_db()


class ReviewRequest(BaseModel):
    decision: Literal["verified", "rejected"]

    reviewer_id: str = Field(
        default="admin",
        min_length=1,
        max_length=80,
    )

    reviewer_note: str = Field(
        default="",
        max_length=1000,
    )


def require_report_admin_key(
    x_admin_key: str | None = Header(
        default=None,
        alias="X-Admin-Key",
    ),
) -> None:
    configured_key = os.getenv(
        "REPORT_ADMIN_KEY",
        "",
    ).strip()

    if not configured_key:
        raise HTTPException(
            status_code=503,
            detail=(
                "REPORT_ADMIN_KEY 尚未設定，"
                "審核 API 暫不可用。"
            ),
        )

    if (
        not x_admin_key
        or not secrets.compare_digest(
            x_admin_key,
            configured_key,
        )
    ):
        raise HTTPException(
            status_code=403,
            detail="審核金鑰無效。",
        )


@router.get("/summary")
def report_summary():
    return get_report_summary()


@router.get("/pending")
def pending_reports(
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
    ),
    _: None = Depends(require_report_admin_key),
):
    reports = list_reports(
        status="pending",
        limit=limit,
    )

    return {
        "count": len(reports),
        "data": reports,
    }


@router.post("/{report_id}/review")
def review_single_report(
    report_id: str,
    payload: ReviewRequest,
    _: None = Depends(require_report_admin_key),
):
    try:
        report = review_report(
            report_id=report_id,
            decision=payload.decision,
            reviewer_id=payload.reviewer_id,
            reviewer_note=payload.reviewer_note,
        )

        return {
            "status": "success",
            "report": report,
            "summary": get_report_summary(),
        }

    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    except ValueError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error