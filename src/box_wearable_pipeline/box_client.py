"""Narrow Box REST client for read/download/upload pipeline operations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


BOX_API_BASE = "https://api.box.com/2.0"
BOX_UPLOAD_BASE = "https://upload.box.com/api/2.0"
BOX_TOKEN_URL = "https://api.box.com/oauth2/token"


@dataclass(frozen=True)
class BoxItem:
    id: str
    type: str
    name: str
    size: int | None = None
    sha1: str | None = None
    etag: str | None = None
    file_version_id: str | None = None
    created_at: str | None = None
    modified_at: str | None = None


class BoxClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        subject_type: str,
        subject_id: str,
        *,
        timeout: int = 60,
    ) -> None:
        import requests

        self.timeout = timeout
        self.session = requests.Session()
        token = self._fetch_access_token(client_id, client_secret, subject_type, subject_id)
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    def _fetch_access_token(
        self,
        client_id: str,
        client_secret: str,
        subject_type: str,
        subject_id: str,
    ) -> str:
        import requests

        response = requests.post(
            BOX_TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "box_subject_type": subject_type,
                "box_subject_id": subject_id,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        return str(response.json()["access_token"])

    def list_folder_items(self, folder_id: str) -> list[BoxItem]:
        items: list[BoxItem] = []
        limit = 1000
        offset = 0
        fields = ",".join(
            [
                "id",
                "type",
                "name",
                "size",
                "sha1",
                "etag",
                "file_version",
                "created_at",
                "modified_at",
            ]
        )
        while True:
            response = self.session.get(
                f"{BOX_API_BASE}/folders/{folder_id}/items",
                params={"limit": limit, "offset": offset, "fields": fields},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            entries = payload.get("entries", [])
            items.extend(_box_item(entry) for entry in entries)
            offset += len(entries)
            if offset >= payload.get("total_count", 0) or not entries:
                break
        return items

    def download_file(self, file_id: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with self.session.get(
            f"{BOX_API_BASE}/files/{file_id}/content",
            stream=True,
            timeout=self.timeout,
        ) as response:
            response.raise_for_status()
            with destination.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        handle.write(chunk)

    def find_child(self, folder_id: str, name: str, item_type: str | None = None) -> BoxItem | None:
        for item in self.list_folder_items(folder_id):
            if item.name == name and (item_type is None or item.type == item_type):
                return item
        return None

    def upload_file(self, folder_id: str, path: Path, name: str) -> BoxItem:
        attributes = {"name": name, "parent": {"id": folder_id}}
        with path.open("rb") as handle:
            response = self.session.post(
                f"{BOX_UPLOAD_BASE}/files/content",
                files={
                    "attributes": (None, _json_dumps(attributes), "application/json"),
                    "file": (name, handle, "text/csv" if name.endswith(".csv") else "application/json"),
                },
                timeout=self.timeout,
            )
        response.raise_for_status()
        return _box_item(response.json()["entries"][0])

    def upload_new_file_version(self, file_id: str, path: Path, name: str) -> BoxItem:
        with path.open("rb") as handle:
            response = self.session.post(
                f"{BOX_UPLOAD_BASE}/files/{file_id}/content",
                files={"file": (name, handle, "text/csv" if name.endswith(".csv") else "application/json")},
                timeout=self.timeout,
            )
        response.raise_for_status()
        return _box_item(response.json()["entries"][0])


def _json_dumps(value: Any) -> str:
    import json

    return json.dumps(value, separators=(",", ":"))


def _box_item(entry: dict[str, Any]) -> BoxItem:
    version = entry.get("file_version") or {}
    return BoxItem(
        id=str(entry["id"]),
        type=str(entry["type"]),
        name=str(entry["name"]),
        size=entry.get("size"),
        sha1=entry.get("sha1"),
        etag=entry.get("etag"),
        file_version_id=str(version["id"]) if version.get("id") else None,
        created_at=entry.get("created_at"),
        modified_at=entry.get("modified_at"),
    )
