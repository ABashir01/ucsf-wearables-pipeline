"""Filename parsing for FITriMSII source files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


PERSONAL_TRACKER_RE = re.compile(
    r"^FITriMSII_(?P<study_id>\d{1,3})[ _]+(?P<source>Fitbit|Garmin|Whoop|Oura|Apple)\.(?P<ext>csv|xml)$",
    re.IGNORECASE,
)
ACTIGRAPH_RE = re.compile(
    r"^FITriMSII_(?P<study_id>\d{1,3}).*60sec\.csv$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ParsedFilename:
    study_id: str
    source_type: str


def parse_source_filename(name: str, folder_hint: str | None = None) -> ParsedFilename | None:
    """Parse a source filename into StudyID and source type."""
    basename = Path(name).name
    personal_match = PERSONAL_TRACKER_RE.match(basename)
    if personal_match:
        return ParsedFilename(
            study_id=personal_match.group("study_id").zfill(3),
            source_type=personal_match.group("source").lower(),
        )

    if folder_hint and folder_hint.lower() == "actigraph":
        actigraph_match = ACTIGRAPH_RE.match(basename)
        if actigraph_match:
            return ParsedFilename(
                study_id=actigraph_match.group("study_id").zfill(3),
                source_type="actigraph",
            )

    return None
