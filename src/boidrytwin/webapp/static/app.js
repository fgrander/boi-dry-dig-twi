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
