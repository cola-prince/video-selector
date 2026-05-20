from __future__ import annotations

import random
import time
from dataclasses import dataclass

from video_selector.scanner import VideoFile


@dataclass(frozen=True)
class Match:
    files: tuple[VideoFile, ...]
    total_duration: float
    delta: float


@dataclass(frozen=True)
class SearchResult:
    matches: list[Match]
    timed_out: bool
    capped: bool


def find_matches(
    videos: list[VideoFile],
    target: float,
    tolerance: tuple[float, float],
    max_results: int = 20,
    timeout_seconds: float = 10.0,
    min_files: int = 1,
    random_seed: int | None = None,
) -> SearchResult:
    """Find unordered video combinations whose total duration is in range."""
    if max_results <= 0:
        raise ValueError("max_results must be greater than zero.")
    if min_files <= 0:
        raise ValueError("min_files must be greater than zero.")
    lower, upper = tolerance
    min_total = target + lower
    max_total = target + upper
    if min_total < 0:
        min_total = 0
    if min_total > max_total:
        raise ValueError("Tolerance produces an empty target range.")

    ordered = list(videos)
    rng = random.Random(random_seed)
    rng.shuffle(ordered)
    suffix_sums = [0.0] * (len(ordered) + 1)
    for index in range(len(ordered) - 1, -1, -1):
        suffix_sums[index] = suffix_sums[index + 1] + ordered[index].duration

    matches: list[Match] = []
    start = time.monotonic()
    timed_out = False
    capped = False
    epsilon = 1e-6

    def timed_out_now() -> bool:
        return time.monotonic() - start >= timeout_seconds

    def visit(index: int, total: float, chosen: list[VideoFile]) -> None:
        nonlocal timed_out, capped
        if timed_out or capped:
            return
        if timed_out_now():
            timed_out = True
            return
        if len(chosen) + (len(ordered) - index) < min_files:
            return
        if total > max_total + epsilon:
            return
        if total + suffix_sums[index] < min_total - epsilon:
            return
        if (
            min_total - epsilon <= total <= max_total + epsilon
            and len(chosen) >= min_files
        ):
            matches.append(
                Match(
                    files=tuple(sorted(chosen, key=lambda video: str(video.path).lower())),
                    total_duration=total,
                    delta=total - target,
                )
            )
            if len(matches) >= max_results:
                capped = True
                return

        if index >= len(ordered):
            return

        for next_index in range(index, len(ordered)):
            video = ordered[next_index]
            next_total = total + video.duration
            if next_total > max_total + epsilon:
                continue
            chosen.append(video)
            visit(next_index + 1, next_total, chosen)
            chosen.pop()
            if timed_out or capped:
                return

    visit(0, 0.0, [])
    matches.sort(key=lambda match: (abs(match.delta), len(match.files), match.total_duration))
    return SearchResult(matches=matches, timed_out=timed_out, capped=capped)
