// The process drawing below the tabs. The service draws it for a run at an output time;
// the slider chooses the time, which also sets the key figures and the drum profiles.

import { useEffect, useState } from "preact/hooks";
import { enc, fetchText } from "../api.js";
import { html } from "../html.js";
import { lang, t } from "../i18n.js";
import { fmtHours } from "../format.js";
import { setState, useAppState } from "../store.js";
import { setRunTime } from "../session.js";

const NAMES = ["plant", "heaters", "dryer"];

function available(state) {
  const out = [];
  if (state.boiler) out.push("plant", "heaters");
  if (state.dryer) out.push("dryer");
  return out.filter((n, i, all) => NAMES.includes(n) && all.indexOf(n) === i);
}

export function hoursAt(state) {
  const times = state.times || [];
  if (!times.length) return NaN;
  return (Date.parse(state.time) - Date.parse(times[0])) / 3.6e6;
}

export function Diagram() {
  const s = useAppState();
  const run = s.run;
  const [name, setName] = useState("plant");
  const [svg, setSvg] = useState("");
  const state = run && run.state;
  const names = state ? available(state) : [];
  const shown = names.includes(name) ? name : names[0];
  const time = state ? state.time : null;
  useEffect(() => {
    if (!run || !shown) {
      setSvg("");
      return undefined;
    }
    let live = true;
    fetchText(`/runs/${enc(run.id)}/diagram/${shown}?time=${enc(time)}`).then(
      (text) => live && setSvg(text),
      () => live && setSvg(""),
    );
    return () => {
      live = false;
    };
  }, [run && run.id, shown, time, lang()]);
  if (!state || !shown) return html`<p class="muted small empty">${t("ui-diagram-empty")}</p>`;
  const toggle = html`<button type="button" class="link" id="diagram-toggle"
    onClick=${() => setState({ diagramHidden: !s.diagramHidden })}>${t(s.diagramHidden ? "ui-diagram-show" : "ui-diagram-hide")}</button>`;
  const times = state.times || [];
  const index = Math.max(0, times.indexOf(time));
  return html`<div aria-label=${t("ui-diagram")}>
    ${s.diagramHidden ? null : html`<div class="drawing" id="drawing" dangerouslySetInnerHTML=${{ __html: svg }}></div>`}
    <div class="timebar small no-print">
      ${names.length > 1
        ? html`<span role="group" aria-label=${t("ui-diagram")}>${names.map(
            (n) => html`<button type="button" class="btn" aria-pressed=${n === shown} onClick=${() => setName(n)}>
              ${t("ui-diagram-" + n)}</button>`,
          )}</span>`
        : null}
      <label for="time-slider">${t("ui-time")}</label>
      <input type="range" id="time-slider" min="0" max=${Math.max(times.length - 1, 0)} value=${index}
        onInput=${(e) => setRunTime(times[Number(e.target.value)])} />
      <span id="time-label" style="min-width: 15rem; text-align: left">
        ${fmtHours(hoursAt(state))} · ${time.replace("T", " ").replace("Z", " UTC")}</span>
      <button type="button" class="link" onClick=${() => setRunTime(times[times.length - 1])}>${t("ui-end")}</button>
      ${toggle}
    </div>
  </div>`;
}
