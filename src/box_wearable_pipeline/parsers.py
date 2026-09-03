"""Source file parsers and daily aggregation."""

from __future__ import annotations

from collections import defaultdict
import csv
from datetime import datetime
from pathlib import Path
from typing import Iterable
from xml.etree.ElementTree import iterparse


DailyRows = dict[tuple[str, str], dict[str, str]]


def parse_date(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None


def _clean_number(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _to_float(value: str | None) -> float:
    if value is None:
        return 0.0
    text = value.strip()
    if not text:
        return 0.0
    return float(text)


def _dict_reader(path: Path, delimiter: str = ",") -> Iterable[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        yield from csv.DictReader(handle, delimiter=delimiter)


def parse_demographics(path: Path) -> dict[str, dict[str, str]]:
    required = {"StudyID", "ParticipantType", "Age_Group", "MS_Type", "EDSS_Group", "Sex"}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Demographics file is missing columns: {sorted(missing)}")
        demographics: dict[str, dict[str, str]] = {}
        for row in reader:
            study_id = (row.get("StudyID") or "").strip().zfill(3)
            if not study_id:
                continue
            demographics[study_id] = {col: (row.get(col) or "").strip() for col in required}
            demographics[study_id]["StudyID"] = study_id
        return demographics


def parse_fitbit(path: Path, study_id: str) -> DailyRows:
    rows: DailyRows = {}
    minute_step_totals: defaultdict[str, float] = defaultdict(float)
    for row in _dict_reader(path):
        if "ActivityDay" in row and "StepTotal" in row:
            date = parse_date(row.get("ActivityDay"))
            if not date:
                continue
            rows[(study_id, date)] = {"fitbit_steps": (row.get("StepTotal") or "").strip()}
            continue

        if "timestamp" in row and "steps" in row:
            date = parse_date(row.get("timestamp"))
            if not date:
                continue
            minute_step_totals[date] += _to_float(row.get("steps"))

    for date, total in minute_step_totals.items():
        rows[(study_id, date)] = {"fitbit_steps": _clean_number(total)}
    return rows


def parse_garmin(path: Path, study_id: str) -> DailyRows:
    rows: DailyRows = {}
    for row in _dict_reader(path):
        date = parse_date(row.get("Date"))
        if not date:
            continue
        rows[(study_id, date)] = {
            "garmin_steps_actual": (row.get("Actual") or "").strip(),
            "garmin_steps_goal": (row.get("Goal") or "").strip(),
        }
    return rows


def parse_whoop(path: Path, study_id: str) -> DailyRows:
    rows: DailyRows = {}
    for row in _dict_reader(path):
        date = parse_date(row.get("Date"))
        if not date:
            continue
        rows[(study_id, date)] = {"whoop_steps": (row.get("Steps") or "").strip()}
    return rows


OURA_COLUMN_MAP = {
    "id": "oura_id",
    "active_calories": "oura_active_calories",
    "average_met_minutes": "oura_average_met_minutes",
    "class_5_min": "oura_class_5_min",
    "contributors": "oura_contributors_json",
    "equivalent_walking_distance": "oura_equivalent_walking_distance",
    "high_activity_met_minutes": "oura_high_activity_met_minutes",
    "high_activity_time": "oura_high_activity_time",
    "inactivity_alerts": "oura_inactivity_alerts",
    "low_activity_met_minutes": "oura_low_activity_met_minutes",
    "low_activity_time": "oura_low_activity_time",
    "medium_activity_met_minutes": "oura_medium_activity_met_minutes",
    "medium_activity_time": "oura_medium_activity_time",
    "met": "oura_met_json",
    "meters_to_target": "oura_meters_to_target",
    "non_wear_time": "oura_non_wear_time",
    "resting_time": "oura_resting_time",
    "score": "oura_score",
    "sedentary_met_minutes": "oura_sedentary_met_minutes",
    "sedentary_time": "oura_sedentary_time",
    "steps": "oura_steps",
    "target_calories": "oura_target_calories",
    "target_meters": "oura_target_meters",
    "timestamp": "oura_timestamp",
    "total_calories": "oura_total_calories",
}


def parse_oura(path: Path, study_id: str) -> DailyRows:
    rows: DailyRows = {}
    for row in _dict_reader(path, delimiter=";"):
        date = parse_date(row.get("day"))
        if not date:
            continue
        rows[(study_id, date)] = {
            target: (row.get(source) or "").strip()
            for source, target in OURA_COLUMN_MAP.items()
        }
    return rows


APPLE_RECORD_MAP = {
    "HKQuantityTypeIdentifierStepCount": ("apple_step_count_sum", None),
    "HKQuantityTypeIdentifierDistanceWalkingRunning": (
        "apple_distance_walking_running_sum",
        "apple_distance_walking_running_unit",
    ),
    "HKQuantityTypeIdentifierActiveEnergyBurned": (
        "apple_active_energy_burned_sum",
        "apple_active_energy_burned_unit",
    ),
    "HKQuantityTypeIdentifierBasalEnergyBurned": (
        "apple_basal_energy_burned_sum",
        "apple_basal_energy_burned_unit",
    ),
    "HKQuantityTypeIdentifierFlightsClimbed": ("apple_flights_climbed_sum", None),
    "HKQuantityTypeIdentifierAppleExerciseTime": ("apple_exercise_time_sum", None),
    "HKQuantityTypeIdentifierAppleStandTime": ("apple_stand_time_sum", None),
}

APPLE_ACTIVITY_SUMMARY_MAP = {
    "activeEnergyBurned": "apple_activity_summary_active_energy_burned",
    "activeEnergyBurnedGoal": "apple_activity_summary_active_energy_burned_goal",
    "appleExerciseTime": "apple_activity_summary_exercise_time",
    "appleExerciseTimeGoal": "apple_activity_summary_exercise_time_goal",
    "appleStandHours": "apple_activity_summary_stand_hours",
    "appleStandHoursGoal": "apple_activity_summary_stand_hours_goal",
}


def parse_apple(path: Path, study_id: str) -> DailyRows:
    sums: dict[tuple[str, str], defaultdict[str, float]] = {}
    units: dict[tuple[str, str], dict[str, str]] = {}
    activity_rows: DailyRows = {}

    for _event, elem in iterparse(path, events=("end",)):
        if elem.tag == "Record":
            record_type = elem.attrib.get("type")
            if record_type in APPLE_RECORD_MAP:
                date = parse_date((elem.attrib.get("startDate") or "")[:10])
                if date:
                    key = (study_id, date)
                    if key not in sums:
                        sums[key] = defaultdict(float)
                        units[key] = {}
                    sum_col, unit_col = APPLE_RECORD_MAP[record_type]
                    sums[key][sum_col] += _to_float(elem.attrib.get("value"))
                    if unit_col:
                        unit = elem.attrib.get("unit")
                        if unit:
                            units[key].setdefault(unit_col, unit)
            elem.clear()
        elif elem.tag == "ActivitySummary":
            date = parse_date(elem.attrib.get("dateComponents"))
            if date:
                activity_rows[(study_id, date)] = {
                    target: (elem.attrib.get(source) or "").strip()
                    for source, target in APPLE_ACTIVITY_SUMMARY_MAP.items()
                }
            elem.clear()

    rows: DailyRows = {}
    for key, values in sums.items():
        rows[key] = {col: _clean_number(value) for col, value in values.items()}
        rows[key].update(units.get(key, {}))
    for key, values in activity_rows.items():
        rows.setdefault(key, {}).update(values)
    return rows


ACTIGRAPH_SUM_COLUMNS = {
    "Steps": "actigraph_steps_sum",
    "Axis1": "actigraph_axis1_sum",
    "Axis2": "actigraph_axis2_sum",
    "Axis3": "actigraph_axis3_sum",
    "Inclinometer Off": "actigraph_inclinometer_off_sum",
    "Inclinometer Standing": "actigraph_inclinometer_standing_sum",
    "Inclinometer Sitting": "actigraph_inclinometer_sitting_sum",
    "Inclinometer Lying": "actigraph_inclinometer_lying_sum",
    "Vector Magnitude": "actigraph_vector_magnitude_sum",
}


def parse_actigraph(path: Path, study_id: str) -> DailyRows:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for line in handle:
            if line.startswith("Date,"):
                header_line = line
                break
        else:
            raise ValueError(f"Actigraph data header not found in {path.name}")
        reader = csv.DictReader([header_line, *handle])
        aggregates: dict[tuple[str, str], dict[str, object]] = {}
        for raw_row in reader:
            row = {(key or "").strip(): (value or "").strip() for key, value in raw_row.items()}
            date = parse_date(row.get("Date"))
            if not date:
                continue
            key = (study_id, date)
            current = aggregates.setdefault(
                key,
                {
                    "epoch_count": 0,
                    "first_time": "",
                    "last_time": "",
                    "lux_sum": 0.0,
                    "lux_count": 0,
                    "sums": defaultdict(float),
                },
            )
            current["epoch_count"] = int(current["epoch_count"]) + 1
            time = row.get("Time") or ""
            if time:
                if not current["first_time"] or time < str(current["first_time"]):
                    current["first_time"] = time
                if not current["last_time"] or time > str(current["last_time"]):
                    current["last_time"] = time
            for source, target in ACTIGRAPH_SUM_COLUMNS.items():
                current["sums"][target] += _to_float(row.get(source))  # type: ignore[index]
            if row.get("Lux"):
                current["lux_sum"] = float(current["lux_sum"]) + _to_float(row.get("Lux"))
                current["lux_count"] = int(current["lux_count"]) + 1

    rows: DailyRows = {}
    for key, values in aggregates.items():
        row = {
            "actigraph_epoch_count": str(values["epoch_count"]),
            "actigraph_first_time": str(values["first_time"]),
            "actigraph_last_time": str(values["last_time"]),
        }
        for col, value in values["sums"].items():  # type: ignore[union-attr]
            row[col] = _clean_number(value)
        lux_count = int(values["lux_count"])
        if lux_count:
            row["actigraph_lux_mean"] = _clean_number(float(values["lux_sum"]) / lux_count)
        rows[key] = row
    return rows


PARSER_BY_SOURCE = {
    "fitbit": parse_fitbit,
    "garmin": parse_garmin,
    "whoop": parse_whoop,
    "oura": parse_oura,
    "apple": parse_apple,
    "actigraph": parse_actigraph,
}
