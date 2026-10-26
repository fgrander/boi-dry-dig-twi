// Shared helpers of the web app pages (no build step; see research R1).
"use strict";

const PERIOD_COLORS = { warning: "rgba(198, 40, 40, 0.12)", flag: "rgba(178, 106, 0, 0.10)" };

const twin = {
  async getJSON(url) {
    const r = await fetch(url, { headers: { Accept: "application/json" } });
    if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
    return r.json();
  },

  async postJSON(url, body) {
    const r = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
    });
    const data = r.status === 204 ? {} : await r.json();
    return { ok: r.ok, status: r.status, data };
  },

  // One line from an error response: the loader issues, or the error text.
  issueText(data) {
    if (data && Array.isArray(data.issues)) {
      return data.issues.map((i) => `${i.field}: ${i.reason}${i.allowed ? " (allowed: " + i.allowed + ")" : ""}`).join("; ");
    }
    return (data && data.error) || "request failed";
  },

  fmt(value, digits = 3) {
    if (value === null || value === undefined || Number.isNaN(value)) return "–";
    return Number(value).toPrecision(digits);
  },

  // A y axis that does not zoom into round-off: a flat line gets a sensible span.
  yAxis(col) {
    const values = col.traces.flatMap((t) => t.values).filter((v) => v !== null && Number.isFinite(v));
    const axis = { title: { text: col.unit }, automargin: true, tickformat: "~r", exponentformat: "none" };
    if (!values.length) return axis;
    const lo = Math.min(...values), hi = Math.max(...values);
    const span = Math.max(Math.abs(hi), Math.abs(lo), 1) * 0.002;
    if (hi - lo < span) axis.range = [lo - span * 2.5, hi + span * 2.5];
    return axis;
  },

  // One Plotly figure per column; several runs are several traces; periods are shaded;
  // optional marks ({time, label}) are drawn as dashed vertical lines (e.g. input steps).
  drawPlots(container, plotData, config, marks = []) {
    container.innerHTML = "";
    const several = plotData.runs.length > 1;
    for (const col of plotData.columns) {
      const div = document.createElement("div");
      div.className = "plot";
      container.appendChild(div);
      const traces = col.traces.map((t) => ({
        x: t.times, y: t.values, type: "scatter", mode: "lines",
        name: several ? t.run_id.slice(0, 8) : col.column,
      }));
      const seen = new Set();
      const shapes = [];
      for (const p of col.periods) {
        const key = `${p.label}|${p.start}|${p.end}`;
        if (seen.has(key)) continue;
        seen.add(key);
        shapes.push({ type: "rect", xref: "x", yref: "paper", x0: p.start, x1: p.end, y0: 0, y1: 1,
          fillcolor: PERIOD_COLORS[p.kind] || PERIOD_COLORS.flag, line: { width: 0 } });
      }
      for (const m of marks) {
        shapes.push({ type: "line", xref: "x", yref: "paper", x0: m.time, x1: m.time, y0: 0, y1: 1,
          line: { color: "#5f6670", width: 1, dash: "dash" } });
      }
      const annotations = marks.map((m) => ({ x: m.time, xref: "x", y: 1, yref: "paper", text: m.label,
        showarrow: false, xanchor: "left", yanchor: "top", font: { size: 11, color: "#5f6670" } }));
      const labels = [...new Set(col.periods.map((p) => p.label))];
      const layout = {
        title: { text: `${col.column}${labels.length ? " · shaded: " + labels.join(", ") : ""}`, font: { size: 13 } },
        margin: { l: 60, r: 20, t: 36, b: 40 }, height: 300, shapes, annotations,
        yaxis: twin.yAxis(col), xaxis: { type: "date" }, showlegend: several,
      };
      Plotly.newPlot(div, traces, layout, config);
    }
  },

  // Measured against predicted per output, with the statistics of the comparison report.
  async showComparison(runId, config) {
    const body = document.getElementById("comparison-body");
    const data = await twin.getJSON(`/api/runs/${runId}/comparison`);
    const rows = Object.entries(data.report.outputs).map(([name, o]) => `<tr><td>${name}</td>
      <td class="num">${twin.fmt(o.bias)}</td><td class="num">${twin.fmt(o.rmse)}</td>
      <td class="num">${o.tolerance ?? "–"}</td>
      <td class="num">${o.fraction_within_tolerance === null ? "–" : (100 * o.fraction_within_tolerance).toFixed(0) + " %"}</td>
      <td class="num">${o.n_compared}</td><td class="num">${o.n_excluded}</td>
      <td class="${o.passed === null ? "" : o.passed ? "ok" : "bad"}">${o.passed === null ? "statistics only" : o.passed ? "passed" : "failed"}</td></tr>`);
    body.innerHTML = `<table><thead><tr><th>Output</th><th class="num">Bias (SI)</th><th class="num">RMSE (SI)</th>
      <th class="num">Tolerance (SI)</th><th class="num">Within</th><th class="num">Compared</th><th class="num">Excluded</th><th>Result</th></tr></thead>
      <tbody>${rows.join("")}</tbody></table><div id="comparison-plots"></div>`;
    const plots = document.getElementById("comparison-plots");
    for (const [name, s] of Object.entries(data.series)) {
      const div = document.createElement("div");
      div.className = "plot";
      plots.appendChild(div);
      const excludedX = s.times.filter((_, i) => !s.included[i]);
      const excludedY = s.measured.filter((_, i) => !s.included[i]);
      Plotly.newPlot(div, [
        { x: s.times, y: s.predicted, name: "predicted", mode: "lines" },
        { x: s.times, y: s.measured.map((v, i) => (s.included[i] ? v : null)), name: "measured", mode: "markers", marker: { size: 4 } },
        { x: excludedX, y: excludedY, name: "excluded", mode: "markers", marker: { size: 6, symbol: "x", color: "#c62828" } },
      ], { title: { text: name, font: { size: 13 } }, height: 300, margin: { l: 60, r: 20, t: 36, b: 40 },
        yaxis: { title: { text: s.unit } }, xaxis: { type: "date" } }, config);
    }
  },

  // Process drawings of a run: tabs, a time slider and play (SVG drawn by the server).
  setupProcess(runId, times, first = "plant") {
    const box = document.getElementById("process-diagram");
    const slider = document.getElementById("process-time");
    const label = document.getElementById("process-time-label");
    const play = document.getElementById("process-play");
    let name = first;
    let pending = null;
    let loading = false;
    let timer = null;
    const load = async () => {
      if (loading) { pending = true; return; }
      loading = true;
      const t = times[Number(slider.value)];
      label.textContent = t.replace("T", " ").replace("Z", " UTC");
      const r = await fetch(`/runs/${runId}/diagram/${name}?time=${encodeURIComponent(t)}`);
      box.innerHTML = r.ok ? await r.text() : `<p class="note">${await r.text()}</p>`;
      loading = false;
      if (pending) { pending = null; load(); }
    };
    for (const tab of document.querySelectorAll("[data-diagram]")) {
      tab.addEventListener("click", () => {
        document.querySelectorAll("[data-diagram]").forEach((t) => t.classList.toggle("on", t === tab));
        name = tab.dataset.diagram;
        load();
      });
    }
    slider.addEventListener("input", load);
    play.addEventListener("click", () => {
      if (timer) { clearInterval(timer); timer = null; play.textContent = "▶"; return; }
      if (Number(slider.value) >= times.length - 1) slider.value = 0;
      const stride = Math.max(1, Math.round(times.length / 120));
      play.textContent = "❚❚";
      timer = setInterval(() => {
        slider.value = Math.min(times.length - 1, Number(slider.value) + stride);
        load();
        if (Number(slider.value) >= times.length - 1) { clearInterval(timer); timer = null; play.textContent = "▶"; }
      }, 250);
    });
    load();
  },

  async setupProfiles(runId, config) {
    const select = document.getElementById("profile-time");
    const first = await twin.getJSON(`/api/runs/${runId}/profiles`);
    for (const t of first.times) {
      const o = document.createElement("option");
      o.value = t; o.textContent = t.replace("T", " ").slice(0, 16);
      select.appendChild(o);
    }
    select.value = first.time;
    const draw = (data) => {
      const traces = Object.entries(data.columns).map(([name, values]) => ({
        x: data.cells, y: values, name: `${name} [${data.units[name]}]`, mode: "lines+markers",
      }));
      Plotly.newPlot("profiles", traces, { height: 360, xaxis: { title: { text: "cell (inlet → outlet)" } },
        margin: { l: 60, r: 20, t: 20, b: 40 } }, config);
    };
    draw(first);
    select.addEventListener("change", async () => draw(await twin.getJSON(`/api/runs/${runId}/profiles?time=${select.value}`)));
  },
};
window.twin = twin;
