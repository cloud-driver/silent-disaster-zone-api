from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_AUTH_DB_PATH = (
    PROJECT_ROOT
    / "data"
    / "auth"
    / "api_auth.sqlite3"
)

TOKEN_TTL_SECONDS = 15 * 60
LOGIN_WINDOW_SECONDS = 60
LOGIN_MAX_ATTEMPTS = 5

PASSWORD_SCHEME = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 600_000


class AuthConfigurationError(RuntimeError):
    """Authentication environment variables are incomplete."""


class InvalidAccessTokenError(ValueError):
    """Access token is missing, invalid, or revoked."""


class ExpiredAccessTokenError(ValueError):
    """Access token has expired."""


def now_epoch() -> int:
    return int(time.time())


def epoch_to_iso(epoch: int) -> str:
    return datetime.fromtimestamp(
        epoch,
        tz=timezone.utc,
    ).isoformat(timespec="seconds")


def b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(
        value
    ).decode("ascii").rstrip("=")


def b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)

    return base64.urlsafe_b64decode(
        value + padding
    )


def resolve_auth_db_path(
    db_path: str | Path | None = None,
) -> Path:
    if db_path is not None:
        return Path(db_path).expanduser().resolve()

    configured = os.getenv(
        "AUTH_DB_PATH",
        "",
    ).strip()

    if configured:
        return Path(configured).expanduser().resolve()

    return DEFAULT_AUTH_DB_PATH


def get_connection(
    db_path: str | Path | None = None,
) -> sqlite3.Connection:
    path = resolve_auth_db_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(
        path,
        timeout=30,
    )

    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")

    return connection


def init_auth_db(
    db_path: str | Path | None = None,
) -> None:
    connection = get_connection(db_path)

    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS access_tokens (
                token_hash TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                issued_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                last_used_at INTEGER NOT NULL,
                revoked_at INTEGER
            );

            CREATE TABLE IF NOT EXISTS login_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_hash TEXT NOT NULL,
                attempted_at INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_access_tokens_expires
            ON access_tokens(expires_at);

            CREATE INDEX IF NOT EXISTS idx_login_attempts_ip_time
            ON login_attempts(ip_hash, attempted_at DESC);
            """
        )

        connection.commit()

    finally:
        connection.close()


def get_auth_settings() -> dict[str, str]:
    username = os.getenv(
        "AUTH_LOGIN_USERNAME",
        "",
    ).strip()

    password_hash = os.getenv(
        "AUTH_LOGIN_PASSWORD_HASH",
        "",
    ).strip()

    storage_secret = os.getenv(
        "AUTH_STORAGE_SECRET",
        "",
    ).strip()

    if not username:
        raise AuthConfigurationError(
            "AUTH_LOGIN_USERNAME 尚未設定。"
        )

    if not password_hash:
        raise AuthConfigurationError(
            "AUTH_LOGIN_PASSWORD_HASH 尚未設定。"
        )

    if not storage_secret:
        raise AuthConfigurationError(
            "AUTH_STORAGE_SECRET 尚未設定。"
        )

    return {
        "username": username,
        "password_hash": password_hash,
        "storage_secret": storage_secret,
    }


def hash_password(
    password: str,
    iterations: int = PASSWORD_ITERATIONS,
) -> str:
    if not password:
        raise ValueError("密碼不可為空。")

    salt = secrets.token_bytes(16)

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )

    return "$".join(
        [
            PASSWORD_SCHEME,
            str(iterations),
            b64url_encode(salt),
            b64url_encode(digest),
        ]
    )


def verify_password(
    password: str,
    encoded_hash: str,
) -> bool:
    try:
        scheme, iteration_text, salt_text, digest_text = (
            encoded_hash.split("$", 3)
        )

        if scheme != PASSWORD_SCHEME:
            return False

        iterations = int(iteration_text)

        if iterations < 1:
            return False

        salt = b64url_decode(salt_text)
        expected_digest = b64url_decode(digest_text)

        actual_digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations,
        )

        return hmac.compare_digest(
            actual_digest,
            expected_digest,
        )

    except (
        ValueError,
        TypeError,
        UnicodeError,
    ):
        return False


def keyed_hash(
    purpose: str,
    value: str,
) -> str:
    settings = get_auth_settings()

    payload = (
        purpose
        + ":"
        + value
    ).encode("utf-8")

    return hmac.new(
        settings["storage_secret"].encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()


def hash_access_token(token: str) -> str:
    return keyed_hash("access_token", token)


def hash_client_ip(client_ip: str) -> str:
    return keyed_hash("client_ip", client_ip)


def verify_login_credentials(
    username: str,
    password: str,
) -> bool:
    settings = get_auth_settings()

    username_matches = hmac.compare_digest(
        username.strip(),
        settings["username"],
    )

    password_matches = verify_password(
        password,
        settings["password_hash"],
    )

    return username_matches and password_matches


def consume_login_attempt(
    client_ip: str,
    db_path: str | Path | None = None,
) -> tuple[bool, int]:
    """
    Records one login API call.

    Returns:
        (allowed, retry_after_seconds)
    """
    init_auth_db(db_path)

    now = now_epoch()
    ip_hash = hash_client_ip(client_ip)

    connection = get_connection(db_path)

    try:
        connection.execute("BEGIN IMMEDIATE")

        connection.execute(
            """
            DELETE FROM login_attempts
            WHERE attempted_at < ?
            """,
            (now - 24 * 60 * 60,),
        )

        cutoff = now - LOGIN_WINDOW_SECONDS

        row = connection.execute(
            """
            SELECT
                COUNT(*) AS attempt_count,
                MIN(attempted_at) AS oldest_attempt
            FROM login_attempts
            WHERE
                ip_hash = ?
                AND attempted_at > ?
            """,
            (
                ip_hash,
                cutoff,
            ),
        ).fetchone()

        attempt_count = int(row["attempt_count"])
        oldest_attempt = row["oldest_attempt"]

        if attempt_count >= LOGIN_MAX_ATTEMPTS:
            connection.commit()

            retry_after = max(
                1,
                int(oldest_attempt)
                + LOGIN_WINDOW_SECONDS
                - now,
            )

            return False, retry_after

        connection.execute(
            """
            INSERT INTO login_attempts (
                ip_hash,
                attempted_at
            )
            VALUES (?, ?)
            """,
            (
                ip_hash,
                now,
            ),
        )

        connection.commit()

        return True, 0

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def issue_access_token(
    username: str,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    init_auth_db(db_path)

    issued_at = now_epoch()
    expires_at = issued_at + TOKEN_TTL_SECONDS

    connection = get_connection(db_path)

    try:
        connection.execute("BEGIN IMMEDIATE")

        connection.execute(
            """
            DELETE FROM access_tokens
            WHERE expires_at <= ?
            """,
            (issued_at,),
        )

        for _ in range(3):
            access_token = secrets.token_urlsafe(32)
            token_hash = hash_access_token(access_token)

            try:
                connection.execute(
                    """
                    INSERT INTO access_tokens (
                        token_hash,
                        username,
                        issued_at,
                        expires_at,
                        last_used_at,
                        revoked_at
                    )
                    VALUES (?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        token_hash,
                        username,
                        issued_at,
                        expires_at,
                        issued_at,
                    ),
                )

                connection.commit()

                return {
                    "access_token": access_token,
                    "token_type": "Bearer",
                    "expires_in": TOKEN_TTL_SECONDS,
                    "expires_at": epoch_to_iso(expires_at),
                }

            except sqlite3.IntegrityError:
                continue

        raise RuntimeError("無法建立唯一 access token。")

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def validate_access_token(
    access_token: str,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    if not access_token.strip():
        raise InvalidAccessTokenError(
            "Access token 不可為空。"
        )

    init_auth_db(db_path)

    token_hash = hash_access_token(access_token)
    now = now_epoch()

    connection = get_connection(db_path)

    try:
        row = connection.execute(
            """
            SELECT *
            FROM access_tokens
            WHERE token_hash = ?
            """,
            (token_hash,),
        ).fetchone()

        if row is None:
            raise InvalidAccessTokenError(
                "Access token 無效。"
            )

        if row["revoked_at"] is not None:
            raise InvalidAccessTokenError(
                "Access token 已被撤銷。"
            )

        if int(row["expires_at"]) <= now:
            connection.execute(
                """
                DELETE FROM access_tokens
                WHERE token_hash = ?
                """,
                (token_hash,),
            )

            connection.commit()

            raise ExpiredAccessTokenError(
                "Access token 已過期。"
            )

        connection.execute(
            """
            UPDATE access_tokens
            SET last_used_at = ?
            WHERE token_hash = ?
            """,
            (
                now,
                token_hash,
            ),
        )

        connection.commit()

        return {
            "username": row["username"],
            "issued_at": epoch_to_iso(
                int(row["issued_at"])
            ),
            "expires_at": epoch_to_iso(
                int(row["expires_at"])
            ),
            "expires_in": max(
                0,
                int(row["expires_at"]) - now,
            ),
        }

    finally:
        connection.close()


def revoke_access_token(
    access_token: str,
    db_path: str | Path | None = None,
) -> bool:
    if not access_token.strip():
        return False

    init_auth_db(db_path)

    token_hash = hash_access_token(access_token)
    now = now_epoch()

    connection = get_connection(db_path)

    try:
        result = connection.execute(
            """
            UPDATE access_tokens
            SET revoked_at = ?
            WHERE
                token_hash = ?
                AND revoked_at IS NULL
            """,
            (
                now,
                token_hash,
            ),
        )

        connection.commit()

        return result.rowcount > 0

    finally:
        connection.close()