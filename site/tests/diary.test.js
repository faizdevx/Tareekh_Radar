import { test } from "node:test";
import assert from "node:assert/strict";
import { addPeriod, applySteps, buildICS, caseSummary, daysBetween, loadDiary, sanitizeDiary, saveDiary } from "../js/diary.js";
import { DEADLINES } from "../js/help.js";

const memStore = () => { const m = new Map(); return { getItem: (k) => m.get(k) ?? null, setItem: (k, v) => m.set(k, String(v)) }; };

test("diary round-trips through storage and survives blocked storage", () => {
  const st = memStore();
  assert.deepEqual(loadDiary(st), { cases: [] });
  const d = { cases: [{ id: "a1", label: "Cheque case", entries: [{ id: "e1", date: "2026-01-10", next: "2026-03-01", purpose: "evidence", adjBy: "other", happened: "" }] }] };
  assert.equal(saveDiary(d, st), true);
  assert.equal(loadDiary(st).cases[0].entries[0].next, "2026-03-01");
  const broken = { getItem: () => { throw new Error("blocked"); }, setItem: () => { throw new Error("full"); } };
  assert.deepEqual(loadDiary(broken), { cases: [] });
  assert.equal(saveDiary(d, broken), false);
});

test("imports are sanitised (unknown fields, bad dates, bad adjBy dropped)", () => {
  assert.equal(sanitizeDiary({ nope: 1 }), null);
  const out = sanitizeDiary({ cases: [{ id: "x", label: "<b>L</b>", evil: "x", cnr: "dlst010000122024",
    entries: [{ date: "2026-13-99x", happened: "bad" }, { date: "2026-02-01", adjBy: "hacker", next: "soon", happened: 5 }] }] });
  const c = out.cases[0];
  assert.equal(c.evil, undefined);
  assert.equal(c.cnr, "DLST010000122024");
  assert.equal(c.entries.length, 1);
  assert.deepEqual([c.entries[0].adjBy, c.entries[0].next, c.entries[0].happened], ["none", "", ""]);
});

test("case summary uses the latest hearing and counts adjournments", () => {
  const s = caseSummary({ entries: [
    { date: "2026-03-01", next: "2026-05-01", purpose: "arguments", adjBy: "court" },
    { date: "2026-01-01", next: "2026-03-01", purpose: "evidence", adjBy: "other" }] });
  assert.deepEqual([s.hearings, s.last, s.next, s.purpose, s.adj.other, s.adj.court], [2, "2026-03-01", "2026-05-01", "arguments", 1, 1]);
});

test("date math: days, month-end clamping, chained steps", () => {
  assert.equal(addPeriod("2026-01-10", { days: 30 }), "2026-02-09");
  assert.equal(addPeriod("2026-01-31", { months: 1 }), "2026-02-28");
  assert.equal(addPeriod("2024-01-31", { months: 1 }), "2024-02-29");
  assert.equal(addPeriod("2024-02-29", { years: 2 }), "2026-02-28");
  assert.equal(applySteps("2026-01-01", [{ days: 16 }, { months: 1 }]), "2026-02-17");
  assert.equal(daysBetween("2026-01-01", "2026-03-01"), 59);
});

test("calendar file is valid all-day event with escaped text", () => {
  const ics = buildICS({ uid: "a", date: "2026-03-01", title: "Hearing; Sharma, case", description: "line1\nline2" });
  assert.match(ics, /DTSTART;VALUE=DATE:20260301\r\n/);
  assert.match(ics, /DTEND;VALUE=DATE:20260302\r\n/);
  assert.match(ics, /SUMMARY:Hearing\\; Sharma\\, case\r\n/);
  assert.match(ics, /DESCRIPTION:line1\\nline2\r\n/);
  assert.ok(ics.includes("BEGIN:VALARM") && ics.endsWith("END:VCALENDAR\r\n"));
});

test("every deadline has steps, a law and both languages", () => {
  for (const d of DEADLINES) {
    assert.ok(d.steps.length && d.law, d.key);
    for (const l of ["en", "hi"]) assert.ok(d[l].t && d[l].from, `${d.key}.${l}`);
    assert.match(applySteps("2026-01-15", d.steps), /^\d{4}-\d{2}-\d{2}$/);
  }
});
