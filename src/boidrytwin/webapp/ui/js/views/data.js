// Measurements and comparison: upload a file of plant measurements, run the saved scenario
// against it, and see per output how far the model is from the measurement.

import { useRef, useState } from "preact/hooks";
import { html } from "../html.js";
import { columnLabel, lang, t } from "../i18n.js";
import { fmt } from "../format.js";
import { useAppState } from "../store.js";
import { isRunning, startComparison } from "../session.js";
import { Btn, ErrorBox, Panel } from "../components/common.js";
import { Chart } from "../components/chart.js";

function comparisonGroup(series) {
  if (!series.times.length) return null;
  const start = Date.parse(series.times[0]);
  return {
    xs: series.times.map((x) => (Date.parse(x) - start) / 3.6e6),
    series: [
      { label: t("ui-predicted"), values: series.predicted },
      { label: t("ui-measured"), values: series.measured, points: true },
    ],
  };
}

function OutputsTable({ report }) {
  const rows = Object.entries(report.outputs || {});
  const verdict = (o) => (o.passed === null || o.passed === undefined ? "–" : o.passed ? "✓" : "✗");
  return html`<div class="tablewrap"><table class="data" id="comparison-outputs"><thead><tr><th>${t("ui-output")}</th>
    <th class="n">${t("ui-bias")}</th><th class="n">RMSE</th><th class="n">${t("ui-max-error")}</th>
    <th class="n">${t("ui-tolerance")}</th><th class="n">${t("ui-within")}</th><th class="n">${t("ui-samples")}</th>
    <th class="n">${t("ui-excluded")}</th><th></th></tr></thead>
    <tbody>${rows.map(
      ([name, o]) => html`<tr data-output=${name}><td>${columnLabel(name)}</td><td class="n">${fmt(o.bias, lang())}</td>
        <td class="n">${fmt(o.rmse, lang())}</td><td class="n">${fmt(o.max_abs_error, lang())}</td>
        <td class="n">${fmt(o.tolerance, lang())}</td>
        <td class="n">${o.fraction_within_tolerance === null || o.fraction_within_tolerance === undefined
          ? "–" : fmt(o.fraction_within_tolerance * 100, lang(), 3) + " %"}</td>
        <td class="n">${o.n_steady}</td><td class="n">${o.n_excluded}</td>
        <td class=${o.passed ? "pass" : o.passed === false ? "fail" : ""}>${verdict(o)}</td></tr>`,
    )}</tbody></table></div>`;
}

export function DataView() {
  const s = useAppState();
  const fileRef = useRef(null);
  const [err, setErr] = useState(null);
  const sc = s.scenario;
  const ready = !!sc && !sc.dirty && s.valid === true;
  const start = async () => {
    setErr(null);
    const f = fileRef.current.files[0];
    if (!f) return;
    try {
      await startComparison(f);
    } catch (e) {
      setErr(e);
    }
  };
  const comparison = s.run && s.run.comparison;
  return html`<div>
    <${Panel} title=${t("ui-nav-data")} id="data">
      <p class="muted" style="margin-top: 0">${t("ui-data-intro")}</p>
      <div class="row">
        <input type="file" accept=".csv" id="measured-file" ref=${fileRef} aria-label=${t("ui-measured-file")} />
        <${Btn} primary id="btn-compare" disabled=${!ready || isRunning()} onClick=${start}>${t("ui-compare-run")}<//>
        ${isRunning() ? html`<span class="muted" role="status">${t("ui-busy")}</span>` : null}
        ${!ready ? html`<span class="muted small">${t("ui-data-needs-saved")}</span>` : null}
      </div>
      <${ErrorBox} error=${err || (s.runError && !s.runError.failed ? s.runError : null)} />
    <//>
    ${comparison
      ? html`<${Panel} title=${t("ui-comparison")} id="comparison"
            extra=${html`<span class=${comparison.report.passed ? "pass" : "fail"}>${comparison.report.passed
              ? t("ui-comparison-passed") : t("ui-comparison-failed")}</span>`}>
          <p class="muted small" style="margin-top: 0">${t("ui-comparison-note", {
            share: fmt((comparison.report.required_fraction || 0) * 100, lang(), 3) })}</p>
          <${OutputsTable} report=${comparison.report} />
        <//>
        <div class="charts">
          ${Object.entries(comparison.series).map(([name, series]) => {
            const group = comparisonGroup(series);
            return group
              ? html`<${Chart} key=${name} id=${"chart-compare-" + name} title=${columnLabel(name)} xLabel=${t("ui-x-time")}
                  yLabel=${series.unit} groups=${[group]} />`
              : null;
          })}
        </div>`
      : html`<p class="muted" id="no-comparison">${t("ui-no-comparison")}</p>`}
  </div>`;
}
