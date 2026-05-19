from pathlib import Path

from video_selector.probe import ProbeError, probe_videos
from video_selector.scanner import VideoFile


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
