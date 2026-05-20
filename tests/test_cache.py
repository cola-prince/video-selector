from pathlib import Path

from video_selector.cache import CacheRefreshProgress, VideoCache
from video_selector.probe import ProbeError
from video_selector.scanner import VideoFile


def test_refresh_root_populates_directories_and_videos(tmp_path):
    root = tmp_path / "library"
    alpha = root / "alpha"
    nested = alpha / "nested"
    beta = root / "beta"
    nested.mkdir(parents=True)
    beta.mkdir(parents=True)
    first = alpha / "first.mp4"
    second = nested / "second.mov"
    third = beta / "third.webm"
    ignored = beta / "audio.mp3"
    for path in [first, second, third, ignored]:
        path.write_text("content")

    durations = {
        first.resolve(): 1.0,
        second.resolve(): 2.0,
        third.resolve(): 3.0,
    }
    cache = VideoCache(tmp_path / "cache.sqlite3")
    progress: list[CacheRefreshProgress] = []

    result = cache.refresh_root(
        root,
        runner=lambda path: durations[path],
        progress=progress.append,
    )

    assert result.total == 3
    assert result.probed == 3
    assert result.reused == 0
    assert result.removed == 0
    assert result.warnings == []
    assert cache.list_directories(root) == [
        alpha.resolve(),
        nested.resolve(),
        beta.resolve(),
    ]
    assert cache.list_videos([alpha]) == [
        VideoFile(path=first.resolve(), duration=1.0),
        VideoFile(path=second.resolve(), duration=2.0),
    ]
    assert progress[-1] == CacheRefreshProgress("done", 3, 3)


def test_refresh_root_reuses_unchanged_files(tmp_path):
    root = tmp_path / "library"
    root.mkdir()
    video = root / "clip.mp4"
    video.write_text("content")
    calls: list[Path] = []
    cache = VideoCache(tmp_path / "cache.sqlite3")

    cache.refresh_root(root, runner=lambda path: 12.5)
    result = cache.refresh_root(
        root,
        runner=lambda path: calls.append(path) or 99.0,
    )

    assert result.total == 1
    assert result.probed == 0
    assert result.reused == 1
    assert calls == []
    assert cache.list_videos([root]) == [
        VideoFile(path=video.resolve(), duration=12.5),
    ]


def test_refresh_root_updates_changed_files_and_removes_stale_rows(tmp_path):
    root = tmp_path / "library"
    root.mkdir()
    changed = root / "changed.mp4"
    stale = root / "stale.mp4"
    changed.write_text("old")
    stale.write_text("old")
    cache = VideoCache(tmp_path / "cache.sqlite3")

    cache.refresh_root(
        root,
        runner=lambda path: {changed.resolve(): 1.0, stale.resolve(): 2.0}[path],
    )
    changed.write_text("new content")
    stale.unlink()

    result = cache.refresh_root(root, runner=lambda path: 3.0)

    assert result.total == 1
    assert result.probed == 1
    assert result.reused == 0
    assert result.removed == 1
    assert cache.list_videos([root]) == [
        VideoFile(path=changed.resolve(), duration=3.0),
    ]


def test_refresh_root_keeps_renamed_file_with_same_file_id(tmp_path):
    root = tmp_path / "library"
    root.mkdir()
    original = root / "original.mp4"
    renamed = root / "renamed.mp4"
    original.write_text("content")
    cache = VideoCache(tmp_path / "cache.sqlite3")

    cache.refresh_root(root, runner=lambda path: 12.5)
    original.rename(renamed)
    result = cache.refresh_root(root, runner=lambda path: 99.0)

    assert result.total == 1
    assert result.probed == 0
    assert result.reused == 1
    assert result.removed == 0
    assert cache.list_videos([root]) == [
        VideoFile(path=renamed.resolve(), duration=12.5),
    ]


def test_refresh_root_drops_failed_probe_from_cache(tmp_path):
    root = tmp_path / "library"
    root.mkdir()
    video = root / "clip.mp4"
    video.write_text("content")
    cache = VideoCache(tmp_path / "cache.sqlite3")
    cache.refresh_root(root, runner=lambda path: 12.5)

    video.write_text("changed")
    result = cache.refresh_root(
        root,
        runner=lambda path: (_ for _ in ()).throw(ProbeError("cannot read clip")),
    )

    assert result.total == 1
    assert result.probed == 0
    assert result.reused == 0
    assert result.removed == 0
    assert result.warnings == ["cannot read clip"]
    assert cache.list_videos([root]) == []
