// Pure logic for Case Clock (no DOM). Used by the app and by node tests.

export const DAY_MS = 86400000;
export const MONTH_DAYS = 30.4375;

export function parseDate(s) {
  if (!s || typeof s !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(s)) return null;
  const d = new Date(s + "T00:00:00Z");
  return Number.isNaN(d.getTime()) ? null : d;
}

export function daysBetween(a, b) {
  return Math.round((b.getTime() - a.getTime()) / DAY_MS);
}

/** Choose the most local statistics with enough cases: district -> state -> national. */
export function pickStats(category, district, state, national) {
  const levels = [["district", district], ["state", state], ["national", national]];
  for (const [level, src] of levels) {
    const s = src && src.categories && src.categories[category];
    if (s && !s.suppressed && s.time_to_decision_days) return { level, stats: s };
  }
  return { level: null, stats: null };
}

/** Share of similar cases decided by `months` (from a monthly KM curve). */
export function shareDecidedAt(curve, months) {
  if (!Array.isArray(curve) || curve.length === 0) return { value: null, beyond: false };
  const m = Math.max(0, Math.floor(months));
  let lastIdx = -1;
  for (let i = curve.length - 1; i >= 0; i--) if (curve[i] !== null && curve[i] !== undefined) { lastIdx = i; break; }
  if (lastIdx < 0) return { value: null, beyond: false };
  if (m > lastIdx) return { value: curve[lastIdx], beyond: true, lastMonth: lastIdx };
  return { value: curve[m], beyond: false };
}

/**
 * Time left for a case that is already `ageDays` old: among similar cases still pending at that age,
 * when were half / 9 in 10 of them decided? Uses the monthly KM curve, conditional on surviving to the age.
 * status: ok | beyond (age past the follow-up) | none. Months are whole months; null = not reached in the data.
 */
export function remainingTime(curve, ageDays) {
  if (!Array.isArray(curve) || ageDays == null || !(ageDays >= 0)) return { status: "none" };
  let last = -1;
  for (let i = curve.length - 1; i >= 0; i--) if (curve[i] !== null && curve[i] !== undefined) { last = i; break; }
  if (last < 0) return { status: "none" };
  const a = Math.floor(ageDays / MONTH_DAYS);
  if (last - a < 6) return { status: "beyond", followupMonths: last }; // too little follow-up left to say anything
  const fa = curve[a];
  if (fa === null || fa === undefined) return { status: "none" };
  const pending = 1 - fa;
  if (pending <= 0.005) return { status: "none" };
  const after = (m) => (curve[m] - fa) / pending;
  const find = (q) => { for (let m = a + 1; m <= last; m++) if (curve[m] !== null && curve[m] !== undefined && after(m) >= q) return m - a; return null; };
  return { status: "ok", ageMonths: a, stillPending: pending, thin: pending < 0.03, p50: find(0.5), p90: find(0.9),
    next12: a + 12 <= last && curve[a + 12] != null ? after(a + 12) : null, moreThan: last - a };
}

export function validateInputs({ filing, last, next, today }) {
  const errors = [];
  const f = parseDate(filing), l = parseDate(last), n = next ? parseDate(next) : null;
  if (!f) errors.push("err_filing");
  if (!l) errors.push("err_last");
  if (next && !n) errors.push("err_next");
  if (f && f > today) errors.push("err_filing_future");
  if (l && l > today) errors.push("err_last_future");
  if (f && l && l < f) errors.push("err_last_before_filing");
  if (l && n && n < l) errors.push("err_next_before_last");
  return { errors, f, l, n };
}

/**
 * Compare a user's case with historical similar cases.
 * verdict: "usual" | "somewhat" | "longer" | "insufficient"
 */
export function checkCase(inputs, stats, today = new Date()) {
  const { errors, f, l, n } = validateInputs({ ...inputs, today });
  if (errors.length) return { errors };
  const out = { errors: [], reasons: [] };
  out.ageDays = daysBetween(f, today);
  out.gapDays = daysBetween(l, today);
  out.scheduledGapDays = n ? daysBetween(l, n) : null;
  const gap = stats && stats.next_hearing_gap_days;
  const curve = stats && stats.curve_monthly_share_decided;
  const age = shareDecidedAt(curve, out.ageDays / MONTH_DAYS);
  out.shareDecidedByAge = age.value;
  out.ageBeyondFollowup = age.beyond;
  out.shareStillPendingAtAge = age.value === null ? null : Math.round((1 - age.value) * 1000) / 1000;
  let level = 0; // 0 usual, 1 somewhat, 2 longer
  let evidence = 0;
  if (gap && gap.p95 != null) {
    evidence++;
    out.gapP75 = gap.p75;
    out.gapP95 = gap.p95;
    const g = out.scheduledGapDays !== null ? Math.max(out.gapDays, 0) : out.gapDays;
    if (g > gap.p95) { level = Math.max(level, 2); out.reasons.push("reason_gap_p95"); }
    else if (g > gap.p75) { level = Math.max(level, 1); out.reasons.push("reason_gap_p75"); }
    if (out.scheduledGapDays !== null && out.scheduledGapDays > gap.p95) {
      level = Math.max(level, 2); out.reasons.push("reason_next_p95");
    }
  }
  if (out.shareStillPendingAtAge !== null) {
    evidence++;
    if (out.shareStillPendingAtAge < 0.10) { level = Math.max(level, 2); out.reasons.push("reason_age_p90"); }
    else if (out.shareStillPendingAtAge < 0.25) { level = Math.max(level, 1); out.reasons.push("reason_age_p75"); }
  }
  out.verdict = evidence === 0 ? "insufficient" : ["usual", "somewhat", "longer"][level];
  return out;
}

/** Human duration: days -> {years, months} rounded to months. */
export function splitDuration(days) {
  if (days === null || days === undefined || Number.isNaN(days)) return null;
  const totalMonths = Math.max(0, Math.round(days / MONTH_DAYS));
  return { years: Math.floor(totalMonths / 12), months: totalMonths % 12, totalMonths };
}

export function formatDuration(days, lang = "en") {
  const d = splitDuration(days);
  if (!d) return lang === "hi" ? "उपलब्ध नहीं" : "n/a";
  if (d.totalMonths < 1) {
    const dd = Math.max(0, Math.round(days));
    return lang === "hi" ? `${dd} दिन` : `${dd} day${dd === 1 ? "" : "s"}`;
  }
  if (d.totalMonths < 24) {
    return lang === "hi" ? `${d.totalMonths} महीने` : `${d.totalMonths} month${d.totalMonths === 1 ? "" : "s"}`;
  }
  if (lang === "hi") return d.months ? `${d.years} साल, ${d.months} महीने` : `${d.years} साल`;
  return d.months ? `${d.years} years, ${d.months} month${d.months === 1 ? "" : "s"}` : `${d.years} years`;
}

/** Short headline form: "14 months" or "3.8 years". */
export function formatHeadline(days, lang = "en") {
  if (days === null || days === undefined) return null;
  const months = days / MONTH_DAYS;
  if (months < 24) {
    const m = Math.max(1, Math.round(months));
    return lang === "hi" ? `${m} महीने` : `${m} month${m === 1 ? "" : "s"}`;
  }
  const y = (months / 12).toFixed(1);
  return lang === "hi" ? `${y} साल` : `${y} years`;
}

export function pct(x, digits = 0) {
  return x === null || x === undefined ? "–" : `${(x * 100).toFixed(digits)}%`;
}
