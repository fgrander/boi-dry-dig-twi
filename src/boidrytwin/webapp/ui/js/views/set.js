// Scenario view: new from an example, open, save, save as, rename, delete, download, upload,
// and the inputs by section with the issues of the twin's own check at each input.

import { useEffect, useRef, useState } from "preact/hooks";
import { enc } from "../api.js";
import { html } from "../html.js";
import { keyLabel, sectionLabel, t } from "../i18n.js";
import { useAppState } from "../store.js";
import {
  addRecirculation,
  deleteScenario,
  hasSection,
  isChanged,
  issueCount,
  loadList,
  openScenario,
  renameScenario,
  saveScenario,
  saveScenarioAs,
  uploadScenario,
} from "../session.js";
import { Btn, Dialog, ErrorBox, Issues, Panel } from "../components/common.js";
import { Field } from "../components/field.js";

function discardOk(s) {
  return !s.scenario || !s.scenario.dirty || window.confirm(t("ui-confirm-discard"));
}

function OpenDialog({ open, onClose }) {
  const s = useAppState();
  const [err, setErr] = useState(null);
  useEffect(() => {
    if (open) loadList().catch(setErr);
  }, [open]);
  const pick = async (item) => {
    try {
      await openScenario(item.name, item.source);
      onClose();
    } catch (e) {
      setErr(e);
    }
  };
  const table = (items, id) => html`<table class="data" id=${id}><tbody>${items.map(
    (item) => html`<tr><td><b>${item.name}</b><div class="small muted">${item.title}</div>
        ${item.derived_from ? html`<div class="small muted">${t("ui-derived")} ${item.derived_from}</div>` : null}</td>
      <td style="width: 1%"><button type="button" class="btn" data-open=${item.name}
        onClick=${() => pick(item)}>${t("ui-open")}</button></td></tr>`,
  )}</tbody></table>`;
  const list = s.list;
  return html`<${Dialog} open=${open} title=${t("ui-open-set")} onClose=${onClose}>
    <${ErrorBox} error=${err} />
    <h3>${t("ui-saved-sets")}</h3>
    ${list && list.saved.length ? table(list.saved, "open-saved") : html`<p class="muted">${t("ui-no-sets")}</p>`}
    <h3>${t("ui-examples")}</h3>
    ${list ? html`<div class="tablewrap">${table(list.examples, "open-examples")}</div>` : null}
    <div class="row" style="margin-top: .6rem"><span class="spacer"></span><${Btn} onClick=${onClose}>${t("ui-close")}<//></div>
  <//>`;
}

function NameDialog({ open, title, initial, onClose, onOk }) {
  const [name, setName] = useState(initial || "");
  const [err, setErr] = useState(null);
  useEffect(() => {
    if (open) {
      setName(initial || "");
      setErr(null);
    }
  }, [open]);
  const ok = async () => {
    try {
      await onOk(name.trim());
      onClose();
    } catch (e) {
      setErr(e);
    }
  };
  return html`<${Dialog} open=${open} title=${title} onClose=${onClose}>
    <label class="row">${t("ui-name")}
      <input type="text" id="name-input" value=${name} onInput=${(e) => setName(e.target.value)}
        onKeyDown=${(e) => e.key === "Enter" && ok()} /></label>
    <p class="muted small">${t("ui-name-rule")}</p>
    <${ErrorBox} error=${err} />
    <div class="row"><span class="spacer"></span>
      <${Btn} onClick=${onClose}>${t("ui-cancel")}<//><${Btn} primary id="name-ok" onClick=${ok}>${t("ui-ok")}<//></div>
  <//>`;
}

function Toolbar() {
  const s = useAppState();
  const [dlg, setDlg] = useState(null);
  const [err, setErr] = useState(null);
  const [example, setExample] = useState("plant_recirculation");
  const fileRef = useRef(null);
  const examples = s.list ? s.list.examples : [];
  const sc = s.scenario;
  const saved = !!sc && sc.source === "saved";
  const valid = s.valid === true;
  const guard = (fn) => async () => {
    setErr(null);
    try {
      await fn();
    } catch (e) {
      setErr(e);
    }
  };
  const create = guard(async () => {
    if (discardOk(s)) await openScenario(example, "example");
  });
  const upload = guard(async () => {
    const f = fileRef.current.files[0];
    if (!f) return;
    try {
      await uploadScenario(f);
    } finally {
      fileRef.current.value = "";
    }
  });
  const del = guard(async () => {
    if (window.confirm(t("ui-confirm-delete", { name: sc.name }))) await deleteScenario();
  });
  return html`<div class="row" role="toolbar" aria-label=${t("ui-set-actions")}>
    <select aria-label=${t("ui-new-from")} id="new-example" value=${example} onChange=${(e) => setExample(e.target.value)}>
      ${examples.map((x) => html`<option value=${x.name}>${x.name}</option>`)}
    </select>
    <${Btn} id="btn-new" onClick=${create}>${t("ui-new")}<//>
    <${Btn} id="btn-open" onClick=${() => discardOk(s) && setDlg("open")}>${t("ui-open")}<//>
    <${Btn} id="btn-save" primary disabled=${!saved || !valid || !sc.dirty} onClick=${guard(saveScenario)}>${t("ui-save")}<//>
    <${Btn} id="btn-saveas" disabled=${!sc || !valid} onClick=${() => setDlg("saveas")}>${t("ui-save-as")}<//>
    <${Btn} id="btn-rename" disabled=${!saved || sc.dirty} onClick=${() => setDlg("rename")}>${t("ui-rename")}<//>
    <${Btn} id="btn-delete" disabled=${!saved} onClick=${del}>${t("ui-delete")}<//>
    ${sc && !sc.dirty
      ? html`<a class="btn" id="btn-download" href=${`/api/scenarios/${enc(sc.name)}/file?source=${sc.source}`}>${t("ui-download")}</a>`
      : null}
    <label class="btn">${t("ui-upload")}<input type="file" accept=".toml" class="visually-hidden" id="set-upload"
      ref=${fileRef} onChange=${upload} /></label>
    ${saved && !sc.dirty && hasSection("dryer") && !hasSection("recirculation")
      ? html`<${Btn} id="btn-recirculation" onClick=${guard(addRecirculation)}>${t("ui-add-recirculation")}<//>`
      : null}
    <${ErrorBox} error=${err} />
    <${OpenDialog} open=${dlg === "open"} onClose=${() => setDlg(null)} />
    <${NameDialog} open=${dlg === "saveas"} title=${t("ui-save-as")} initial=${sc ? (saved ? sc.name + "_2" : sc.name + "_1") : ""}
      onClose=${() => setDlg(null)} onOk=${saveScenarioAs} />
    <${NameDialog} open=${dlg === "rename"} title=${t("ui-rename")} initial=${sc ? sc.name : ""}
      onClose=${() => setDlg(null)} onOk=${renameScenario} />
  </div>`;
}

export function SetView() {
  const s = useAppState();
  const [filter, setFilter] = useState({ changed: false, q: "" });
  const sc = s.scenario;
  if (!sc) {
    return html`<${Panel} title=${t("ui-set")}><${Toolbar} /><p class="muted" id="start-hint">${t("ui-start-hint")}</p><//>`;
  }
  const q = filter.q.trim().toLowerCase();
  const visible = (section, f) =>
    (!filter.changed || isChanged(section, f)) &&
    (!q || f.key.toLowerCase().includes(q) || keyLabel(f.key).toLowerCase().includes(q) ||
      sectionLabel(section.name).toLowerCase().includes(q));
  const errors = issueCount();
  return html`<div>
    <${Panel} title=${t("ui-set")}><${Toolbar} />
      <div class="row small" style="margin-top: .5rem">
        <label><input type="checkbox" id="filter-changed" checked=${filter.changed}
          onChange=${(e) => setFilter({ ...filter, changed: e.target.checked })} /> ${t("ui-filter-changed")}</label>
        <input type="text" id="filter-q" placeholder=${t("ui-search")} aria-label=${t("ui-search")} value=${filter.q}
          onInput=${(e) => setFilter({ ...filter, q: e.target.value })} />
        <span id="check-state" class=${s.valid === false ? "fail" : "muted"}>
          ${s.validating ? t("ui-checking") : s.valid === true ? t("ui-valid") : s.valid === false ? t("ui-invalid", { n: errors }) : ""}</span>
      </div>
      ${sc.source === "example" ? html`<p class="muted small">${t("ui-readonly-hint")}</p>` : null}
      <${Issues} issues=${sc.form.issues} />
    <//>
    <${Panel} title=${t("ui-parameters")} id="form" key=${sc.loadId}>
      ${sc.form.sections.map((section) => {
        const fields = section.fields.filter((f) => visible(section, f));
        if (!fields.length) return null;
        const nChanged = section.fields.filter((f) => isChanged(section, f)).length;
        return html`<details class="group" open data-group=${section.name}>
          <summary>${sectionLabel(section.name)}
            ${section.name ? html`<span class="path">[${section.name}]</span>` : null}
            ${nChanged ? html` <span class="badge">${t("ui-changed-n", { n: nChanged })}</span>` : null}</summary>
          ${fields.map((f) => html`<${Field} key=${section.name + "|" + f.key} section=${section} field=${f} />`)}
        </details>`;
      })}
    <//>
  </div>`;
}
