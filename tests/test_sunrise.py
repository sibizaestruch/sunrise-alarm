"""Unit tests for the pure sunrise engine and scheduling maths."""

from datetime import datetime, time, timedelta

import pytest

from custom_components.sunrise_alarm.sunrise import (
    PROFILES,
    SUNRISE,
    active_window,
    human_delta,
    next_start,
    state_at,
)

WEEKDAYS = dict.fromkeys(range(5), time(7, 30))  # Mon-Fri at 07:30
# 2026-09-07 is a Monday.
MON = datetime(2026, 9, 7)


def test_progress_is_clamped():
    assert state_at(-5) == state_at(0.0)
    assert state_at(99) == state_at(1.0)


def test_endpoints_match_the_profile():
    assert state_at(0.0)[1] == SUNRISE[0].rgb
    assert state_at(1.0) == (100, SUNRISE[-1].rgb)


@pytest.mark.parametrize("points", PROFILES.values(), ids=list(PROFILES))
def test_brightness_is_monotonic_and_in_range(points):
    previous = 0
    for step in range(101):
        brightness, rgb = state_at(step / 100, 100, points)
        assert 1 <= brightness <= 100
        assert brightness >= previous
        assert all(0 <= channel <= 255 for channel in rgb)
        previous = brightness
    assert brightness == 100


@pytest.mark.parametrize("points", PROFILES.values(), ids=list(PROFILES))
def test_colour_moves_from_red_to_warm_white(points):
    green = [state_at(step / 20, 100, points)[1][1] for step in range(21)]
    assert green == sorted(green)
    assert state_at(0.0, 100, points)[1][2] < state_at(1.0, 100, points)[1][2]


def test_max_brightness_scales_the_curve():
    assert state_at(1.0, max_brightness=50)[0] == 50
    assert state_at(0.5, max_brightness=100)[0] >= state_at(0.5, max_brightness=50)[0]


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (MON.replace(hour=6, minute=59), None),  # a minute too early
        (MON.replace(hour=7, minute=0), (7, 0)),  # sunrise start
        (MON.replace(hour=7, minute=29), (7, 0)),
        (MON.replace(hour=7, minute=30), None),  # wake time: finished
    ],
)
def test_active_window(now, expected):
    window = active_window(now, WEEKDAYS, timedelta(minutes=30))
    if expected is None:
        assert window is None
    else:
        assert window[0] == now.replace(hour=expected[0], minute=expected[1], second=0)
        assert window[1] == now.replace(hour=7, minute=30, second=0)


def test_weekend_does_not_trigger():
    saturday = MON + timedelta(days=5, hours=7, minutes=10)
    assert active_window(saturday, WEEKDAYS, timedelta(minutes=30)) is None


def test_window_crossing_midnight():
    # 00:05 alarm on Monday starts on Sunday at 23:35
    sunday_night = MON - timedelta(minutes=15)
    window = active_window(sunday_night, {0: time(0, 5)}, timedelta(minutes=30))
    assert window == (MON - timedelta(minutes=25), MON + timedelta(minutes=5))


def test_next_start_same_day_and_next_week():
    duration = timedelta(minutes=30)
    assert next_start(MON, WEEKDAYS, duration) == MON.replace(hour=7)
    after = MON.replace(hour=8)
    assert next_start(after, WEEKDAYS, duration) == MON.replace(day=8, hour=7)
    friday_evening = MON + timedelta(days=4, hours=20)
    assert next_start(friday_evening, WEEKDAYS, duration) == MON.replace(day=14, hour=7)
    assert next_start(MON, {}, duration) is None


def test_next_start_single_day():
    only_wednesday = {2: time(7, 30)}
    start = next_start(MON, only_wednesday, timedelta(minutes=30))
    assert start == MON.replace(day=9, hour=7)


def test_each_day_keeps_its_own_time():
    """A late weekend wins over an earlier weekday once the week has moved on."""
    schedule = {4: time(7, 0), 5: time(9, 30), 6: time(11, 0)}
    duration = timedelta(minutes=30)
    friday_noon = MON + timedelta(days=4, hours=12)
    assert next_start(friday_noon, schedule, duration) == MON.replace(day=12, hour=9)
    saturday = MON + timedelta(days=5, hours=9, minutes=10)
    assert active_window(saturday, schedule, duration) == (
        MON.replace(day=12, hour=9),
        MON.replace(day=12, hour=9, minute=30),
    )
    # Saturday's 09:30 does not arm Friday, which wakes at 07:00.
    friday_morning = MON.replace(day=11, hour=9, minute=10)
    assert active_window(friday_morning, schedule, duration) is None


def test_human_delta():
    """Durations render short, and never negative."""
    assert human_delta(timedelta(minutes=9)) == "9m"
    assert human_delta(timedelta(hours=2, minutes=5)) == "2h 05m"
    assert human_delta(timedelta(seconds=-30)) == "0m"
