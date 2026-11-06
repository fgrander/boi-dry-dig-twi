// One input of the scenario: value and unit, a step sequence, a time series from a file, or
// the text as it stands in the file. The service checks the values, not the page.

import { html } from "../html.js";
import { keyLabel, t } from "../i18n.js";
import { editField, isChanged, resetField } from "../session.js";
import { Issues } from "./common.js";

function Steps({ field, id }) {
  const seq = field.steps;
  const change = (patch) => editField(field, { steps: { ...seq, ...patch } });
  const setStep = (i, patch) => change({ steps: seq.steps.map((x, j) => (j === i ? { ...x, ...patch } : x)) });
  const add = () => {
    const last = seq.steps[seq.steps.length - 1];
    change({ steps: [...seq.steps, { time: last ? last.time : "2026-01-01T06:00:00Z", value: last ? last.value : seq.start_value }] });
  };
  return html`<div class="steps" role="group" aria-label=${t("ui-steps")}>
    <div class="row"><span>${t("ui-steps-start")}</span>
      <input type="text" class="num" id=${id + "-start"} value=${seq.start_value}
        onInput=${(e) => change({ start_value: Number(e.target.value.replace(",", ".")) })} />
      <input type="text" class="unit-in" aria-label=${t("ui-unit")} value=${seq.unit}
        onInput=${(e) => change({ unit: e.target.value })} /></div>
    ${seq.steps.map(
      (step, i) => html`<div class="row"><span>${t("ui-steps-at")}</span>
        <input type="text" style="width: 14rem" value=${step.time} onInput=${(e) => setStep(i, { time: e.target.value })} />
        <span>→</span>
        <input type="text" class="num" value=${step.value}
          onInput=${(e) => setStep(i, { value: Number(e.target.value.replace(",", ".")) })} />
        <button type="button" class="link" onClick=${() => change({ steps: seq.steps.filter((_, j) => j !== i) })}>
          ${t("ui-steps-remove")}</button></div>`,
    )}
    <div class="row"><button type="button" class="link" onClick=${add}>${t("ui-steps-add")}</button>
      <button type="button" class="link" onClick=${() =>
        editField(field, { kind: "quantity", value: String(seq.start_value), unit: seq.unit, steps: null })}>
        ${t("ui-steps-fixed")}</button></div>
  </div>`;
}

export function Field({ section, field }) {
  const id = `f-${section.name}-${field.key}`.replace(/[^A-Za-z0-9_-]/g, "_");
  const changed = isChanged(section, field);
  const label = keyLabel(field.key);
  let input;
  let unit = html`<span></span>`;
  if (field.kind === "quantity") {
    input = html`<input type="text" inputmode="decimal" class="num" id=${id} value=${field.value ?? ""}
      onInput=${(e) => editField(field, { value: e.target.value.trim().replace(",", ".") })} />`;
    unit = html`<input type="text" class="unit-in" aria-label=${t("ui-unit") + ": " + label} value=${field.unit ?? ""}
      onInput=${(e) => editField(field, { unit: e.target.value })} />`;
  } else if (field.kind === "number") {
    input = html`<input type="text" inputmode="decimal" class="num" id=${id} value=${field.value ?? ""}
      onInput=${(e) => editField(field, { value: e.target.value.trim().replace(",", ".") })} />`;
  } else if (field.kind === "text" || field.kind === "bool") {
    input = html`<input type="text" class=${field.key === "name" ? "wide" : ""} id=${id} value=${field.value ?? ""}
      onInput=${(e) => editField(field, { value: e.target.value })} />`;
  } else if (field.kind === "steps") {
    input = html`<span class="muted small" id=${id}>${t("ui-steps")}</span>`;
  } else if (field.kind === "series_file") {
    input = html`<span class="muted small" id=${id}>${t("ui-series", { file: field.value, column: field.unit })}</span>`;
  } else {
    input = html`<input type="text" class="wide" id=${id} value=${field.raw}
      onInput=${(e) => editField(field, { raw: e.target.value })} />`;
  }
  const canStep = field.series_ok && field.kind === "quantity";
  return html`<div class="field ${changed ? "changed" : ""}" data-key=${field.key}>
    <label class="label" for=${id}>${label}<code>${field.key}</code></label>
    ${input}${unit}
    <span class="marks">
      ${canStep
        ? html`<button type="button" class="link" onClick=${() => {
            const start = Number(field.value);
            editField(field, { kind: "steps", steps: { unit: field.unit || "", start_value: Number.isFinite(start) ? start : 0, steps: [] } });
          }}>${t("ui-steps-edit")}</button>`
        : null}
      ${changed
        ? html`<button type="button" class="link" aria-label=${t("ui-reset") + ": " + label}
            onClick=${() => resetField(field)}>${t("ui-reset")}</button>`
        : null}
    </span>
    ${field.kind === "steps" ? html`<${Steps} field=${field} id=${id} />` : null}
    ${changed && field.orig_kind !== "steps" && field.orig_kind !== "other"
      ? html`<div class="hint">${t("ui-was", { v: `${field.orig_value ?? ""} ${field.orig_kind === "quantity" ? field.orig_unit ?? "" : ""}`.trim() })}</div>`
      : null}
    <${Issues} issues=${field.issues} />
  </div>`;
}
