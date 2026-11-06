// Print-friendly report of the shown run. The browser prints it or saves it as PDF. Only the
// changed inputs are listed, so a report stays short.

import { html } from "../html.js";
import { chartLabel, keyLabel, kpiLabel, lang, sectionLabel, t } from "../i18n.js";
import { fmtHours, fmtTime, localText } from "../format.js";
import { useAppState } from "../store.js";
import { changedFields, fieldValue, isOutdated, scenarioHash } from "../session.js";
import { Btn } from "../components/common.js";
import { Chart } from "../components/chart.js";
import { hoursAt } from "../components/diagram.js";
import { chartUnit, kpiItems, LimitsTable, Messages, periodEvents, profileGroup, timeGroup } from "./results.js";

const REPORT_CHARTS = [
  ["oil", ["oil_outlet_temperature", "max_film_temperature"]],
  ["dryer-gas", ["drum_inlet_gas_temperature", "exhaust_temperature", "exhaust_dew_point", "product_temperature"]],
  ["moisture", ["product_moisture_wet_basis"]],
  ["power", ["heat_released", "heat_to_oil"]],
];

function HeaderBlock({ run }) {
  const r = run.record;
  const stamp = (x) => (x ? String(x).replace("T", " ").replace("Z", " UTC") : "–");
  return html`<table class="data report-head" id="report-head"><tbody>
    <tr><th>${t("ui-name")}</th><td>${r.scenario_name || "–"}</td></tr>
    <tr><th>${t("ui-run-id")}</th><td class="fp">${run.id}</td></tr>
    <tr><th>${t("ui-fingerprint")}</th><td class="fp">${(r.scenario_sha256 || "–").slice(0, 16)}</td></tr>
    <tr><th>${t("ui-software")}</th><td>boidrytwin ${r.model_version || "–"}${r.python ? ` · Python ${r.python}` : ""}</td></tr>
    <tr><th>${t("ui-computed")}</th><td>${fmtTime(r.created_at, lang())} (${r.created_at})</td></tr>
    <tr><th>${t("ui-period")}</th><td>${stamp(r.start)} – ${stamp(r.end)}</td></tr>
  </tbody></table>`;
}

// The inputs changed in the editor, if the shown run was computed from the open scenario.
function ChangedInputs({ s }) {
  const run = s.run;
  const own = !!s.scenario && !!run.hash && run.hash === scenarioHash();
  if (!own) {
    return html`<section class="panel"><h2>${t("ui-changed-params", { n: "–" })}</h2>
      <p class="muted">${t("ui-changes-unknown")}</p></section>`;
  }
  const changed = changedFields();
  const base = `${s.scenario.source === "example" ? t("ui-example") + " " : ""}${s.scenario.name}`;
  return html`<section class="panel"><h2>${t("ui-changed-params", { n: changed.length })}
      <span class="muted small" style="font-weight: 400"> ${t("ui-changed-against", { base })}</span></h2>
    ${changed.length
      ? html`<table class="data" id="report-changed"><thead><tr><th>${t("ui-section")}</th><th>${t("ui-parameter")}</th>
          <th class="n">${t("ui-value")}</th><th class="n">${t("ui-initial")}</th></tr></thead>
          <tbody>${changed.map(
            ({ section, field, was }) => html`<tr><td>${sectionLabel(section.name)}</td><td>${keyLabel(field.key)}</td>
              <td class="n">${fieldValue(field)}</td><td class="n">${was}</td></tr>`,
          )}</tbody></table>`
      : html`<p class="muted">${t("ui-no-changes")}</p>`}
  </section>`;
}

export function ReportView() {
  const s = useAppState();
  const run = s.run;
  if (!run) return html`<p class="muted" id="no-report">${t("ui-report-hint")} ${t("ui-no-run")}</p>`;
  const at = run.state ? fmtHours(hoursAt(run.state)) : "";
  return html`<div class="report">
    <div class="row no-print">
      <span class="muted">${t("ui-report-hint")}</span>
      ${isOutdated() ? html`<span class="tag-outdated">${t("ui-outdated")}</span>` : null}
      <span class="spacer"></span>
      <${Btn} primary id="btn-print" onClick=${() => window.print()}>${t("ui-print")}<//>
    </div>
    <div id="report-run">
      <h1>${t("ui-report-title")}</h1>
      <${HeaderBlock} run=${run} />
      <${ChangedInputs} s=${s} />
      <section class="panel"><h2>${t("ui-key-figures")}
          <span class="muted small" style="font-weight: 400"> ${t("ui-at-time", { time: at })}</span></h2>
        <table class="data" id="report-kpis"><tbody>${kpiItems(run.state).map(
          ([key, v]) => html`<tr><td>${kpiLabel(key)}</td><td class="n">${localText(v.text, lang())}</td></tr>`,
        )}</tbody></table>
      </section>
      <section class="panel"><h2>${t("ui-limits")}</h2><${LimitsTable} info=${run.info} state=${run.state} /></section>
      <section class="panel page-break"><h2>${t("ui-over-time")}</h2>
        ${REPORT_CHARTS.map(([id, columns]) => {
          const group = timeGroup(run.plot, columns);
          if (!group) return null;
          return html`<${Chart} key=${id} id=${"report-" + id} title=${chartLabel(id)} xLabel=${t("ui-x-time")}
            yLabel=${chartUnit(run.plot, columns)} groups=${[group]} events=${periodEvents(run.plot, columns)} height=${200} />`;
        })}
        ${run.profiles
          ? html`<${Chart} id="report-profile-moisture" title=${chartLabel("profile-moisture") + " · " + at}
              xLabel=${t("ui-x-cell")} yLabel=${run.profiles.units.moisture_wet_basis}
              groups=${[profileGroup(run.profiles, ["moisture_wet_basis"])]} points=${true} height=${200} />`
          : null}
      </section>
      <section class="panel"><h2>${t("ui-messages")}</h2><${Messages} info=${run.info} /></section>
    </div>
  </div>`;
}
