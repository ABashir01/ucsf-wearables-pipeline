"""Pipeline state and fingerprinting."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Protocol

from .box_client import BoxItem
from .schema import PARSER_VERSION


STATE_FILE_NAME = "pipeline_state.json"


@dataclass(frozen=True)
class SourceFingerprintItem:
    file_id: str
    file_version_id: str
    name: str
    size: int | None
    sha1: str | None
    etag: str | None


class StateBoxClient(Protocol):
    def find_child(self, folder_id: str, name: str, item_type: str | None = None) -> BoxItem | None:
        ...

    def download_file(self, file_id: str, destination: Path) -> None:
        ...

    def upload_file(self, folder_id: str, path: Path, name: str) -> BoxItem:
        ...

    def upload_new_file_version(self, file_id: str, path: Path, name: str) -> BoxItem:
        ...


def default_state() -> dict:
    return {
        "parser_version": PARSER_VERSION,
        "completed_fingerprints": {},
        "last_run": None,
    }


def compute_output_fingerprint(items: list[SourceFingerprintItem]) -> str:
    payload = {
        "parser_version": PARSER_VERSION,
        "items": [asdict(item) for item in sorted(items, key=lambda x: (x.file_id, x.file_version_id, x.name))],
    }
    data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def load_state(box: StateBoxClient, control_folder_id: str, tmp_dir: Path) -> tuple[dict, BoxItem | None]:
    state_item = box.find_child(control_folder_id, STATE_FILE_NAME, "file")
    if not state_item:
        return default_state(), None
    local_path = tmp_dir / STATE_FILE_NAME
    box.download_file(state_item.id, local_path)
    with local_path.open(encoding="utf-8") as handle:
        state = json.load(handle)
    if not isinstance(state, dict):
        raise ValueError("pipeline_state.json must contain a JSON object")
    state.setdefault("parser_version", PARSER_VERSION)
    state.setdefault("completed_fingerprints", {})
    state.setdefault("last_run", None)
    return state, state_item


def save_state(box: StateBoxClient, control_folder_id: str, state_item: BoxItem | None, state: dict, tmp_dir: Path) -> BoxItem:
    path = tmp_dir / STATE_FILE_NAME
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
        handle.write("\n")
    if state_item:
        return box.upload_new_file_version(state_item.id, path, STATE_FILE_NAME)
    return box.upload_file(control_folder_id, path, STATE_FILE_NAME)
