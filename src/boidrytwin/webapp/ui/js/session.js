// What the user does with the open scenario and the runs: open, edit, check, save, run, look
// at a run. The page computes nothing itself; every number comes from the service.

import { api, ApiError, enc } from "./api.js";
import { contentHash, getState, setState } from "./store.js";

const POLL_MS = 600;
const CHECK_AFTER_MS = 700;
export const MAX_PINS = 4;

// Result columns that the charts and tables use, if a run has them.
export const WANTED_COLUMNS = [
  "oil_outlet_temperature", "max_film_temperature", "furnace_temperature",
  "gas_temperature_after_heater_1", "gas_temperature_after_heater_2", "gas_temperature_after_heater_3",
  "gas_temperature_after_heater_4", "gas_temperature_after_heater_5", "flue_gas_to_dryer_temperature",
  "heat_released", "heat_to_oil", "fuel_feed", "fuel_delivered", "o2_dry_measured",
  "drum_inlet_gas_temperature", "exhaust_temperature", "exhaust_dew_point", "product_temperature",
  "product_moisture_wet_basis", "evaporation_rate", "product_dry_mass_flow", "bypass_position",
  "recirculation_damper_position", "recirculation_share", "flue_gas_to_dryer_mass_flow",
  "dilution_air_flow", "recirculation_mass_flow", "exhaust_mass_flow", "mixing_chamber_pressure",
  "mixing_chamber_pressure_setpoint",
];

let loadId = 0;
let checkTimer = null;
let checkSeq = 0;
let timeTimer = null;

// ----- the scenario -------------------------------------------------------------------------

export function fieldValue(f) {
  if (f.kind === "steps") return JSON.stringify(f.steps);
  if (f.kind === "quantity") return `${f.value ?? ""} ${f.unit ?? ""}`.trim();
  if (f.kind === "text" || f.kind === "number" || f.kind === "bool") return String(f.value ?? "");
  return f.raw;
}

function originalOf(form) {
  const out = {};
  for (const s of form.sections) for (const f of s.fields) out[`${s.name}|${f.key}`] = fieldValue(f);
  return out;
}

// What the run is computed from: the inputs only, not the issues attached for display.
function inputsOf(form) {
  return form.sections.map((s) => [s.name, s.fields.map((f) => [f.key, f.kind, fieldValue(f), !!f.remove])]);
}

export function scenarioHash() {
  const s = getState().scenario;
  return s ? contentHash(inputsOf(s.form)) : null;
}

export function scenarioTitle(scenario) {
  if (!scenario) return "";
  for (const s of scenario.form.sections) {
    if (s.name === "") {
      const f = s.fields.find((x) => x.key === "name");
      if (f && f.value) return f.value;
    }
  }
  return scenario.name;
}

export async function loadList() {
  const { data } = await api.get("/scenarios");
  setState({ list: data });
  return data;
}

export async function openScenario(name, source) {
  const { data } = await api.get(`/scenarios/${enc(name)}?source=${source}`);
  loadId += 1;
  // what "reset" goes back to; the service ignores these extra entries
  for (const section of data.sections) {
    for (const f of section.fields) {
      f.orig_kind = f.kind;
      f.orig_steps = f.steps ? JSON.stringify(f.steps) : null;
    }
  }
  const saved = (getState().list?.saved || []).find((x) => x.name === name);
  const scenario = {
    name,
    source,
    form: data,
    dirty: false,
    loadId,
    original: originalOf(data),
    derivedFrom: source === "saved" ? (saved?.derived_from || "") : "",
  };
  setState((s) => ({ scenario, valid: null, last: { ...(s.last || {}), name, source } }));
  await validateNow();
}

export function isChanged(section, field) {
  const s = getState().scenario;
  return !!s && s.original[`${section.name}|${field.key}`] !== fieldValue(field);
}

export function changedFields() {
  const s = getState().scenario;
  if (!s) return [];
  const out = [];
  for (const section of s.form.sections) {
    for (const field of section.fields) {
      const was = s.original[`${section.name}|${field.key}`];
      if (was !== fieldValue(field)) out.push({ section, field, was });
    }
  }
  return out;
}

function touch() {
  const s = getState().scenario;
  setState({ scenario: { ...s, dirty: changedFields().length > 0 }, valid: null });
  clearTimeout(checkTimer);
  checkTimer = setTimeout(validateNow, CHECK_AFTER_MS);
}

export function editField(field, patch) {
  Object.assign(field, patch);
  touch();
}

export function resetField(field) {
  field.kind = field.orig_kind;
  field.raw = field.orig_raw;
  field.value = field.orig_value;
  field.unit = field.orig_unit;
  field.steps = field.orig_steps ? JSON.parse(field.orig_steps) : null;
  touch();
}

function clearIssues(form) {
  form.issues = [];
  for (const s of form.sections) for (const f of s.fields) f.issues = [];
}

// Issues come back attached to a copy of the form; put them on the form being edited.
function takeIssues(form, checked) {
  clearIssues(form);
  form.issues = checked.issues || [];
  checked.sections.forEach((cs, i) => {
    const section = form.sections[i];
    if (!section) return;
    cs.fields.forEach((cf, j) => {
      if (section.fields[j]) section.fields[j].issues = cf.issues || [];
    });
  });
}

export function issueCount() {
  const s = getState().scenario;
  if (!s) return 0;
  let n = (s.form.issues || []).length;
  for (const section of s.form.sections) for (const f of section.fields) n += (f.issues || []).length;
  return n;
}

export async function validateNow() {
  const scenario = getState().scenario;
  if (!scenario) return;
  clearTimeout(checkTimer);
  const seq = ++checkSeq;
  setState({ validating: true });
  try {
    await api.post("/scenarios/validate", { form: scenario.form });
    if (seq !== checkSeq) return;
    clearIssues(scenario.form);
    setState({ valid: true, validating: false });
  } catch (e) {
    if (seq !== checkSeq) return;
    if (e instanceof ApiError && e.data && e.data.form) takeIssues(scenario.form, e.data.form);
    else scenario.form.issues = e.issues || [{ field: "", reason: String(e.message || e) }];
    setState({ valid: false, validating: false });
  }
}

export async function saveScenario() {
  const s = getState().scenario;
  await api.put(`/scenarios/${enc(s.name)}`, { form: s.form });
  await loadList();
  await openScenario(s.name, "saved");
}

export async function saveScenarioAs(name) {
  const s = getState().scenario;
  await api.post("/scenarios", { name, derived_from: s.derivedFrom || `${s.source}:${s.name}`, form: s.form });
  await loadList();
  await openScenario(name, "saved");
}

export async function renameScenario(name) {
  const s = getState().scenario;
  const { data } = await api.post(`/scenarios/${enc(s.name)}/rename`, { name });
  await loadList();
  await openScenario(data.name, "saved");
}

export async function deleteScenario() {
  const s = getState().scenario;
  await api.del(`/scenarios/${enc(s.name)}`);
  setState((st) => ({ scenario: null, valid: null, last: { ...(st.last || {}), name: null, source: null } }));
  await loadList();
}

export async function uploadScenario(file) {
  const { data } = await api.upload("/scenarios/upload", file);
  await loadList();
  await openScenario(data.name, "saved");
}

export async function addRecirculation() {
  const s = getState().scenario;
  await api.post(`/scenarios/${enc(s.name)}/recirculation`, {});
  await openScenario(s.name, "saved");
}

export function hasSection(prefix) {
  const s = getState().scenario;
  return !!s && s.form.sections.some((x) => x.name === prefix || x.name.startsWith(prefix + "."));
}

// ----- running --------------------------------------------------------------------------------

export function isRunning() {
  const job = getState().job;
  return !!job && (job.state === "queued" || job.state === "running");
}

export function isOutdated() {
  const { run, scenario } = getState();
  return !!run && !!scenario && !!run.hash && run.hash !== scenarioHash();
}

// Run the scenario as it is saved against a file of measurements (feature 003, US4).
export async function startComparison(file) {
  const s = getState().scenario;
  if (!s || isRunning()) return;
  const hash = scenarioHash();
  setState({ runError: null, job: { job_id: null, state: "queued", progress: null } });
  try {
    const { data } = await api.upload("/comparisons", file, { scenario: s.name, source: s.source }, "measured");
    setState({ job: { job_id: data.job_id, state: "queued", progress: null } });
    poll(data.job_id, hash);
  } catch (e) {
    setState({ job: null });
    throw e;
  }
}

async function poll(jobId, hash) {
  for (;;) {
    await new Promise((ok) => setTimeout(ok, POLL_MS));
    let job;
    try {
      job = (await api.get(`/jobs/${jobId}`)).data;
    } catch (e) {
      if (e.status === 0) continue; // the service is away: keep waiting
      setState({ job: null, runError: e });
      return;
    }
    if (getState().job?.job_id !== jobId) return; // another run was started
    setState({ job });
    if (job.state === "completed" && job.run_id) {
      await loadRun(job.run_id, hash);
      setState({ job: null });
      return;
    }
    if (job.state !== "queued" && job.state !== "running") {
      setState({ job: null, runError: { failed: job.state, message: job.message || "" } });
      if (job.run_id) await loadRun(job.run_id, hash).catch(() => {});
      return;
    }
  }
}

export async function runScenario() {
  const s = getState().scenario;
  if (!s || isRunning()) return;
  const hash = scenarioHash();
  setState({ runError: null, job: { job_id: null, state: "queued", progress: null } });
  try {
    const { data } = await api.post("/jobs/draft", {
      form: s.form,
      derived_from: s.derivedFrom || `${s.source}:${s.name}`,
      label: scenarioTitle(s),
    });
    setState({ job: { job_id: data.job_id, state: "queued", progress: null } });
    poll(data.job_id, hash);
  } catch (e) {
    if (e instanceof ApiError && e.data && e.data.form) takeIssues(s.form, e.data.form);
    setState({ job: null, runError: e, valid: e.status === 422 ? false : getState().valid });
  }
}

// ----- a run ------------------------------------------------------------------------------------

function columnsOf(info) {
  const have = new Set(info.columns || []);
  return WANTED_COLUMNS.filter((c) => have.has(c));
}

async function optional(path) {
  try {
    return (await api.get(path)).data;
  } catch (e) {
    if (e.status === 404 || e.status === 422) return null;
    throw e;
  }
}

async function runData(id) {
  const info = (await api.get(`/runs/${enc(id)}`)).data;
  const columns = columnsOf(info);
  const files = new Set(info.files || []);
  const [record, state, plot, profiles, comparison] = await Promise.all([
    api.get(`/runs/${enc(id)}/record`).then((r) => r.data),
    optional(`/runs/${enc(id)}/state`),
    columns.length ? optional(`/runs/${enc(id)}/plot?columns=${columns.join(",")}`) : null,
    // asked for only if the run folder has them, so that no call fails by design
    files.has("profiles.csv") ? optional(`/runs/${enc(id)}/profiles`) : null,
    files.has("validation_report.json") ? optional(`/runs/${enc(id)}/comparison`) : null,
  ]);
  return { id, info, record, state, plot, profiles, comparison };
}

export async function loadRun(id, hash = null) {
  const data = await runData(id);
  setState((s) => ({ run: { ...data, hash }, last: { ...(s.last || {}), run: id } }));
}

export function closeRun() {
  setState((s) => ({ run: null, last: { ...(s.last || {}), run: null } }));
}

// Show the values of another output time in the drawing, the key figures and the profiles.
export function setRunTime(iso) {
  const run = getState().run;
  if (!run || !run.state) return;
  setState({ run: { ...run, state: { ...run.state, time: iso }, pending: true } });
  clearTimeout(timeTimer);
  timeTimer = setTimeout(async () => {
    const id = run.id;
    const [state, profiles] = await Promise.all([
      optional(`/runs/${enc(id)}/state?time=${enc(iso)}`),
      run.profiles ? optional(`/runs/${enc(id)}/profiles?time=${enc(iso)}`) : null,
    ]);
    const now = getState().run;
    if (!now || now.id !== id || now.state.time !== iso) return;
    setState({ run: { ...now, state: state || now.state, profiles: profiles || now.profiles, pending: false } });
  }, 120);
}

// ----- pins -------------------------------------------------------------------------------------

export async function loadPins() {
  const { pins, pinPlots } = getState();
  for (const pin of pins) {
    if (pinPlots[pin.id]) continue;
    try {
      const data = await runData(pin.id);
      setState((s) => ({ pinPlots: { ...s.pinPlots, [pin.id]: data } }));
    } catch {
      setState((s) => ({ pins: s.pins.filter((p) => p.id !== pin.id) })); // the run is gone
    }
  }
}

export function pinRun() {
  const { run, pins } = getState();
  if (!run || pins.some((p) => p.id === run.id) || pins.length >= MAX_PINS) return;
  const label = run.record.scenario_name || run.id.slice(0, 8);
  setState((s) => ({ pins: [...s.pins, { id: run.id, label }], pinPlots: { ...s.pinPlots, [run.id]: run } }));
}

export function unpin(id) {
  setState((s) => ({ pins: s.pins.filter((p) => p.id !== id) }));
}
