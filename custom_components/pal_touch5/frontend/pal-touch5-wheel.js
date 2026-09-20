/* App-wheel dashboard card for the PAL TOUCH-5 integration.
 * No controller address, token, or other private data belongs in this file.
 */
class PalTouch5WheelCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.shadowRoot.innerHTML = `
      <style>
        ha-card { padding: 12px 14px; }
        .summary { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
        .title { display: flex; flex-direction: column; min-width: 0; }
        .title strong { font-size: .95rem; }
        .state, .note { color: var(--secondary-text-color); font-size: .8rem; }
        .actions { display: flex; gap: 8px; flex-shrink: 0; }
        button {
          background: var(--primary-color); border: 0; border-radius: 8px;
          color: white; padding: 8px 12px; cursor: pointer; font: inherit;
        }
        button:disabled { opacity: .5; cursor: default; }
        .error { color: var(--error-color, #db4437); font-size: .8rem; }
        .error:empty { display: none; }
        dialog {
          box-sizing: border-box; width: min(350px, calc(100vw - 32px));
          padding: 20px; border: 0; border-radius: 16px;
          color: var(--primary-text-color); background: var(--card-background-color, #fff);
          box-shadow: 0 8px 32px #0005; text-align: center;
        }
        dialog::backdrop { background: #0009; }
        .dialog-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
        h2 { font-size: 1.15rem; margin: 0; }
        .close { background: transparent; color: var(--primary-text-color); padding: 5px 8px; }
        .wheel {
          position: relative; width: 220px; height: 220px; margin: auto;
          border-radius: 50%; touch-action: none; cursor: crosshair;
          background: conic-gradient(#1852c5 0deg, #00bfc4 60deg,
            #15b545 120deg, #f5d300 180deg, #df2033 240deg,
            #9628c5 300deg, #1852c5 360deg);
        }
        .wheel::after {
          content: ""; position: absolute; inset: 43px; border-radius: 50%;
          background: var(--card-background-color, #fff);
        }
        .marker {
          position: absolute; width: 16px; height: 16px; z-index: 1;
          border: 3px solid white; border-radius: 50%; box-sizing: border-box;
          box-shadow: 0 0 3px #333; transform: translate(-50%, -50%);
          display: none; pointer-events: none;
        }
        .readout { margin: 14px 0 6px; font-weight: 600; }
      </style>
      <ha-card>
        <div class="summary">
          <div class="title"><strong>Pool/spa lights</strong><span class="state">Unknown</span></div>
          <div class="actions"><button class="power" type="button">Turn on</button>
            <button class="color" type="button">Color</button></div>
        </div>
        <div class="error" role="status"></div>
      </ha-card>
      <dialog aria-label="Pool/spa light color wheel">
        <div class="dialog-head"><h2>Color wheel</h2>
          <button class="close" type="button" aria-label="Close color wheel">Close</button></div>
        <div class="wheel" role="slider" tabindex="0" aria-label="PAL wheel position"
             aria-valuemin="0" aria-valuemax="359">
          <div class="marker"></div>
        </div>
        <div class="readout">Choose a wheel position</div>
        <div class="note">Six app-captured anchors · last command, not measured state</div>
      </dialog>`;
    this._wheel = this.shadowRoot.querySelector(".wheel");
    this._dialog = this.shadowRoot.querySelector("dialog");
    this._wheel.addEventListener("pointerdown", (event) => this._start(event));
    this._wheel.addEventListener("pointermove", (event) => this._move(event));
    this._wheel.addEventListener("pointerup", (event) => this._end(event));
    this._wheel.addEventListener("pointercancel", () => this._cancel());
    this._wheel.addEventListener("keydown", (event) => this._key(event));
    this.shadowRoot.querySelector(".power").addEventListener("click", () => this._power());
    this.shadowRoot.querySelector(".color").addEventListener("click", () => this._dialog.showModal());
    this.shadowRoot.querySelector(".close").addEventListener("click", () => this._dialog.close());
    this._dialog.addEventListener("click", (event) => {
      if (event.target === this._dialog) this._dialog.close();
    });
  }

  setConfig(config) {
    if (!config.entity?.startsWith("number.")) {
      throw new Error("PAL wheel requires its wheel-position number entity");
    }
    if (config.light && !config.light.startsWith("light.")) {
      throw new Error("PAL wheel light must be a light entity");
    }
    this._config = config;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() { return 1; }

  _hueFromPoint(event) {
    const box = this._wheel.getBoundingClientRect();
    const dx = event.clientX - box.left - box.width / 2;
    const dy = event.clientY - box.top - box.height / 2;
    return Math.round((Math.atan2(dx, -dy) * 180 / Math.PI + 360) % 360) % 360;
  }

  _currentHue() {
    const state = this._hass?.states[this._config?.entity]?.state;
    const value = Number(state);
    return state != null && state !== "unknown" && state !== "unavailable" &&
      Number.isFinite(value) ? value : null;
  }

  _start(event) {
    if (!this._hass || !this._config || this._busy) return;
    event.preventDefault();
    this._dragging = true;
    this._wheel.setPointerCapture(event.pointerId);
    this._preview = this._hueFromPoint(event);
    this._render();
  }

  _move(event) {
    if (!this._dragging) return;
    this._preview = this._hueFromPoint(event);
    this._render();
  }

  _end(event) {
    if (!this._dragging) return;
    this._preview = this._hueFromPoint(event);
    this._dragging = false;
    this._sendHue(this._preview);
  }

  _cancel() {
    this._dragging = false;
    this._preview = null;
    this._render();
  }

  _key(event) {
    if (!["ArrowLeft", "ArrowDown", "ArrowRight", "ArrowUp", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const current = this._currentHue() ?? 0;
    const hue = event.key === "Home" ? 0 : event.key === "End" ? 359 :
      (current + (["ArrowRight", "ArrowUp"].includes(event.key) ? 1 : 359)) % 360;
    this._sendHue(hue);
  }

  async _sendHue(hue) {
    if (this._busy || !this._hass || !this._config) return;
    this._busy = true;
    this._render();
    try {
      await this._hass.callService("number", "set_value", {
        entity_id: this._config.entity, value: hue,
      });
      this._error = "";
    } catch (error) {
      this._error = `Color command failed: ${error.message || error}`;
    } finally {
      this._busy = false;
      this._preview = null;
      this._render();
    }
  }

  async _power() {
    if (this._busy || !this._hass || !this._config?.light) return;
    const on = this._hass.states[this._config.light]?.state !== "on";
    this._busy = true;
    this._render();
    try {
      await this._hass.callService("light", on ? "turn_on" : "turn_off", {
        entity_id: this._config.light,
      });
      this._error = "";
    } catch (error) {
      this._error = `Light command failed: ${error.message || error}`;
    } finally {
      this._busy = false;
      this._render();
    }
  }

  _render() {
    const hue = this._preview ?? this._currentHue();
    const marker = this.shadowRoot.querySelector(".marker");
    marker.style.display = hue == null ? "none" : "block";
    if (hue != null) {
      const radians = hue * Math.PI / 180;
      marker.style.left = `${110 + 88 * Math.sin(radians)}px`;
      marker.style.top = `${110 - 88 * Math.cos(radians)}px`;
      this._wheel.setAttribute("aria-valuenow", String(hue));
    } else {
      this._wheel.removeAttribute("aria-valuenow");
    }
    this.shadowRoot.querySelector(".readout").textContent =
      hue == null ? "Choose a wheel position" : `${hue}° on PAL wheel`;
    const lightState = this._hass?.states[this._config?.light]?.state;
    this.shadowRoot.querySelector(".state").textContent =
      lightState === "on" ? "On · assumed" :
      lightState === "off" ? "Off · assumed" : "Unknown state";
    const power = this.shadowRoot.querySelector(".power");
    power.textContent = lightState === "on" ? "Turn off" : "Turn on";
    power.setAttribute("aria-pressed", lightState === "on" ? "true" : "false");
    power.disabled = this._busy || !this._hass || !this._config?.light ||
      lightState === "unavailable";
    this.shadowRoot.querySelector(".color").disabled = this._busy || !this._hass;
    this.shadowRoot.querySelector(".error").textContent = this._error || "";
  }
}

customElements.define("pal-touch5-wheel-card", PalTouch5WheelCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "pal-touch5-wheel-card",
  name: "PAL TOUCH-5 color wheel",
  description: "Compact power toggle with a color-wheel dialog",
});
