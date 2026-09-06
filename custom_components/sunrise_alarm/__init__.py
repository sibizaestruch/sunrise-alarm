"""Sunrise Alarm: turns Home Assistant lights into a wake-up light."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import (
    CONF_DAYS,
    CONF_DURATION,
    CONF_ENABLED,
    CONF_HOLD_MINUTES,
    CONF_LIGHTS,
    CONF_MAX_BRIGHTNESS,
    CONF_NAME,
    CONF_PROFILE,
    CONF_SNOOZE_MINUTES,
    CONF_WAKE_TIME,
    DEFAULT_HOLD_MINUTES,
    DEFAULT_MAX_BRIGHTNESS,
    DEFAULT_PROFILE,
    DEFAULT_SNOOZE_MINUTES,
    DOMAIN,
    SNOOZE_RAMP,
    UPDATE_INTERVAL,
    WEEKDAYS,
)
from .sunrise import PROFILES, Point, active_window, human_delta, next_start, state_at

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BUTTON, Platform.SWITCH]
COLOR_MODES = {"hs", "rgb", "rgbw", "rgbww", "xy"}
TRANSITION_SUPPORT = 32  # LightEntityFeature.TRANSITION


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a sunrise alarm from a config entry."""
    alarm = SunriseAlarm(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = alarm
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(alarm.async_start())
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


class SunriseAlarm:
    """Runtime state of one alarm: ticks on a timer and drives the lights."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise the alarm."""
        self.hass = hass
        self.entry = entry
        self._manual: tuple[datetime, datetime] | None = None
        self._skip_until: datetime | None = None
        self._off_at: datetime | None = None
        self._last: tuple[int, tuple[int, int, int]] | None = None

    # --- configuration ------------------------------------------------------

    @property
    def _cfg(self) -> dict:
        return {**self.entry.data, **self.entry.options}

    @property
    def name(self) -> str:
        """Name of the alarm."""
        return self._cfg[CONF_NAME]

    @property
    def enabled(self) -> bool:
        """Whether the schedule is armed."""
        return self._cfg.get(CONF_ENABLED, True)

    @property
    def lights(self) -> list[str]:
        """Light entities driven by this alarm."""
        return list(self._cfg[CONF_LIGHTS])

    @property
    def wake_time(self):
        """Configured wake-up time."""
        return dt_util.parse_time(self._cfg[CONF_WAKE_TIME])

    @property
    def days(self) -> set[int]:
        """Weekday numbers the alarm runs on."""
        return {WEEKDAYS[day] for day in self._cfg[CONF_DAYS] if day in WEEKDAYS}

    @property
    def duration(self) -> timedelta:
        """Sunrise duration."""
        return timedelta(minutes=float(self._cfg[CONF_DURATION]))

    @property
    def profile(self) -> tuple[Point, ...]:
        """Sunrise curve to follow. Falls back if a saved profile disappeared."""
        name = self._cfg.get(CONF_PROFILE, DEFAULT_PROFILE)
        return PROFILES.get(name, PROFILES[DEFAULT_PROFILE])

    @property
    def device_info(self) -> DeviceInfo:
        """Device grouping every entity of this alarm."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.entry.entry_id)},
            name=self.name,
            manufacturer="Sunrise Alarm",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def max_brightness(self) -> float:
        """Brightness reached at wake time."""
        return float(self._cfg.get(CONF_MAX_BRIGHTNESS, DEFAULT_MAX_BRIGHTNESS))

    @property
    def hold_minutes(self) -> float:
        """Minutes the lights stay on after the sunrise finishes. 0 = forever."""
        return float(self._cfg.get(CONF_HOLD_MINUTES, DEFAULT_HOLD_MINUTES))

    @property
    def snooze_minutes(self) -> float:
        """How long the snooze button delays the sunrise."""
        return float(self._cfg.get(CONF_SNOOZE_MINUTES, DEFAULT_SNOOZE_MINUTES))

    # --- runtime state ------------------------------------------------------

    def window(self, now: datetime) -> tuple[datetime, datetime] | None:
        """Return the (start, end) of the sunrise running at `now`, if any."""
        if self._manual is not None:
            start, end = self._manual
            if now >= end:
                self._manual = None
            elif now >= start:
                return start, end
            else:
                return None  # snoozed: nothing runs until the manual window
        if self._skip_until is not None and now < self._skip_until:
            return None
        if not self.enabled:
            return None
        return active_window(now, self.wake_time, self.days, self.duration)

    @property
    def next_start(self) -> datetime | None:
        """Start time of the next scheduled sunrise."""
        if not self.enabled:
            return None
        now = dt_util.now()
        if self._manual is not None and now < self._manual[0]:
            return self._manual[0]
        return next_start(now, self.wake_time, self.days, self.duration)

    @property
    def state(self) -> dict:
        """Attributes describing the current state."""
        now = dt_util.now()
        window = self.window(now)
        start = self.next_start
        attrs = {
            "wake_time": self._cfg[CONF_WAKE_TIME],
            "days": self._cfg[CONF_DAYS],
            "duration": self._cfg[CONF_DURATION],
            "max_brightness": self.max_brightness,
            "profile": self._cfg.get(CONF_PROFILE, DEFAULT_PROFILE),
            "next_sunrise_start": start,
            "next_wake": start + self.duration if start else None,
            "starts_in": human_delta(start - now) if start else None,
            "progress": None,
            "remaining": None,
            "lights_off_at": self._off_at,
        }
        if window is None:
            phase = "disabled" if not self.enabled else "armed"
            if self._manual is not None and now < self._manual[0]:
                phase = "snoozed"
        else:
            phase = "sunrise"
            begin, end = window
            attrs["progress"] = round((now - begin) / (end - begin), 3)
            attrs["remaining"] = str(end - now).split(".")[0]
        attrs["phase"] = phase
        return attrs

    # --- driving the lights -------------------------------------------------

    def async_start(self):
        """Start ticking. Returns the unsubscribe callback."""
        self.hass.async_create_task(self._tick())  # catch up after a restart
        return async_track_time_interval(
            self.hass, self._tick, timedelta(seconds=UPDATE_INTERVAL)
        )

    async def _tick(self, _now: datetime | None = None) -> None:
        now = dt_util.now()
        window = self.window(now)
        if window is None:
            if self._last is not None:  # window just ended: land on the final state
                self._last = None
                _LOGGER.info("%s: sunrise completed", self.name)
                await self._apply(*state_at(1.0, self.max_brightness, self.profile))
                hold = self.hold_minutes
                self._off_at = now + timedelta(minutes=hold) if hold else None
            elif self._off_at is not None and now >= self._off_at:
                _LOGGER.info("%s: extra time over, lights off", self.name)
                self._off_at = None
                await self._turn_off()
            return
        start, end = window
        progress = (now - start) / (end - start)
        brightness, rgb = state_at(progress, self.max_brightness, self.profile)
        if self._last is not None:
            last_brightness, last_rgb = self._last
            if (
                brightness == last_brightness
                and max(abs(a - b) for a, b in zip(rgb, last_rgb)) < 3
            ):
                return
        self._last = (brightness, rgb)
        await self._apply(brightness, rgb)

    async def _apply(self, brightness: int, rgb: tuple[int, int, int]) -> None:
        for entity_id in self.lights:
            state = self.hass.states.get(entity_id)
            if state is None or state.state == STATE_UNAVAILABLE:
                _LOGGER.debug("%s: skipping unavailable light %s", self.name, entity_id)
                continue
            data = {ATTR_ENTITY_ID: entity_id, "brightness_pct": brightness}
            if state.attributes.get("supported_features", 0) & TRANSITION_SUPPORT:
                data["transition"] = UPDATE_INTERVAL  # smooth over the tick interval
            if COLOR_MODES & set(state.attributes.get("supported_color_modes") or ()):
                data["rgb_color"] = list(rgb)
            _LOGGER.debug("%s: %s -> %s", self.name, entity_id, data)
            await self.hass.services.async_call(
                LIGHT_DOMAIN, SERVICE_TURN_ON, data, blocking=False
            )

    async def _turn_off(self) -> None:
        await self.hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: self.lights},
            blocking=False,
        )

    # --- services -----------------------------------------------------------

    async def async_start_sunrise(self, duration: float | None = None) -> None:
        """Run a sunrise now, optionally with a shorter duration (minutes)."""
        now = dt_util.now()
        length = timedelta(minutes=duration) if duration else self.duration
        _LOGGER.info("%s: starting sunrise, duration %s", self.name, length)
        self._manual = (now, now + length)
        self._skip_until = None
        self._off_at = None
        self._last = None
        await self._tick()

    async def async_stop(self) -> None:
        """Stop the running sunrise and turn the lights off."""
        _LOGGER.info("%s: sunrise stopped", self.name)
        now = dt_util.now()
        self._manual = None
        self._last = None
        self._off_at = None
        window = active_window(now, self.wake_time, self.days, self.duration)
        self._skip_until = window[1] if window else None
        await self._turn_off()

    async def async_snooze(self, minutes: float | None = None) -> None:
        """Turn the lights off and run a short sunrise again in `minutes`."""
        minutes = self.snooze_minutes if minutes is None else minutes
        _LOGGER.info("%s: snoozed for %s minutes", self.name, minutes)
        now = dt_util.now()
        self._last = None
        self._off_at = None
        start = now + timedelta(minutes=minutes)
        self._manual = (start, start + timedelta(minutes=SNOOZE_RAMP))
        await self._turn_off()
