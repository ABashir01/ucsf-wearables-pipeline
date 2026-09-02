# Box Wearable Pipeline

Small scheduled Python pipeline for FITriMSII de-identified wearable exports in Box.

The pipeline reads the configured Box source folder, downloads files into temporary local storage, creates master CSV outputs, and uploads those outputs into a separate destination folder. It never mutates source files.

## Outputs

- `daily_wearable_summary.csv`: one row per `StudyID` and calendar date.
- `source_file_manifest.csv`: discovered source files and versions.
- `pipeline_state.json`: durable state stored in a separate Box control folder.

## Required Box Layout

Source folder: `De-Identified Data`

```text
De-Identified Data/
  final_demographics.csv
  De-identified_Demographics.Rmd
  Actigraph/
    FITriMSII_034_HV (2026-06-30)60sec.csv
  Personal Tracker/
    FITriMSII_002 Fitbit.csv
    FITriMSII_011 Garmin.csv
    FITriMSII_032 Whoop.csv
    FITriMSII_036 Oura.csv
    FITriMSII_014 Apple.xml
```

## Configuration

Set these environment variables in GitHub Actions secrets or repository variables:

```text
BOX_CLIENT_ID
BOX_CLIENT_SECRET
BOX_SUBJECT_TYPE          # enterprise or user
BOX_SUBJECT_ID
BOX_SOURCE_ROOT_FOLDER_ID
BOX_DESTINATION_FOLDER_ID
BOX_CONTROL_FOLDER_ID
```

Optional:

```text
PIPELINE_OUTPUT_DIR       # local output directory for dry-run/debug output
PIPELINE_SCHEDULE_LABEL   # label written to logs/state
```

## Local Commands

Install:

```powershell
python -m pip install -e ".[dev]"
```

Run tests:

```powershell
pytest
```

Run against local sample files without Box:

```powershell
box-wearable-pipeline local `
  --source-dir "C:\path\to\De-Identified Data" `
  --output-dir ".\outputs"
```

Run against Box:

```powershell
box-wearable-pipeline run
```

Use `--dry-run --output-dir .\outputs` to build outputs locally from Box downloads without uploading destination files or state.

## Safety Model

- The source Box folder should be shared to the Box app/service account with read-only access.
- Destination and control folders should be separate from the source folder.
- The Box client exposes only list, download, create, and update-version methods needed for destination/control outputs.
- Source files are never moved, renamed, deleted, overwritten, or versioned.
