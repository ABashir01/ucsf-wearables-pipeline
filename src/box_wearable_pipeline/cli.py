"""Command-line entrypoint."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from .box_client import BoxClient
from .pipeline import BoxPipelineConfig, dump_result, run_box_pipeline, run_local_pipeline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="box-wearable-pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run against Box folders.")
    run_parser.add_argument("--dry-run", action="store_true", help="Build outputs locally but do not upload.")
    run_parser.add_argument("--output-dir", type=Path, default=_optional_path_env("PIPELINE_OUTPUT_DIR"))

    local_parser = subparsers.add_parser("local", help="Run against a local De-Identified Data folder.")
    local_parser.add_argument("--source-dir", type=Path, required=True)
    local_parser.add_argument("--output-dir", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.command == "local":
        result = run_local_pipeline(args.source_dir, args.output_dir)
        print(dump_result(result))
        return 0

    box = BoxClient(
        client_id=_required_env("BOX_CLIENT_ID"),
        client_secret=_required_env("BOX_CLIENT_SECRET"),
        subject_type=_required_env("BOX_SUBJECT_TYPE"),
        subject_id=_required_env("BOX_SUBJECT_ID"),
    )
    config = BoxPipelineConfig(
        source_root_folder_id=_required_env("BOX_SOURCE_ROOT_FOLDER_ID"),
        destination_folder_id=_required_env("BOX_DESTINATION_FOLDER_ID"),
        control_folder_id=_required_env("BOX_CONTROL_FOLDER_ID"),
        schedule_label=os.environ.get("PIPELINE_SCHEDULE_LABEL", "manual"),
    )
    result = run_box_pipeline(box, config, dry_run=args.dry_run, output_dir=args.output_dir)
    print(dump_result(result))
    return 0


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def _optional_path_env(name: str) -> Path | None:
    value = os.environ.get(name)
    return Path(value) if value else None


if __name__ == "__main__":
    raise SystemExit(main())
