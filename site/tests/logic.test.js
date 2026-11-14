import { test } from "node:test";
import assert from "node:assert/strict";
import { checkCase, formatDuration, formatHeadline, pickStats, shareDecidedAt, validateInputs } from "../js/logic.js";

const stats = {
  n: 500,
  time_to_decision_days: { p50: 400, p75: 700, p90: 1200, max_followup: 3800 },
  curve_monthly_share_decided: Array.from({ length: 121 }, (_, m) => Math.min(0.95, m / 60)),
  next_hearing_gap_days: { n: 200, p50: 30, p75: 60, p90: 100, p95: 120 },
};
const today = new Date("2026-11-14T00:00:00Z");

test("validation catches bad and inconsistent dates", () => {
  assert.deepEqual(validateInputs({ filing: "", last: "2026-01-01", today }).errors, ["err_filing"]);
  assert.ok(validateInputs({ filing: "2030-01-01", last: "2026-01-01", today }).errors.includes("err_filing_future"));
  assert.ok(validateInputs({ filing: "2025-01-01", last: "2024-01-01", today }).errors.includes("err_last_before_filing"));
  assert.ok(validateInputs({ filing: "2025-01-01", last: "2026-01-01", next: "2025-12-01", today }).errors.includes("err_next_before_last"));
});

test("recent hearing and young case is usual", () => {
  const r = checkCase({ filing: "2026-06-01", last: "2026-11-01" }, stats, today);
  assert.equal(r.verdict, "usual");
  assert.equal(r.gapDays, 13);
});

test("gap beyond p95 is longer than usual", () => {
  const r = checkCase({ filing: "2026-01-01", last: "2026-03-01" }, stats, today);
  assert.equal(r.verdict, "longer");
  assert.ok(r.reasons.includes("reason_gap_p95"));
});

test("gap between p75 and p95 is on the longer side", () => {
  const r = checkCase({ filing: "2026-06-01", last: "2026-09-01" }, stats, today);
  assert.equal(r.verdict, "somewhat");
});

test("old case: few similar cases still pending", () => {
  const r = checkCase({ filing: "2022-01-01", last: "2026-11-01" }, stats, today);
  assert.ok(r.shareStillPendingAtAge < 0.1);
  assert.equal(r.verdict, "longer");
  assert.ok(r.reasons.includes("reason_age_p90"));
});

test("far next date flagged", () => {
  const r = checkCase({ filing: "2026-06-01", last: "2026-11-01", next: "2027-06-01" }, stats, today);
  assert.ok(r.reasons.includes("reason_next_p95"));
});

test("no stats -> insufficient, never a guess", () => {
  const r = checkCase({ filing: "2026-06-01", last: "2026-11-01" }, null, today);
  assert.equal(r.verdict, "insufficient");
});

test("age beyond follow-up uses last observed value and says so", () => {
  const s = shareDecidedAt([0, 0.2, 0.4, null, null], 10);
  assert.deepEqual(s, { value: 0.4, beyond: true, lastMonth: 2 });
});

test("pickStats falls back district -> state -> national", () => {
  const ok = { suppressed: false, time_to_decision_days: { p50: 1 } };
  const sup = { suppressed: true };
  assert.equal(pickStats("x", { categories: { x: ok } }, null, null).level, "district");
  assert.equal(pickStats("x", { categories: { x: sup } }, { categories: { x: ok } }, null).level, "state");
  assert.equal(pickStats("x", null, { categories: {} }, { categories: { x: ok } }).level, "national");
  assert.equal(pickStats("x", null, null, null).stats, null);
});

test("duration formatting", () => {
  assert.equal(formatDuration(426), "14 months");
  assert.equal(formatDuration(1004), "2 years, 9 months");
  assert.equal(formatHeadline(1388), "3.8 years");
  assert.equal(formatDuration(426, "hi"), "14 महीने");
  assert.equal(formatDuration(null), "n/a");
});
