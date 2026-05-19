from __future__ import annotations

import subprocess
from collections.abc import Callable, Iterable
from pathlib import Path

from video_selector.scanner import VideoFile


class ProbeError(RuntimeError):
    """Raised when ffprobe cannot read a file duration."""


ProbeRunner = Callable[[Path], float]


def probe_duration(path: Path) -> float:
    """Read media duration in seconds using ffprobe."""
    try:
        completed = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except FileNotFoundError as exc:
        raise ProbeError("ffprobe was not found on PATH.") from exc
    except subprocess.TimeoutExpired as exc:
        raise ProbeError(f"ffprobe timed out for {path}") from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        raise ProbeError(f"ffprobe failed for {path}: {detail}") from exc

    output = completed.stdout.strip()
    try:
        duration = float(output)
    except ValueError as exc:
        raise ProbeError(f"ffprobe returned an invalid duration for {path}: {output!r}") from exc

    if duration <= 0:
        raise ProbeError(f"ffprobe returned a non-positive duration for {path}")
    return duration


def probe_videos(
    paths: Iterable[Path],
    runner: ProbeRunner = probe_duration,
) -> tuple[list[VideoFile], list[str]]:
    videos: list[VideoFile] = []
    warnings: list[str] = []

    for path in paths:
        try:
            videos.append(VideoFile(path=path, duration=runner(path)))
        except ProbeError as exc:
            warnings.append(str(exc))

    return videos, warnings
