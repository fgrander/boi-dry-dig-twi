// Shared helpers of the web app pages (no build step; see research R1).
"use strict";

const twin = {
  async getJSON(url) {
    const r = await fetch(url, { headers: { Accept: "application/json" } });
    if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
    return r.json();
  },

  async postJSON(url, body) {
    const r = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
    });
    const data = r.status === 204 ? {} : await r.json();
    return { ok: r.ok, status: r.status, data };
  },

  fmt(value, digits = 3) {
    if (value === null || value === undefined || Number.isNaN(value)) return "–";
    return Number(value).toPrecision(digits);
  },
};
window.twin = twin;
