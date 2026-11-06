// Small shared components: issue lists, dialogs, buttons, panels.

import { useEffect, useRef } from "preact/hooks";
import { html } from "../html.js";

// An issue of the twin's loader: field, reason and what is allowed.
export function Issues({ issues }) {
  const list = issues || [];
  if (!list.length) return null;
  return html`<div class="issues">
    ${list.map(
      (i) => html`<div class="issue error" role="alert">
        ${i.field ? html`<b>${i.field}</b>: ` : null}${i.reason || i.message || ""}
        ${i.allowed ? html` <span class="small">(${i.allowed})</span>` : null}
        ${i.location ? html` <span class="muted small">${i.location}</span>` : null}
      </div>`,
    )}
  </div>`;
}

export function ErrorBox({ error }) {
  if (!error) return null;
  const issues = error.issues || [{ reason: String(error.message || error) }];
  return html`<${Issues} issues=${issues} />`;
}

export function Dialog({ open, title, onClose, children }) {
  const ref = useRef(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return html`<dialog ref=${ref} onClose=${onClose} aria-label=${title}>
    <h2>${title}</h2>
    ${open ? children : null}
  </dialog>`;
}

export function Btn({ onClick, children, primary, disabled, title, id }) {
  return html`<button type="button" id=${id} class="btn ${primary ? "primary" : ""}" onClick=${onClick}
    disabled=${disabled} title=${title}>${children}</button>`;
}

export function Panel({ title, children, id, extra }) {
  return html`<section class="panel" id=${id} aria-label=${title}>
    <div class="row"><h2>${title}</h2><span class="spacer"></span>${extra}</div>
    ${children}
  </section>`;
}
