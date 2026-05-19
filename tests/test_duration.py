import pytest

from video_selector.duration import DurationParseError, parse_duration, parse_tolerance


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("90", 90.0),
        ("90.5", 90.5),
        (" 01:02 ", 62.0),
        ("1:02:03", 3723.0),
    ],
)
def test_parse_duration_accepts_supported_formats(value, expected):
    assert parse_duration(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "0",
        "-1",
        "abc",
        "1::02",
        "1:60",
        "1:60:00",
        "1:02:60",
        "1:2:3:4",
    ],
)
def test_parse_duration_rejects_invalid_values(value):
    with pytest.raises(DurationParseError):
        parse_duration(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("-1,10", (-1.0, 10.0)),
        ("0,0", (0.0, 0.0)),
        (" 0.25 , 2.5 ", (0.25, 2.5)),
    ],
)
def test_parse_tolerance_accepts_inclusive_bounds(value, expected):
    assert parse_tolerance(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "1",
        "1,",
        ",1",
        "2,1",
        "left,right",
    ],
)
def test_parse_tolerance_rejects_invalid_values(value):
    with pytest.raises(DurationParseError):
        parse_tolerance(value)
