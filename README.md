# Sunrise Alarm

Home Assistant custom integration that turns any `light` entities into a
Philips-style wake-up light: a gradual sunrise of brightness and colour that
finishes at your wake-up time.

## Install

Copy `custom_components/sunrise_alarm` into `/config/custom_components/`,
restart Home Assistant, then **Settings → Devices & services → Add integration
→ Sunrise Alarm**. No HACS needed.

ZIP for copying to another machine:

```bash
(cd custom_components && zip -r ../sunrise_alarm.zip sunrise_alarm -x '*__pycache__*')
```

## Use

The integration creates one switch per alarm, e.g. `switch.bedroom_sunrise`:
**on = armed**. Attributes expose `phase`, `progress`, `remaining`,
`next_sunrise_start` and `next_wake`.

Three buttons run a sunrise by hand, no automation needed:

| Button | Effect |
| --- | --- |
| `button.<name>_test_sunrise_1_min` | One minute sunrise — for testing the bulb |
| `button.<name>_run_sunrise_now` | Sunrise at the configured duration |
| `button.<name>_stop_sunrise` | Stops it, lights off, alarm stays armed |

## Dashboard card

All entities share one device, so **Settings → Devices & services → Sunrise
Alarm → the device → Add to dashboard** builds a card for you. For the
countdown, paste this into a manual card instead (swap the entity ids if your
alarm is named differently):

```yaml
type: vertical-stack
cards:
  - type: markdown
    content: >-
      {% set s = states.switch.sunrise_alarm %} ## ☀️ {{ s.name }}

      Alarm at **{{ s.attributes.wake_time[:5] }}** — {{ 'enabled' if
      is_state('switch.sunrise_alarm', 'on') else 'disabled' }}

      {% if s.attributes.phase == 'sunrise' %} Sunrise running, **{{
      s.attributes.remaining }}** to go ({{ (s.attributes.progress * 100) |
      round }}%) {% elif s.attributes.next_sunrise_start %} Sunrise starts **{{
      s.attributes.next_sunrise_start | as_timestamp | timestamp_custom('%a
      %H:%M') }}**, in {{ s.attributes.starts_in }} {% endif %}
  - type: entities
    entities:
      - entity: switch.sunrise_alarm
        name: Armed
      - button.sunrise_alarm_test_sunrise_1_min
      - button.sunrise_alarm_run_sunrise_now
      - button.sunrise_alarm_stop_sunrise
```

The switch attributes behind it: `phase`, `progress`, `remaining`,
`wake_time`, `next_sunrise_start`, `next_wake`, `starts_in`.

Services (target the switch):

| Service | Fields | Effect |
| --- | --- | --- |
| `sunrise_alarm.start` | `duration` (minutes, optional) | Runs a sunrise now — use a short duration to test |
| `sunrise_alarm.stop` | — | Stops it and turns the lights off |
| `sunrise_alarm.snooze` | `minutes` (default 9) | Lights off, then a 5 minute sunrise again |

Testing with the real bulb:

```yaml
action: sunrise_alarm.start
target:
  entity_id: switch.bedroom_sunrise
data:
  duration: 1
```

The desired light state is computed from the clock every 5 seconds, so a
restart mid-sunrise resumes at the right progress and a missed tick fixes
itself.

## Profiles

Pick one in the config flow (and change it later under *Configure*):

| Profile | Shape |
| --- | --- |
| `philips` | Dim and red for a long time, strong surge at the end |
| `gentle` | Smooth ramp, no last-minute surge, warm to the end |
| `daylight` | Usable light early, ends near white — for dark mornings |

## Tuning the curve

A profile is just a list of control points in
`custom_components/sunrise_alarm/sunrise.py`. Edit them, or add a profile to
`PROFILES` and a label to `_PROFILE_LABELS` in `config_flow.py`, then look
before touching the bulb:

```bash
uv run python scripts/simulate_sunrise.py --duration 30 --profile gentle
```

## Development

```bash
uv sync            # installs homeassistant + pytest + ruff
uv run pytest
uv run ruff check .
```

Local Home Assistant with the integration mounted:

```bash
mkdir -p config/custom_components
ln -s ../../custom_components/sunrise_alarm config/custom_components/sunrise_alarm
docker run --rm -p 8123:8123 -v "$PWD/config:/config" \
  ghcr.io/home-assistant/home-assistant:stable
```

Then open http://localhost:8123. A `light.*` demo entity can be added with the
`demo` integration or a `template` light.

Hassfest validation:

```bash
docker run --rm -v "$PWD:/github/workspace" ghcr.io/home-assistant/hassfest:latest
```
