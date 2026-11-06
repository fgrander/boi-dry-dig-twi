// Number and time formatting by language (decimal comma in German).

const LOCALE = { de: "de-DE", en: "en-GB" };
const cache = new Map();

function formatter(lang, digits) {
  const key = `${lang}:${digits}`;
  if (!cache.has(key)) {
    cache.set(
      key,
      new Intl.NumberFormat(LOCALE[lang] || "de-DE", { maximumSignificantDigits: digits, useGrouping: false }),
    );
  }
  return cache.get(key);
}

export function fmt(value, lang, digits = 4) {
  if (value === null || value === undefined || Number.isNaN(value)) return "–";
  if (typeof value === "boolean") return value ? "✓" : "✗";
  if (typeof value !== "number") return String(value);
  if (!Number.isFinite(value)) return "–";
  if (value !== 0 && (Math.abs(value) < 1e-3 || Math.abs(value) >= 1e7)) {
    const s = value.toExponential(digits - 1);
    return lang === "de" ? s.replace(".", ",") : s;
  }
  return formatter(lang, digits).format(value);
}

// A text from the service such as "22.5 %": only the decimal sign follows the language.
export function localText(text, lang) {
  if (typeof text !== "string") return "–";
  return lang === "de" ? text.replace(/(\d)\.(\d)/g, "$1,$2") : text;
}

export function fmtTime(iso, lang) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "–";
  return d.toLocaleString(LOCALE[lang] || "de-DE", { dateStyle: "short", timeStyle: "short" });
}

// Hours and minutes since the start of a run, e.g. "06:30 h".
export function fmtHours(hours) {
  if (!Number.isFinite(hours)) return "–";
  const minutes = Math.round(hours * 60);
  return `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")} h`;
}
