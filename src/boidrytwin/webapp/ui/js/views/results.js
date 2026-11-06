// Results view: run, key figures, limits and checks, messages, courses over time, profiles
// along the drum and the heater table. All numbers come from the service.

import { useEffect, useState } from "preact/hooks";
import { api } from "../api.js";
import { html } from "../html.js";
import { balanceLabel, chartLabel, columnLabel, flagLabel, kpiLabel, lang, t } from "../i18n.js";
import { fmt, fmtHours, fmtTime, localText } from "../format.js";
import { useAppState } from "../store.js";
import {
  closeRun,
  isOutdated,
  isRunning,
  loadPins,
  loadRun,
  MAX_PINS,
  pinRun,
  runScenario,
  unpin,
} from "../session.js";
import { Btn, Dialog, ErrorBox, Panel } from "../components/common.js";
import { Chart } from "../components/chart.js";
import { hoursAt } from "../components/diagram.js";

// Courses over time: which result columns are drawn together.
export const TIME_CHARTS = [
  ["oil", ["oil_outlet_temperature", "max_film_temperature"]],
  ["boiler-gas", ["furnace_temperature", "gas_temperature_after_heater_1", "gas_temperature_after_heater_2",
    "gas_temperature_after_heater_3", "gas_temperature_after_heater_4", "gas_temperature_after_heater_5",
    "flue_gas_to_dryer_temperature"]],
  ["power", ["heat_released", "heat_to_oil"]],
  ["fuel", ["fuel_feed", "fuel_delivered"]],
  ["o2", ["o2_dry_measured"]],
  ["dryer-gas", ["drum_inlet_gas_temperature", "exhaust_temperature", "exhaust_dew_point", "product_temperature"]],
  ["moisture", ["product_moisture_wet_basis"]],
  ["evaporation", ["evaporation_rate", "product_dry_mass_flow"]],
  ["positions", ["bypass_position", "recirculation_damper_position", "recirculation_share"]],
  ["gas-flows", ["flue_gas_to_dryer_mass_flow", "dilution_air_flow", "recirculation_mass_flow", "exhaust_mass_flow"]],
  ["pressure", ["mixing_chamber_pressure", "mixing_chamber_pressure_setpoint"]],
];
export const PROFILE_CHARTS = [
  ["profile-temperatures", ["gas_temperature", "solids_temperature", "shell_temperature"]],
  ["profile-moisture", ["moisture_wet_basis"]],
  ["profile-holdup", ["solids_holdup"]],
];
const KPI_KEYS = [
  ["dryer", ["product_moisture", "product_temperature", "product_flow", "evaporation", "specific_energy",
    "drum_inlet", "exhaust", "holdup"]],
  ["boiler", ["fuel_feed", "load", "heat_released", "furnace", "o2", "oil_supply", "heat_to_oil"]],
  ["recirculation", ["share", "pressure"]],
];

function hours(times) {
  const start = Date.parse(times[0]);
  return times.map((x) => (Date.parse(x) - start) / 3.6e6);
}

function plotColumn(plot, column) {
  return plot ? plot.columns.find((c) => c.column === column) : null;
}

// One group of series for a chart from the plot data of one run.
export function timeGroup(plot, columns, suffix = "") {
  const found = columns.map((c) => plotColumn(plot, c)).filter((c) => c && c.traces.length);
  if (!found.length) return null;
  const trace = found[0].traces[0];
  return {
    xs: hours(trace.times),
    series: found.map((c) => ({ label: columnLabel(c.column) + suffix, values: c.traces[0].values })),
  };
}

export function chartUnit(plot, columns) {
  const units = [...new Set(columns.map((c) => plotColumn(plot, c)).filter(Boolean).map((c) => c.unit))];
  return units.join(" / ");
}

// Start and end of flagged or warned periods, as markers in the charts of their columns.
export function periodEvents(plot, columns) {
  const out = [];
  const seen = new Set();
  for (const name of columns) {
    const c = plotColumn(plot, name);
    if (!c || !c.traces.length) continue;
    const start = Date.parse(c.traces[0].times[0]);
    const last = c.traces[0].times[c.traces[0].times.length - 1];
    for (const p of c.periods || []) {
      const key = `${p.start}|${p.label}`;
      if (seen.has(key)) continue;
      seen.add(key);
      // a period over the whole run needs no marker
      if (Date.parse(p.start) > start) out.push({ x: (Date.parse(p.start) - start) / 3.6e6, label: p.label });
      if (Date.parse(p.end) < Date.parse(last)) out.push({ x: (Date.parse(p.end) - start) / 3.6e6, label: "" });
    }
  }
  return out;
}

export function profileGroup(profiles, columns, suffix = "") {
  if (!profiles) return null;
  const found = columns.filter((c) => profiles.columns[c]);
  if (!found.length) return null;
  return {
    xs: profiles.cells.map((c) => c + 1),
    series: found.map((c) => ({ label: columnLabel(c) + suffix, values: profiles.columns[c] })),
  };
}

export function kpiItems(state) {
  const items = [];
  for (const [part, keys] of KPI_KEYS) {
    const values = state && state[part];
    if (!values) continue;
    for (const key of keys) if (values[key] && values[key].value !== null) items.push([key, values[key]]);
  }
  return items;
}

export function Kpis({ state }) {
  return html`<div class="kpis" id="kpis">
    ${kpiItems(state).map(
      ([key, v]) => html`<div class="kpi" data-kpi=${key}>
        <div class="v">${localText(v.text.replace(" " + v.unit, ""), lang())} <span class="small">${v.unit}</span></div>
        <div class="k">${kpiLabel(key)}</div></div>`,
    )}
  </div>`;
}

// Balances: relative error against the tolerance. Flags: share of the output times.
export function limitRows(info, state) {
  const balances = [];
  for (const [part, quantities] of Object.entries(info.balances?.entries || {})) {
    for (const [quantity, b] of Object.entries(quantities)) {
      if (!b || typeof b.relative_residual !== "number") continue;
      // below a millionth of a percent it is rounding of the solver, shown as 0
      const raw = Math.abs(b.relative_residual) * 100;
      const value = raw < 1e-6 ? 0 : raw;
      const limit = b.tolerance * 100;
      balances.push({ name: `${balanceLabel(part)}: ${balanceLabel(quantity)}`, key: `${part}.${quantity}`,
        value, limit, margin: limit - value, unit: "%", passed: !!b.passed });
    }
  }
  const samples = state?.times?.length || 0;
  const flags = Object.entries(info.summary?.flags || {}).map(([flag, count]) => {
    const value = samples ? (100 * count) / samples : count;
    return { name: flagLabel(flag), key: flag, value, limit: 0, margin: 0 - value || 0, unit: samples ? "%" : "", passed: count === 0 };
  });
  return { balances, flags };
}

export function LimitsTable({ info, state }) {
  const { balances, flags } = limitRows(info, state);
  const row = (l) => html`<tr data-limit=${l.key}><td>${l.name}</td><td class="n">${fmt(l.value, lang(), 3)}</td>
    <td class="n">${fmt(l.limit, lang(), 3)} ${l.unit}</td><td class="n">${fmt(l.margin, lang(), 3)}</td>
    <td class=${l.passed ? "pass" : "fail"}>${l.passed ? "✓" : "✗"}</td></tr>`;
  return html`<table class="data" id="limits"><thead><tr><th>${t("ui-limit")}</th><th class="n">${t("ui-value")}</th>
    <th class="n">${t("ui-limit-value")}</th><th class="n">${t("ui-margin")}</th><th></th></tr></thead>
    <tbody>
      ${flags.length ? html`<tr class="sub"><th colspan="5">${t("ui-flags")}</th></tr>` : null}
      ${flags.map(row)}
      ${balances.length ? html`<tr class="sub"><th colspan="5">${t("ui-balances")}</th></tr>` : null}
      ${balances.map(row)}
    </tbody></table>`;
}

export function Messages({ info }) {
  const warnings = info.warnings || [];
  const when = (x) => String(x).replace("T", " ").replace("Z", "").replace("+00:00", "");
  return html`<div id="messages">
    <p class=${info.summary.checks_passed ? "pass" : "fail"}>${info.summary.checks_passed ? t("ui-all-passed") : t("ui-not-passed")}</p>
    ${warnings.map(
      (w) => html`<div class="issue warning">${t("ui-warning-text", {
        quantity: w.quantity, kind: t("ui-warning-" + w.limit_type), limit: fmt(w.limit, lang()),
        extreme: fmt(w.observed_extreme, lang()), from: when(w.period_start), to: when(w.period_end) })}</div>`,
    )}
    ${warnings.length ? null : html`<p class="muted small">${t("ui-no-messages")}</p>`}
  </div>`;
}

function HeaterTable({ heaters }) {
  if (!heaters || !heaters.length) return null;
  const cell = (v) => html`<td class="n">${v ? localText(v.text, lang()) : "–"}</td>`;
  return html`<${Panel} title=${t("ui-heaters")}><table class="data" id="heaters"><thead><tr><th>${t("ui-heater")}</th><th></th>
    <th class="n">${t("ui-gas-in")}</th><th class="n">${t("ui-gas-out")}</th><th class="n">${t("ui-oil-in")}</th>
    <th class="n">${t("ui-oil-out")}</th><th class="n">${t("ui-duty")}</th></tr></thead>
    <tbody>${heaters.map(
      (h) => html`<tr><td>${h.n}</td><td>${t("ui-heater-kind-" + h.kind)}</td>${cell(h.gas_in)}${cell(h.gas_out)}
        ${cell(h.oil_in)}${cell(h.oil_out)}${cell(h.duty)}</tr>`,
    )}</tbody></table><//>`;
}

function RunsDialog({ open, onClose }) {
  const [runs, setRuns] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => {
    if (open) api.get("/runs?limit=100").then((r) => setRuns(r.data.runs), setErr);
  }, [open]);
  const pick = async (id) => {
    try {
      await loadRun(id);
      onClose();
    } catch (e) {
      setErr(e);
    }
  };
  return html`<${Dialog} open=${open} title=${t("ui-open-run")} onClose=${onClose}>
    <${ErrorBox} error=${err} />
    ${runs
      ? html`<div class="tablewrap"><table class="data" id="runs-list"><thead><tr><th>${t("ui-name")}</th>
          <th>${t("ui-run-created")}</th><th>${t("ui-run-kind")}</th><th>${t("ui-run-status")}</th><th>${t("ui-run-checks")}</th><th></th></tr></thead>
          <tbody>${runs.map(
            (r) => html`<tr><td>${r.scenario_name}<div class="small muted">${r.run_id}</div></td>
              <td>${fmtTime(r.created_at, lang())}</td><td>${r.kind}</td><td>${r.status}</td>
              <td class=${r.checks_passed ? "pass" : "fail"}>${r.checks_passed ? "✓" : "✗"}</td>
              <td><button type="button" class="btn" onClick=${() => pick(r.run_id)}>${t("ui-open")}</button></td></tr>`,
          )}</tbody></table></div>`
      : null}
    <div class="row" style="margin-top: .6rem"><span class="spacer"></span><${Btn} onClick=${onClose}>${t("ui-close")}<//></div>
  <//>`;
}

function Progress({ job }) {
  const p = job.progress;
  const share = p && p.duration_s > 0 ? Math.min(1, p.simulated_s / p.duration_s) : 0;
  return html`<span class="row" role="status" id="progress">
    <span class="muted">${t(job.state === "running" ? "ui-job-running" : "ui-job-queued")}</span>
    <span class="progress"><div style=${`width: ${Math.round(share * 100)}%`}></div></span>
    ${p ? html`<span class="muted small">${t("ui-simulated", { done: fmtHours(p.simulated_s / 3600), total: fmtHours(p.duration_s / 3600) })}</span>` : null}
  </span>`;
}

function RunBar({ s }) {
  const [dlg, setDlg] = useState(false);
  const running = isRunning();
  const pinned = s.run && s.pins.some((p) => p.id === s.run.id);
  return html`<div class="row">
    <${Btn} primary id="btn-run" disabled=${!s.scenario || s.valid !== true || running} onClick=${runScenario}>${t("ui-run")}<//>
    ${running ? html`<${Progress} job=${s.job} />` : null}
    ${!running && isOutdated() ? html`<span class="tag-outdated" id="outdated">${t("ui-outdated")}</span>` : null}
    ${s.scenario && s.valid === false ? html`<span class="muted small">${t("ui-run-needs-valid")}</span>` : null}
    <span class="spacer"></span>
    <${Btn} id="btn-open-run" onClick=${() => setDlg(true)}>${t("ui-open-run")}<//>
    <${Btn} id="btn-pin" disabled=${!s.run || pinned || s.pins.length >= MAX_PINS} title=${s.pins.length >= MAX_PINS ? t("ui-pins-full") : ""}
      onClick=${pinRun}>${t("ui-pin")}<//>
    <${RunsDialog} open=${dlg} onClose=${() => setDlg(false)} />
  </div>`;
}

function PinsBar({ s }) {
  if (!s.pins.length) return null;
  return html`<div class="row small" style="margin-top: .5rem" id="pins"><span class="muted">${t("ui-pinned")}:</span>
    <span class="pin-list">${s.pins.map(
      (p, i) => html`<span class="pin">${i + 1}: ${p.label}
        <button type="button" class="link" onClick=${() => unpin(p.id)}>${t("ui-unpin")}</button></span>`,
    )}</span></div>`;
}

// Pinned runs other than the shown one, with their loaded data.
export function otherPins(s) {
  return s.pins
    .map((p, i) => ({ ...p, n: i + 1, data: s.pinPlots[p.id] }))
    .filter((p) => p.data && (!s.run || p.id !== s.run.id));
}

function PinsTable({ s }) {
  const pins = otherPins(s);
  if (!pins.length || !s.run) return null;
  const columns = [{ label: t("ui-current"), state: s.run.state }, ...pins.map((p) => ({ label: `${p.n}: ${p.label}`, state: p.data.state }))];
  const keys = [...new Set(columns.flatMap((c) => kpiItems(c.state).map(([k]) => k)))];
  const value = (state, key) => {
    const found = kpiItems(state).find(([k]) => k === key);
    return found ? localText(found[1].text, lang()) : "–";
  };
  return html`<${Panel} title=${t("ui-compare")} id="pins-table"><div class="tablewrap"><table class="data">
    <thead><tr><th></th>${columns.map((c) => html`<th class="n">${c.label}</th>`)}</tr></thead>
    <tbody>${keys.map((k) => html`<tr><td>${kpiLabel(k)}</td>${columns.map((c) => html`<td class="n">${value(c.state, k)}</td>`)}</tr>`)}</tbody>
  </table></div><//>`;
}

export function ResultsView() {
  const s = useAppState();
  useEffect(() => {
    loadPins();
  }, [s.pins.length]);
  const run = s.run;
  const pins = otherPins(s);
  const failed = s.runError && s.runError.failed;
  return html`<div>
    <${Panel} title=${t("ui-run")} id="run"><${RunBar} s=${s} />
      ${failed
        ? html`<div class="issue error" role="alert" id="run-failed">${failed === "failed"
            ? t("ui-job-failed", { message: s.runError.message }) : t("ui-job-interrupted")}</div>`
        : html`<${ErrorBox} error=${s.runError} />`}
      <${PinsBar} s=${s} />
    <//>
    ${run
      ? html`<div class=${isOutdated() ? "outdated" : ""} id="results" data-run=${run.id}>
          <${Panel} title=${t("ui-key-figures")}
            extra=${run.state ? html`<span class="muted small">${t("ui-at-time", { time: fmtHours(hoursAt(run.state)) })}</span>` : null}>
            <${Kpis} state=${run.state} />
            <p class="muted small" style="margin: .5rem 0 0">${run.record.scenario_name} · ${t("ui-run-id")} ${run.id}
              <button type="button" class="link no-print" onClick=${closeRun}>${t("ui-close")}</button></p>
          <//>
          <div class="grid2">
            <${Panel} title=${t("ui-limits")}><div class="tablewrap"><${LimitsTable} info=${run.info} state=${run.state} /></div><//>
            <${Panel} title=${t("ui-messages")}><${Messages} info=${run.info} /><//>
          </div>
          <${PinsTable} s=${s} />
          <h2 style="font-size: 1rem">${t("ui-over-time")}</h2>
          <div class="charts" id="time-charts">
            ${TIME_CHARTS.map(([id, columns]) => {
              const groups = [timeGroup(run.plot, columns),
                ...pins.map((p) => timeGroup(p.data.plot, columns, ` (${p.n})`))].filter(Boolean);
              if (!groups.length) return null;
              return html`<${Chart} key=${id} id=${"chart-" + id} title=${chartLabel(id)} xLabel=${t("ui-x-time")}
                yLabel=${chartUnit(run.plot, columns)} groups=${groups} events=${periodEvents(run.plot, columns)} />`;
            })}
          </div>
          ${run.profiles
            ? html`<h2 style="font-size: 1rem">${t("ui-profiles")}
                <span class="muted small" style="font-weight: 400"> ${t("ui-at-time", { time: fmtHours(hoursAt(run.state || {})) })}</span></h2>
              <div class="charts" id="profile-charts">
                ${PROFILE_CHARTS.map(([id, columns]) => {
                  const groups = [profileGroup(run.profiles, columns),
                    ...pins.map((p) => profileGroup(p.data.profiles, columns, ` (${p.n})`))].filter(Boolean);
                  if (!groups.length) return null;
                  const unit = [...new Set(columns.map((c) => run.profiles.units[c]).filter(Boolean))].join(" / ");
                  return html`<${Chart} key=${id} id=${"chart-" + id} title=${chartLabel(id)} xLabel=${t("ui-x-cell")}
                    yLabel=${unit} groups=${groups} points=${true} />`;
                })}
              </div>`
            : null}
          <${HeaterTable} heaters=${run.state && run.state.heaters} />
        </div>`
      : html`<p class="muted" id="no-run">${s.scenario ? t("ui-no-run") : t("ui-start-hint")}</p>`}
  </div>`;
}
