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
    CONF_LIGHTS,
    CONF_MAX_BRIGHTNESS,
    CONF_NAME,
    CONF_PROFILE,
    CONF_WAKE_TIME,
    DEFAULT_DAYS,
    DEFAULT_DURATION,
    DEFAULT_MAX_BRIGHTNESS,
    DEFAULT_NAME,
    DEFAULT_PROFILE,
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
    """Build the (single) configuration form."""
    fields: dict = {}
    if with_name:
        fields[
            vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME))
        ] = selector.TextSelector()
    fields.update(
        {
            vol.Required(
                CONF_LIGHTS, default=defaults.get(CONF_LIGHTS, [])
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="light", multiple=True)
            ),
            vol.Required(
                CONF_WAKE_TIME, default=defaults.get(CONF_WAKE_TIME, DEFAULT_WAKE_TIME)
            ): selector.TimeSelector(),
            vol.Required(
                CONF_DAYS, default=defaults.get(CONF_DAYS, DEFAULT_DAYS)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=day, label=_DAY_LABELS[day])
                        for day in WEEKDAYS
                    ],
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
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
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)
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
            # keep the armed state, it lives in the options too
            return self.async_create_entry(
                data={**user_input, CONF_ENABLED: current.get(CONF_ENABLED, True)}
            )
        return self.async_show_form(step_id="init", data_schema=_schema(current, False))
