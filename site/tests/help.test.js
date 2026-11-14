import { test } from "node:test";
import assert from "node:assert/strict";
import { approxPercentile, costEstimate, decodePurpose, nextSteps, normPurpose, parseCNR, questionsFor, STAGES } from "../js/help.js";

test("decoder handles real, messy stage text from the records", () => {
  const cases = {
    "N.B.W. unready": "warrant", "appearence": "appearance", "appereance": "appearance", "w s": "reply",
    "W.S.": "reply", "evidence": "evidence", "awated for final form / chargesheet": "police_report", "call on": "routine",
    "framing of charge/ plea": "charge", "issue": "issues", "kurki attachment warrant / possession report": "execution",
    "referred to lokadalat": "settlement", "steps unready": "steps", "summons": "service", "judgement": "judgment",
    "ia / ea pending / cmp pending": "application", "await lcr": "records", "argument": "arguments", "bail": "bail",
  };
  for (const [text, key] of Object.entries(cases)) {
    assert.equal(decodePurpose(text)?.key, key, text);
  }
  assert.equal(decodePurpose(""), null);
  assert.equal(decodePurpose("hbc"), null); // unknown abbreviations are not guessed
  assert.equal(normPurpose("  Appearance of Accused/ Surety "), "appearance of accused/ surety");
});

test("every stage has English and Hindi text", () => {
  for (const s of STAGES) for (const l of ["en", "hi"]) for (const f of ["t", "m", "n"]) assert.ok(s[l][f], `${s.key}.${l}.${f}`);
});

test("CNR format check", () => {
  const ok = parseCNR("dlst 0100 0012 2024");
  assert.equal(ok.ok, true);
  assert.deepEqual([ok.state, ok.district, ok.establishment, ok.serial, ok.year], ["DL", "ST", "01", "000012", 2024]);
  assert.equal(parseCNR("MHAU01001234").error, "len");
  assert.equal(parseCNR("MH4U010012342019").error, "format");
  assert.equal(parseCNR("MHAU010012341800").error, "year");
  assert.equal(parseCNR("DLSTO10000122024").ok, true); // letter O typed for zero in the digit part
});

test("cost estimate", () => {
  assert.deepEqual(costEstimate({ durationDays: 600, gapDays: 60, perDay: 1000, people: 2 }), { hearings: 10, gap: 60, total: 20000 });
  assert.equal(costEstimate({ durationDays: 600, gapDays: 1, perDay: 100 }).gap, 7); // at most weekly
  assert.equal(costEstimate({ durationDays: null, gapDays: 30, perDay: 100 }), null);
});

test("approximate percentile and next steps", () => {
  const q = { p50: 30, p75: 60, p90: 100, p95: 120 };
  assert.equal(approxPercentile(30, q), 50);
  assert.equal(approxPercentile(45, q), 62.5);
  assert.equal(approxPercentile(500, q), 97);
  assert.equal(approxPercentile(null, q), null);
  const s = nextSteps({ verdict: "longer", shareStillPendingAtAge: 0.05 }, "maintenance");
  assert.ok(s.includes("ns_early") && s.includes("ns_highcourt") && s.includes("ns_maint") && s.includes("ns_aid"));
  assert.ok(!nextSteps({ verdict: "usual", shareStillPendingAtAge: 0.5 }, "civil_suit").includes("ns_highcourt"));
  assert.ok(questionsFor("evidence", "hi").length > 5);
});
