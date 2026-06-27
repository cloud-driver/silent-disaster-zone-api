from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.reports.store import get_connection


def now_iso() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat(timespec="seconds")


def init_line_storage(
    db_path: str | Path | None = None,
) -> None:
    connection = get_connection(db_path)

    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS line_report_sessions (
                reporter_hash TEXT PRIMARY KEY,
                step TEXT NOT NULL,
                draft_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS line_processed_events (
                webhook_event_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                completed_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_line_sessions_updated
            ON line_report_sessions(updated_at DESC);
            """
        )

        connection.commit()

    finally:
        connection.close()


def claim_webhook_event(
    webhook_event_id: str,
    db_path: str | Path | None = None,
) -> bool:
    init_line_storage(db_path)

    webhook_event_id = webhook_event_id.strip()

    if not webhook_event_id:
        return True

    connection = get_connection(db_path)

    try:
        try:
            connection.execute(
                """
                INSERT INTO line_processed_events (
                    webhook_event_id,
                    status,
                    created_at
                )
                VALUES (?, 'processing', ?)
                """,
                (
                    webhook_event_id,
                    now_iso(),
                ),
            )

            connection.commit()

            return True

        except sqlite3.IntegrityError:
            return False

    finally:
        connection.close()


def complete_webhook_event(
    webhook_event_id: str,
    db_path: str | Path | None = None,
) -> None:
    if not webhook_event_id.strip():
        return

    init_line_storage(db_path)

    connection = get_connection(db_path)

    try:
        connection.execute(
            """
            UPDATE line_processed_events
            SET
                status = 'completed',
                completed_at = ?
            WHERE webhook_event_id = ?
            """,
            (
                now_iso(),
                webhook_event_id,
            ),
        )

        connection.commit()

    finally:
        connection.close()


def release_webhook_event(
    webhook_event_id: str,
    db_path: str | Path | None = None,
) -> None:
    if not webhook_event_id.strip():
        return

    init_line_storage(db_path)

    connection = get_connection(db_path)

    try:
        connection.execute(
            """
            DELETE FROM line_processed_events
            WHERE
                webhook_event_id = ?
                AND status = 'processing'
            """,
            (webhook_event_id,),
        )

        connection.commit()

    finally:
        connection.close()


def get_line_session(
    reporter_hash: str,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    init_line_storage(db_path)

    connection = get_connection(db_path)

    try:
        row = connection.execute(
            """
            SELECT step, draft_json
            FROM line_report_sessions
            WHERE reporter_hash = ?
            """,
            (reporter_hash,),
        ).fetchone()

        if row is None:
            return {
                "step": "idle",
                "draft": {},
            }

        try:
            draft = json.loads(row["draft_json"])
        except json.JSONDecodeError:
            draft = {}

        if not isinstance(draft, dict):
            draft = {}

        return {
            "step": row["step"],
            "draft": draft,
        }

    finally:
        connection.close()


def save_line_session(
    reporter_hash: str,
    step: str,
    draft: dict[str, Any],
    db_path: str | Path | None = None,
) -> None:
    init_line_storage(db_path)

    connection = get_connection(db_path)

    try:
        connection.execute(
            """
            INSERT INTO line_report_sessions (
                reporter_hash,
                step,
                draft_json,
                updated_at
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(reporter_hash)
            DO UPDATE SET
                step = excluded.step,
                draft_json = excluded.draft_json,
                updated_at = excluded.updated_at
            """,
            (
                reporter_hash,
                step,
                json.dumps(
                    draft,
                    ensure_ascii=False,
                ),
                now_iso(),
            ),
        )

        connection.commit()

    finally:
        connection.close()


def clear_line_session(
    reporter_hash: str,
    db_path: str | Path | None = None,
) -> None:
    init_line_storage(db_path)

    connection = get_connection(db_path)

    try:
        connection.execute(
            """
            DELETE FROM line_report_sessions
            WHERE reporter_hash = ?
            """,
            (reporter_hash,),
        )

        connection.commit()

    finally:
        connection.close()