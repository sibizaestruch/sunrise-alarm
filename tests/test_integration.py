"""Home Assistant level tests: config flow, sunrise run, restart, disabled."""

from datetime import timedelta

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.sunrise_alarm.const import DOMAIN

CONFIG = {
    "name": "Bedroom Sunrise",
    "lights": ["light.bedroom"],
    "wake_time": "07:30:00",
    "days": ["mon", "tue", "wed", "thu", "fri"],
    "duration": 30,
    "max_brightness": 100,
}


@pytest.fixture
def bulb(hass: HomeAssistant):
    """A virtual RGB bulb recording every light.turn_on call."""
    hass.states.async_set(
        "light.bedroom",
        "off",
        {"supported_color_modes": ["hs", "color_temp"], "supported_features": 32},
    )
    return async_mock_service(hass, "light", "turn_on")


async def setup_alarm(hass: HomeAssistant, **overrides) -> MockConfigEntry:
    """Add and set up a config entry."""
    await hass.config.async_set_time_zone("UTC")
    entry = MockConfigEntry(domain=DOMAIN, data={**CONFIG, **overrides}, title="Test")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_config_flow(hass: HomeAssistant):
    """The user step creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], CONFIG)
    assert result["type"] == "create_entry"
    assert result["title"] == "Bedroom Sunrise"
    # one wake time on a set of days is stored as a time per day
    assert result["data"]["schedule"] == dict.fromkeys(
        ["mon", "tue", "wed", "thu", "fri"], "07:30:00"
    )
    assert "wake_time" not in result["data"]


async def test_manual_sunrise_runs_to_full_brightness(
    hass: HomeAssistant, bulb, freezer
):
    """The start service runs a complete, monotonically brightening sunrise."""
    freezer.move_to("2026-09-07 03:00:00+00:00")  # Monday, nowhere near wake time
    await setup_alarm(hass)
    await hass.services.async_call(
        DOMAIN,
        "start",
        {"entity_id": "switch.bedroom_sunrise", "duration": 1},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert bulb, "sunrise should send an immediate first update"
    assert bulb[0].data["brightness_pct"] == 1
    assert bulb[0].data["rgb_color"] == [255, 20, 0]
    assert bulb[0].data["transition"] == 5

    for _ in range(13):  # 65 seconds of 5 second ticks
        freezer.tick(timedelta(seconds=5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    brightness = [call.data["brightness_pct"] for call in bulb]
    assert brightness == sorted(brightness)
    assert brightness[-1] == 100
    assert bulb[-1].data["rgb_color"] == [255, 225, 170]


async def test_resumes_at_the_right_progress_after_restart(hass, bulb, freezer):
    """Setting up mid-window jumps straight to the current progress."""
    freezer.move_to("2026-09-07 07:16:00+00:00")  # 16 of 30 minutes in
    await setup_alarm(hass)
    assert bulb
    expected = state_pct = bulb[0].data["brightness_pct"]
    assert 15 < expected < 30, f"unexpected brightness {state_pct}"
    attrs = hass.states.get("switch.bedroom_sunrise").attributes
    assert attrs["phase"] == "sunrise"
    assert 0.5 < attrs["progress"] < 0.56


async def test_disabled_alarm_does_nothing(hass, bulb, freezer):
    """A disarmed alarm sends no commands inside its window."""
    freezer.move_to("2026-09-07 07:16:00+00:00")
    await setup_alarm(hass, enabled=False)
    assert not bulb
    assert hass.states.get("switch.bedroom_sunrise").state == "off"


async def test_weekend_does_not_trigger(hass, bulb, freezer):
    """Saturday is not in the configured days."""
    freezer.move_to("2026-09-12 07:16:00+00:00")  # Saturday
    await setup_alarm(hass)
    assert not bulb


async def test_stop_turns_the_light_off(hass, bulb, freezer):
    """Stop cancels the sunrise for the rest of the window."""
    turn_off = async_mock_service(hass, "light", "turn_off")
    freezer.move_to("2026-09-07 07:16:00+00:00")
    await setup_alarm(hass)
    sent = len(bulb)
    await hass.services.async_call(
        DOMAIN, "stop", {"entity_id": "switch.bedroom_sunrise"}, blocking=True
    )
    await hass.async_block_till_done()
    assert turn_off
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(bulb) == sent


async def test_snooze_pauses_then_restarts(hass, bulb, freezer):
    """Snooze turns the light off and starts a short sunrise later."""
    async_mock_service(hass, "light", "turn_off")
    freezer.move_to("2026-09-07 07:16:00+00:00")
    await setup_alarm(hass)
    await hass.services.async_call(
        DOMAIN,
        "snooze",
        {"entity_id": "switch.bedroom_sunrise", "minutes": 1},
        blocking=True,
    )
    await hass.async_block_till_done()
    bulb.clear()
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert not bulb, "still snoozed"

    freezer.tick(timedelta(seconds=45))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert bulb, "sunrise restarts after the snooze"
    assert bulb[0].data["brightness_pct"] == 1


async def test_profile_choice_changes_the_colours(hass: HomeAssistant, bulb, freezer):
    """The configured profile is the curve that actually reaches the light."""
    entry = await setup_alarm(hass, profile="daylight")
    alarm = hass.data[DOMAIN][entry.entry_id]
    await alarm.async_start_sunrise(duration=1)
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    # halfway through "daylight" is far brighter than halfway through "philips"
    assert bulb[-1].data["brightness_pct"] >= 30


async def test_brightness_only_light_gets_no_colour(hass, freezer):
    """Lights without colour support only receive brightness."""
    hass.states.async_set(
        "light.plain", "off", {"supported_color_modes": ["brightness"]}
    )
    calls = async_mock_service(hass, "light", "turn_on")
    freezer.move_to("2026-09-07 07:16:00+00:00")
    await setup_alarm(hass, lights=["light.plain"])
    assert calls
    assert "rgb_color" not in calls[0].data
    assert "transition" not in calls[0].data  # light does not support transitions
    assert calls[0].data["brightness_pct"] > 1


async def test_unavailable_light_is_skipped(hass, freezer):
    """A missing entity does not blow up the tick."""
    calls = async_mock_service(hass, "light", "turn_on")
    freezer.move_to("2026-09-07 07:16:00+00:00")
    await setup_alarm(hass, lights=["light.gone"])
    assert not calls
    assert hass.states.get("switch.bedroom_sunrise").attributes["phase"] == "sunrise"


async def test_test_button_starts_sunrise(hass: HomeAssistant, bulb, freezer):
    """Pressing the test button runs a one minute sunrise."""
    freezer.move_to("2024-01-01 03:00:00+00:00")  # a Monday, far from wake time
    await setup_alarm(hass)
    assert not bulb

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.bedroom_sunrise_test_sunrise_1_min"},
        blocking=True,
    )
    assert bulb, "button press should have driven the light"

    freezer.tick(timedelta(minutes=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert bulb[-1].data["brightness_pct"] == 100


async def test_snooze_button_uses_the_configured_minutes(hass, bulb, freezer):
    """Pressing the snooze button delays the sunrise by the configured time."""
    async_mock_service(hass, "light", "turn_off")
    freezer.move_to("2026-09-07 07:16:00+00:00")
    await setup_alarm(hass, snooze_minutes=2)
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.bedroom_sunrise_snooze_2_min"},
        blocking=True,
    )
    await hass.async_block_till_done()
    bulb.clear()
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert not bulb, "still snoozed after one of two minutes"

    freezer.tick(timedelta(minutes=1, seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert bulb, "sunrise restarts once the snooze elapses"


async def test_lights_switch_off_after_the_extra_time(hass, bulb, freezer):
    """The lights stay on for the configured extra time, then go off."""
    turn_off = async_mock_service(hass, "light", "turn_off")
    freezer.move_to("2026-09-07 07:29:00+00:00")  # one minute of sunrise left
    await setup_alarm(hass, hold_minutes=2)
    freezer.tick(timedelta(minutes=1, seconds=5))  # sunrise finishes
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert bulb[-1].data["brightness_pct"] == 100
    assert not turn_off, "lights stay on during the extra time"

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert not turn_off, "still within the extra time"

    freezer.tick(timedelta(minutes=1, seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert turn_off, "lights go off once the extra time is over"


async def test_set_days_service_reschedules(hass: HomeAssistant, bulb, freezer):
    """set_days keeps working, moving each day's time onto the new days."""
    freezer.move_to("2026-09-07 03:00:00+00:00")  # Monday
    entry = await setup_alarm(hass)
    assert hass.states.get("switch.bedroom_sunrise").attributes["days"] == [
        "mon",
        "tue",
        "wed",
        "thu",
        "fri",
    ]

    await hass.services.async_call(
        DOMAIN,
        "set_days",
        {"entity_id": "switch.bedroom_sunrise", "days": ["sat", "sun"]},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert entry.options["schedule"] == {"sat": "07:30:00", "sun": "07:30:00"}
    state = hass.states.get("switch.bedroom_sunrise")
    assert state.attributes["days"] == ["sat", "sun"]
    assert state.attributes["next_sunrise_start"].weekday() == 5, "next is Saturday"


async def test_set_schedule_service_gives_each_day_its_own_time(hass, bulb, freezer):
    """The card's time slots call set_schedule, which persists and reschedules."""
    freezer.move_to("2026-09-11 12:00:00+00:00")  # Friday lunchtime
    entry = await setup_alarm(hass)

    await hass.services.async_call(
        DOMAIN,
        "set_schedule",
        {
            "entity_id": "switch.bedroom_sunrise",
            "schedule": {"fri": "07:00:00", "sat": "09:30:00"},
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert entry.options["schedule"] == {"fri": "07:00:00", "sat": "09:30:00"}
    state = hass.states.get("switch.bedroom_sunrise")
    assert state.attributes["schedule"] == {"fri": "07:00:00", "sat": "09:30:00"}
    assert state.attributes["days"] == ["fri", "sat"]
    # Friday 07:00 is gone; the next sunrise is Saturday's, 30 min before 09:30.
    start = state.attributes["next_sunrise_start"]
    assert (start.weekday(), start.hour, start.minute) == (5, 9, 0)


async def test_old_wake_time_config_still_runs(hass: HomeAssistant, bulb, freezer):
    """An entry saved before per-day times keeps its single wake time."""
    freezer.move_to("2026-09-07 07:16:00+00:00")  # Monday, mid-window
    entry = await setup_alarm(hass)  # CONFIG is the pre-schedule shape
    assert "schedule" not in entry.data
    assert bulb, "the migrated schedule still drives the lights"
    state = hass.states.get("switch.bedroom_sunrise")
    assert state.attributes["schedule"] == dict.fromkeys(
        ["mon", "tue", "wed", "thu", "fri"], "07:30:00"
    )


async def test_options_flow_keeps_the_schedule(hass: HomeAssistant, bulb):
    """Editing the lights or the profile must not wipe the card's schedule."""
    entry = await setup_alarm(hass, schedule={"sat": "09:30:00"})
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert "wake_time" not in result["data_schema"].schema, "the card owns the times"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "lights": ["light.bedroom"],
            "duration": 45,
            "max_brightness": 80,
            "hold_minutes": 0,
            "snooze_minutes": 9,
            "profile": "gentle",
        },
    )
    await hass.async_block_till_done()
    assert result["data"]["schedule"] == {"sat": "09:30:00"}
    assert entry.options["schedule"] == {"sat": "09:30:00"}


async def test_card_is_served_and_auto_loaded(hass: HomeAssistant, bulb):
    """Setup registers the Lovelace card so users add no dashboard resource."""
    from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL, UrlManager
    from homeassistant.setup import async_setup_component

    from custom_components.sunrise_alarm import CARD_FILE, CARD_URL

    # The real `frontend` component needs the compiled hass_frontend package,
    # which isn't installed here: bring up http and the URL store it would make.
    assert await async_setup_component(hass, "http", {})
    hass.data[DATA_EXTRA_MODULE_URL] = UrlManager(lambda *args: None, [])

    assert CARD_FILE.is_file(), "the card bundle ships with the integration"
    await setup_alarm(hass)

    urls = hass.data[DATA_EXTRA_MODULE_URL].urls
    assert any(url.startswith(CARD_URL) for url in urls), urls
