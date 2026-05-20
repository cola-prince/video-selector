import threading
from pathlib import Path

from video_selector import probe as probe_module
from video_selector.probe import ProbeError, ffprobe_executable, probe_videos
from video_selector.scanner import VideoFile


def test_ffprobe_executable_prefers_pyinstaller_bundle(tmp_path, monkeypatch):
    executable_name = "ffprobe.exe" if probe_module.sys.platform == "win32" else "ffprobe"
    bundled_ffprobe = tmp_path / executable_name
    bundled_ffprobe.write_text("")
    monkeypatch.setattr(probe_module.sys, "_MEIPASS", str(tmp_path), raising=False)

    assert ffprobe_executable() == str(bundled_ffprobe)


def test_ffprobe_executable_falls_back_to_path(monkeypatch):
    monkeypatch.delattr(probe_module.sys, "_MEIPASS", raising=False)
    monkeypatch.setattr(probe_module.sys, "frozen", False, raising=False)

    assert ffprobe_executable() == "ffprobe"


def test_probe_videos_collects_successes_and_probe_warnings():
    paths = [Path("first.mp4"), Path("broken.mp4"), Path("last.mov")]
    calls = []

    def runner(path):
        calls.append(path)
        if path == Path("broken.mp4"):
            raise ProbeError("cannot read broken.mp4")
        return {
            Path("first.mp4"): 12.5,
            Path("last.mov"): 7.0,
        }[path]

    videos, warnings = probe_videos(paths, runner=runner, max_workers=1)

    assert calls == paths
    assert videos == [
        VideoFile(path=Path("first.mp4"), duration=12.5),
        VideoFile(path=Path("last.mov"), duration=7.0),
    ]
    assert warnings == ["cannot read broken.mp4"]


def test_probe_videos_returns_results_in_input_order_when_concurrent():
    paths = [Path("slow.mp4"), Path("fast.mp4"), Path("last.mov")]
    slow_can_finish = threading.Event()
    finish_order = []

    def runner(path):
        if path == Path("slow.mp4"):
            slow_can_finish.wait(timeout=1)
        else:
            finish_order.append(path)
            slow_can_finish.set()
        return {
            Path("slow.mp4"): 12.5,
            Path("fast.mp4"): 7.0,
            Path("last.mov"): 3.0,
        }[path]

    videos, warnings = probe_videos(paths, runner=runner, max_workers=2)

    assert finish_order[0] == Path("fast.mp4")
    assert videos == [
        VideoFile(path=Path("slow.mp4"), duration=12.5),
        VideoFile(path=Path("fast.mp4"), duration=7.0),
        VideoFile(path=Path("last.mov"), duration=3.0),
    ]
    assert warnings == []


def test_probe_videos_rejects_non_positive_max_workers():
    try:
        probe_videos([Path("video.mp4")], runner=lambda path: 1.0, max_workers=0)
    except ValueError as exc:
        assert "max_workers" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
