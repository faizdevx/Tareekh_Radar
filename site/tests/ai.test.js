import { test } from "node:test";
import assert from "node:assert/strict";
import { remainingTime } from "../js/logic.js";
import { aiLinks, buildPrompt, describeLeft } from "../js/ai.js";

// Deterministic curve: 2% of the original cases are decided each month for 50 months (then flat 1.0 would be wrong, so stop).
const curve = Array.from({ length: 61 }, (_, m) => (m <= 50 ? m / 50 : null));

test("time left is conditional on the case's age", () => {
  const r0 = remainingTime(curve, 0);
  assert.equal(r0.status, "ok");
  assert.equal(r0.p50, 25); assert.equal(r0.p90, 45);
  // At month 25, half the cases are gone; of the rest (0.5), half (0.25) are decided by month 37.5 -> 13 more months.
  const r = remainingTime(curve, 25 * 30.4375 + 1);
  assert.equal(r.ageMonths, 25);
  assert.equal(r.p50, 13);
  assert.equal(r.p90, 23); // (0.1 more decided of 0.5 remaining) -> month 48 -> 23 more
  assert.ok(Math.abs(r.stillPending - 0.5) < 1e-9);
  assert.ok(Math.abs(r.next12 - 0.48) < 1e-9);
});

test("beyond the follow-up, unknown or empty data gives no estimate", () => {
  assert.equal(remainingTime(curve, 49 * 30.4375).status, "beyond"); // fewer than 6 months of follow-up left
  assert.equal(remainingTime(curve, 70 * 30.4375).status, "beyond");
  assert.equal(remainingTime([], 100).status, "none");
  assert.equal(remainingTime(null, 100).status, "none");
  assert.equal(remainingTime(curve, -5).status, "none");
  const flat = [0, 0.2, 0.4, 0.6, 0.8, 1, 1, 1, 1, 1, 1, 1, 1];
  assert.equal(remainingTime(flat, 1 * 30.4375).p90, 4);
});

test("a quantile not reached within the follow-up is null (shown as 'more than')", () => {
  const slow = Array.from({ length: 40 }, (_, m) => m * 0.01); // only 39% decided by month 39
  const r = remainingTime(slow, 5 * 30.4375);
  assert.equal(r.status, "ok"); assert.equal(r.p50, null); assert.equal(r.p90, null); assert.equal(r.moreThan, 34);
  assert.match(describeLeft(r), /fewer than half were decided within 2 years, 10 months more, and fewer than 9 in 10/);
  assert.equal(describeLeft({ status: "none" }), null);
});

test("prompt contains only the supplied facts and sanitises text", () => {
  const p = buildPrompt({ category: "Cheque bounce", place: "Udaipur, Rajasthan", source: "this district", n: 3850, age: "3 years", sinceLast: "5 months",
    stage: { text: "N.B.W.\nunready\u0007", meaning: "warrant" }, half: "4.8 years", nine: "more than 10 years", left: "half within 14 months more",
    adj: { mine: 1, other: 3 }, hearings: 7, outcomes: ["Withdrawn 37%"], verdict: "Your case is within the usual range.", question: "x".repeat(900) }, "hi");
  assert.match(p, /ONLY the facts below/);
  assert.match(p, /simple Hindi/);
  assert.match(p, /Case type: Cheque bounce/);
  assert.match(p, /"N\.B\.W\. unready"/);
  assert.match(p, /other side 3/);
  assert.ok(!p.includes("\u0007"));
  assert.ok(p.includes("x".repeat(500)) && !p.includes("x".repeat(501)));
  assert.ok(!/CNR|phone|name:/i.test(p.replace(/ONLY the facts/, "")));
  assert.ok(!buildPrompt({ category: "A" }).includes("Age of my case"));
});

test("links pre-fill the question and are withheld when too long", () => {
  const l = aiLinks("Hello & goodbye?");
  assert.equal(l.chatgpt, "https://chatgpt.com/?q=Hello%20%26%20goodbye%3F");
  assert.equal(l.claude, "https://claude.ai/new?q=Hello%20%26%20goodbye%3F");
  const big = aiLinks("a".repeat(8000));
  assert.deepEqual([big.direct, big.chatgpt, big.claude], [false, null, null]);
});
