// CSV export: ";" and decimal comma for German, "," and point for English.

export function toCSV(headers, rows, lang) {
  const sep = lang === "de" ? ";" : ",";
  const cell = (v) => {
    if (v === null || v === undefined || (typeof v === "number" && !Number.isFinite(v))) return "";
    let s = String(v);
    if (typeof v === "number" && lang === "de") s = s.replace(".", ",");
    return s.includes(sep) || /["\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [headers, ...rows].map((r) => r.map(cell).join(sep)).join("\r\n") + "\r\n";
}

export function download(filename, content, type = "text/csv;charset=utf-8") {
  const blob = content instanceof Blob ? content : new Blob(["﻿", content], { type });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    URL.revokeObjectURL(a.href);
    a.remove();
  }, 0);
}
