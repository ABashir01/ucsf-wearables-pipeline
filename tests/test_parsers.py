from pathlib import Path

import pytest

from box_wearable_pipeline.parsers import (
    parse_actigraph,
    parse_apple,
    parse_demographics,
    parse_fitbit,
    parse_garmin,
    parse_oura,
    parse_whoop,
)


DOWNLOADS = Path("C:/Users/ahadb/Downloads")


def require_sample(name: str) -> Path:
    path = DOWNLOADS / name
    if not path.exists():
        pytest.skip(f"sample file not available: {path}")
    return path


def test_demographics_sample_shape():
    demographics = parse_demographics(require_sample("final_demographics.csv"))
    assert len(demographics) == 37
    assert demographics["002"]["StudyID"] == "002"
    assert {"ParticipantType", "Age_Group", "MS_Type", "EDSS_Group", "Sex"}.issubset(demographics["002"])


def test_simple_tracker_parsers():
    fitbit = parse_fitbit(require_sample("FITriMSII_002 Fitbit.csv"), "002")
    garmin = parse_garmin(require_sample("FITriMSII_011 Garmin.csv"), "011")
    whoop = parse_whoop(require_sample("FITriMSII_032 Whoop.csv"), "032")

    assert fitbit[("002", "2025-03-12")]["fitbit_steps"] == "3206"
    assert garmin[("011", "2025-11-25")]["garmin_steps_actual"] == "5174"
    assert garmin[("011", "2025-11-25")]["garmin_steps_goal"] == "10000"
    assert whoop[("032", "2026-06-12")]["whoop_steps"] == "7851"


def test_garmin_blank_date_header_sample_when_available():
    path = Path("C:/Users/ahadb/Downloads/De-Identified Data/De-Identified Data/Personal Tracker/FITriMSII_003 Garmin.csv")
    if not path.exists():
        pytest.skip(f"sample file not available: {path}")
    rows = parse_garmin(path, "003")
    assert rows[("003", "2025-04-04")]["garmin_steps_actual"] == "7539"
    assert rows[("003", "2025-04-04")]["garmin_steps_goal"] == "15000"


def test_garmin_title_row_sample_when_available():
    path = Path("C:/Users/ahadb/Downloads/De-Identified Data/De-Identified Data/Personal Tracker/FITriMSII_025 Garmin.csv")
    if not path.exists():
        pytest.skip(f"sample file not available: {path}")
    rows = parse_garmin(path, "025")
    assert rows[("025", "2026-04-30")]["garmin_steps_actual"] == "8882"
    assert rows[("025", "2026-04-30")]["garmin_steps_goal"] == "10000"


def test_fitbit_timestamp_steps_sample_when_available():
    path = Path("C:/Users/ahadb/Downloads/De-Identified Data/De-Identified Data/Personal Tracker/FITriMSII_015 Fitbit.csv")
    if not path.exists():
        pytest.skip(f"sample file not available: {path}")
    rows = parse_fitbit(path, "015")
    assert len(rows) > 1
    assert rows[("015", "2026-01-01")]["fitbit_steps"] == "3986"


def test_oura_semicolon_sample():
    rows = parse_oura(require_sample("FITriMSII_036 Oura.csv"), "036")
    assert len(rows) == 152
    assert rows[("036", "2026-02-18")]["oura_steps"] == "4373"
    assert rows[("036", "2026-02-18")]["oura_contributors_json"].startswith("{")


def test_oura_comma_standard_sample_when_available():
    path = Path("C:/Users/ahadb/Downloads/De-Identified Data/De-Identified Data/Personal Tracker/FITriMSII_006 Oura.csv")
    if not path.exists():
        pytest.skip(f"sample file not available: {path}")
    rows = parse_oura(path, "006")
    assert rows[("006", "2021-04-08")]["oura_steps"] == "17224"
    assert rows[("006", "2021-04-08")]["oura_id"]


def test_oura_legacy_activity_sample_when_available():
    path = Path("C:/Users/ahadb/Downloads/De-Identified Data/De-Identified Data/Personal Tracker/FITriMSII_001 Oura.csv")
    if not path.exists():
        pytest.skip(f"sample file not available: {path}")
    rows = parse_oura(path, "001")
    assert rows[("001", "2025-03-06")]["oura_steps"] == "13152"
    assert rows[("001", "2025-03-06")]["oura_score"] == "95"
    assert rows[("001", "2025-03-06")]["oura_contributors_json"].startswith("{")


def test_oura_date_steps_sample_when_available():
    path = Path("C:/Users/ahadb/Downloads/De-Identified Data/De-Identified Data/Personal Tracker/FITriMSII_009 Oura.csv")
    if not path.exists():
        pytest.skip(f"sample file not available: {path}")
    rows = parse_oura(path, "009")
    assert rows[("009", "2024-01-14")]["oura_steps"] == "306"


def test_actigraph_skips_metadata_and_aggregates():
    rows = parse_actigraph(require_sample("FITriMSII_034_HV (2026-06-30)60sec.csv"), "034")
    assert rows[("034", "2026-06-30")]["actigraph_first_time"] == "16:00:00"
    assert rows[("034", "2026-06-30")]["actigraph_epoch_count"] == "480"
    assert "actigraph_steps_sum" in rows[("034", "2026-06-30")]


def test_apple_stream_parse_daily_activity():
    rows = parse_apple(require_sample("FITriMSII_014 Apple.xml"), "014")
    assert rows[("014", "2019-09-05")]["apple_step_count_sum"] == "1502"
    assert rows[("014", "2022-11-08")]["apple_activity_summary_active_energy_burned"] == "49.358"
