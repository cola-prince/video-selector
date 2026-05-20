from datetime import datetime
from pathlib import Path

from video_selector.export import export_matches
from video_selector.scanner import VideoFile
from video_selector.search import Match


def video(path: Path) -> VideoFile:
    return VideoFile(path=path, duration=1)


def match(files: list[Path]) -> Match:
    return Match(
        files=tuple(video(path) for path in files),
        total_duration=float(len(files)),
        delta=0,
    )


def test_export_matches_copies_each_result_to_timestamped_directory(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    first = source / "first.mp4"
    second = source / "second.mp4"
    third = source / "third.mp4"
    first.write_text("first")
    second.write_text("second")
    third.write_text("third")

    output_root = tmp_path / "output"
    export_root = export_matches(
        [match([first, second]), match([third])],
        output_root,
        now=datetime(2026, 5, 20, 14, 30, 5),
    )

    assert export_root == output_root / "20260520-143005"
    assert (export_root / "result-01" / "first.mp4").read_text() == "first"
    assert (export_root / "result-01" / "second.mp4").read_text() == "second"
    assert (export_root / "result-02" / "third.mp4").read_text() == "third"


def test_export_matches_keeps_files_with_duplicate_names(tmp_path):
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    first = first_dir / "clip.mp4"
    second = second_dir / "clip.mp4"
    first.write_text("first")
    second.write_text("second")

    export_root = export_matches(
        [match([first, second])],
        tmp_path / "output",
        now=datetime(2026, 5, 20, 14, 30, 5),
    )

    assert (export_root / "result-01" / "clip.mp4").read_text() == "first"
    assert (export_root / "result-01" / "clip-2.mp4").read_text() == "second"


def test_export_matches_uses_unique_timestamp_directory(tmp_path):
    source = tmp_path / "source.mp4"
    source.write_text("source")
    existing = tmp_path / "output" / "20260520-143005"
    existing.mkdir(parents=True)

    export_root = export_matches(
        [match([source])],
        tmp_path / "output",
        now=datetime(2026, 5, 20, 14, 30, 5),
    )

    assert export_root == tmp_path / "output" / "20260520-143005-2"
    assert (export_root / "result-01" / "source.mp4").read_text() == "source"


def test_export_matches_skips_empty_matches(tmp_path):
    export_root = export_matches([], tmp_path / "output")

    assert export_root is None
    assert not (tmp_path / "output").exists()
