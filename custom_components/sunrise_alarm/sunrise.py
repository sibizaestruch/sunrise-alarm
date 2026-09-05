"""Sunrise engine and alarm scheduling maths.

Pure Python: no Home Assistant imports, so it can be unit tested and run from
scripts/simulate_sunrise.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta


@dataclass(frozen=True)
class Point:
    """Control point of the sunrise curve."""

    at: float  # progress 0.0 - 1.0
    brightness: float  # percent 0 - 100
    rgb: tuple[int, int, int]


# Philips-inspired. Tune these against the real bulb; the points *are* the
# brightness curve, so no separate easing function is needed.
# ponytail: single hardcoded profile, add a profile option when a second one exists.
SUNRISE: tuple[Point, ...] = (
    Point(0.00, 1, (255, 20, 0)),
    Point(0.15, 2, (255, 45, 0)),
    Point(0.35, 8, (255, 90, 5)),
    Point(0.55, 20, (255, 145, 25)),
    Point(0.75, 45, (255, 190, 80)),
    Point(1.00, 100, (255, 225, 170)),
)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def state_at(
    progress: float, max_brightness: float = 100, points: tuple[Point, ...] = SUNRISE
) -> tuple[int, tuple[int, int, int]]:
    """Return (brightness_pct, rgb) for a progress value, clamped to [0, 1]."""
    p = min(1.0, max(0.0, progress))
    lo, hi = points[0], points[-1]
    for a, b in zip(points, points[1:]):
        if p <= b.at:
            lo, hi = a, b
            break
    t = 0.0 if hi.at == lo.at else (p - lo.at) / (hi.at - lo.at)
    brightness = _lerp(lo.brightness, hi.brightness, t) * max_brightness / 100
    rgb = tuple(round(_lerp(c, d, t)) for c, d in zip(lo.rgb, hi.rgb))
    return max(1, round(brightness)), rgb  # type: ignore[return-value]


# --- scheduling -------------------------------------------------------------
# `days` are weekday numbers (Mon=0) of the *wake* time, so a 00:05 alarm on
# Monday with a 30 minute sunrise starts on Sunday at 23:35.


def _wake_on(day: datetime, wake: time) -> datetime:
    return day.replace(hour=wake.hour, minute=wake.minute, second=0, microsecond=0)


def active_window(
    now: datetime, wake: time, days: set[int], duration: timedelta
) -> tuple[datetime, datetime] | None:
    """Return (start, wake) if `now` is inside a sunrise, else None."""
    for offset in (0, 1):
        wake_dt = _wake_on(now + timedelta(days=offset), wake)
        if wake_dt.weekday() in days and wake_dt - duration <= now < wake_dt:
            return wake_dt - duration, wake_dt
    return None


def next_start(
    now: datetime, wake: time, days: set[int], duration: timedelta
) -> datetime | None:
    """Return the next sunrise start at or after `now`."""
    if not days:
        return None
    for offset in range(8):
        wake_dt = _wake_on(now + timedelta(days=offset), wake)
        if wake_dt.weekday() in days and wake_dt - duration >= now:
            return wake_dt - duration
    return None


def human_delta(delta: timedelta) -> str:
    """Round a positive duration down to a short "2h 05m" / "9m" string."""
    minutes = max(int(delta.total_seconds()) // 60, 0)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m" if hours else f"{minutes}m"
