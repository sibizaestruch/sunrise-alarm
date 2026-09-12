"""Config and options flow for Sunrise Alarm."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_DAYS,
    CONF_DURATION,
    CONF_ENABLED,
    CONF_HOLD_MINUTES,
    CONF_LIGHTS,
    CONF_MAX_BRIGHTNESS,
    CONF_NAME,
    CONF_PROFILE,
    CONF_SCHEDULE,
    CONF_SNOOZE_MINUTES,
    CONF_WAKE_TIME,
    DEFAULT_DAYS,
    DEFAULT_DURATION,
    DEFAULT_HOLD_MINUTES,
    DEFAULT_MAX_BRIGHTNESS,
    DEFAULT_NAME,
    DEFAULT_PROFILE,
    DEFAULT_SNOOZE_MINUTES,
    DEFAULT_WAKE_TIME,
    DOMAIN,
    WEEKDAYS,
)
from .sunrise import PROFILES

_PROFILE_LABELS = {
    "philips": "Philips-inspired (dim and red for long, surge at the end)",
    "gentle": "Gentle (smooth ramp, warm to the end)",
    "daylight": "Daylight (bright early, ends near white)",
}

_DAY_LABELS = {
    "mon": "Monday",
    "tue": "Tuesday",
    "wed": "Wednesday",
    "thu": "Thursday",
    "fri": "Friday",
    "sat": "Saturday",
    "sun": "Sunday",
}


def _schema(defaults: dict, with_name: bool) -> vol.Schema:
    """Build the configuration form.

    `with_name` marks the initial setup, which is also the only place the
    schedule is asked for: one wake time on a set of days, expanded on save.
    Afterwards the card owns the schedule, a time per day.
    """
    fields: dict = {}
    if with_name:
        fields[
            vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME))
        ] = selector.TextSelector()
    fields[vol.Required(CONF_LIGHTS, default=defaults.get(CONF_LIGHTS, []))] = (
        selector.EntitySelector(
            selector.EntitySelectorConfig(domain="light", multiple=True)
        )
    )
    if with_name:
        fields[
            vol.Required(
                CONF_WAKE_TIME, default=defaults.get(CONF_WAKE_TIME, DEFAULT_WAKE_TIME)
            )
        ] = selector.TimeSelector()
        fields[
            vol.Required(CONF_DAYS, default=defaults.get(CONF_DAYS, DEFAULT_DAYS))
        ] = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    selector.SelectOptionDict(value=day, label=_DAY_LABELS[day])
                    for day in WEEKDAYS
                ],
                multiple=True,
                mode=selector.SelectSelectorMode.LIST,
            )
        )
    fields.update(
        {
            vol.Required(
                CONF_DURATION, default=defaults.get(CONF_DURATION, DEFAULT_DURATION)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.5, max=180, step=0.5, unit_of_measurement="min"
                )
            ),
            vol.Required(
                CONF_MAX_BRIGHTNESS,
                default=defaults.get(CONF_MAX_BRIGHTNESS, DEFAULT_MAX_BRIGHTNESS),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=100, step=1, unit_of_measurement="%"
                )
            ),
            vol.Required(
                CONF_HOLD_MINUTES,
                default=defaults.get(CONF_HOLD_MINUTES, DEFAULT_HOLD_MINUTES),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=180, step=1, unit_of_measurement="min"
                )
            ),
            vol.Required(
                CONF_SNOOZE_MINUTES,
                default=defaults.get(CONF_SNOOZE_MINUTES, DEFAULT_SNOOZE_MINUTES),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=60, step=1, unit_of_measurement="min"
                )
            ),
            vol.Required(
                CONF_PROFILE, default=defaults.get(CONF_PROFILE, DEFAULT_PROFILE)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(
                            value=name, label=_PROFILE_LABELS[name]
                        )
                        for name in PROFILES
                    ]
                )
            ),
        }
    )
    return vol.Schema(fields)


class SunriseAlarmConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial configuration."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Single-step setup."""
        if user_input is not None:
            data = {**user_input}
            wake = data.pop(CONF_WAKE_TIME)
            data[CONF_SCHEDULE] = {day: wake for day in data.pop(CONF_DAYS)}
            return self.async_create_entry(title=data[CONF_NAME], data=data)
        return self.async_show_form(step_id="user", data_schema=_schema({}, True))

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return SunriseAlarmOptionsFlow()


class SunriseAlarmOptionsFlow(OptionsFlow):
    """Edit an existing alarm."""

    async def async_step_init(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Reconfigure the alarm."""
        current = {**self.config_entry.data, **self.config_entry.options}
        if user_input is not None:
            # The form asks for neither: keep what the switch and the card own.
            keep = {CONF_ENABLED: current.get(CONF_ENABLED, True)}
            if CONF_SCHEDULE in current:
                keep[CONF_SCHEDULE] = current[CONF_SCHEDULE]
            return self.async_create_entry(data={**user_input, **keep})
        return self.async_show_form(step_id="init", data_schema=_schema(current, False))
