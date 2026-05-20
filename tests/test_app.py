import pytest

from video_selector.app import parse_positive_float


def test_parse_positive_float_accepts_positive_seconds():
    assert parse_positive_float("12.5", "Search timeout seconds") == 12.5


def test_parse_positive_float_rejects_non_number():
    with pytest.raises(ValueError, match="Search timeout seconds must be a number"):
        parse_positive_float("soon", "Search timeout seconds")


def test_parse_positive_float_rejects_non_positive_value():
    with pytest.raises(
        ValueError,
        match="Search timeout seconds must be a finite number greater than zero",
    ):
        parse_positive_float("0", "Search timeout seconds")


def test_parse_positive_float_rejects_non_finite_value():
    with pytest.raises(
        ValueError,
        match="Search timeout seconds must be a finite number greater than zero",
    ):
        parse_positive_float("nan", "Search timeout seconds")
