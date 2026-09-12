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
const NEW_DAY_TIME = "07:30:00"; // used when a day is switched on and nothing else is

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

/** Compare two schedules ignoring key order and seconds. */
const key = (s) =>
  DAYS.filter((d) => s && s[d])
    .map((d) => `${d}${s[d].slice(0, 5)}`)
    .join();

const STYLE = `
  ha-card { --sa-sun: #ffb53d; padding: 16px; }
  .head { display: flex; align-items: center; gap: 12px; }
  .head ha-icon { --mdc-icon-size: 30px; }
  .title { flex: 1; font-size: 1.05em; font-weight: 500; cursor: pointer; }

  .hero { display: flex; align-items: baseline; gap: 14px; margin: 12px 0 2px; }
  .time { font-size: 2.6em; font-weight: 300; line-height: 1; letter-spacing: -0.02em; }
  .when { color: var(--secondary-text-color); font-size: 0.8em; margin-top: 4px; }
  .meta { flex: 1; text-align: right; color: var(--secondary-text-color); }
  .status { color: var(--primary-text-color); font-size: 0.95em; }
  .legend { font-size: 0.75em; margin-top: 4px; }

  .bar { height: 4px; border-radius: 2px; background: var(--divider-color); margin: 12px 0 0; overflow: hidden; }
  .bar > div { height: 100%; background: linear-gradient(90deg, #e2693c, var(--sa-sun)); transition: width 1s linear; }

  .week { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; margin: 16px 0 2px; }
  .week.off { opacity: 0.45; }
  .col { display: flex; flex-direction: column; align-items: center; gap: 5px; min-width: 0; }
  .chip {
    width: 100%; max-width: 34px; aspect-ratio: 1;
    display: flex; align-items: center; justify-content: center;
    border: 1px solid var(--divider-color); border-radius: 50%;
    background: none; color: var(--secondary-text-color);
    font: inherit; font-size: 0.85em; font-weight: 500; cursor: pointer;
    transition: background 0.15s, color 0.15s;
  }
  .chip:hover { border-color: var(--sa-sun); }
  .col.on .chip { background: var(--sa-sun); border-color: var(--sa-sun); color: #2b1b0a; }
  .col.today .chip { box-shadow: 0 0 0 2px var(--primary-text-color); }
  .slot {
    position: relative; width: 100%; padding: 2px 0; border-radius: 6px;
    text-align: center; cursor: pointer; font-size: 0.7em;
    font-variant-numeric: tabular-nums; color: var(--secondary-text-color);
  }
  .slot:hover { background: var(--secondary-background-color); }
  .col.next .slot { color: var(--sa-sun); font-weight: 600; }
  /* The native time picker, anchored over the slot it edits but invisible:
     the slot draws the time itself, compactly and in the user's format. */
  .picker { position: absolute; inset: 0; width: 100%; opacity: 0; border: 0; padding: 0; }

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
      (id) => id.startsWith("switch.") && hass.states[id].attributes.schedule !== undefined,
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
    this._pending = null; // schedule shown until the entity catches up
    this._editing = null; // day whose time picker is open
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
    if (this._pending && key(state.attributes.schedule) === key(this._pending)) {
      this._pending = null;
    }
    if (this._editing === null) this._render(); // never yank an open picker away
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
    if (this._editing === null) this._render();
  }

  /** Week starting on the day the user's HA locale starts on. */
  _week() {
    const first = (this._hass.locale || {}).first_weekday; // "monday", "sunday", "language"
    const offset = DAYS.findIndex((d) => first && first.startsWith(d));
    return offset <= 0 ? DAYS : [...DAYS.slice(offset), ...DAYS.slice(0, offset)];
  }

  /** The schedule to draw: the optimistic one while a change is in flight. */
  _schedule() {
    return this._pending || this._state.attributes.schedule || {};
  }

  /** HA's hour format: "12"/"24" say outright, "language"/"system" imply it. */
  _h12() {
    const format = (this._hass.locale || {}).time_format;
    if (format === "12") return true;
    if (format === "24") return false;
    const options = new Intl.DateTimeFormat(this._language(), { hour: "numeric" });
    return options.resolvedOptions().hour12 === true;
  }

  /** "07:00:00" -> "07:00" / "7:00 AM", or the compact "7:00a" for the week. */
  _fmt(value, compact) {
    const [h, m] = value.split(":").map(Number);
    const minute = String(m).padStart(2, "0");
    if (!this._h12()) return `${String(h).padStart(2, "0")}:${minute}`;
    const hour = h % 12 || 12;
    return compact ? `${hour}:${minute}${h < 12 ? "a" : "p"}` : `${hour}:${minute} ${h < 12 ? "AM" : "PM"}`;
  }

  /** The language HA formats in: its own, the browser's, or unset for "system". */
  _language() {
    const locale = this._hass.locale || {};
    return locale.time_format === "system" ? undefined : locale.language || undefined;
  }

  /** "today" / "tomorrow" / "Saturday" for an ISO timestamp. */
  _when(iso) {
    const midnight = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
    const date = new Date(iso);
    const days = Math.round((midnight(date) - midnight(new Date())) / 86400000);
    if (days === 0) return "today";
    if (days === 1) return "tomorrow";
    return date.toLocaleDateString(this._language(), { weekday: "long" });
  }

  _render() {
    const state = this._state;
    const a = state.attributes;
    const phase = PHASES[a.phase] || PHASES.armed;
    const schedule = this._schedule();
    const today = DAYS[(new Date().getDay() + 6) % 7];
    const next = a.next_wake ? DAYS[(new Date(a.next_wake).getDay() + 6) % 7] : null;

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
      <div class="hero">
        <div>
          <div class="time">${a.next_wake ? this._fmt(a.next_wake.slice(11, 16), false) : "—"}</div>
          <div class="when">${a.next_wake ? this._when(a.next_wake) : "no sunrise due"}</div>
        </div>
        <div class="meta">
          <div class="status">${this._status(state)}</div>
          <div class="legend">${a.duration}-min sunrise</div>
        </div>
      </div>
      ${
        a.phase === "sunrise"
          ? `<div class="bar"><div style="width:${Math.round((a.progress || 0) * 100)}%"></div></div>`
          : ""
      }
      <div class="week${state.state === "on" ? "" : " off"}">
        ${this._week()
          .map((d) => {
            const classes = [schedule[d] && "on", d === today && "today", d === next && "next"];
            return `
              <div class="col ${classes.filter(Boolean).join(" ")}">
                <button class="chip" data-day="${d}" title="${d}">${DAY_LETTER[d]}</button>
                <div class="slot" data-day="${d}" title="Set the time for ${d}">${
                  schedule[d] ? this._fmt(schedule[d], true) : "–"
                }</div>
              </div>`;
          })
          .join("")}
      </div>
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
    for (const chip of this._root.querySelectorAll(".chip")) {
      chip.addEventListener("click", () => this._toggleDay(chip.dataset.day));
    }
    for (const slot of this._root.querySelectorAll(".slot")) {
      slot.addEventListener("click", () => this._editTime(slot.dataset.day, slot));
    }
    for (const button of this._root.querySelectorAll(".buttons button")) {
      button.addEventListener("click", () =>
        this._hass.callService("button", "press", {
          entity_id: this._buttons[button.dataset.key],
        }),
      );
    }
  }

  /** Turn a day on (reusing another day's time) or off. */
  _toggleDay(day) {
    const schedule = { ...this._schedule() };
    if (schedule[day]) delete schedule[day];
    else schedule[day] = Object.values(schedule)[0] || NEW_DAY_TIME;
    this._save(schedule);
  }

  /** Open the native time picker over the slot; picking also enables the day. */
  _editTime(day, slot) {
    if (!this._picker) {
      this._picker = document.createElement("input");
      this._picker.type = "time";
      this._picker.className = "picker";
      this._picker.addEventListener("change", () => {
        const value = this._picker.value;
        this._close();
        if (value) {
          this._save({ ...this._schedule(), [this._edited]: `${value}:00` });
        }
      });
      // Dismissing the picker, or tapping elsewhere, ends the edit.
      this._picker.addEventListener("cancel", () => this._close());
      this._picker.addEventListener("blur", () => this._close());
    }
    // A time input renders in its element locale, so name one that matches HA's
    // hour format instead of letting the browser's own setting win.
    // ponytail: Chromium and Safari honour `lang` here, Firefox uses the OS.
    this._picker.lang = this._h12() ? "en-US" : "en-GB";
    this._editing = day;
    this._edited = day;
    this._picker.value = (this._schedule()[day] || NEW_DAY_TIME).slice(0, 5);
    slot.appendChild(this._picker);
    this._picker.focus();
    if (this._picker.showPicker) {
      try {
        this._picker.showPicker();
      } catch {
        /* not allowed here: the focused input still takes a typed time */
      }
    }
  }

  _close() {
    if (this._editing === null) return;
    this._editing = null;
    this._picker.remove();
    this._render();
  }

  /** Send the schedule, showing it straight away: the entry reload takes a moment. */
  _save(schedule) {
    this._pending = schedule;
    this._render();
    this._hass.callService("sunrise_alarm", "set_schedule", {
      entity_id: this._config.entity,
      schedule,
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
  description: "Wake-up light: a wake time per day, countdown, progress and manual buttons.",
  documentationURL: "https://github.com/sibizaestruch/sunrise-alarm",
  preview: true,
});
