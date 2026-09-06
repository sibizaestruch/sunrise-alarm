"""Constants for the Sunrise Alarm integration."""

from __future__ import annotations

DOMAIN = "sunrise_alarm"

CONF_NAME = "name"
CONF_LIGHTS = "lights"
CONF_WAKE_TIME = "wake_time"
CONF_DAYS = "days"
CONF_DURATION = "duration"
CONF_MAX_BRIGHTNESS = "max_brightness"
CONF_PROFILE = "profile"
CONF_ENABLED = "enabled"
CONF_SNOOZE_MINUTES = "snooze_minutes"
CONF_HOLD_MINUTES = "hold_minutes"

DEFAULT_NAME = "Sunrise Alarm"
DEFAULT_WAKE_TIME = "07:30:00"
DEFAULT_DAYS = ["mon", "tue", "wed", "thu", "fri"]
DEFAULT_DURATION = 30  # minutes
DEFAULT_MAX_BRIGHTNESS = 100  # percent
DEFAULT_PROFILE = "philips"

WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}

SERVICE_START = "start"
SERVICE_STOP = "stop"
SERVICE_SNOOZE = "snooze"

ATTR_DURATION = "duration"
ATTR_MINUTES = "minutes"

UPDATE_INTERVAL = 5  # seconds between light updates during a sunrise
DEFAULT_SNOOZE_MINUTES = 9
DEFAULT_HOLD_MINUTES = 0  # minutes to stay lit after wake time; 0 = leave the lights on
SNOOZE_RAMP = 5  # minutes of sunrise after a snooze
TEST_DURATION = 1  # minutes for the test button
