// Scenario editor: sections and fields with value and unit, and a step editor for inputs
// that accept a time series (FR-007, FR-007a). Validation is done by the server (loader).
"use strict";

function scenarioEditor(name, source) {
  let form = null;
  const root = document.getElementById("form");
  const status = document.getElementById("status");

  function el(tag, attrs = {}, ...children) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "class") e.className = v; else if (k.startsWith("on")) e.addEventListener(k.slice(2), v); else e.setAttribute(k, v);
    }
    for (const c of children) e.append(c);
    return e;
  }

  function stepEditor(field) {
    const box = el("div", { class: "panel" });
    const s = field.steps;
    const unit = el("input", { type: "text", value: s.unit, size: 8, oninput: (ev) => { s.unit = ev.target.value; } });
    const start = el("input", { type: "number", step: "any", value: s.start_value,
      oninput: (ev) => { s.start_value = Number(ev.target.value); } });
    box.append(el("div", { class: "toolbar" }, "Start value ", start, " unit ", unit));
    s.steps.forEach((step, i) => {
      const time = el("input", { type: "text", value: step.time, size: 22,
        oninput: (ev) => { step.time = ev.target.value; } });
      const value = el("input", { type: "number", step: "any", value: step.value,
        oninput: (ev) => { step.value = Number(ev.target.value); } });
      const del = el("button", { class: "secondary", onclick: () => { s.steps.splice(i, 1); render(); } }, "remove");
      box.append(el("div", { class: "toolbar" }, "At (UTC) ", time, " → ", value, " ", del));
    });
    box.append(el("button", { class: "secondary", onclick: () => {
      const last = s.steps.length ? s.steps[s.steps.length - 1] : null;
      s.steps.push({ time: last ? last.time : "2026-01-01T06:00:00Z", value: last ? last.value : s.start_value });
      render();
    } }, "add step"));
    return box;
  }

  function fieldRow(field) {
    const row = el("div", { class: "field" });
    row.append(el("label", {}, field.key));
    if (field.kind === "quantity") {
      row.append(el("input", { type: "text", value: field.value ?? "", oninput: (ev) => { field.value = ev.target.value; } }));
      row.append(el("input", { type: "text", value: field.unit ?? "", oninput: (ev) => { field.unit = ev.target.value; } }));
    } else if (field.kind === "steps") {
      row.append(stepEditor(field));
      row.append(el("button", { class: "secondary", onclick: () => {
        field.kind = "quantity"; field.value = String(field.steps.start_value); field.unit = field.steps.unit; field.steps = null; render();
      } }, "fixed value"));
    } else if (field.kind === "series_file") {
      row.append(el("span", { class: "note" }, `time series: ${field.value} (${field.unit})`));
      row.append(el("span"));
    } else if (field.kind === "text" || field.kind === "number" || field.kind === "bool") {
      row.append(el("input", { type: "text", value: field.value ?? "", oninput: (ev) => { field.value = ev.target.value; } }));
      row.append(el("span"));
    } else {
      row.append(el("input", { type: "text", value: field.raw, oninput: (ev) => { field.raw = ev.target.value; } }));
      row.append(el("span"));
    }
    if (field.series_ok && field.kind !== "steps") {
      row.append(el("button", { class: "secondary", onclick: () => {
        const start = Number(field.value);
        field.kind = "steps";
        field.steps = { unit: field.unit || "", start_value: Number.isFinite(start) ? start : 0, steps: [] };
        render();
      } }, "step editor"));
    }
    for (const issue of field.issues || []) {
      row.append(el("div", { class: "issue" }, `${issue.reason}${issue.allowed ? " (allowed: " + issue.allowed + ")" : ""}`));
    }
    return row;
  }

  function render() {
    root.innerHTML = "";
    for (const section of form.sections) {
      const panel = el("section", { class: "panel" }, el("h2", {}, section.name || "general"));
      for (const f of section.fields) panel.append(fieldRow(f));
      root.append(panel);
    }
    const formIssues = document.getElementById("form-issues");
    formIssues.textContent = (form.issues || []).map((i) => `${i.field}: ${i.reason}`).join("; ");
  }

  async function check() {
    const r = await twin.postJSON("/api/scenarios/validate", { form });
    if (r.ok) { status.textContent = "All inputs are valid."; status.className = "ok"; clearIssues(); render(); return true; }
    if (r.data.form) { form = r.data.form; render(); }
    status.textContent = twin.issueText(r.data); status.className = "bad";
    return false;
  }

  function clearIssues() {
    form.issues = [];
    for (const s of form.sections) for (const f of s.fields) f.issues = [];
  }

  async function save() {
    const newName = document.getElementById("save-name").value.trim();
    if (!newName) { status.textContent = "Enter a name to save under."; status.className = "bad"; return null; }
    const r = await twin.postJSON("/api/scenarios", { name: newName, derived_from: `${source}:${name}`, form });
    if (r.ok) { status.textContent = `Saved as ${newName}.`; status.className = "ok"; return newName; }
    if (r.data.form) { form = r.data.form; render(); }
    status.textContent = twin.issueText(r.data); status.className = "bad";
    return null;
  }

  document.getElementById("validate").addEventListener("click", check);
  document.getElementById("save").addEventListener("click", async () => {
    const saved = await save();
    if (saved) window.location = `/scenarios/${saved}?source=saved`;
  });
  document.getElementById("save-run").addEventListener("click", async () => {
    const saved = await save();
    if (!saved) return;
    const r = await twin.postJSON("/api/jobs", { scenario: saved, source: "saved" });
    if (r.ok) window.location = "/queue"; else { status.textContent = twin.issueText(r.data); status.className = "bad"; }
  });

  const addRecirculation = document.getElementById("add-recirculation");
  if (addRecirculation) addRecirculation.addEventListener("click", async () => {
    // appends the default [recirculation] block to the saved file (feature 004)
    const r = await twin.postJSON(`/api/scenarios/${name}/recirculation`, {});
    if (r.ok) { window.location.reload(); return; }
    status.textContent = r.data.detail || twin.issueText(r.data); status.className = "bad";
  });

  twin.getJSON(`/api/scenarios/${name}?source=${source}`).then((data) => { form = data; render(); });
}
window.scenarioEditor = scenarioEditor;
