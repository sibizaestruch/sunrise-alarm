"""Buttons to run a sunrise by hand, without touching the schedule."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SunriseAlarm
from .const import DOMAIN, TEST_DURATION


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the manual buttons."""
    alarm: SunriseAlarm = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            SunriseAlarmButton(
                alarm,
                "test",
                f"Test sunrise ({TEST_DURATION:g} min)",
                "mdi:test-tube",
                lambda: alarm.async_start_sunrise(TEST_DURATION),
            ),
            SunriseAlarmButton(
                alarm,
                "run",
                "Run sunrise now",
                "mdi:weather-sunset-up",
                lambda: alarm.async_start_sunrise(None),
            ),
            SunriseAlarmButton(
                alarm,
                "snooze",
                f"Snooze ({alarm.snooze_minutes:g} min)",
                "mdi:alarm-snooze",
                alarm.async_snooze,
            ),
            SunriseAlarmButton(
                alarm,
                "stop",
                "Stop sunrise",
                "mdi:stop",
                alarm.async_stop,
            ),
        ]
    )


class SunriseAlarmButton(ButtonEntity):
    """One press, one alarm method."""

    _attr_has_entity_name = True

    def __init__(
        self,
        alarm: SunriseAlarm,
        key: str,
        label: str,
        icon: str,
        action: Callable[[], Awaitable[None]],
    ) -> None:
        """Initialise the entity."""
        self._action = action
        self._attr_name = label
        self._attr_device_info = alarm.device_info
        self._attr_icon = icon
        self._attr_unique_id = f"{alarm.entry.entry_id}_{key}"

    async def async_press(self) -> None:
        """Run the action."""
        await self._action()
