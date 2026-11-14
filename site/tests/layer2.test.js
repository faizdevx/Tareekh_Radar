import { test } from "node:test";
import assert from "node:assert/strict";
import { PROBLEMS, AID_QUESTIONS, aidEligible, NOTICES, buildNotice, JOURNEYS, buildQuiz, agenda, rankOf } from "../js/layer2.js";

test("content has both languages", () => {
  for (const p of PROBLEMS) { assert.ok(p.t.en && p.t.hi); for (const r of p.routes) assert.ok(r.en && r.hi, p.key); }
  for (const q of AID_QUESTIONS) assert.ok(q.t.en && q.t.hi);
  for (const [k, steps] of Object.entries(JOURNEYS)) for (const s of steps) assert.ok(s.en && s.hi, k);
  for (const n of Object.values(NOTICES)) { assert.ok(n.t.en && n.t.hi && n.note.en && n.note.hi); for (const f of n.fields) assert.ok(f[1] && f[2]); }
});

test("legal aid: any ground means likely eligible", () => {
  assert.deepEqual(aidEligible({}), { likely: false, grounds: [] });
  assert.deepEqual(aidEligible({ woman_child: true, income: false }), { likely: true, grounds: ["woman_child"] });
  assert.equal(aidEligible({ income: true }).likely, true);
});

test("notice drafts fill values and show blanks for missing ones", () => {
  const t = buildNotice("cheque", { from: "Ram Kumar\nVillage X", to: "Shyam", chequeNo: "123456", amount: "50,000", reason: "Funds insufficient" }, "14 Nov 2026");
  assert.match(t, /SECTION 138/);
  assert.match(t, /cheque no\. 123456/);
  assert.match(t, /within 15 \(fifteen\) days/);
  assert.match(t, /\[ \.{12} \]/); // missing bank etc.
  assert.match(t, /\nRam Kumar\n$/);
  assert.match(buildNotice("rti", { info: "copy of file\nfile notings", bpl: "yes" }, "x"), /\(1\) copy of file\n   \(2\) file notings[\s\S]*Below Poverty Line/);
  assert.ok(!/no-objection/.test(buildNotice("lawyer", { change: "no" }, "x")));
  assert.match(buildNotice("lawyer", { change: "yes" }, "x"), /no-objection/);
});

test("quiz: deterministic, answer always among options, no duplicate options", () => {
  const a = buildQuiz("en", 8, 3), b = buildQuiz("en", 8, 3);
  assert.deepEqual(a, b);
  assert.equal(a.length, 8);
  for (const q of a) { assert.ok(q.options.includes(q.answer)); assert.equal(new Set(q.options).size, q.options.length); }
  assert.ok(buildQuiz("hi", 6, 1).every((q) => q.options.includes(q.answer)));
});

test("agenda groups dates and flags clashes", () => {
  const cases = [{ id: "a", n: "2026-11-10" }, { id: "b", n: "2026-11-14" }, { id: "c", n: "2026-11-18" }, { id: "d", n: "2026-11-18" }, { id: "e", n: "2027-01-01" }, { id: "f", n: "" }];
  const g = agenda(cases, "2026-11-14", (c) => c.n);
  assert.deepEqual([g.overdue, g.today, g.week, g.later].map((x) => x.map((y) => y.c.id)), [["a"], ["b"], ["c", "d"], ["e"]]);
  assert.ok(g.week.every((x) => x.clash) && !g.later[0].clash);
});

test("rankOf", () => {
  const rows = [["x", 100], ["y", 200], ["z", null]];
  assert.deepEqual(rankOf(rows, "y"), { rank: 2, of: 3 });
  assert.equal(rankOf(rows, "q"), null);
});
