from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_DB_PATH = (
    PROJECT_ROOT
    / "data"
    / "reports"
    / "disaster_reports.sqlite3"
)

REPORT_CATEGORIES = {
    "flooding",
    "landslide",
    "road_blocked",
    "trapped_people",
    "power_or_comms",
    "other",
}

REPORT_STATUSES = {
    "pending",
    "verified",
    "rejected",
}

REPORT_SOURCES = {
    "line",
    "manual",
    "api",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    )


def resolve_db_path(
    db_path: str | Path | None = None,
) -> Path:
    if db_path is not None:
        return Path(db_path).expanduser().resolve()

    configured = os.getenv("REPORT_DB_PATH", "").strip()

    if configured:
        return Path(configured).expanduser().resolve()

    return DEFAULT_DB_PATH


def get_connection(
    db_path: str | Path | None = None,
) -> sqlite3.Connection:
    path = resolve_db_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(
        path,
        timeout=30,
    )

    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")

    return connection


def row_to_dict(
    row: sqlite3.Row | None,
) -> dict[str, Any] | None:
    if row is None:
        return None

    return dict(row)


def init_db(
    db_path: str | Path | None = None,
) -> None:
    connection = get_connection(db_path)

    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS disaster_reports (
                report_id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                external_event_id TEXT UNIQUE,
                reporter_hash TEXT NOT NULL,
                category TEXT NOT NULL,
                severity INTEGER NOT NULL,
                description TEXT NOT NULL,
                latitude REAL,
                longitude REAL,
                location_label TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                reviewed_at TEXT,
                reviewer_id TEXT,
                reviewer_note TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_reports_status_created
            ON disaster_reports(status, created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_reports_location
            ON disaster_reports(latitude, longitude);
            """
        )

        connection.commit()

    finally:
        connection.close()


def hash_reporter_id(
    raw_user_id: str,
    secret: str,
) -> str:
    if not raw_user_id.strip():
        raise ValueError("raw_user_id 不可為空。")

    if not secret.strip():
        raise ValueError(
            "REPORTER_HASH_SECRET 尚未設定。"
        )

    return hmac.new(
        secret.encode("utf-8"),
        raw_user_id.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def validate_report_input(
    *,
    source: str,
    reporter_hash: str,
    category: str,
    severity: int,
    description: str,
    latitude: float | None,
    longitude: float | None,
) -> tuple[str, str, str, int, str, float | None, float | None]:
    source = source.strip().lower()
    category = category.strip().lower()
    description = description.strip()

    if source not in REPORT_SOURCES:
        raise ValueError(
            f"不支援的 source：{source}"
        )

    if not reporter_hash.strip():
        raise ValueError("reporter_hash 不可為空。")

    if category not in REPORT_CATEGORIES:
        raise ValueError(
            f"不支援的災情類型：{category}"
        )

    if severity not in {1, 2, 3}:
        raise ValueError(
            "severity 必須是 1、2 或 3。"
        )

    if not description:
        raise ValueError("description 不可為空。")

    if len(description) > 1000:
        raise ValueError(
            "description 不可超過 1000 字。"
        )

    if latitude is not None:
        latitude = float(latitude)

        if not -90 <= latitude <= 90:
            raise ValueError("latitude 超出有效範圍。")

    if longitude is not None:
        longitude = float(longitude)

        if not -180 <= longitude <= 180:
            raise ValueError("longitude 超出有效範圍。")

    return (
        source,
        reporter_hash.strip(),
        category,
        severity,
        description,
        latitude,
        longitude,
    )


def get_report(
    report_id: str,
    db_path: str | Path | None = None,
) -> dict[str, Any] | None:
    init_db(db_path)

    connection = get_connection(db_path)

    try:
        row = connection.execute(
            """
            SELECT *
            FROM disaster_reports
            WHERE report_id = ?
            """,
            (report_id,),
        ).fetchone()

        return row_to_dict(row)

    finally:
        connection.close()


def create_report(
    *,
    source: str,
    reporter_hash: str,
    category: str,
    severity: int,
    description: str,
    latitude: float | None = None,
    longitude: float | None = None,
    location_label: str | None = None,
    external_event_id: str | None = None,
    db_path: str | Path | None = None,
) -> tuple[dict[str, Any], bool]:
    init_db(db_path)

    (
        source,
        reporter_hash,
        category,
        severity,
        description,
        latitude,
        longitude,
    ) = validate_report_input(
        source=source,
        reporter_hash=reporter_hash,
        category=category,
        severity=severity,
        description=description,
        latitude=latitude,
        longitude=longitude,
    )

    external_event_id = (
        external_event_id.strip()
        if external_event_id
        else None
    )

    location_label = (
        location_label.strip()
        if location_label
        else None
    )

    connection = get_connection(db_path)

    try:
        if external_event_id:
            existing = connection.execute(
                """
                SELECT *
                FROM disaster_reports
                WHERE external_event_id = ?
                """,
                (external_event_id,),
            ).fetchone()

            if existing is not None:
                return row_to_dict(existing), False

        report_id = (
            "RPT-"
            + uuid.uuid4().hex[:12].upper()
        )

        created_at = now_iso()

        connection.execute(
            """
            INSERT INTO disaster_reports (
                report_id,
                source,
                external_event_id,
                reporter_hash,
                category,
                severity,
                description,
                latitude,
                longitude,
                location_label,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (
                report_id,
                source,
                external_event_id,
                reporter_hash,
                category,
                severity,
                description,
                latitude,
                longitude,
                location_label,
                created_at,
            ),
        )

        connection.commit()

    finally:
        connection.close()

    report = get_report(
        report_id,
        db_path=db_path,
    )

    if report is None:
        raise RuntimeError("通報建立後無法重新讀取。")

    return report, True


def list_reports(
    *,
    status: str | None = None,
    limit: int = 50,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    init_db(db_path)

    if limit < 1 or limit > 200:
        raise ValueError("limit 必須介於 1 至 200。")

    query = """
        SELECT *
        FROM disaster_reports
    """

    parameters: list[Any] = []

    if status is not None:
        status = status.strip().lower()

        if status not in REPORT_STATUSES:
            raise ValueError(
                f"不支援的 status：{status}"
            )

        query += " WHERE status = ?"
        parameters.append(status)

    query += " ORDER BY created_at DESC LIMIT ?"
    parameters.append(limit)

    connection = get_connection(db_path)

    try:
        rows = connection.execute(
            query,
            parameters,
        ).fetchall()

        return [
            row_to_dict(row)
            for row in rows
        ]

    finally:
        connection.close()


def list_verified_reports(
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    init_db(db_path)

    connection = get_connection(db_path)

    try:
        rows = connection.execute(
            """
            SELECT *
            FROM disaster_reports
            WHERE status = 'verified'
            ORDER BY created_at DESC
            """
        ).fetchall()

        return [
            row_to_dict(row)
            for row in rows
        ]

    finally:
        connection.close()

def review_report(
    *,
    report_id: str,
    decision: str,
    reviewer_id: str,
    reviewer_note: str = "",
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    init_db(db_path)

    decision = decision.strip().lower()

    if decision not in {"verified", "rejected"}:
        raise ValueError(
            "decision 必須是 verified 或 rejected。"
        )

    reviewer_id = reviewer_id.strip()

    if not reviewer_id:
        raise ValueError("reviewer_id 不可為空。")

    reviewer_note = reviewer_note.strip()

    if len(reviewer_note) > 1000:
        raise ValueError(
            "reviewer_note 不可超過 1000 字。"
        )

    connection = get_connection(db_path)

    try:
        current = connection.execute(
            """
            SELECT *
            FROM disaster_reports
            WHERE report_id = ?
            """,
            (report_id,),
        ).fetchone()

        if current is None:
            raise KeyError(
                f"找不到通報：{report_id}"
            )

        if current["status"] != "pending":
            raise ValueError(
                "只有 pending 通報可進行審核。"
            )

        connection.execute(
            """
            UPDATE disaster_reports
            SET
                status = ?,
                reviewed_at = ?,
                reviewer_id = ?,
                reviewer_note = ?
            WHERE report_id = ?
            """,
            (
                decision,
                now_iso(),
                reviewer_id,
                reviewer_note,
                report_id,
            ),
        )

        connection.commit()

    finally:
        connection.close()

    report = get_report(
        report_id,
        db_path=db_path,
    )

    if report is None:
        raise RuntimeError("審核後無法重新讀取通報。")

    return report


def get_report_summary(
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    init_db(db_path)

    summary = {
        "total": 0,
        "pending": 0,
        "verified": 0,
        "rejected": 0,
    }

    connection = get_connection(db_path)

    try:
        rows = connection.execute(
            """
            SELECT status, COUNT(*) AS count
            FROM disaster_reports
            GROUP BY status
            """
        ).fetchall()

        for row in rows:
            status = row["status"]
            count = int(row["count"])

            if status in summary:
                summary[status] = count

        summary["total"] = (
            summary["pending"]
            + summary["verified"]
            + summary["rejected"]
        )

        return summary

    finally:
        connection.close()