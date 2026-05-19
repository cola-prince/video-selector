from __future__ import annotations


class DurationParseError(ValueError):
    """Raised when a user-provided duration cannot be parsed."""


def parse_duration(value: str) -> float:
    """Parse seconds, MM:SS, or HH:MM:SS into seconds."""
    text = value.strip()
    if not text:
        raise DurationParseError("Duration is required.")

    if ":" not in text:
        try:
            seconds = float(text)
        except ValueError as exc:
            raise DurationParseError(f"Invalid duration: {value!r}") from exc
        if seconds <= 0:
            raise DurationParseError("Duration must be greater than zero.")
        return seconds

    parts = text.split(":")
    if len(parts) not in (2, 3):
        raise DurationParseError("Use MM:SS or HH:MM:SS.")
    if any(part.strip() == "" for part in parts):
        raise DurationParseError(f"Invalid duration: {value!r}")

    try:
        numbers = [int(part) for part in parts]
    except ValueError as exc:
        raise DurationParseError(f"Invalid duration: {value!r}") from exc

    if any(number < 0 for number in numbers):
        raise DurationParseError("Duration parts cannot be negative.")
    if numbers[-1] >= 60:
        raise DurationParseError("Seconds must be less than 60.")
    if len(numbers) == 3 and numbers[-2] >= 60:
        raise DurationParseError("Minutes must be less than 60.")

    if len(numbers) == 2:
        minutes, seconds = numbers
        total = minutes * 60 + seconds
    else:
        hours, minutes, seconds = numbers
        total = hours * 3600 + minutes * 60 + seconds

    if total <= 0:
        raise DurationParseError("Duration must be greater than zero.")
    return float(total)


def parse_tolerance(value: str) -> tuple[float, float]:
    """Parse inclusive lower/upper tolerance seconds from 'lower,upper'."""
    text = value.strip()
    parts = [part.strip() for part in text.split(",")]
    if len(parts) != 2 or not all(parts):
        raise DurationParseError("Tolerance must be formatted as lower,upper.")

    try:
        lower, upper = (float(part) for part in parts)
    except ValueError as exc:
        raise DurationParseError(f"Invalid tolerance: {value!r}") from exc

    if lower > upper:
        raise DurationParseError("Tolerance lower bound cannot exceed upper bound.")
    return lower, upper


def format_duration(seconds: float) -> str:
    """Format seconds as H:MM:SS with millisecond precision when needed."""
    sign = "-" if seconds < 0 else ""
    remaining = abs(seconds)
    whole = int(remaining)
    fraction = remaining - whole
    hours, rem = divmod(whole, 3600)
    minutes, secs = divmod(rem, 60)

    if fraction:
        sec_text = f"{secs + fraction:06.3f}"
    else:
        sec_text = f"{secs:02d}"

    if hours:
        return f"{sign}{hours}:{minutes:02d}:{sec_text}"
    return f"{sign}{minutes}:{sec_text}"
