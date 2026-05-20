from pathlib import Path

from video_selector.app import run_match_job
from video_selector.scanner import VideoFile


class FakeCache:
    def __init__(self, videos):
        self.videos = videos
        self.directories = None

    def list_videos(self, directories):
        self.directories = directories
        return self.videos


def test_run_match_job_reads_videos_from_cache():
    directory = Path("cached")
    cache = FakeCache(
        [
            VideoFile(Path("cached/first.mp4"), duration=7),
            VideoFile(Path("cached/second.mp4"), duration=5),
        ]
    )

    job = run_match_job(
        cache,
        [directory],
        target=12,
        tolerance=(0, 0),
        max_results=1,
        min_files=2,
    )

    assert cache.directories == [directory]
    assert job.video_count == 2
    assert job.warnings == []
    assert len(job.result.matches) == 1
