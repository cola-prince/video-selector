from pathlib import Path

import pytest

from video_selector.scanner import VideoFile
from video_selector.search import find_matches


def video(name, duration):
    return VideoFile(path=Path(name), duration=duration)


def match_summary(result):
    return [
        (tuple(file.path.name for file in match.files), match.total_duration, match.delta)
        for match in result.matches
    ]


def test_find_matches_sorts_by_delta_file_count_then_total_duration():
    videos = [
        video("ten.mp4", 10),
        video("six.mp4", 6),
        video("four.mp4", 4),
        video("eleven.mp4", 11),
        video("five.mp4", 5),
    ]

    result = find_matches(
        videos,
        target=10,
        tolerance=(0, 1),
        max_results=10,
        timeout_seconds=60,
    )

    assert not result.timed_out
    assert not result.capped
    assert match_summary(result) == [
        (("ten.mp4",), 10.0, 0.0),
        (("four.mp4", "six.mp4"), 10.0, 0.0),
        (("eleven.mp4",), 11.0, 1.0),
        (("five.mp4", "six.mp4"), 11.0, 1.0),
    ]


def test_find_matches_respects_result_cap():
    videos = [
        video("ten.mp4", 10),
        video("nine.mp4", 9),
        video("one.mp4", 1),
        video("eight.mp4", 8),
        video("two.mp4", 2),
    ]

    result = find_matches(
        videos,
        target=10,
        tolerance=(0, 0),
        max_results=2,
        timeout_seconds=60,
        random_seed=0,
    )

    assert result.capped
    assert not result.timed_out
    assert len(result.matches) == 2
    assert match_summary(result) == [
        (("ten.mp4",), 10.0, 0.0),
        (("nine.mp4", "one.mp4"), 10.0, 0.0),
    ]


def test_find_matches_rejects_non_positive_result_cap():
    with pytest.raises(ValueError, match="max_results"):
        find_matches([], target=10, tolerance=(0, 0), max_results=0)


def test_find_matches_rejects_non_positive_min_files():
    with pytest.raises(ValueError, match="min_files"):
        find_matches([], target=10, tolerance=(0, 0), min_files=0)


def test_find_matches_filters_by_min_files():
    videos = [
        video("ten.mp4", 10),
        video("six.mp4", 6),
        video("four.mp4", 4),
        video("seven.mp4", 7),
        video("three.mp4", 3),
    ]

    result = find_matches(
        videos,
        target=10,
        tolerance=(0, 0),
        max_results=10,
        timeout_seconds=60,
        min_files=2,
        random_seed=0,
    )

    assert not result.timed_out
    assert not result.capped
    assert match_summary(result) == [
        (("four.mp4", "six.mp4"), 10.0, 0.0),
        (("seven.mp4", "three.mp4"), 10.0, 0.0),
    ]


def test_find_matches_can_return_different_capped_results_for_different_seeds():
    videos = [
        video("a.mp4", 5),
        video("b.mp4", 5),
        video("c.mp4", 5),
        video("d.mp4", 5),
    ]

    seed_zero = find_matches(
        videos,
        target=10,
        tolerance=(0, 0),
        max_results=1,
        timeout_seconds=60,
        min_files=2,
        random_seed=0,
    )
    seed_one = find_matches(
        videos,
        target=10,
        tolerance=(0, 0),
        max_results=1,
        timeout_seconds=60,
        min_files=2,
        random_seed=1,
    )

    assert seed_zero.capped
    assert seed_one.capped
    assert match_summary(seed_zero) != match_summary(seed_one)
