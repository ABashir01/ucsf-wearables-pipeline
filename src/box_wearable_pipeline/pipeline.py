"""Pipeline orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import csv
import json
import tempfile
from pathlib import Path

from .box_client import BoxClient, BoxItem
from .filenames import parse_source_filename
from .merge import merge_daily_rows
from .parsers import PARSER_BY_SOURCE, parse_demographics
from .schema import DAILY_COLUMNS, MANIFEST_COLUMNS, PARSER_VERSION
from .state import SourceFingerprintItem, compute_output_fingerprint, load_state, save_state


DAILY_OUTPUT_NAME = "daily_wearable_summary.csv"
MANIFEST_OUTPUT_NAME = "source_file_manifest.csv"


@dataclass(frozen=True)
class BoxPipelineConfig:
    source_root_folder_id: str
    destination_folder_id: str
    control_folder_id: str
    schedule_label: str = "manual"


@dataclass(frozen=True)
class LocalSourceFile:
    path: Path
    folder: str
    source_type: str
    study_id: str
    file_id: str
    file_version_id: str
    size: int
    sha1: str
    etag: str
    created_at: str
    modified_at: str


def run_box_pipeline(
    box: BoxClient,
    config: BoxPipelineConfig,
    *,
    dry_run: bool = False,
    output_dir: Path | None = None,
) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="box-wearable-pipeline-") as tmp:
        tmp_dir = Path(tmp)
        state, state_item = load_state(box, config.control_folder_id, tmp_dir)
        source_files, manifest_rows = _download_box_sources(box, config.source_root_folder_id, tmp_dir)
        fingerprint = compute_output_fingerprint(
            [
                SourceFingerprintItem(
                    file_id=item.file_id,
                    file_version_id=item.file_version_id,
                    name=item.path.name,
                    size=item.size,
                    sha1=item.sha1,
                    etag=item.etag,
                )
                for item in source_files
            ]
        )
        if state["completed_fingerprints"].get(fingerprint) and not dry_run:
            return {"status": "skipped", "reason": "fingerprint already completed", "fingerprint": fingerprint}

        outputs = build_outputs(source_files, tmp_dir, manifest_rows)
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            for name, path in outputs.items():
                _copy_file(path, output_dir / name)

        if dry_run:
            return {"status": "dry-run", "fingerprint": fingerprint, "outputs": list(outputs)}

        _upload_pipeline_owned_output(box, config.destination_folder_id, outputs[DAILY_OUTPUT_NAME], DAILY_OUTPUT_NAME)
        _upload_pipeline_owned_output(box, config.destination_folder_id, outputs[MANIFEST_OUTPUT_NAME], MANIFEST_OUTPUT_NAME)
        state["completed_fingerprints"][fingerprint] = {
            "completed_at": _now_iso(),
            "parser_version": PARSER_VERSION,
            "outputs": [DAILY_OUTPUT_NAME, MANIFEST_OUTPUT_NAME],
            "schedule_label": config.schedule_label,
        }
        state["last_run"] = {
            "completed_at": _now_iso(),
            "fingerprint": fingerprint,
            "input_file_count": len(source_files),
            "parser_version": PARSER_VERSION,
        }
        save_state(box, config.control_folder_id, state_item, state, tmp_dir)
        return {"status": "complete", "fingerprint": fingerprint, "outputs": list(outputs)}


def run_local_pipeline(source_dir: Path, output_dir: Path) -> dict[str, object]:
    source_files, manifest_rows = _discover_local_sources(source_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = build_outputs(source_files, output_dir, manifest_rows)
    return {"status": "complete", "outputs": [str(path) for path in outputs.values()]}


def build_outputs(
    source_files: list[LocalSourceFile],
    output_dir: Path,
    manifest_rows: list[dict[str, str]],
) -> dict[str, Path]:
    demographics_file = _find_demographics(source_files)
    demographics = parse_demographics(demographics_file.path)
    parsed_by_source = []
    for source_file in source_files:
        if source_file.source_type in {"demographics", "rmd"}:
            continue
        parser = PARSER_BY_SOURCE[source_file.source_type]
        parsed_by_source.append((source_file.source_type, parser(source_file.path, source_file.study_id)))
    daily_rows = merge_daily_rows(demographics, parsed_by_source)

    daily_path = output_dir / DAILY_OUTPUT_NAME
    manifest_path = output_dir / MANIFEST_OUTPUT_NAME
    _write_csv(daily_path, DAILY_COLUMNS, daily_rows)
    _write_csv(manifest_path, MANIFEST_COLUMNS, manifest_rows)
    return {DAILY_OUTPUT_NAME: daily_path, MANIFEST_OUTPUT_NAME: manifest_path}


def _download_box_sources(
    box: BoxClient,
    source_root_folder_id: str,
    tmp_dir: Path,
) -> tuple[list[LocalSourceFile], list[dict[str, str]]]:
    root_items = box.list_folder_items(source_root_folder_id)
    actigraph_folder = _require_folder(root_items, "Actigraph")
    tracker_folder = _require_folder(root_items, "Personal Tracker")
    folder_items = [
        ("root", root_items),
        ("Actigraph", box.list_folder_items(actigraph_folder.id)),
        ("Personal Tracker", box.list_folder_items(tracker_folder.id)),
    ]

    source_files: list[LocalSourceFile] = []
    manifest_rows: list[dict[str, str]] = []
    for folder_name, items in folder_items:
        for item in items:
            if item.type != "file":
                continue
            local_file = _box_item_to_local_source(box, item, folder_name, tmp_dir)
            if local_file:
                source_files.append(local_file)
                manifest_rows.append(_manifest_row(local_file, "included", ""))
            else:
                manifest_rows.append(_manifest_row_from_box(item, folder_name, "ignored", "unsupported filename"))
    return source_files, manifest_rows


def _box_item_to_local_source(
    box: BoxClient,
    item: BoxItem,
    folder_name: str,
    tmp_dir: Path,
) -> LocalSourceFile | None:
    if folder_name == "root" and item.name == "final_demographics.csv":
        source_type = "demographics"
        study_id = ""
    elif folder_name == "root" and item.name == "De-identified_Demographics.Rmd":
        source_type = "rmd"
        study_id = ""
    else:
        parsed = parse_source_filename(item.name, folder_name)
        if not parsed:
            return None
        source_type = parsed.source_type
        study_id = parsed.study_id

    local_path = tmp_dir / item.id / item.name
    box.download_file(item.id, local_path)
    return LocalSourceFile(
        path=local_path,
        folder=folder_name,
        source_type=source_type,
        study_id=study_id,
        file_id=item.id,
        file_version_id=item.file_version_id or item.etag or item.id,
        size=item.size or 0,
        sha1=item.sha1 or "",
        etag=item.etag or "",
        created_at=item.created_at or "",
        modified_at=item.modified_at or "",
    )


def _discover_local_sources(source_dir: Path) -> tuple[list[LocalSourceFile], list[dict[str, str]]]:
    folders = {
        "root": source_dir,
        "Actigraph": source_dir / "Actigraph",
        "Personal Tracker": source_dir / "Personal Tracker",
    }
    source_files: list[LocalSourceFile] = []
    manifest_rows: list[dict[str, str]] = []
    for folder_name, folder_path in folders.items():
        if not folder_path.exists():
            continue
        for path in sorted(folder_path.iterdir()):
            if not path.is_file():
                continue
            local_file = _path_to_local_source(path, folder_name)
            if local_file:
                source_files.append(local_file)
                manifest_rows.append(_manifest_row(local_file, "included", ""))
            else:
                manifest_rows.append(
                    {
                        "file_id": str(path),
                        "file_version_id": str(path.stat().st_mtime_ns),
                        "name": path.name,
                        "folder": folder_name,
                        "study_id": "",
                        "source_type": "",
                        "size": str(path.stat().st_size),
                        "sha1": "",
                        "etag": "",
                        "created_at": "",
                        "modified_at": "",
                        "status": "ignored",
                        "message": "unsupported filename",
                    }
                )
    return source_files, manifest_rows


def _path_to_local_source(path: Path, folder_name: str) -> LocalSourceFile | None:
    if folder_name == "root" and path.name == "final_demographics.csv":
        source_type = "demographics"
        study_id = ""
    elif folder_name == "root" and path.name == "De-identified_Demographics.Rmd":
        source_type = "rmd"
        study_id = ""
    else:
        parsed = parse_source_filename(path.name, folder_name)
        if not parsed:
            return None
        source_type = parsed.source_type
        study_id = parsed.study_id
    stat = path.stat()
    return LocalSourceFile(
        path=path,
        folder=folder_name,
        source_type=source_type,
        study_id=study_id,
        file_id=str(path),
        file_version_id=str(stat.st_mtime_ns),
        size=stat.st_size,
        sha1="",
        etag="",
        created_at="",
        modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
    )


def _find_demographics(source_files: list[LocalSourceFile]) -> LocalSourceFile:
    for source_file in source_files:
        if source_file.source_type == "demographics":
            return source_file
    raise ValueError("final_demographics.csv was not found in the source root folder")


def _require_folder(items: list[BoxItem], name: str) -> BoxItem:
    for item in items:
        if item.type == "folder" and item.name == name:
            return item
    raise ValueError(f"Required Box folder not found: {name}")


def _manifest_row(source_file: LocalSourceFile, status: str, message: str) -> dict[str, str]:
    return {
        "file_id": source_file.file_id,
        "file_version_id": source_file.file_version_id,
        "name": source_file.path.name,
        "folder": source_file.folder,
        "study_id": source_file.study_id,
        "source_type": source_file.source_type,
        "size": str(source_file.size),
        "sha1": source_file.sha1,
        "etag": source_file.etag,
        "created_at": source_file.created_at,
        "modified_at": source_file.modified_at,
        "status": status,
        "message": message,
    }


def _manifest_row_from_box(item: BoxItem, folder: str, status: str, message: str) -> dict[str, str]:
    return {
        "file_id": item.id,
        "file_version_id": item.file_version_id or "",
        "name": item.name,
        "folder": folder,
        "study_id": "",
        "source_type": "",
        "size": str(item.size or ""),
        "sha1": item.sha1 or "",
        "etag": item.etag or "",
        "created_at": item.created_at or "",
        "modified_at": item.modified_at or "",
        "status": status,
        "message": message,
    }


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def _upload_pipeline_owned_output(box: BoxClient, folder_id: str, path: Path, name: str) -> BoxItem:
    existing = box.find_child(folder_id, name, "file")
    if existing:
        return box.upload_new_file_version(existing.id, path, name)
    return box.upload_file(folder_id, path, name)


def _copy_file(source: Path, destination: Path) -> None:
    destination.write_bytes(source.read_bytes())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def dump_result(result: dict[str, object]) -> str:
    return json.dumps(result, indent=2, sort_keys=True)
