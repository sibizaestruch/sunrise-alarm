"""Switch entity exposing the alarm: on = armed."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SunriseAlarm
from .const import (
    ATTR_DURATION,
    ATTR_MINUTES,
    CONF_ENABLED,
    DOMAIN,
    SERVICE_SNOOZE,
    SERVICE_START,
    SERVICE_STOP,
    SNOOZE_MINUTES,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the alarm switch and its services."""
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_START,
        {vol.Optional(ATTR_DURATION): vol.All(vol.Coerce(float), vol.Range(min=0.1))},
        "async_start_sunrise",
    )
    platform.async_register_entity_service(SERVICE_STOP, None, "async_stop_sunrise")
    platform.async_register_entity_service(
        SERVICE_SNOOZE,
        {
            vol.Optional(ATTR_MINUTES, default=SNOOZE_MINUTES): vol.All(
                vol.Coerce(float), vol.Range(min=0.1)
            )
        },
        "async_snooze_sunrise",
    )
    async_add_entities([SunriseAlarmSwitch(hass.data[DOMAIN][entry.entry_id])])


class SunriseAlarmSwitch(SwitchEntity):
    """Enable/disable the alarm and expose its runtime state."""

    _attr_should_poll = True
    _attr_icon = "mdi:weather-sunset-up"

    def __init__(self, alarm: SunriseAlarm) -> None:
        """Initialise the entity."""
        self._alarm = alarm
        self._attr_name = alarm.name
        self._attr_unique_id = alarm.entry.entry_id

    @property
    def is_on(self) -> bool:
        """Whether the alarm is armed."""
        return self._alarm.enabled

    @property
    def extra_state_attributes(self) -> dict:
        """Runtime state of the alarm."""
        return self._alarm.state

    async def async_turn_on(self, **kwargs) -> None:
        """Arm the alarm."""
        self._set_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Disarm the alarm and stop any running sunrise."""
        await self._alarm.async_stop()
        self._set_enabled(False)

    def _set_enabled(self, value: bool) -> None:
        entry = self._alarm.entry
        self.hass.config_entries.async_update_entry(
            entry, options={**entry.options, CONF_ENABLED: value}
        )  # persisted; the update listener reloads the entry

    async def async_start_sunrise(self, duration: float | None = None) -> None:
        """Service: start a sunrise now."""
        await self._alarm.async_start_sunrise(duration)

    async def async_stop_sunrise(self) -> None:
        """Service: stop the sunrise."""
        await self._alarm.async_stop()

    async def async_snooze_sunrise(self, minutes: float) -> None:
        """Service: snooze."""
        await self._alarm.async_snooze(minutes)
