from pathlib import Path

from video_selector.scanner import find_video_paths, is_video_path


def test_is_video_path_uses_case_insensitive_whitelist():
    assert is_video_path(Path("clip.MP4"))
    assert is_video_path(Path("clip.mkv"))
    assert not is_video_path(Path("clip.mp3"))
    assert not is_video_path(Path("clip.txt"))


def test_find_video_paths_recurses_sorts_and_dedupes_overlapping_directories(tmp_path):
    root = tmp_path / "library"
    nested = root / "alpha" / "nested"
    nested.mkdir(parents=True)
    beta = root / "beta"
    beta.mkdir()

    alpha_clip = root / "alpha" / "Clip.MP4"
    nested_clip = nested / "scene.mov"
    beta_clip = beta / "other.webm"
    ignored_file = root / "alpha" / "audio.mp3"

    alpha_clip.write_text("not a real video")
    nested_clip.write_text("not a real video")
    beta_clip.write_text("not a real video")
    ignored_file.write_text("not a video")

    videos = find_video_paths([root / "alpha", root, tmp_path / "missing"])

    expected = [alpha_clip.resolve(), nested_clip.resolve(), beta_clip.resolve()]
    assert videos == sorted(expected, key=lambda path: str(path).lower())
