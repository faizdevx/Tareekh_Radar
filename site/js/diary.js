// My Case Diary: stored only in this browser (localStorage). No account, no server.

const KEY = "cc-diary-v1";
const DATE = /^\d{4}-\d{2}-\d{2}$/;
export const ADJ_BY = ["none", "mine", "other", "court", "unknown"];

export function loadDiary(storage = globalThis.localStorage) {
  try { return sanitizeDiary(JSON.parse(storage.getItem(KEY) || "null")) || { cases: [] }; } catch (_) { return { cases: [] }; }
}
/** Returns false when storage is blocked or full, so the UI can warn instead of silently losing data. */
export function saveDiary(diary, storage = globalThis.localStorage) {
  try { storage.setItem(KEY, JSON.stringify(diary)); return true; } catch (_) { return false; }
}
export const newId = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 7);

const str = (v, max) => (typeof v === "string" ? v.slice(0, max) : "");
const date = (v) => (typeof v === "string" && DATE.test(v) ? v : "");

/** Trust boundary for imported files and stored data: keep only known fields, as bounded strings. */
export function sanitizeDiary(raw) {
  if (!raw || typeof raw !== "object" || !Array.isArray(raw.cases)) return null;
  const cases = raw.cases.slice(0, 200).filter((c) => c && typeof c === "object").map((c) => ({
    id: str(c.id, 40) || newId(), label: str(c.label, 120) || "Case", cnr: str(c.cnr, 24).toUpperCase(),
    s: str(c.s, 4), d: str(c.d, 12), c: str(c.c, 40), filed: date(c.filed), court: str(c.court, 160),
    entries: (Array.isArray(c.entries) ? c.entries : []).slice(0, 2000).filter((e) => e && date(e.date)).map((e) => ({
      id: str(e.id, 40) || newId(), date: date(e.date), happened: str(e.happened, 2000), next: date(e.next),
      purpose: str(e.purpose, 200), adjBy: ADJ_BY.includes(e.adjBy) ? e.adjBy : "none",
    })),
  }));
  return { cases };
}

export const sortedEntries = (c) => [...(c.entries || [])].sort((a, b) => a.date.localeCompare(b.date));

/** Latest known hearing, next date and adjournment counts for a case. */
export function caseSummary(c) {
  const e = sortedEntries(c);
  const last = e[e.length - 1];
  const adj = Object.fromEntries(ADJ_BY.map((k) => [k, 0]));
  for (const x of e) adj[x.adjBy] += 1;
  return { hearings: e.length, last: last?.date || "", next: last?.next || "", purpose: last?.purpose || "", adj };
}

const dayMs = 86400000;
export const daysBetween = (a, b) => Math.round((Date.parse(b + "T00:00:00Z") - Date.parse(a + "T00:00:00Z")) / dayMs);
export const todayISO = (now = new Date()) => new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10);

/** Add days or calendar months to a YYYY-MM-DD date; month ends are clamped (31 Jan + 1 month = 28/29 Feb). */
export function addPeriod(iso, { days = 0, months = 0, years = 0 } = {}) {
  months += years * 12;
  const [y, m, d] = iso.split("-").map(Number);
  const t = new Date(Date.UTC(y, m - 1 + months, 1));
  const last = new Date(Date.UTC(t.getUTCFullYear(), t.getUTCMonth() + 1, 0)).getUTCDate();
  t.setUTCDate(Math.min(d, last));
  t.setUTCDate(t.getUTCDate() + days);
  return t.toISOString().slice(0, 10);
}

const icsText = (s) => String(s).replace(/\\/g, "\\\\").replace(/[;,]/g, (c) => "\\" + c).replace(/\r?\n/g, "\\n");
/** All-day calendar event with a reminder the day before (RFC 5545), for any phone calendar. */
export function buildICS({ uid, date: d, title, description = "" }) {
  const ymd = d.replace(/-/g, "");
  const end = addPeriod(d, { days: 1 }).replace(/-/g, "");
  const stamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d+/, "");
  return ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Case Clock//EN", "BEGIN:VEVENT", `UID:${uid}@caseclock`, `DTSTAMP:${stamp}`,
    `DTSTART;VALUE=DATE:${ymd}`, `DTEND;VALUE=DATE:${end}`, `SUMMARY:${icsText(title)}`, `DESCRIPTION:${icsText(description)}`,
    "BEGIN:VALARM", "TRIGGER:-PT12H", "ACTION:DISPLAY", `DESCRIPTION:${icsText(title)}`, "END:VALARM",
    "END:VEVENT", "END:VCALENDAR", ""].join("\r\n");
}

/** Apply period steps in order, e.g. [{days: 16}, {months: 1}]. */
export const applySteps = (iso, steps) => steps.reduce((d, st) => addPeriod(d, st), iso);

/** Trigger a file download in the browser. */
export function download(name, text, type) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type }));
  a.download = name;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
}
