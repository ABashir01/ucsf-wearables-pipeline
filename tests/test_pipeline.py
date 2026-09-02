from pathlib import Path
import csv

from box_wearable_pipeline.pipeline import run_local_pipeline
from box_wearable_pipeline.schema import DAILY_COLUMNS
from box_wearable_pipeline.state import SourceFingerprintItem, compute_output_fingerprint


DOWNLOADS = Path("C:/Users/ahadb/Downloads")


def test_output_schema_columns(tmp_path):
    source_dir = tmp_path / "De-Identified Data"
    tracker_dir = source_dir / "Personal Tracker"
    actigraph_dir = source_dir / "Actigraph"
    tracker_dir.mkdir(parents=True)
    actigraph_dir.mkdir()

    for filename, destination in [
        ("final_demographics.csv", source_dir / "final_demographics.csv"),
        ("FITriMSII_002 Fitbit.csv", tracker_dir / "FITriMSII_002 Fitbit.csv"),
        ("FITriMSII_011 Garmin.csv", tracker_dir / "FITriMSII_011 Garmin.csv"),
        ("FITriMSII_032 Whoop.csv", tracker_dir / "FITriMSII_032 Whoop.csv"),
        ("FITriMSII_036 Oura.csv", tracker_dir / "FITriMSII_036 Oura.csv"),
        ("FITriMSII_034_HV (2026-06-30)60sec.csv", actigraph_dir / "FITriMSII_034_HV (2026-06-30)60sec.csv"),
    ]:
        sample = DOWNLOADS / filename
        if not sample.exists():
            return
        destination.write_bytes(sample.read_bytes())

    output_dir = tmp_path / "outputs"
    run_local_pipeline(source_dir, output_dir)
    with (output_dir / "daily_wearable_summary.csv").open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        assert next(reader) == DAILY_COLUMNS


def test_fingerprint_is_stable_independent_of_input_order():
    a = SourceFingerprintItem("2", "1", "b.csv", 2, "sha-b", "etag-b")
    b = SourceFingerprintItem("1", "1", "a.csv", 1, "sha-a", "etag-a")
    assert compute_output_fingerprint([a, b]) == compute_output_fingerprint([b, a])
