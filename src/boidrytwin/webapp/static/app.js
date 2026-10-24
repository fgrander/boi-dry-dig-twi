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

  // One Plotly figure per column; several runs are several traces; periods are shaded.
  drawPlots(container, plotData, config) {
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
      const labels = [...new Set(col.periods.map((p) => p.label))];
      const layout = {
        title: { text: `${col.column}${labels.length ? " · shaded: " + labels.join(", ") : ""}`, font: { size: 13 } },
        margin: { l: 60, r: 20, t: 36, b: 40 }, height: 300, shapes,
        yaxis: { title: { text: col.unit } }, xaxis: { type: "date" }, showlegend: several,
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
