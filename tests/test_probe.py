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

    videos, warnings = probe_videos(paths, runner=runner)

    assert calls == paths
    assert videos == [
        VideoFile(path=Path("first.mp4"), duration=12.5),
        VideoFile(path=Path("last.mov"), duration=7.0),
    ]
    assert warnings == ["cannot read broken.mp4"]
