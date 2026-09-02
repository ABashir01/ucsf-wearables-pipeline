from box_wearable_pipeline.filenames import parse_source_filename


def test_parse_personal_tracker_filenames():
    assert parse_source_filename("FITriMSII_011 Garmin.csv").study_id == "011"
    assert parse_source_filename("FITriMSII_002 Fitbit.csv").source_type == "fitbit"
    assert parse_source_filename("FITriMSII_032 Whoop.csv").source_type == "whoop"
    assert parse_source_filename("FITriMSII_036 Oura.csv").source_type == "oura"
    assert parse_source_filename("FITriMSII_014 Apple.xml").source_type == "apple"


def test_parse_actigraph_filename():
    parsed = parse_source_filename("FITriMSII_034_HV (2026-06-30)60sec.csv", "Actigraph")
    assert parsed.study_id == "034"
    assert parsed.source_type == "actigraph"


def test_rejects_unknown_filename():
    assert parse_source_filename("notes.txt") is None
