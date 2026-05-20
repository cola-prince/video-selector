from __future__ import annotations

import hashlib
import os
import sqlite3
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from video_selector.probe import ProbeError, ProbeRunner, probe_duration
from video_selector.scanner import VideoFile, find_video_paths


SCHEMA_VERSION = 1


@dataclass(frozen=True)
class CachedVideo:
    file_id: str
    path: Path
    name: str
    directory: Path
    duration: float
    size: int
    mtime_ns: int
    refreshed_at: float


@dataclass(frozen=True)
class CacheRefreshProgress:
    phase: str
    completed: int
    total: int
    current_path: Path | None = None


@dataclass(frozen=True)
class CacheRefreshResult:
    total: int
    probed: int
    reused: int
    removed: int
    warnings: list[str]


ProgressCallback = Callable[[CacheRefreshProgress], None]


def default_cache_path() -> Path:
    if sys.platform == "win32":
        root = os.environ.get("LOCALAPPDATA")
        base = Path(root) if root else Path.home() / "AppData" / "Local"
        return base / "video-selector" / "videos.sqlite3"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "video-selector" / "videos.sqlite3"
    root = os.environ.get("XDG_CACHE_HOME")
    base = Path(root) if root else Path.home() / ".cache"
    return base / "video-selector" / "videos.sqlite3"


def file_id_for_path(path: Path, stat_result: os.stat_result | None = None) -> str:
    stat_result = stat_result or path.stat()
    inode = getattr(stat_result, "st_ino", 0)
    device = getattr(stat_result, "st_dev", 0)
    if inode:
        return f"inode:{device}:{inode}"

    resolved = str(path.resolve())
    digest = hashlib.sha256(
        f"{resolved}\0{stat_result.st_size}\0{stat_result.st_mtime_ns}".encode()
    ).hexdigest()
    return f"path:{digest}"


class VideoCache:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_cache_path()

    def refresh_root(
        self,
        root: Path,
        runner: ProbeRunner = probe_duration,
        progress: ProgressCallback | None = None,
    ) -> CacheRefreshResult:
        root = root.expanduser().resolve()
        if not root.is_dir():
            raise NotADirectoryError(str(root))

        self._ensure_parent()
        with self._connect() as connection:
            self._initialize(connection)
            progress and progress(CacheRefreshProgress("discovering", 0, 1))
            paths = find_video_paths([root])
            total = len(paths)
            progress and progress(CacheRefreshProgress("refreshing", 0, total))

            existing = self._rows_under_root(connection, root)
            existing_by_path = {row.path: row for row in existing}
            existing_by_id = {row.file_id: row for row in existing}
            current_paths = {path.resolve() for path in paths}
            current_file_ids: set[str] = set()

            probed = 0
            reused = 0
            warnings: list[str] = []
            refreshed_at = time.time()

            for index, path in enumerate(paths, start=1):
                progress and progress(
                    CacheRefreshProgress("refreshing", index - 1, total, path)
                )
                try:
                    stat_result = path.stat()
                except OSError as exc:
                    warnings.append(f"Could not stat {path}: {exc}")
                    progress and progress(
                        CacheRefreshProgress("refreshing", index, total, path)
                    )
                    continue

                file_id = file_id_for_path(path, stat_result)
                current_file_ids.add(file_id)
                cached = existing_by_path.get(path) or existing_by_id.get(file_id)
                if (
                    cached is not None
                    and cached.file_id == file_id
                    and cached.size == stat_result.st_size
                    and cached.mtime_ns == stat_result.st_mtime_ns
                ):
                    duration = cached.duration
                    reused += 1
                else:
                    try:
                        duration = runner(path)
                    except ProbeError as exc:
                        self._delete_failed_path(connection, path, file_id)
                        warnings.append(str(exc))
                        progress and progress(
                            CacheRefreshProgress("refreshing", index, total, path)
                        )
                        continue
                    probed += 1

                self._upsert_video(
                    connection,
                    file_id=file_id,
                    path=path,
                    duration=duration,
                    size=stat_result.st_size,
                    mtime_ns=stat_result.st_mtime_ns,
                    refreshed_at=refreshed_at,
                )
                progress and progress(
                    CacheRefreshProgress("refreshing", index, total, path)
                )

            removed = self._delete_stale_rows(
                connection, existing, current_paths, current_file_ids
            )
            connection.commit()
            progress and progress(CacheRefreshProgress("done", total, total))

        return CacheRefreshResult(
            total=total,
            probed=probed,
            reused=reused,
            removed=removed,
            warnings=warnings,
        )

    def list_directories(self, root: Path) -> list[Path]:
        root = root.expanduser().resolve()
        if not root.is_dir():
            raise NotADirectoryError(str(root))

        self._ensure_parent()
        with self._connect() as connection:
            self._initialize(connection)
            directories = {row.directory for row in self._rows_under_root(connection, root)}
        return sorted(directories, key=lambda path: str(path.relative_to(root)).lower())

    def list_videos(self, directories: list[Path]) -> list[VideoFile]:
        if not directories:
            return []

        resolved_dirs = [directory.expanduser().resolve() for directory in directories]
        self._ensure_parent()
        with self._connect() as connection:
            self._initialize(connection)
            rows = self._all_rows(connection)

        videos: list[VideoFile] = []
        seen: set[Path] = set()
        for row in rows:
            if not any(_is_relative_to(row.path, directory) for directory in resolved_dirs):
                continue
            if row.path in seen:
                continue
            seen.add(row.path)
            videos.append(VideoFile(path=row.path, duration=row.duration))

        return sorted(videos, key=lambda video: str(video.path).lower())

    def _ensure_parent(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self, connection: sqlite3.Connection) -> None:
        connection.execute("PRAGMA user_version = %d" % SCHEMA_VERSION)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS videos (
                file_id TEXT PRIMARY KEY,
                path TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                directory TEXT NOT NULL,
                duration REAL NOT NULL,
                size INTEGER NOT NULL,
                mtime_ns INTEGER NOT NULL,
                refreshed_at REAL NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_videos_directory ON videos(directory)"
        )

    def _rows_under_root(
        self, connection: sqlite3.Connection, root: Path
    ) -> list[CachedVideo]:
        rows = self._all_rows(connection)
        return [row for row in rows if _is_relative_to(row.path, root)]

    def _all_rows(self, connection: sqlite3.Connection) -> list[CachedVideo]:
        return [
            _row_to_cached_video(row)
            for row in connection.execute(
                """
                SELECT file_id, path, name, directory, duration, size, mtime_ns, refreshed_at
                FROM videos
                ORDER BY path COLLATE NOCASE
                """
            )
        ]

    def _upsert_video(
        self,
        connection: sqlite3.Connection,
        *,
        file_id: str,
        path: Path,
        duration: float,
        size: int,
        mtime_ns: int,
        refreshed_at: float,
    ) -> None:
        connection.execute(
            "DELETE FROM videos WHERE path = ? AND file_id != ?",
            (str(path), file_id),
        )
        connection.execute(
            """
            INSERT INTO videos (
                file_id, path, name, directory, duration, size, mtime_ns, refreshed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(file_id) DO UPDATE SET
                path = excluded.path,
                name = excluded.name,
                directory = excluded.directory,
                duration = excluded.duration,
                size = excluded.size,
                mtime_ns = excluded.mtime_ns,
                refreshed_at = excluded.refreshed_at
            """,
            (
                file_id,
                str(path),
                path.name,
                str(path.parent),
                duration,
                size,
                mtime_ns,
                refreshed_at,
            ),
        )

    def _delete_failed_path(
        self, connection: sqlite3.Connection, path: Path, file_id: str
    ) -> None:
        connection.execute(
            "DELETE FROM videos WHERE path = ? OR file_id = ?",
            (str(path), file_id),
        )

    def _delete_stale_rows(
        self,
        connection: sqlite3.Connection,
        existing: list[CachedVideo],
        current_paths: set[Path],
        current_file_ids: set[str],
    ) -> int:
        stale = [
            row
            for row in existing
            if row.path not in current_paths and row.file_id not in current_file_ids
        ]
        for row in stale:
            connection.execute("DELETE FROM videos WHERE file_id = ?", (row.file_id,))
        return len(stale)


def _row_to_cached_video(row: sqlite3.Row) -> CachedVideo:
    return CachedVideo(
        file_id=row["file_id"],
        path=Path(row["path"]),
        name=row["name"],
        directory=Path(row["directory"]),
        duration=row["duration"],
        size=row["size"],
        mtime_ns=row["mtime_ns"],
        refreshed_at=row["refreshed_at"],
    )


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
