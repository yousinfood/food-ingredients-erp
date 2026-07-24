"""Collect PostgreSQL DDL from Django migrations without a live DB connection."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings_sqlgen")

import django

django.setup()

from django.core.management import call_command
from django.db import connections
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.loader import MigrationLoader
from io import StringIO


class CollectingSchemaEditor(BaseDatabaseSchemaEditor):
    def __init__(self, connection, collect_into: list[str], atomic=migration_atomic_default):
        self._collect_into = collect_into
        super().__init__(connection, atomic=atomic)

    def execute(self, sql, params=()):
        if params:
            sql = sql % tuple(repr(p) for p in params)
        self._collect_into.append(str(sql).strip())


# Django internal default used by schema editor
from django.db.backends.base.schema import migration_atomic_default  # noqa: E402


def collect_migration_sql(app_label: str, migration_name: str) -> list[str]:
    connection = connections["default"]
    loader = MigrationLoader(connection, ignore_no_migrations=True)
    migration = loader.get_migration_by_prefix(app_label, migration_name)
    statements: list[str] = []
    with CollectingSchemaEditor(connection, statements) as schema_editor:
        for operation in migration.operations:
            operation.database_forwards(app_label, schema_editor, migration.initial_state, migration.final_state)
    return statements


def collect_all_migrations() -> list[tuple[str, str, list[str]]]:
    connection = connections["default"]
    loader = MigrationLoader(connection, ignore_no_migrations=True)
    graph = loader.graph
    leaves = graph.leaves()
    plan = []
    for target in sorted(leaves):
        for node in graph.forwards_plan(node):
            plan.append(node)
    seen = set()
    ordered = []
    for node in plan:
        if node in seen:
            continue
        seen.add(node)
        ordered.append(node)

    results = []
    for app_label, migration_name in ordered:
        migration = loader.get_migration(app_label, migration_name)
        statements: list[str] = []
        with CollectingSchemaEditor(connection, statements) as schema_editor:
            state = loader.project_state([node for node in ordered[: ordered.index((app_label, migration_name))]])
            for operation in migration.operations:
                operation.database_forwards(app_label, schema_editor, state, state.clone())
                state = migration.apply(state, schema_editor)
        if statements:
            results.append((app_label, migration_name, statements))
    return results


def main():
    connection = connections["default"]
    loader = MigrationLoader(connection, ignore_no_migrations=True)
    targets = sorted(loader.graph.leaves())
    plan = []
    for target in targets:
        for node in loader.graph.forwards_plan(target):
            if node not in plan:
                plan.append(node)

    all_sql: list[tuple[str, str, str]] = []
    state = loader.project_state([])

    for app_label, migration_name in plan:
        migration = loader.get_migration(app_label, migration_name)
        statements: list[str] = []
        with CollectingSchemaEditor(connection, statements) as schema_editor:
            old_state = state.clone()
            for operation in migration.operations:
                operation.database_forwards(app_label, schema_editor, old_state, state)
            state = migration.apply(state, schema_editor)
        sql = "\n".join(statements).strip()
        if sql:
            all_sql.append((app_label, migration_name, sql))
            print(f"=== {app_label}.{migration_name} ===")
            print(sql)
            print()

    return all_sql


if __name__ == "__main__":
    main()
