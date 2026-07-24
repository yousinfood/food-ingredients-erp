from __future__ import annotations

import sqlite3
from pathlib import Path

from django.apps import apps


def excel_schema_table_models():
    return [
        model
        for model in apps.get_app_config("excel_schema").get_models()
        if model._meta.db_table
    ]


def get_sqlite_table_counts(sqlite_path: Path) -> dict[str, int | None]:
    if not sqlite_path.exists():
        return {}

    conn = sqlite3.connect(sqlite_path)
    counts: dict[str, int | None] = {}
    try:
        for model in excel_schema_table_models():
            table = model._meta.db_table
            try:
                row = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()
                counts[table] = int(row[0]) if row else 0
            except sqlite3.OperationalError:
                counts[table] = None
    finally:
        conn.close()
    return counts


def get_current_table_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    for model in excel_schema_table_models():
        table = model._meta.db_table
        counts[table] = model.objects.count()
    return counts


def compare_table_counts(sqlite_path: Path) -> list[dict]:
    sqlite_counts = get_sqlite_table_counts(sqlite_path)
    current_counts = get_current_table_counts()
    rows = []
    for model in excel_schema_table_models():
        table = model._meta.db_table
        sqlite_count = sqlite_counts.get(table)
        current_count = current_counts.get(table, 0)
        rows.append(
            {
                "table": table,
                "sqlite": sqlite_count,
                "current": current_count,
                "match": sqlite_count is not None and sqlite_count == current_count,
            }
        )
    return rows
