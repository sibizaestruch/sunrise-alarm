/**
 * Lovelace card for the Sunrise Alarm integration.
 *
 * Plain custom element, no build step: everything it renders comes from the
 * switch entity's attributes, and the buttons are resolved from the entity
 * registry by device, so the config is just the switch.
 *
 *   type: custom:sunrise-alarm-card
 *   entity: switch.sunrise_alarm
 */

const DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
const DAY_LETTER = { mon: "M", tue: "T", wed: "W", thu: "T", fri: "F", sat: "S", sun: "S" };

const BUTTONS = [
  { key: "test", icon: "mdi:test-tube", label: "Test" },
  { key: "run", icon: "mdi:weather-sunset-up", label: "Run" },
  { key: "snooze", icon: "mdi:alarm-snooze", label: "Snooze" },
  { key: "stop", icon: "mdi:stop", label: "Stop" },
];

const PHASES = {
  sunrise: { icon: "mdi:weather-sunset-up", color: "var(--sa-sun)" },
  snoozed: { icon: "mdi:alarm-snooze", color: "var(--secondary-text-color)" },
  armed: { icon: "mdi:alarm", color: "var(--sa-sun)" },
  disabled: { icon: "mdi:alarm-off", color: "var(--secondary-text-color)" },
};

const STYLE = `
  ha-card { --sa-sun: #ffb53d; padding: 16px; }
  .head { display: flex; align-items: center; gap: 12px; }
  .head ha-icon { --mdc-icon-size: 30px; }
  .title { flex: 1; font-size: 1.05em; font-weight: 500; cursor: pointer; }
  .clock { display: flex; align-items: baseline; gap: 12px; margin: 10px 0 2px; }
  .time { font-size: 2.6em; font-weight: 300; line-height: 1; letter-spacing: -0.02em; }
  .status { flex: 1; color: var(--secondary-text-color); font-size: 0.95em; }
  .bar { height: 4px; border-radius: 2px; background: var(--divider-color); margin: 12px 0 0; overflow: hidden; }
  .bar > div { height: 100%; background: linear-gradient(90deg, #e2693c, var(--sa-sun)); transition: width 1s linear; }

  .week { display: flex; justify-content: space-between; gap: 6px; margin: 18px 0 12px; }
  .day {
    flex: 1; position: relative; aspect-ratio: 1; max-width: 40px;
    display: flex; align-items: center; justify-content: center;
    border: 1px solid var(--divider-color); border-radius: 50%;
    background: none; color: var(--secondary-text-color);
    font: inherit; font-size: 0.85em; font-weight: 500; cursor: pointer;
    transition: background 0.15s, color 0.15s;
  }
  .day:hover { border-color: var(--sa-sun); }
  .day.on { background: var(--sa-sun); border-color: var(--sa-sun); color: #2b1b0a; }
  .day.today { border-color: var(--primary-text-color); }
  .day.next::after {
    content: ""; position: absolute; bottom: -8px; left: 50%; transform: translateX(-50%);
    width: 5px; height: 5px; border-radius: 50%; background: var(--sa-sun);
  }
  .legend { color: var(--secondary-text-color); font-size: 0.75em; margin-top: 10px; }

  .buttons { display: flex; gap: 8px; margin-top: 14px; }
  .buttons button {
    flex: 1; display: flex; flex-direction: column; align-items: center; gap: 3px;
    padding: 8px 4px; border: none; border-radius: 12px; cursor: pointer;
    font: inherit; font-size: 0.75em;
    background: var(--secondary-background-color); color: var(--primary-text-color);
  }
  .buttons button:hover:not([disabled]) { background: var(--divider-color); }
  .buttons button[disabled] { opacity: 0.4; cursor: default; }
  .buttons ha-icon { --mdc-icon-size: 20px; }
`;

class SunriseAlarmCard extends HTMLElement {
  static getStubConfig(hass) {
    const entity = Object.keys(hass.states).find(
      (id) =>
        id.startsWith("switch.") && hass.states[id].attributes.next_sunrise_start !== undefined,
    );
    return { entity: entity || "switch.sunrise_alarm" };
  }

  setConfig(config) {
    if (!config.entity || !config.entity.startsWith("switch.")) {
      throw new Error("sunrise-alarm-card: `entity` must be the alarm's switch");
    }
    this._config = config;
    this._buttons = null;
    this._root = null;
    this.innerHTML = "";
  }

  getCardSize() {
    return 4;
  }

  set hass(hass) {
    this._hass = hass;
    const state = hass.states[this._config.entity];
    if (!state) {
      this.innerHTML = `<ha-card style="padding:16px">Entity ${this._config.entity} not found</ha-card>`;
      return;
    }
    if (state === this._state) return; // hass changes on every state in the system
    this._state = state;
    this._render();
    if (this._buttons === null) this._resolveButtons();
  }

  /** Map button key -> entity_id via the entity registry, matched on device. */
  async _resolveButtons() {
    this._buttons = {};
    const registry = await this._hass.callWS({ type: "config/entity_registry/list" });
    const self = registry.find((e) => e.entity_id === this._config.entity);
    if (!self) return;
    for (const entry of registry) {
      if (entry.device_id !== self.device_id || !entry.entity_id.startsWith("button.")) continue;
      // unique_id is `<config entry id>_<key>`; the key is what the card acts on
      this._buttons[entry.unique_id.split("_").pop()] = entry.entity_id;
    }
    this._render();
  }

  /** Week starting on the day the user's HA locale starts on. */
  _week() {
    const first = (this._hass.locale || {}).first_weekday; // "monday", "sunday", "language"
    const offset = DAYS.findIndex((d) => first && first.startsWith(d));
    return offset <= 0 ? DAYS : [...DAYS.slice(offset), ...DAYS.slice(0, offset)];
  }

  _render() {
    const state = this._state;
    const a = state.attributes;
    const phase = PHASES[a.phase] || PHASES.armed;
    const active = new Set(a.days || []);
    const today = DAYS[(new Date().getDay() + 6) % 7];
    const next = a.next_sunrise_start ? DAYS[(new Date(a.next_sunrise_start).getDay() + 6) % 7] : null;

    if (!this._root) {
      this.innerHTML = `<style>${STYLE}</style><ha-card></ha-card>`;
      this._root = this.querySelector("ha-card");
    }
    this._root.innerHTML = `
      <div class="head">
        <ha-icon icon="${phase.icon}" style="color:${phase.color}"></ha-icon>
        <span class="title">${a.friendly_name || "Sunrise Alarm"}</span>
        <ha-switch ${state.state === "on" ? "checked" : ""}></ha-switch>
      </div>
      <div class="clock">
        <span class="time">${(a.wake_time || "").slice(0, 5)}</span>
        <span class="status">${this._status(state)}</span>
      </div>
      ${
        a.phase === "sunrise"
          ? `<div class="bar"><div style="width:${Math.round((a.progress || 0) * 100)}%"></div></div>`
          : ""
      }
      <div class="week">
        ${this._week()
          .map(
            (d) => `<button class="day${active.has(d) ? " on" : ""}${d === today ? " today" : ""}${
              d === next ? " next" : ""
            }" data-day="${d}" title="${d}">${DAY_LETTER[d]}</button>`,
          )
          .join("")}
      </div>
      <div class="legend">${a.duration}-min sunrise · ${a.profile} profile</div>
      <div class="buttons">
        ${BUTTONS.map(
          (b) => `
          <button data-key="${b.key}" ${this._buttons && this._buttons[b.key] ? "" : "disabled"}>
            <ha-icon icon="${b.icon}"></ha-icon>${b.label}
          </button>`,
        ).join("")}
      </div>`;

    this._root.querySelector(".title").addEventListener("click", () => {
      this.dispatchEvent(
        new CustomEvent("hass-more-info", {
          bubbles: true,
          composed: true,
          detail: { entityId: this._config.entity },
        }),
      );
    });
    this._root.querySelector("ha-switch").addEventListener("change", (ev) =>
      this._hass.callService("switch", ev.target.checked ? "turn_on" : "turn_off", {
        entity_id: this._config.entity,
      }),
    );
    for (const chip of this._root.querySelectorAll(".day")) {
      chip.addEventListener("click", () => this._toggleDay(chip.dataset.day));
    }
    for (const button of this._root.querySelectorAll(".buttons button")) {
      button.addEventListener("click", () =>
        this._hass.callService("button", "press", {
          entity_id: this._buttons[button.dataset.key],
        }),
      );
    }
  }

  _toggleDay(day) {
    const active = new Set(this._state.attributes.days || []);
    active.has(day) ? active.delete(day) : active.add(day);
    // Optimistic: reloading the config entry takes a moment to reach the state.
    this._root.querySelector(`.day[data-day="${day}"]`).classList.toggle("on", active.has(day));
    this._hass.callService("sunrise_alarm", "set_days", {
      entity_id: this._config.entity,
      days: DAYS.filter((d) => active.has(d)),
    });
  }

  _status(state) {
    const a = state.attributes;
    if (a.phase === "sunrise") return `Sunrise running — ${a.remaining} to go`;
    if (a.phase === "disabled") return "Alarm off";
    if (a.phase === "snoozed") return `Snoozed — sunrise in ${a.starts_in}`;
    if (!(a.days || []).length) return "No days selected";
    return a.starts_in ? `Sunrise in ${a.starts_in}` : "Armed";
  }
}

// Home Assistant boots a scoped custom element registry that REPLACES
// window.customElements. This module is small and wins the race against the
// app bundle, so defining right here lands in the native registry and HA's
// later customElements.get() returns undefined ("Custom element not found").
// Wait for HA's own element, which only exists once its registry is in place.
(function register() {
  if (!customElements.get("home-assistant")) {
    setTimeout(register, 100);
    return;
  }
  customElements.define("sunrise-alarm-card", SunriseAlarmCard);
})();

window.customCards = window.customCards || [];
window.customCards.push({
  type: "sunrise-alarm-card",
  name: "Sunrise Alarm",
  description: "Wake-up light: week schedule, countdown, progress and manual buttons.",
  documentationURL: "https://github.com/sibizaestruch/sunrise-alarm",
  preview: true,
});
