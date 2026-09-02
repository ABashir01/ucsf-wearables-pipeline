"""Merge parsed source rows into the canonical daily schema."""

from __future__ import annotations

from collections import defaultdict

from .schema import DAILY_COLUMNS


def merge_daily_rows(
    demographics: dict[str, dict[str, str]],
    parsed_by_source: list[tuple[str, dict[tuple[str, str], dict[str, str]]]],
) -> list[dict[str, str]]:
    rows: dict[tuple[str, str], dict[str, str]] = {}
    sources: dict[tuple[str, str], set[str]] = defaultdict(set)

    for source_type, parsed_rows in parsed_by_source:
        for key, values in parsed_rows.items():
            study_id, date = key
            row = rows.setdefault(key, {column: "" for column in DAILY_COLUMNS})
            row["StudyID"] = study_id
            row["date"] = date
            row.update(values)
            sources[key].add(source_type)

    for key, row in rows.items():
        study_id, _date = key
        demo = demographics.get(study_id, {})
        for column in ("ParticipantType", "Age_Group", "MS_Type", "EDSS_Group", "Sex"):
            row[column] = demo.get(column, "")
        row["sources_present"] = ";".join(sorted(sources[key]))

    return [rows[key] for key in sorted(rows)]
