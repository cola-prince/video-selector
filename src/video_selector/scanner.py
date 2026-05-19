from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


VIDEO_EXTENSIONS = {
    ".avi",
    ".flv",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
    ".webm",
    ".wmv",
}


@dataclass(frozen=True)
class VideoFile:
    path: Path
    duration: float


def discover_descendant_dirs(root: Path) -> list[Path]:
    """Return all descendant directories under root, sorted by display path."""
    root = root.expanduser()
    if not root.is_dir():
        raise NotADirectoryError(str(root))

    directories: list[Path] = []
    for current, dirnames, _ in os.walk(root):
        dirnames.sort()
        current_path = Path(current)
        if current_path == root:
            continue
        directories.append(current_path)
    return sorted(directories, key=lambda path: str(path.relative_to(root)).lower())


def is_video_path(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTENSIONS


def find_video_paths(directories: list[Path]) -> list[Path]:
    """Recursively find whitelisted videos under selected directories."""
    seen: set[Path] = set()
    videos: list[Path] = []

    for directory in directories:
        if not directory.is_dir():
            continue
        for current, dirnames, filenames in os.walk(directory):
            dirnames.sort()
            for filename in sorted(filenames):
                path = Path(current) / filename
                if not is_video_path(path):
                    continue
                resolved = path.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                videos.append(resolved)

    return sorted(videos, key=lambda path: str(path).lower())
