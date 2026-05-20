from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from video_selector.scanner import VideoFile


class ProbeError(RuntimeError):
    """Raised when ffprobe cannot read a file duration."""


ProbeRunner = Callable[[Path], float]


def ffprobe_executable() -> str:
    """Return bundled ffprobe when running from PyInstaller, otherwise PATH lookup."""
    for candidate in _bundled_ffprobe_candidates():
        if candidate.is_file():
            return str(candidate)
    return "ffprobe"


def _bundled_ffprobe_candidates() -> list[Path]:
    names = ["ffprobe.exe"] if sys.platform == "win32" else ["ffprobe"]
    roots: list[Path] = []

    pyinstaller_root = getattr(sys, "_MEIPASS", None)
    if pyinstaller_root:
        roots.append(Path(pyinstaller_root))

    if getattr(sys, "frozen", False):
        roots.append(Path(sys.executable).resolve().parent)

    return [root / name for root in roots for name in names]


def probe_duration(path: Path) -> float:
    """Read media duration in seconds using ffprobe."""
    try:
        completed = subprocess.run(
            [
                ffprobe_executable(),
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
        raise ProbeError("ffprobe was not bundled and was not found on PATH.") from exc
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
    max_workers: int | None = None,
) -> tuple[list[VideoFile], list[str]]:
    path_list = list(paths)
    if not path_list:
        return [], []

    if max_workers is None:
        max_workers = min(8, len(path_list))
    if max_workers <= 0:
        raise ValueError("max_workers must be greater than zero.")

    videos: list[VideoFile] = []
    warnings: list[str] = []

    def probe_path(path: Path) -> tuple[Path, float | None, str | None]:
        try:
            return path, runner(path), None
        except ProbeError as exc:
            return path, None, str(exc)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for path, duration, warning in executor.map(probe_path, path_list):
            if warning is not None:
                warnings.append(warning)
                continue
            if duration is not None:
                videos.append(VideoFile(path=path, duration=duration))

    return videos, warnings
