// Service access: every call goes to /api of this origin. Errors arrive as
// {"issues": [...]} (validation) or {"error": "..."} and are raised as ApiError.

export class ApiError extends Error {
  constructor(status, issues, data = null) {
    super(issues.map((i) => (i.field ? `${i.field}: ` : "") + (i.reason || i.message || "")).join("; "));
    this.status = status;
    this.issues = issues;
    this.data = data;
  }
}

const listeners = new Set();
let online = true;

export function onServiceStatus(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

function setOnline(ok) {
  if (ok !== online) {
    online = ok;
    listeners.forEach((fn) => fn(ok));
  }
}

async function request(method, path, { json, form } = {}) {
  let body;
  let headers = {};
  if (json !== undefined) {
    body = JSON.stringify(json);
    headers = { "Content-Type": "application/json" };
  } else if (form) {
    body = form;
  }
  let r;
  try {
    r = await fetch(`/api${path}`, { method, headers, body, credentials: "same-origin" });
  } catch (e) {
    setOnline(false);
    throw new ApiError(0, [{ reason: String(e) }]);
  }
  setOnline(true);
  const data = r.status === 204 ? null : await r.json().catch(() => null);
  if (!r.ok) {
    const issues = (data && data.issues) || [{ reason: (data && (data.error || data.detail)) || r.statusText }];
    throw new ApiError(r.status, issues, data);
  }
  return { data, status: r.status };
}

export const api = {
  get: (path) => request("GET", path),
  post: (path, json) => request("POST", path, { json }),
  put: (path, json) => request("PUT", path, { json }),
  del: (path) => request("DELETE", path),
  upload(path, file, fields = {}, name = "file") {
    const form = new FormData();
    form.append(name, file, file.name);
    for (const [k, v] of Object.entries(fields)) form.append(k, v);
    return request("POST", path, { form });
  },
};

// The drawings are served outside /api.
export async function fetchText(path) {
  const r = await fetch(path, { credentials: "same-origin" });
  if (!r.ok) throw new ApiError(r.status, [{ reason: r.statusText }]);
  return r.text();
}

// Wait for the service after a loss: retry with a growing pause of 1 to 10 s.
export async function waitForService() {
  let delay = 1000;
  for (;;) {
    try {
      await request("GET", "/ui/about");
      return;
    } catch {
      await new Promise((ok) => setTimeout(ok, delay));
      delay = Math.min(10000, delay * 2);
    }
  }
}

export function enc(name) {
  return encodeURIComponent(name);
}
