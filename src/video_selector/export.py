from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from video_selector.search import Match


def export_matches(
    matches: list[Match],
    output_root: Path,
    now: datetime | None = None,
) -> Path | None:
    """Copy each match's videos into timestamped result directories."""
    if not matches:
        return None

    timestamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    export_root = next_available_path(output_root.expanduser() / timestamp)
    export_root.mkdir(parents=True, exist_ok=False)

    for match_index, match in enumerate(matches, start=1):
        result_dir = export_root / f"result-{match_index:02d}"
        result_dir.mkdir()
        for video in match.files:
            shutil.copy2(video.path, next_available_path(result_dir / video.path.name))

    return export_root


def next_available_path(path: Path) -> Path:
    if not path.exists():
        return path

    for index in range(2, 10_000):
        candidate = path.with_name(f"{path.stem}-{index}{path.suffix}")
        if not candidate.exists():
            return candidate

    raise FileExistsError(f"Could not create a unique filename for {path}.")
