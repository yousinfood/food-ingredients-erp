"""PostgreSQL connectivity checks — fail fast with plain-language errors."""

from __future__ import annotations

import socket

from django.conf import settings
from django.db import connection
from django.db.utils import OperationalError


def _database_host() -> str:
    db = settings.DATABASES.get("default") or {}
    return str(db.get("HOST") or "")


def verify_database_connection() -> None:
    """Raise RuntimeError with a user-facing message if PostgreSQL is unreachable."""
    host = _database_host()
    if not host:
        raise RuntimeError("資料庫尚未設定，請確認 DATABASE_URL 或 DATABASE_PUBLIC_URL。")

    if host.endswith(".railway.internal"):
        raise RuntimeError(
            "本機無法連線 postgres.railway.internal。"
            "請在 .env 設定 DATABASE_PUBLIC_URL（Railway Postgres → Connect → Public URL）。"
        )

    try:
        socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise RuntimeError(
            f"無法解析資料庫主機 {host!r}（DNS 失敗：{exc}）。"
            "請確認網路連線，或到 Railway Postgres 重新複製 Public URL 到 DATABASE_PUBLIC_URL。"
        ) from exc

    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except OperationalError as exc:
        raise RuntimeError(
            f"無法連線 PostgreSQL（{host}）：{exc}。"
            "請確認 DATABASE_PUBLIC_URL 密碼與主機是否為最新。"
        ) from exc
