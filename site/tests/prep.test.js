import { test } from "node:test";
import assert from "node:assert/strict";
import { parseOrderText, CARRY, DOCS, SETTLE } from "../js/prep.js";
import { expenseSummary, sanitizeDiary, isEmail } from "../js/diary.js";
import { STAGE_GROUPS } from "../js/help.js";

test("order-sheet parser: typical English order sheet", () => {
  const r = parseOrderText("Dated: 14/11/2026\nComplainant present. Accused absent. NBW issued.\nPut up on 12.03.2027 for evidence.");
  assert.equal(r.hearingDate, "2026-11-14");
  assert.equal(r.nextDate, "2027-03-12");
  assert.equal(r.purpose, "evidence");
});

test("order-sheet parser: keyword before date, named months, Hindi", () => {
  assert.equal(parseOrderText("Order dt 02-01-2026. Fixed for arguments on 5 Feb 2026.").nextDate, "2026-02-05");
  assert.equal(parseOrderText("Order dt 02-01-2026. Fixed for arguments on 5 Feb 2026.").purpose, "arguments");
  const h = parseOrderText("दिनांक 10/10/2026 पक्षकार उपस्थित। अगली तारीख 20/12/2026 साक्ष्य हेतु");
  assert.equal(h.nextDate, "2026-12-20");
  assert.equal(h.hearingDate, "2026-10-10");
});

test("order-sheet parser: no keyword uses the later date; rejects impossible dates", () => {
  assert.equal(parseOrderText("01/02/2026 ... 15/03/2026").nextDate, "2026-03-15");
  const bad = parseOrderText("31/02/2026 and 45/13/2026");
  assert.deepEqual(bad.dates, []);
  assert.equal(parseOrderText("nothing here").nextDate, "");
  assert.equal(parseOrderText("Next date 09/08/26").nextDate, "2026-08-09");
});

test("checklists have ids and both languages; every stage group has a carry list", () => {
  for (const g of STAGE_GROUPS) assert.ok(Array.isArray(CARRY[g]), g);
  const ids = new Set();
  for (const list of [...Object.values(CARRY), ...Object.values(DOCS)]) for (const x of list) {
    assert.match(x.id, /^[a-z0-9_]{1,40}$/); assert.ok(x.en && x.hi, x.id); ids.add(x.id);
  }
  assert.ok(ids.size > 20);
  assert.ok(["often", "some", "no", "compoundable"].includes(SETTLE.cheque_bounce));
});

test("expenses, checks and viewers are sanitised; totals add up", () => {
  const d = sanitizeDiary({ cases: [{ id: "a", label: "x", checks: { cheque: true, "bad key!": true, notice_copy: "yes" },
    viewers: ["Son@Example.com", "son@example.com", "not-an-email", "a@b.co", "c@d.in", "e@f.org", "g@h.net", "i@j.io"],
    expenses: [{ date: "2026-01-02", cat: "transport", amount: 250.6, people: 2 }, { date: "2026-01-02", cat: "hack", amount: -5 },
      { date: "2026-02-10", cat: "lawyer", amount: "1500" }, { date: "bad", amount: 9 }] }] }).cases[0];
  assert.deepEqual(d.checks, { cheque: true });
  assert.deepEqual(d.viewers, ["son@example.com", "a@b.co", "c@d.in", "e@f.org", "g@h.net"]);
  assert.equal(d.expenses.length, 3);
  assert.deepEqual([d.expenses[0].amount, d.expenses[0].people, d.expenses[1].cat, d.expenses[1].amount], [251, 2, "other", 0]);
  const s = expenseSummary(d);
  assert.deepEqual([s.total, s.byCat.transport, s.byCat.lawyer, s.days], [1751, 251, 1500, 2]);
  assert.ok(isEmail("a@b.co") && !isEmail("a@b"));
});
