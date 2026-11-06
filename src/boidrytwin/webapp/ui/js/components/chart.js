// Line chart: uPlot with event markers, cursor values in the legend, overlays of pinned
// results, image and CSV export, and a table of the values.

import uPlot from "uplot";
import { useEffect, useRef, useState } from "preact/hooks";
import { html } from "../html.js";
import { lang, t } from "../i18n.js";
import { fmt } from "../format.js";
import { download, toCSV } from "../csv.js";

// Okabe-Ito, colour-blind-safe
export const COLOURS = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#000000"];
const DASH = [[], [8, 4], [2, 3], [10, 3, 2, 3], [5, 2, 1, 2]];

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#888";
}

function eventsPlugin(events) {
  return {
    hooks: {
      draw: [
        (u) => {
          const { ctx } = u;
          const top = u.bbox.top;
          const h = u.bbox.height;
          ctx.save();
          ctx.strokeStyle = cssVar("--muted");
          ctx.fillStyle = cssVar("--muted");
          ctx.setLineDash([3, 3]);
          ctx.font = `${10 * devicePixelRatio}px sans-serif`;
          ctx.textBaseline = "top";
          let row = 0;
          for (const e of events || []) {
            const x = u.valToPos(e.x, "x", true);
            if (x < u.bbox.left || x > u.bbox.left + u.bbox.width) continue;
            ctx.beginPath();
            ctx.moveTo(x, top);
            ctx.lineTo(x, top + h);
            ctx.stroke();
            if (!e.label) continue;
            // labels inside the plot, in three rows so that they do not overlap
            const y = top + (2 + 12 * (row++ % 3)) * devicePixelRatio;
            const w = ctx.measureText(e.label).width;
            const right = u.bbox.left + u.bbox.width;
            const pad = 3 * devicePixelRatio;
            ctx.fillText(e.label, x + w + pad > right ? x - w - pad : x + pad, y);
          }
          ctx.restore();
        },
      ],
    },
  };
}

// groups: [{xs, series: [{label, values}], dash}] (one group per run; pins add groups)
export function Chart({ id, title, xLabel, yLabel, groups, events, height = 260, points = false }) {
  const box = useRef(null);
  const plot = useRef(null);
  const [table, setTable] = useState(false);
  const live = (groups || []).filter((g) => g && g.xs && g.xs.length && g.series.length);
  const aligned = live.length ? uPlot.join(live.flatMap((g) => g.series.map((s) => [g.xs, s.values]))) : null;
  const labels = live.flatMap((g, gi) =>
    g.series.map((s, si) => ({ ...s, gi, si, dash: g.dash || DASH[gi % DASH.length] })),
  );
  useEffect(() => {
    if (!box.current || !aligned) return undefined;
    const opts = {
      width: box.current.clientWidth || 600,
      height,
      scales: { x: { time: false } },
      axes: [
        { label: xLabel, stroke: cssVar("--fg"), grid: { stroke: cssVar("--line") } },
        { label: yLabel, stroke: cssVar("--fg"), grid: { stroke: cssVar("--line") }, size: 60 },
      ],
      series: [
        { label: xLabel, value: (u, v) => fmt(v, lang(), 4) },
        ...labels.map((s) => ({
          label: s.label,
          stroke: COLOURS[s.si % COLOURS.length],
          dash: s.dash,
          width: 1.6,
          spanGaps: true,
          points: { show: s.points ?? points },
          value: (u, v) => fmt(v, lang(), 4),
        })),
      ],
      plugins: [eventsPlugin(events)],
    };
    plot.current = new uPlot(opts, aligned, box.current);
    const ro = new ResizeObserver(() => {
      if (plot.current && box.current) plot.current.setSize({ width: box.current.clientWidth, height });
    });
    ro.observe(box.current);
    return () => {
      ro.disconnect();
      plot.current.destroy();
      plot.current = null;
    };
  }, [JSON.stringify(aligned), JSON.stringify(labels.map((l) => [l.label, l.dash])), JSON.stringify(events), lang()]);
  const csv = () => {
    const head = [xLabel, ...labels.map((s) => s.label)];
    const rows = aligned[0].map((x, i) => [x, ...labels.map((_, k) => aligned[k + 1][i])]);
    download(`${id}.csv`, toCSV(head, rows, lang()));
  };
  const png = () => plot.current.ctx.canvas.toBlob((b) => download(`${id}.png`, b));
  return html`<figure class="chart panel" id=${id} aria-label=${title}>
    <div class="row"><h3>${title}</h3><span class="spacer"></span>
      ${aligned
        ? html`<span class="tools">
            <button type="button" class="link" onClick=${() => setTable(!table)} aria-pressed=${table}>${t("ui-chart-values")}</button>
            <button type="button" class="link" onClick=${csv}>${t("ui-chart-csv")}</button>
            <button type="button" class="link" onClick=${png}>${t("ui-chart-png")}</button></span>`
        : null}
    </div>
    ${aligned ? html`<div ref=${box}></div>` : html`<p class="muted small">${t("ui-chart-empty")}</p>`}
    ${table && aligned
      ? html`<div class="tablewrap"><table class="data">
          <thead><tr><th class="n">${xLabel}</th>${labels.map((s) => html`<th class="n">${s.label}</th>`)}</tr></thead>
          <tbody>${aligned[0].map(
            (x, i) => html`<tr><td class="n">${fmt(x, lang())}</td>
              ${labels.map((_, k) => html`<td class="n">${fmt(aligned[k + 1][i], lang())}</td>`)}</tr>`,
          )}</tbody></table></div>`
      : null}
  </figure>`;
}
