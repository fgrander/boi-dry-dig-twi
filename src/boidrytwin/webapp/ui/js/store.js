// Application state: one object, subscriptions, persistence. Language, pins and the last
// opened scenario and run live in localStorage; every storage access is guarded, so the page
// works without storage.

import { useEffect, useState } from "preact/hooks";

function load(storage, key, fallback) {
  try {
    const v = storage.getItem(key);
    return v === null ? fallback : JSON.parse(v);
  } catch {
    return fallback;
  }
}

function save(storage, key, value) {
  try {
    if (value === undefined || value === null) storage.removeItem(key);
    else storage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage unavailable or full: keep working in memory */
  }
}

const LS = typeof localStorage === "undefined" ? null : localStorage;

const state = {
  lang: LS ? load(LS, "boidry.lang", "de") : "de",
  view: "set",
  diagramHidden: LS ? load(LS, "boidry.diagramHidden", false) : false,
  online: true,
  about: null,
  list: null, // {examples, saved}
  scenario: null, // {name, source, form, dirty, loadId, original}
  valid: null, // null: not checked yet
  validating: false,
  job: null, // {job_id, state, progress, message}
  runError: null,
  run: null, // {id, info, record, plot, state, profiles, hash}
  pins: LS ? load(LS, "boidry.pins", []) : [], // [{id, label}]
  pinPlots: {}, // run id -> plot
  last: LS ? load(LS, "boidry.last", null) : null, // {name, source, run}
  formulas: null,
};

const subs = new Set();

export function getState() {
  return state;
}

export function setState(patch) {
  Object.assign(state, typeof patch === "function" ? patch(state) : patch);
  if (LS) {
    save(LS, "boidry.lang", state.lang);
    save(LS, "boidry.pins", state.pins);
    save(LS, "boidry.last", state.last);
    save(LS, "boidry.diagramHidden", state.diagramHidden || null);
  }
  subs.forEach((fn) => fn(state));
}

export function subscribe(fn) {
  subs.add(fn);
  return () => subs.delete(fn);
}

// Preact hook: draw again when the state changes.
export function useAppState() {
  const [, tick] = useState(0);
  useEffect(() => subscribe(() => tick((n) => n + 1)), []);
  return state;
}

// Stable hash of a value, to tell that the results belong to an older scenario.
export function contentHash(content) {
  const str = JSON.stringify(content || {});
  let h = 0x811c9dc5; // FNV-1a
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return `${h.toString(16)}-${str.length}`;
}
