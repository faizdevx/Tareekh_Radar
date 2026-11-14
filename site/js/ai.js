// "Ask an AI" helpers: build a facts-only prompt and the links that pre-fill ChatGPT / Claude.
// Pure functions (no DOM, no network). Nothing is sent anywhere by this file; the person
// reviews the text and opens the AI app themselves.
import { formatDuration, MONTH_DAYS } from "./logic.js";

const clean = (s, n) => String(s ?? "").replace(/[\u0000-\u001f\u007f]+/g, " ").replace(/\s+/g, " ").trim().slice(0, n);

/** One-sentence plain-English description of remainingTime() output, or null. */
export function describeLeft(r) {
  if (!r) return null;
  const dur = (m) => formatDuration(m * MONTH_DAYS, "en");
  if (r.status === "beyond") return `My case is older than the data can follow (${dur(r.followupMonths)}), so no estimate of time left is possible.`;
  if (r.status !== "ok") return null;
  const half = r.p50 == null ? `fewer than half were decided within ${dur(r.moreThan)} more` : `half were decided within ${dur(r.p50)} more`;
  const nine = r.p90 == null ? `fewer than 9 in 10 were decided within ${dur(r.moreThan)} more` : `9 in 10 within ${dur(r.p90)} more`;
  let s = `${half}, and ${nine}`;
  if (r.next12 != null) s += `; ${Math.round(r.next12 * 100)}% were decided within the next 12 months`;
  if (r.thin) s += " (very few cases lasted this long, so this is only a rough guide)";
  return s;
}

export function buildPrompt(f, lang = "en") {
  const L = [];
  const add = (label, v) => { if (v !== null && v !== undefined && v !== "") L.push(`- ${label}: ${v}`); };
  L.push("I am a litigant in an Indian district court. Help me understand my situation using ONLY the facts below.");
  L.push("Rules: do not invent numbers, dates or laws; if the facts do not say something, say you do not know. "
    + "This is general information, not legal advice. Do not predict how my case will end. "
    + `Answer in ${lang === "hi" ? "simple Hindi (Devanagari script)" : "simple English"}, with short headings.`);
  L.push("");
  L.push(`FACTS (historical eCourts records of cases filed ${f.years || "2014-2018"}, summarised by Case Clock; they describe past similar cases, not my case):`);
  add("Case type", clean(f.category, 80));
  add("Court", clean(f.place, 80));
  if (f.source) add("Statistics level", `${clean(f.source, 40)}${f.n ? ` (based on ${Number(f.n).toLocaleString("en-IN")} cases)` : ""}`);
  add("Age of my case", clean(f.age, 40));
  add("Time since my last hearing", clean(f.sinceLast, 40));
  add("Gap to my next scheduled hearing", clean(f.scheduled, 40));
  if (f.stage) add("Stage written for my next date", `"${clean(f.stage.text, 100)}"${f.stage.meaning ? ` (${clean(f.stage.meaning, 160)})` : ""}`);
  if (f.hearings != null) add("Hearings I have logged", f.hearings);
  if (f.adj) add("Adjournments so far (by whom)", `my side ${f.adj.mine || 0}, other side ${f.adj.other || 0}, court ${f.adj.court || 0}, unknown ${f.adj.unknown || 0}`);
  add("Similar cases, from filing", f.half ? `half were decided within ${clean(f.half, 40)}; 9 in 10 within ${clean(f.nine, 40)}` : "");
  add("Similar cases still pending at my case's age", clean(f.left, 300));
  add("Usual gap between hearings in similar pending cases", f.gapMedian ? `median ${clean(f.gapMedian, 40)}; 95% within ${clean(f.gapP95, 40)}` : "");
  if (f.outcomes?.length) add("How similar cases ended", f.outcomes.map((x) => clean(x, 60)).join("; "));
  add("Comparison with similar cases", clean(f.verdict, 120));
  if (f.reasons?.length) add("Why", f.reasons.map((x) => clean(x, 160)).join(" "));
  const q = clean(f.question, 500);
  if (q) L.push("", `My own question: ${q}`);
  L.push("", "PLEASE:",
    "1. Explain in plain words what these facts mean for me.",
    "2. Say whether my timing looks normal compared with similar cases.",
    "3. Give 5 specific questions I should ask my lawyer.",
    "4. Suggest practical, lawful next steps (for example asking about an early hearing date, free legal aid, Lok Adalat) and what I should not do.",
    "5. Tell me what these numbers cannot tell me.");
  return L.join("\n");
}

// ChatGPT (chatgpt.com/?q=) and Claude (claude.ai/new?q=) both pre-fill the box; the person presses send.
// Very long links are not reliable, so beyond the cap only "copy" is offered.
export const MAX_LINK = 7000;
export function aiLinks(prompt) {
  const q = encodeURIComponent(prompt);
  const ok = q.length <= MAX_LINK;
  return { direct: ok, chatgpt: ok ? `https://chatgpt.com/?q=${q}` : null, claude: ok ? `https://claude.ai/new?q=${q}` : null };
}
