// Entry point: the header, the tabs and the drawing band around the four views.

import { useEffect, useState } from "preact/hooks";
import { api, onServiceStatus, waitForService } from "./api.js";
import { html, render } from "./html.js";
import { LANGS, t } from "./i18n.js";
import { getState, setState, useAppState } from "./store.js";
import { loadList, loadRun, openScenario, scenarioTitle } from "./session.js";
import { Diagram } from "./components/diagram.js";
import { SetView } from "./views/set.js";
import { ResultsView } from "./views/results.js";
import { DataView } from "./views/data.js";
import { FormulasView } from "./views/formulas.js";
import { ReportView } from "./views/report.js";

const VIEWS = [
  ["set", "ui-nav-set", SetView],
  ["results", "ui-nav-results", ResultsView],
  ["data", "ui-nav-data", DataView],
  ["formulas", "ui-nav-formulas", FormulasView],
  ["report", "ui-nav-report", ReportView],
];

// The drawings are made by the service in the language of this cookie.
function useLanguage(lang) {
  document.cookie = `lang=${lang}; path=/; max-age=${10 * 365 * 24 * 3600}; samesite=lax`;
  document.documentElement.lang = lang;
  document.title = t("ui-title");
}

function viewFromHash() {
  const id = location.hash.replace(/^#/, "");
  return VIEWS.some((v) => v[0] === id) ? id : null;
}

function selectView(id) {
  history.replaceState(null, "", `#${id}`);
  setState({ view: id });
}

function Header() {
  const s = useAppState();
  const sc = s.scenario;
  return html`<header class="top">
    <h1>${t("ui-title")}</h1>
    ${sc
      ? html`<span id="set-badge" title=${scenarioTitle(sc)}>${sc.name}
          ${sc.source === "example" ? html` <span class="badge readonly">${t("ui-example")}</span>` : null}
          ${sc.dirty ? html` <span class="badge dirty">${t("ui-unsaved")}</span>` : null}</span>`
      : html`<span class="muted" id="set-badge">${t("ui-no-set")}</span>`}
    <span class="spacer"></span>
    <a class="small" href="/classic" id="link-classic">${t("ui-classic")}</a>
    <span role="group" aria-label=${t("ui-language")}>
      ${LANGS.map(
        (l) => html`<button type="button" class="btn" id=${"lang-" + l} aria-pressed=${s.lang === l}
          onClick=${() => { useLanguage(l); setState({ lang: l }); }}>${l.toUpperCase()}</button>`,
      )}
    </span>
    <span class="status-dot ${s.online ? "" : "off"}" title=${s.online ? t("ui-online") : t("ui-offline")}></span>
  </header>`;
}

function App() {
  const s = useAppState();
  useEffect(() => {
    const follow = () => {
      const id = viewFromHash();
      if (id) setState({ view: id });
    };
    follow();
    window.addEventListener("hashchange", follow);
    return () => window.removeEventListener("hashchange", follow);
  }, []);
  useEffect(
    () =>
      onServiceStatus((ok) => {
        setState({ online: ok });
        if (!ok) waitForService().then(() => setState({ online: true }));
      }),
    [],
  );
  const View = (VIEWS.find((v) => v[0] === s.view) || VIEWS[0])[2];
  const about = s.about;
  return html`
    <${Header} />
    ${about
      ? html`<p class="ai-note small muted" id="ai-note">${t("ui-ai-note", {
          who: about.guided_by, hours: String(about.ai_work_hours).replace(".", s.lang === "de" ? "," : ".") })}</p>`
      : null}
    ${s.online ? null : html`<div class="banner" role="alert">${t("ui-service-lost")}</div>`}
    <nav class="views" role="tablist" aria-label=${t("ui-navigation")}>
      ${VIEWS.map(
        ([id, key]) => html`<button role="tab" id=${"nav-" + id} aria-selected=${s.view === id}
          onClick=${() => selectView(id)}>${t(key)}</button>`,
      )}
    </nav>
    <div class="band diagram"><${Diagram} /></div>
    <main role="tabpanel"><${View} /></main>`;
}

function Boot() {
  const [ready, setReady] = useState(false);
  const [err, setErr] = useState(null);
  useEffect(() => {
    (async () => {
      try {
        useLanguage(getState().lang);
        const [about] = await Promise.all([api.get("/ui/about"), loadList()]);
        setState({ about: about.data });
        // come back to what was open; a scenario or run that is gone is simply not opened
        const last = getState().last;
        if (last && last.name) await openScenario(last.name, last.source).catch(() => {});
        if (last && last.run) await loadRun(last.run).catch(() => {});
        setReady(true);
      } catch (e) {
        setErr(String(e.message || e));
      }
    })();
  }, []);
  if (err) return html`<p class="banner" role="alert">${err}</p>`;
  return ready ? html`<${App} />` : html`<p class="boot">…</p>`;
}

render(html`<${Boot} />`, document.getElementById("app"));
