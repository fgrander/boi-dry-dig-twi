// Formulas and sources: every formula of the models as the service lists it, typeset as
// MathML by the vendored Temml. Nothing is evaluated here.

import temml from "temml";
import { useEffect, useMemo, useState } from "preact/hooks";
import { api } from "../api.js";
import { html } from "../html.js";
import { lang, t } from "../i18n.js";
import { setState, useAppState } from "../store.js";
import { Btn, ErrorBox, Panel } from "../components/common.js";

const cache = new Map();

function tex(source, display) {
  const key = (display ? "d:" : "i:") + source;
  if (!cache.has(key)) {
    let out;
    try {
      out = temml.renderToString(source, { displayMode: display, annotate: true, throwOnError: true });
    } catch {
      out = `<code class="fail">${source.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c])}</code>`;
    }
    cache.set(key, out);
  }
  return cache.get(key);
}

function Tex({ source, display }) {
  return html`<span class=${display ? "math-d" : ""} dangerouslySetInnerHTML=${{ __html: tex(source, display) }}></span>`;
}

function plain(text) {
  return String(text).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

function matches(f, sources, q) {
  if (!q) return true;
  const parts = [f.title, f.note, f.module, f.function || "", ...f.symbols.flatMap((s) => [s.meaning, s.tex, s.unit]),
    ...f.sources.map((k) => (sources[k] ? sources[k].citation : ""))];
  return plain(parts.join(" ")).includes(q);
}

function Formula({ f, sources }) {
  return html`<article class="formula">
    <div class="row"><h3>${f.title}</h3><span class="spacer"></span>
      ${f.sources.map((k) => sources[k]
        ? html`<a class="cite" href=${sources[k].url} target="_blank" rel="noopener noreferrer" title=${sources[k].citation}>[${sources[k].number}]</a>`
        : null)}
    </div>
    ${f.equations.map((e) => html`<div class="eq"><${Tex} source=${e} display=${true} /></div>`)}
    <table class="data symbols"><tbody>${f.symbols.map(
      (s) => html`<tr><td style="width: 22%"><${Tex} source=${s.tex} /></td><td>${s.meaning}</td><td class="unit">${s.unit}</td></tr>`,
    )}</tbody></table>
    ${f.note ? html`<p class="small">${f.note}</p>` : null}
    <p class="muted small">${t("ui-implemented")} <code>${f.module}</code>${f.function ? html` · <code>${f.function}()</code>` : null}</p>
  </article>`;
}

export function FormulasView() {
  const s = useAppState();
  const [q, setQ] = useState("");
  const [err, setErr] = useState(null);
  useEffect(() => {
    if (!s.formulas) api.get("/formulas").then((r) => setState({ formulas: r.data }), setErr);
  }, []);
  const data = s.formulas;
  const needle = plain(q.trim());
  const shown = useMemo(
    () => (data ? data.sections.map((sec) => ({ ...sec, formulas: sec.formulas.filter((f) => matches(f, data.sources, needle)) })) : []),
    [data, needle],
  );
  if (err) return html`<${ErrorBox} error=${err} />`;
  if (!data) return html`<p class="muted">…</p>`;
  const refs = Object.values(data.sources).sort((a, b) => a.number - b.number);
  const count = shown.reduce((n, sec) => n + sec.formulas.length, 0);
  return html`<div class="formulas">
    <${Panel} title=${t("ui-nav-formulas")}>
      <p class="muted" style="margin-top: 0">${t("ui-formulas-intro")}
        ${lang() === "de" ? " " + t("ui-formulas-language") : ""}</p>
      <div class="row no-print">
        <input type="text" id="formula-search" placeholder=${t("ui-search")} aria-label=${t("ui-search")} value=${q}
          onInput=${(e) => setQ(e.target.value)} />
        <span class="muted small" id="formula-count">${count}</span>
        <span class="spacer"></span>
        <${Btn} onClick=${() => window.print()}>${t("ui-print")}<//>
      </div>
    <//>
    ${count === 0 ? html`<p class="muted">${t("ui-no-match")}</p>` : null}
    ${shown.map((sec) => sec.formulas.length
      ? html`<section class="panel stage" id=${"formulas-" + sec.key}><h2>${sec.title}</h2>
          ${sec.formulas.map((f) => html`<${Formula} key=${f.title} f=${f} sources=${data.sources} />`)}</section>`
      : null)}
    <${Panel} title=${t("ui-references")} id="formula-references-panel">
      <ol id="formula-references">${refs.map(
        (r) => html`<li>${r.citation} <a href=${r.url} target="_blank" rel="noopener noreferrer">${r.doi ? "doi:" + r.doi : r.link_kind}</a>
          ${r.link_kind === "search" ? html` <span class="muted small">${t("ui-no-doi")}</span>` : null}</li>`,
      )}</ol>
    <//>
  </div>`;
}
