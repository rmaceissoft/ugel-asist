from __future__ import annotations

from collections import defaultdict

from . import db


def calculate_and_store_changes(version_id: int) -> list[dict]:
    with db.connect() as conn:
        db.init_db()
        previous_id = db.get_previous_version_id(conn, version_id)
        current_rows = db.get_docentes(conn, version_id)
        if previous_id is None:
            changes = _first_version_changes(current_rows)
        else:
            previous_rows = db.get_docentes(conn, previous_id)
            changes = compare_versions(current_rows, previous_rows)
        db.replace_school_changes(conn, version_id, changes)
        return changes


def compare_versions(current_rows, previous_rows) -> list[dict]:
    current_by_school = _group_by_school(current_rows)
    previous_by_school = _group_by_school(previous_rows)
    all_codes = sorted(set(current_by_school) | set(previous_by_school))
    changes = []

    for code in all_codes:
        current = {row["dni"]: row for row in current_by_school.get(code, [])}
        previous = {row["dni"]: row for row in previous_by_school.get(code, [])}

        added_dnis = sorted(set(current) - set(previous))
        removed_dnis = sorted(set(previous) - set(current))
        modified_dnis = sorted(
            dni
            for dni in set(current) & set(previous)
            if current[dni]["row_hash"] != previous[dni]["row_hash"]
        )

        colegio_nombre = _school_name(
            current_by_school.get(code) or previous_by_school.get(code) or []
        )
        changes.append(
            {
                "colegio_codigo": code,
                "colegio_nombre": colegio_nombre,
                "added_count": len(added_dnis),
                "removed_count": len(removed_dnis),
                "modified_count": len(modified_dnis),
                "has_changes": int(bool(added_dnis or removed_dnis or modified_dnis)),
                "change_summary": {
                    "added": added_dnis,
                    "removed": removed_dnis,
                    "modified": modified_dnis,
                },
            }
        )
    return changes


def _first_version_changes(rows) -> list[dict]:
    changes = []
    for code, school_rows in sorted(_group_by_school(rows).items()):
        changes.append(
            {
                "colegio_codigo": code,
                "colegio_nombre": _school_name(school_rows),
                "added_count": len(school_rows),
                "removed_count": 0,
                "modified_count": 0,
                "has_changes": 1,
                "change_summary": {
                    "added": sorted(row["dni"] for row in school_rows),
                    "removed": [],
                    "modified": [],
                },
            }
        )
    return changes


def _group_by_school(rows) -> dict[str, list]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["colegio_codigo"]].append(row)
    return dict(grouped)


def _school_name(rows) -> str:
    for row in rows:
        if row["colegio_nombre"]:
            return row["colegio_nombre"]
    return ""
