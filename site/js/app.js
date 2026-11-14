import { t } from "./i18n.js";
import { icons, logo, hero, brush, vignetteScales, vignetteHourglass, vignettePen, courthouse } from "./art.js";
import { pickStats, checkCase, formatDuration, formatHeadline, pct, shareDecidedAt, remainingTime, MONTH_DAYS } from "./logic.js";
import { buildPrompt, aiLinks, describeLeft } from "./ai.js";
import { STAGES, decodePurpose, STAGE_GROUPS, GROUP_LABEL, questionsFor, QUESTIONS, parseCNR, DAKSH, CRIMINAL_CATS,
  costEstimate, approxPercentile, nextSteps, DEADLINES } from "./help.js";
import { loadDiary, saveDiary, sanitizeDiary, newId, sortedEntries, caseSummary, daysBetween, todayISO, buildICS, download,
  applySteps, ADJ_BY, mergeCases } from "./diary.js";

const OUTCOME_COLORS = {
  compromise: "#4b8a3c", lok_adalat: "#8fb35d", allowed: "#2f6f8f", dismissed: "#b8ad9e", withdrawn: "#ddd3c4",
  convicted: "#e3a23b", acquitted: "#e07b39", closed: "#8a7f74", unspecified: "#cfc6b8",
};
const LINKS = {
  dlsa: "https://nalsa.gov.in/",
  lok: "https://nalsa.gov.in/",
  ecourts: "https://services.ecourts.gov.in/",
  hc: "https://hcservices.ecourts.gov.in/",
  judgments: "https://judgments.ecourts.gov.in/",
};

const state = { lang: "en", meta: null, national: null, states: {}, districts: {}, purposes: null };
const $ = (sel, root = document) => root.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const tr = (k, v) => t(state.lang, k, v);

function loadLang() {
  try { const l = localStorage.getItem("cc-lang"); if (l === "hi" || l === "en") return l; } catch (_) { /* storage blocked */ }
  return (navigator.language || "").startsWith("hi") ? "hi" : "en";
}
function saveLang(l) { try { localStorage.setItem("cc-lang", l); } catch (_) { /* ignore */ } }

async function getJSON(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}
async function meta() { return state.meta ??= await getJSON("data/meta.json"); }
async function national() { return state.national ??= await getJSON("data/national.json"); }
async function stateData(code) { return state.states[code] ??= await getJSON(`data/states/${code}.json`); }
async function districtData(id) { return state.districts[id] ??= await getJSON(`data/districts/${id}.json`); }

const yearSpan = (ys) => (ys.length > 2 ? `${ys[0]}–${ys[ys.length - 1]}` : ys.join(", "));
const catName = (k) => (state.meta?.categories?.[k]?.[state.lang] ?? k);
const outName = (k) => (state.meta?.outcome_groups?.[k]?.[state.lang] ?? k);
const fmtN = (n) => (n == null ? "–" : Number(n).toLocaleString(state.lang === "hi" ? "hi-IN" : "en-IN"));

function parseHash() {
  const raw = location.hash.replace(/^#/, "") || "/";
  const [path, q] = raw.split("?");
  return { path: path || "/", params: new URLSearchParams(q || "") };
}
function go(path, params) {
  const q = params ? new URLSearchParams(Object.entries(params).filter(([, v]) => v)).toString() : "";
  location.hash = path + (q ? `?${q}` : "");
}

/* ---------------- chrome ---------------- */
function renderChrome(path) {
  document.documentElement.lang = state.lang;
  $("#brand").innerHTML = `${logo()}<span><div class="brand-name">${tr("brand")}</div><div class="brand-hi">${tr("brand_hi")}</div></span>`;
  const nav = [["/diary", "nav_diary"], ["/estimate", "nav_estimate"], ["/check", "nav_check"], ["/district", "nav_districts"], ["/help", "nav_help"], ["/method", "nav_method"], ["/about", "nav_about"]];
  const helpPaths = ["/help", "/find", "/decode", "/lawyer", "/cost", "/rights", "/deadlines"];
  const isActive = (p) => path === p || (p === "/help" && helpPaths.includes(path)) || (p === "/diary" && path === "/case");
  $("#main-nav").innerHTML = nav.map(([p, k]) => `<a href="#${p}" class="${isActive(p) ? "active" : ""}">${tr(k)}</a>`).join("");
  $("#lang-toggle").innerHTML = state.lang === "en" ? "<b>EN</b> / हिंदी" : "EN / <b>हिंदी</b>";
  const bn = [["/", "nav_home", icons.home], ["/diary", "nav_diary", icons.book], ["/check", "nav_check_short", icons.calsm], ["/district", "nav_districts", icons.barsm], ["/help", "nav_help", icons.helpsm]];
  $("#bottom-nav").innerHTML = bn.map(([p, k, ic]) => `<a href="#${p}" class="${isActive(p) ? "active" : ""}">${ic}<span>${tr(k)}</span></a>`).join("");
  $("#disclaimer").textContent = tr("disclaimer");
  paintChip();
  const m = state.meta;
  const years = m ? yearSpan(m.filing_years) : "";
  $("#footer").innerHTML = `<a class="brand" href="#/">${logo("#fff")}<span><div class="brand-name">${tr("brand")}</div><div class="brand-hi">${tr("brand_hi")}</div></span></a>
    <div class="fnote">${tr("footer_note")} ${years ? `(${esc(years)})` : ""}</div>
    <nav><a href="#/about">${tr("nav_about")}</a><a href="#/method">${tr("nav_method")}</a><a href="#/privacy">${tr("privacy_title")}</a><a href="${m ? esc(m.source_url) : "#/method"}" rel="noopener">Data</a></nav>
    <div class="footer-art">${courthouse()}</div>
    <div class="src">${m ? `Data: ${esc(m.source)}. ${esc(m.license)}` : ""}</div>`;
}

/* ---------------- selectors ---------------- */
function selectorHTML({ withCategory = true, s = "", d = "", c = "" } = {}) {
  const m = state.meta;
  const st = m.states.find((x) => x.code === s);
  const cats = Object.keys(m.categories);
  return `<div class="form-grid">
    <div class="field"><label for="sel-s">${tr("state")}</label><select id="sel-s"><option value="">${tr("select_state")}</option>
      ${m.states.map((x) => `<option value="${x.code}" ${x.code === s ? "selected" : ""}>${esc(x.name)}</option>`).join("")}</select></div>
    <div class="field"><label for="sel-d">${tr("district")}</label><select id="sel-d" ${st ? "" : "disabled"}><option value="">${tr("select_district")}</option>
      ${st ? st.districts.map((x) => `<option value="${x.id}" ${x.id === d ? "selected" : ""}>${esc(x.name)}</option>`).join("") : ""}</select></div>
    ${withCategory ? `<div class="field"><label for="sel-c">${tr("case_type")}</label><select id="sel-c"><option value="">${tr("select_type")}</option>
      ${cats.map((k) => `<option value="${k}" ${k === c ? "selected" : ""}>${esc(catName(k))}</option>`).join("")}</select></div>` : ""}
  </div>`;
}
function wireSelectors(root) {
  const s = $("#sel-s", root), d = $("#sel-d", root);
  s.addEventListener("change", () => {
    const st = state.meta.states.find((x) => x.code === s.value);
    d.disabled = !st;
    d.innerHTML = `<option value="">${tr("select_district")}</option>` + (st ? st.districts.map((x) => `<option value="${x.id}">${esc(x.name)}</option>`).join("") : "");
  });
}
const readSel = () => ({ s: $("#sel-s")?.value || "", d: $("#sel-d")?.value || "", c: $("#sel-c")?.value || "" });

/* ---------------- small components ---------------- */
function outcomeBlock(stats) {
  if (!stats || !stats.outcomes) return `<p class="note">${tr("suppressed")}</p>`;
  const all = Object.entries(stats.outcomes).sort((a, b) => (a[0] === "unspecified") - (b[0] === "unspecified") || b[1] - a[1]);
  const entries = all.filter(([, v]) => v >= 0.005);
  return `<div class="outcome-bar" role="img" aria-label="${esc(entries.map(([k, v]) => `${outName(k)} ${pct(v)}`).join(", "))}">
      ${entries.map(([k, v]) => `<span style="width:${(v * 100).toFixed(2)}%;background:${OUTCOME_COLORS[k] || "#ccc"}" title="${esc(outName(k))}: ${pct(v)}"></span>`).join("")}</div>
    <div class="legend">${entries.map(([k, v]) => `<div><i style="background:${OUTCOME_COLORS[k] || "#ccc"}"></i>${esc(outName(k))}<span class="val">${pct(v)}</span></div>`).join("")}</div>
    <p class="note">${tr("based_on", { n: fmtN(stats.n_outcomes) })}</p>`;
}
function headlineOrBeyond(days, stats) {
  if (days != null) return formatHeadline(days, state.lang);
  const max = stats?.time_to_decision_days?.max_followup;
  return tr("not_reached", { d: formatHeadline(max, state.lang) || "" });
}
function twoStats(stats) {
  const tt = stats.time_to_decision_days || {};
  return `<div class="two-stats">
    <div class="statbox"><div class="k">${tr("half_within")}</div><div class="v">${esc(headlineOrBeyond(tt.p50, stats))}</div></div>
    <div class="statbox"><div class="k">${tr("ninety_within")}</div><div class="v">${esc(headlineOrBeyond(tt.p90, stats))}</div></div></div>`;
}
function curveChart(curve) {
  if (!curve) return "";
  const W = 560, H = 220, L = 40, B = 28, T = 10, Rr = 10;
  const pts = curve.map((v, i) => [i, v]).filter(([, v]) => v != null);
  const maxM = pts.length ? pts[pts.length - 1][0] : 12;
  const x = (m) => L + (m / Math.max(maxM, 1)) * (W - L - Rr);
  const y = (v) => T + (1 - v) * (H - T - B);
  const path = pts.map(([m, v], i) => `${i ? "L" : "M"}${x(m).toFixed(1)},${y(v).toFixed(1)}`).join("");
  const yrs = [];
  for (let yy = 0; yy * 12 <= maxM; yy += maxM > 72 ? 2 : 1) yrs.push(yy);
  return `<div class="chart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(tr("est_curve"))}">
    ${[0, 0.5, 0.9, 1].map((v) => `<line x1="${L}" x2="${W - Rr}" y1="${y(v)}" y2="${y(v)}" stroke="#d9c9ad" ${v === 0.5 || v === 0.9 ? 'stroke-dasharray="4 4"' : ""}/><text x="${L - 6}" y="${y(v) + 4}" font-size="11" text-anchor="end" fill="#7a6f63">${v * 100}%</text>`).join("")}
    ${yrs.map((yy) => `<text x="${x(yy * 12)}" y="${H - 8}" font-size="11" text-anchor="middle" fill="#7a6f63">${yy}</text>`).join("")}
    <path d="${path}" fill="none" stroke="#c4232b" stroke-width="3"/>
    </svg><div class="note" style="text-align:center">${tr("est_curve_x")}</div></div>`;
}
function levelNote(level, n) {
  const lv = { district: tr("level_district"), state: tr("level_state"), national: tr("level_national") }[level] || "";
  return `<p class="note">${tr("stats_from", { level: lv })} ${tr("based_on", { n: fmtN(n) })}. ${dataYearsNote()}</p>`;
}
function dataYearsNote() {
  const m = state.meta;
  const snaps = m.states.map((s) => s.snapshot_date).sort();
  return tr("data_years", { years: yearSpan(m.filing_years), snap: snaps.filter(Boolean)[Math.floor(snaps.filter(Boolean).length / 2)]?.slice(0, 4) || "" });
}
async function statsFor(s, d, c) {
  const [dd, ss, nn] = await Promise.all([d ? districtData(d).catch(() => null) : null, s ? stateData(s).catch(() => null) : null, national()]);
  return { ...pickStats(c, dd, ss, nn), district: dd, stateObj: ss };
}

/* ---------------- pages ---------------- */
async function pageHome() {
  const m = state.meta;
  // Optional artwork: set <meta name="cc-hero-image" content="assets/hero.webp"> in index.html.
  const heroImg = document.querySelector('meta[name="cc-hero-image"]')?.content || "";
  const ex = m.example;
  let exHTML = "";
  if (ex) {
    const dd = await districtData(ex.district_id);
    const st = dd.categories[ex.category];
    exHTML = `<div class="card has-art"><h2>${esc(tr("example_title", { cat: catName(ex.category), district: dd.name }))}</h2>
      ${twoStats(st)}${outcomeBlock(st)}
      <a class="btn btn-dark" href="#/estimate?s=${dd.state_code}&d=${dd.id}&c=${ex.category}">${tr("open_estimate")} <span class="arrow">→</span></a>
      <div class="card-art">${courthouse()}</div></div>`;
  }
  const typeCount = m.totals.categories;
  $("#main").innerHTML = `
  <section class="hero">
    <div class="hero-art">${hero()}${heroImg ? `<img class="hero-img" src="${esc(heroImg)}" alt="" onerror="this.remove()">` : ""}</div>
    <div class="hero-copy"><div>
      <h1 class="hero-title">${tr("hero_title_1")}<br>${tr("hero_title_2")}</h1>${brush()}
      <p class="hero-sub">${tr("hero_sub")}</p>
      <a class="btn btn-dark" href="#/check">${tr("cta_check")} <span class="arrow">→</span></a></div>
      <div class="vignettes"><div class="vignette">${vignetteHourglass()}</div><div class="vignette red">${vignetteScales()}</div><div class="vignette">${vignettePen()}</div></div>
    </div>
  </section>
  <div class="scallop"></div>
  <section class="wrap">
  <div class="tools-sec"><h2 class="section-title">${tr("tools_title")}</h2><p class="note">${tr("tools_sub")}</p>${toolsGrid()}</div>
  <div class="band"><div class="band-art">${courthouse()}</div>
    <div><div class="big">${fmtN(m.totals.cases)}</div><div class="lbl">${tr("band_cases")} (${tr("band_years")} ${esc(yearSpan(m.filing_years))})</div></div>
    <div><div class="big">${fmtN(m.totals.districts)}</div><div class="lbl">${tr("band_districts")}</div></div>
    <div><div class="big">${fmtN(typeCount)}</div><div class="lbl">${tr("band_types")}</div></div>
  </div>
  <div class="grid-2">${exHTML}
    <div class="card"><h2>${tr("explore_title")}</h2><p>${tr("explore_sub")}</p>
      <form class="inline-form" id="explore"><label class="sr-only" for="ex-s">${tr("state")}</label>
      <select id="ex-s"><option value="">${tr("select_state")}</option>${m.states.map((x) => `<option value="${x.code}">${esc(x.name)}</option>`).join("")}</select>
      <button class="icon-btn" aria-label="${tr("nav_districts")}">→</button></form></div>
  </div></section>`;
  $("#explore").addEventListener("submit", (e) => { e.preventDefault(); const s = $("#ex-s").value; if (s) go("/district", { s }); });
}

async function pageEstimate(params) {
  const s = params.get("s") || "", d = params.get("d") || "", c = params.get("c") || "";
  $("#main").innerHTML = `<section class="wrap page"><div class="page-head"><a class="back" href="#/" aria-label="${tr("back")}">←</a><h1>${tr("est_title")}</h1></div>
    <form id="f">${selectorHTML({ s, d, c })}<div class="form-actions"><button class="btn btn-red">${tr("est_go")} <span class="arrow">→</span></button></div><ul class="errors" id="errs"></ul></form>
    <div id="out" class="result"></div></section>`;
  wireSelectors($("#main"));
  $("#f").addEventListener("submit", (e) => {
    e.preventDefault();
    const v = readSel();
    if (!v.s || !v.d || !v.c) { $("#errs").innerHTML = `<li>${tr("err_select")}</li>`; return; }
    go("/estimate", v);
  });
  if (!(s && d && c)) return;
  $("#out").innerHTML = `<p class="note">${tr("loading")}</p>`;
  const { level, stats, district } = await statsFor(s, d, c);
  if (!stats) { $("#out").innerHTML = `<p>${tr("suppressed")}</p>`; return; }
  const gap = stats.next_hearing_gap_days, ttf = stats.days_to_first_listing;
  $("#out").innerHTML = `<div class="crumb">${esc(catName(c))} · ${esc(district?.name || "")}, ${esc(district?.state_name || "")}</div>
    <div class="grid-2"><div class="card">${twoStats(stats)}
      <h2 style="font-size:20px">${tr("est_outcomes")}</h2>${outcomeBlock(stats)}</div>
      <div class="card"><h2 style="font-size:20px">${tr("est_curve")}</h2>${curveChart(stats.curve_monthly_share_decided)}
      <div class="two-stats"><div class="statbox"><div class="k">${tr("est_first")}</div><div class="v" style="font-size:24px">${esc(ttf ? formatDuration(ttf.p50, state.lang) : "–")}</div></div>
      <div class="statbox"><div class="k">${tr("est_gap")}</div><div class="v" style="font-size:24px">${esc(gap ? formatDuration(gap.p50, state.lang) : "–")}</div></div></div></div></div>
    <div id="ai-slot"></div>
    ${levelNote(level, stats.n)}<p class="note">${tr("not_advice")}</p>`;
  mountAskAI($("#ai-slot"), aiFacts({ stats, level, district, c }));
}

async function pageCheck(params) {
  const s = params.get("s") || "", d = params.get("d") || "", c = params.get("c") || "";
  $("#main").innerHTML = `<section class="wrap page"><div class="page-head"><a class="back" href="#/" aria-label="${tr("back")}">←</a><h1>${tr("check_title")}</h1></div>
    <h2 class="section-title" style="font-size:20px">${tr("check_enter")}</h2>
    <form id="f">${selectorHTML({ s, d, c })}
      <div class="form-grid" style="margin-top:14px">
        <div class="field"><label for="i-f">${tr("filing_date")}</label><input type="date" id="i-f" required></div>
        <div class="field"><label for="i-l">${tr("last_hearing")}</label><input type="date" id="i-l" required></div>
        <div class="field"><label for="i-n">${tr("next_hearing")}</label><input type="date" id="i-n"></div>
      </div>
      <div class="field" style="margin-top:14px"><label for="i-pu">${tr("check_stage")}</label><input class="text" id="i-pu" maxlength="100" list="i-plist" autocomplete="off" placeholder="${esc(tr("decode_ph"))}"><datalist id="i-plist"></datalist></div>
      <div class="form-actions"><button class="btn btn-red">${tr("check_go")} <span class="arrow">→</span></button><span class="note">${tr("privacy_note")}</span></div>
      <ul class="errors" id="errs"></ul></form><div id="out" class="result"></div></section>`;
  wireSelectors($("#main"));
  purposes().then((pp) => { const dl = $("#i-plist"); if (dl && pp) dl.innerHTML = pp.purposes.slice(0, 80).map((r) => `<option value="${esc(r.text)}">`).join(""); });
  $("#f").addEventListener("submit", async (e) => {
    e.preventDefault();
    const v = readSel();
    const errs = [];
    if (!v.s || !v.d || !v.c) errs.push(tr("err_select"));
    const inputs = { filing: $("#i-f").value, last: $("#i-l").value, next: $("#i-n").value || null };
    const today = new Date(new Date().toISOString().slice(0, 10) + "T00:00:00Z");
    if (errs.length) { $("#errs").innerHTML = errs.map((x) => `<li>${x}</li>`).join(""); return; }
    const { level, stats, district } = await statsFor(v.s, v.d, v.c);
    const res = checkCase(inputs, stats, today);
    if (res.errors.length) { $("#errs").innerHTML = res.errors.map((k) => `<li>${tr(k)}</li>`).join(""); return; }
    $("#errs").innerHTML = "";
    renderCheckResult(res, stats, level, district, v.c, v, $("#i-pu").value.trim());
  });
}

function renderCheckResult(res, stats, level, district, c, sel = {}, purposeText = "") {
  const vText = { longer: tr("v_longer"), somewhat: tr("v_somewhat"), usual: tr("v_usual"), insufficient: tr("v_insufficient") }[res.verdict];
  let rangeHTML = "";
  if (res.gapP95 != null) {
    const max = Math.max(res.gapDays, res.gapP95) * 1.08 || 1;
    rangeHTML = `<div class="range"><div class="range-track"><span class="range-dot" style="left:${(res.gapP95 / max) * 100}%"></span>
      <span class="range-dot you" style="left:${Math.min(100, (Math.max(res.gapDays, 0) / max) * 100)}%"></span></div>
      <div class="range-labels"><span>${esc(formatDuration(res.gapP95, state.lang))} ${tr("usual_label")}</span><span>${esc(formatDuration(res.gapDays, state.lang))} ${tr("yours_label")}</span></div></div>`;
  }
  const ageLine = res.shareStillPendingAtAge == null ? "" : `<p>${esc(res.ageBeyondFollowup
    ? tr("age_beyond", { max: formatDuration(stats.time_to_decision_days.max_followup, state.lang), share: pct(res.shareStillPendingAtAge) })
    : tr("age_line", { age: formatDuration(res.ageDays, state.lang), share: pct(res.shareStillPendingAtAge) }))}</p>`;
  $("#out").innerHTML = `<h2 class="section-title">${tr("result_title")}</h2>
    <div class="crumb">${esc(catName(c))} · ${esc(district?.name || "")}, ${esc(district?.state_name || "")}</div>
    <div class="verdict ${res.verdict}">${icons.hourglass}<span>${esc(vText)}</span></div>
    <div class="two-stats"><div class="statbox"><div class="k">${tr("since_last")}</div><div class="v">${esc(formatDuration(res.gapDays, state.lang))}</div></div>
      <div class="statbox"><div class="k">${tr("similar_listed")}</div><div class="v" style="color:var(--green)">${esc(res.gapP95 != null ? formatDuration(res.gapP95, state.lang) : "–")}</div><div class="note">${tr("of_cases_95")}</div></div></div>
    ${rangeHTML}${ageLine}
    ${res.reasons.length ? `<ul class="reasons">${res.reasons.map((r) => `<li>${esc(tr(r))}</li>`).join("")}</ul>` : ""}
    ${timeLeftHTML(stats, res.ageDays)}${stuckMeter(res, stats)}
    <div id="ai-slot" style="margin-top:18px"></div>
    <h2 class="section-title" style="margin-top:20px;font-size:20px">${tr("steps_title")}</h2>
    <ul class="links">${nextSteps(res, c).map((k) => `<li><a href="${stepHref(k, sel, c)}">${STEP_ICONS[k] || icons.doc}${esc(tr(k))}<span class="go">→</span></a></li>`).join("")}
    </ul>${levelNote(level, stats?.n)}<p class="note">${tr("not_advice")}</p>`;
  if (stats) mountAskAI($("#ai-slot"), aiFacts({ stats, level, district, c, res, purposeText }));
}

async function pageDistrict(params) {
  const s = params.get("s") || "", d = params.get("d") || "";
  $("#main").innerHTML = `<section class="wrap page"><div class="page-head"><a class="back" href="#/" aria-label="${tr("back")}">←</a><h1>${tr("district_report")}</h1></div>
    <form id="f">${selectorHTML({ withCategory: false, s, d })}<div class="form-actions"><button class="btn btn-red">${tr("nav_districts")} <span class="arrow">→</span></button></div></form>
    <div id="out" class="result"></div></section>`;
  wireSelectors($("#main"));
  $("#f").addEventListener("submit", (e) => { e.preventDefault(); const v = readSel(); if (v.s) go("/district", { s: v.s, d: v.d }); });
  if (!s) return;
  const ss = await stateData(s);
  const dd = d ? await districtData(d) : null;
  const obj = dd || ss;
  const sm = obj.summary, sts = ss.summary;
  const years = yearSpan(state.meta.filing_years);
  const metric = (ic, v, k, cmp) => `<div class="metric">${ic}<div><div class="v">${v}</div><div class="k">${k}</div>${cmp ? `<div class="s">${cmp}</div>` : ""}</div></div>`;
  const med = (x) => x?.time_to_decision_days?.p50;
  const byYear = Object.entries(sm.by_filing_year || {});
  const cats = Object.entries(obj.categories || {}).filter(([, v]) => !v.suppressed).sort((a, b) => b[1].n - a[1].n);
  $("#out").innerHTML = `<div class="card"><h2 style="font-size:28px">${esc(obj.name)}${dd ? `, ${esc(dd.state_name)}` : ""}</h2>
    <p class="note">${tr("hist_perf", { years })} · ${tr("based_on", { n: fmtN(sm.n) })}</p>
    <div class="metrics">
      ${metric(icons.clock, esc(headlineOrBeyond(med(sm), sm)), tr("m_median"), dd ? tr("compare_state", { v: esc(headlineOrBeyond(med(sts), sts)) }) : "")}
      ${metric(icons.layers, pct(sm.share_undecided_at_3y), tr("m_3y"), dd ? tr("compare_state", { v: pct(sts.share_undecided_at_3y) }) : "")}
      ${metric(icons.cal, pct(sm.pending_next_gap_over_6m_share), tr("m_dormant"), dd ? tr("compare_state", { v: pct(sts.pending_next_gap_over_6m_share) }) : "")}
    </div>
    ${byYear.length ? `<h3>${tr("by_year")}</h3>${yearChart(byYear, sts.by_filing_year)}<p class="note">${tr("cohort_note")}</p>` : ""}
    </div>
    <div class="card" style="margin-top:18px"><h2 style="font-size:22px">${tr("cat_table")}</h2>
    <table class="data"><thead><tr><th>${tr("col_type")}</th><th class="num">${tr("col_n")}</th><th class="num">${tr("col_median")}</th><th class="num">${tr("col_3y")}</th><th></th></tr></thead><tbody>
    ${cats.map(([k, v]) => `<tr><td>${esc(catName(k))}</td><td class="num">${fmtN(v.n)}</td><td class="num">${esc(headlineOrBeyond(med(v), v))}</td><td class="num">${pct(v.share_undecided_at_3y)}</td>
      <td class="num"><a href="#/estimate?s=${s}&d=${dd ? dd.id : ""}&c=${k}" aria-label="${esc(catName(k))}">→</a></td></tr>`).join("")}
    </tbody></table></div>
    <p class="note">${dataYearsNote()} ${tr("disclaimer")}</p>`;
}

function yearChart(rows, stateRows) {
  const W = 900, H = 220, L = 40, B = 26, T = 18, Rr = 24;
  const pts = rows.map(([y, v]) => [Number(y), v.share_undecided_at_3y]).filter(([, v]) => v != null);
  if (!pts.length) return "";
  const xs = pts.map((p) => p[0]); const minX = Math.min(...xs), maxX = Math.max(...xs);
  const all = pts.map((p) => p[1]).concat(Object.values(stateRows || {}).map((v) => v.share_undecided_at_3y).filter((v) => v != null));
  const maxY = Math.min(1, Math.ceil((Math.max(...all) + 0.05) * 10) / 10);
  const x = (v) => (maxX === minX ? (L + W - Rr) / 2 : L + ((v - minX) / (maxX - minX)) * (W - L - Rr));
  const y = (v) => T + (1 - v / maxY) * (H - T - B);
  const line = (p) => p.map(([a, b], i) => `${i ? "L" : "M"}${x(a)},${y(b)}`).join("");
  const sp = Object.entries(stateRows || {}).map(([yy, v]) => [Number(yy), v.share_undecided_at_3y]).filter(([, v]) => v != null);
  const ticks = [0, maxY / 2, maxY];
  return `<div class="chart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(tr("by_year"))}">
    ${ticks.map((v) => `<line x1="${L}" x2="${W - Rr}" y1="${y(v)}" y2="${y(v)}" stroke="#d9c9ad"/><text x="${L - 6}" y="${y(v) + 4}" font-size="11" text-anchor="end" fill="#7a6f63">${Math.round(v * 100)}%</text>`).join("")}
    ${pts.map(([a]) => `<text x="${x(a)}" y="${H - 6}" font-size="11" text-anchor="middle" fill="#7a6f63">${a}</text>`).join("")}
    ${sp.length > 1 ? `<path d="${line(sp)}" fill="none" stroke="#7a6f63" stroke-dasharray="5 4" stroke-width="2"/>` : ""}
    ${pts.length > 1 ? `<path d="${line(pts)}" fill="none" stroke="#4b8a3c" stroke-width="3"/>` : ""}
    ${pts.map(([a, b]) => `<circle cx="${x(a)}" cy="${y(b)}" r="5" fill="#4b8a3c"/><text x="${x(a)}" y="${y(b) - 10}" font-size="12" text-anchor="middle">${pct(b)}</text>`).join("")}
  </svg></div>`;
}

async function pageMethod() {
  const m = state.meta;
  let mapping = [];
  try { mapping = await getJSON("data/category_mapping.json"); } catch (_) { /* optional */ }
  const hiNote = state.lang === "hi" ? `<p><b>सारांश:</b> सभी आँकड़े वास्तविक ई-कोर्ट्स रिकॉर्ड (डेवलपमेंट डेटा लैब, हार्वर्ड डेटावर्स) से निकाले गए हैं। लंबित मामलों को कपलान–मायर पद्धति से गिना जाता है ताकि अधूरे मामले छूटें नहीं। 30 से कम मामलों वाले समूह नहीं दिखाए जाते। यह कानूनी सलाह नहीं है। नीचे विवरण अंग्रेज़ी में है।</p>` : "";
  $("#main").innerHTML = `<section class="wrap page prose"><h1>${tr("method_title")}</h1>${hiNote}
  <h2>Where the numbers come from</h2>
  <p>Every number is computed from real district-court case records collected from eCourts and published, de-identified, by the Development Data Lab: <a href="${esc(m.source_url)}" rel="noopener">${esc(m.source)}</a>. Licence: ${esc(m.license)} Please cite: ${esc(m.citation)}.</p>
  <p>Coverage on this site: cases <b>filed ${esc(yearSpan(m.filing_years))}</b>, ${fmtN(m.totals.cases)} cases in ${fmtN(m.totals.states)} states and ${fmtN(m.totals.districts)} districts, as recorded when the data was collected (mostly early 2019, some records updated in 2020). ${esc(dataYearsNote())} These are <b>historical patterns</b>, not live case status.</p>
  <p><b>Older filing years are incomplete.</b> The number of records per filing year rises from about 4.3 million (2010) to 13.7 million (2018). Real filings did not triple, so earlier years appear to be missing many cases that were decided quickly, before courts moved their records to eCourts. Durations from older filing years are therefore biased upward, and the "by filing year" chart overstates how much faster courts became.${m.min_filing_year ? ` To limit this bias, statistics here use only cases filed from ${m.min_filing_year}.` : ""}</p>
  <p>Case Clock does <b>not</b> scrape eCourts, solve CAPTCHAs or look up any live case. What you type in the delay checker never leaves your browser.</p>
  <h2>How long cases take</h2>
  <p>"Half / 9 in 10 were decided within" are the 50th and 90th percentiles of time from filing to decision, estimated with the <b>Kaplan–Meier</b> method. A case still pending in the data is counted as "undecided for at least this long", up to its own last recorded hearing, rather than dropped. Dropping pending cases would make courts look faster than they are. Stopping at the last recorded hearing can only understate delays, never overstate them. Cases transferred to or committed to another court are treated the same way, because their outcome is decided elsewhere. If fewer than 10% (or 50%) of cases were still pending at the end of the follow-up, the site says "more than …".</p>
  <h2>The delay check</h2>
  <ul><li><b>Gap since last hearing</b> is compared with the distribution of gaps between the last hearing and the next scheduled hearing in similar <i>pending</i> cases. Beyond the 95th percentile, it is shown as "longer than usual"; beyond the 75th, as "on the longer side".</li>
  <li><b>Case age</b>: if fewer than 10% (or 25%) of similar cases were still undecided at your case's age, that is reported too.</li>
  <li>"Similar" means the same case type in the same district. If that group has fewer than ${m.min_n} cases, the whole state, then all covered states, is used, and the page says which.</li></ul>
  <h2>Case types</h2>
  <p>Courts record case types with local abbreviations that differ by state. The site groups them conservatively using the recorded type name, and the act/section where recorded. Anything unclear stays in "Other / unclear type". Known gap: cheque-bounce complaints filed under generic criminal case types are counted as "Criminal case" unless the act is recorded. Most common recorded types and their group:</p>
  <table class="data"><thead><tr><th>Recorded type (normalised)</th><th>Group</th><th class="num">Cases</th></tr></thead><tbody>
  ${mapping.slice(0, 60).map((r) => `<tr><td>${esc(r.type)}</td><td>${esc(catName(r.category))}</td><td class="num">${fmtN(r.cases)}</td></tr>`).join("")}</tbody></table>
  <h2>How cases end</h2><p>The "nature of disposal" recorded by the court is grouped into broad outcomes. "Disposed (outcome not specified)" means the record does not say how the case ended.</p>
  <h2>Limits</h2><ul>
  <li>Records can contain wrong dates. Impossible dates (e.g. year 0001 or 9201) and inconsistent ones (decision before filing) are excluded from the affected figures.</li>
  <li>Groups with fewer than ${m.min_n} cases are not shown.</li>
  <li>Delays have many legitimate causes, such as summons not served, judge vacancies, stays by higher courts, complex evidence and absent witnesses. Nothing here says that any judge, lawyer, litigant or official did anything wrong.</li>
  <li>This is not legal advice. For your case, consult a lawyer or the District Legal Services Authority (free legal aid).</li></ul>
  <p class="note">Data generated ${esc(m.generated_at)}. Open-source code: Tareekh Radar.</p></section>`;
}

function pageAbout() {
  $("#main").innerHTML = `<section class="wrap page prose"><h1>${tr("about_title")}</h1>
  ${state.lang === "hi" ? `<p>Case Clock (तारीख घड़ी) आम लोगों के लिए एक मुफ़्त, गैर-व्यावसायिक उपकरण है। यह बताता है कि आपके ज़िले में समान मामलों में कितना समय लगा और क्या आपके मामले में सामान्य से अधिक देरी दिख रही है। यह किसी व्यक्ति पर आरोप नहीं लगाता और कानूनी सलाह नहीं देता।</p>` : ""}
  <p>Case Clock (तारीख घड़ी) is a free, non-commercial public tool. It answers two questions people in Indian courts ask every day: <i>how long will this take?</i> and <i>is my case taking longer than usual?</i></p>
  <p>It is built on the open-source <b>Tareekh Radar</b> research project. All figures are aggregates of real historical records. No individual case is shown, and groups of fewer than ${state.meta.min_n} cases are hidden.</p>
  <p>Data: Development Data Lab, Harvard Dataverse (doi:10.7910/DVN/GHLGSW). Please cite the original authors when you use these figures.</p>
  <p>${tr("disclaimer")}</p></section>`;
}


/* ---------------- help tools ---------------- */
const TOOLS = [["/diary", "tool_diary", "cal"], ["/deadlines", "tool_deadline", "clock"], ["/check", "tool_check", "calendar"], ["/find", "tool_find", "globe"], ["/decode", "tool_decode", "doc"],
  ["/lawyer", "tool_lawyer", "scales"], ["/cost", "tool_cost", "layers"], ["/rights", "tool_rights", "building"]];
function toolsGrid() {
  return `<div class="tools">${TOOLS.map(([p, k, ic]) => `<a class="tool" href="#${p}"><span class="tool-ic">${icons[ic]}</span><div><h3>${tr(k + "_t")}</h3><p>${tr(k + "_s")}</p></div><span class="go">→</span></a>`).join("")}</div>`;
}
const STEP_ICONS = { ns_decode: icons.doc, ns_status: icons.globe, ns_early: icons.doc, ns_highcourt: icons.building,
  ns_maint: icons.scales, ns_cheque: icons.scales, ns_undertrial: icons.scales, ns_lawyer: icons.doc, ns_aid: icons.scales, ns_cost: icons.clock };
function stepHref(k, sel, c) {
  const q = new URLSearchParams(Object.entries({ s: sel.s, d: sel.d, c }).filter(([, v]) => v)).toString();
  return { ns_decode: "#/decode", ns_status: "#/find", ns_early: "#/lawyer", ns_highcourt: "#/rights", ns_maint: "#/rights",
    ns_cheque: "#/rights", ns_undertrial: "#/rights", ns_lawyer: "#/lawyer", ns_aid: "#/rights", ns_cost: `#/cost?${q}` }[k] || "#/help";
}
function stuckMeter(res, stats) {
  const gp = approxPercentile(res.gapDays, stats?.next_hearing_gap_days);
  const decided = res.shareStillPendingAtAge == null ? null : 1 - res.shareStillPendingAtAge;
  if (gp == null && decided == null) return "";
  const bar = (v, label) => `<div class="meter"><div class="meter-track"><span style="width:${Math.max(2, Math.min(100, v)).toFixed(1)}%"></span></div><div class="meter-label">${label}</div></div>`;
  const gpTxt = gp >= 96 ? (state.lang === "hi" ? "95% से अधिक" : "more than 95%") : (state.lang === "hi" ? `लगभग ${Math.round(gp)}%` : `about ${Math.round(gp)}%`);
  return `<div class="card stuck"><h3>${tr("stuck_title")}</h3>
    ${gp != null ? bar(gp, esc(tr("stuck_gap", { p: gpTxt }))) : ""}
    ${decided != null ? bar(decided * 100, esc(tr("stuck_age", { p: pct(decided) }))) : ""}</div>`;
}
const backHead = (title, to = "#/help") => `<div class="page-head"><a class="back" href="${to}" aria-label="${tr("back")}">←</a><h1>${title}</h1></div>`;
async function purposes() { try { return (state.purposes ??= await getJSON("data/purposes.json")); } catch (_) { return null; } }
function stageText(st) { return st[state.lang] || st.en; }

function pageHelp() {
  $("#main").innerHTML = `<section class="wrap page">${backHead(tr("help_title"), "#/")}
    <p class="note">${tr("tools_sub")}</p>${toolsGrid()}</section>`;
}

function pageFind() {
  $("#main").innerHTML = `<section class="wrap page">${backHead(tr("find_title"))}
    <p class="lead">${tr("find_intro")}</p>
    <div class="grid-2 even">
      <div class="card"><h2>${tr("find_where")}</h2><ol class="clean">${[1, 2, 3, 4].map((i) => `<li>${tr("find_where_" + i)}</li>`).join("")}</ol></div>
      <div class="card"><h2>${tr("find_check")}</h2>
        <form id="cnr" class="inline-form"><label class="sr-only" for="cnr-i">CNR</label>
          <input id="cnr-i" class="text" placeholder="${tr("find_ph")}" maxlength="24" autocomplete="off" spellcheck="false" autocapitalize="characters">
          <button class="btn btn-red">${tr("find_go")}</button></form>
        <div id="cnr-out" class="cnr-out" aria-live="polite"></div><p class="note">${tr("cnr_note")}</p></div>
    </div>
    <div class="grid-2 even">
      <div class="card"><h2>${tr("find_how")}</h2><ul class="links">
        <li><a href="${LINKS.ecourts}" target="_blank" rel="noopener">${icons.globe}${tr("find_web")}<span class="go">↗</span></a></li>
        <li><a href="${LINKS.hc}" target="_blank" rel="noopener">${icons.building}${tr("find_hc")}<span class="go">↗</span></a></li>
        <li><a href="${LINKS.judgments}" target="_blank" rel="noopener">${icons.doc}${tr("find_judg")}<span class="go">↗</span></a></li></ul>
        <ul class="plain"><li>${tr("find_app")}</li><li>${esc(tr("find_sms"))}</li></ul></div>
      <div class="card"><h2>${tr("find_wrong")}</h2><ul class="plain">${[1, 2, 3].map((i) => `<li>${tr("find_wrong_" + i)}</li>`).join("")}</ul></div>
    </div><p class="note">${tr("not_advice")}</p></section>`;
  $("#cnr").addEventListener("submit", (e) => {
    e.preventDefault();
    const r = parseCNR($("#cnr-i").value);
    const out = $("#cnr-out");
    if (r.ok) {
      out.className = "cnr-out ok";
      out.innerHTML = `<b>✓ ${tr("cnr_ok")}</b><div class="mono">${esc(r.value)}</div><div>${esc(tr("cnr_parts", { st: r.state, di: r.district, es: r.establishment, se: r.serial, yr: r.year }))}</div>`;
    } else {
      out.className = "cnr-out bad";
      out.textContent = r.error === "len" ? tr("cnr_len", { n: r.value.length }) : tr(r.error === "year" ? "cnr_year" : "cnr_format");
    }
  });
}

async function pageDecode(params) {
  const q = params.get("q") || "";
  const pp = await purposes();
  // Real shares: aggregate recorded purposes of pending cases by decoded stage.
  const byStage = {};
  if (pp) for (const r of pp.purposes) { const st = decodePurpose(r.text); const k = st ? st.key : "_other"; byStage[k] = (byStage[k] || 0) + r.n; }
  const total = pp?.total_pending_with_purpose || 0;
  const top = Object.entries(byStage).filter(([k]) => k !== "_other").sort((a, b) => b[1] - a[1]).slice(0, 10);
  const stageBy = Object.fromEntries(STAGES.map((s) => [s.key, s]));
  $("#main").innerHTML = `<section class="wrap page">${backHead(tr("decode_title"))}
    <p class="lead">${tr("decode_intro")}</p>
    <form id="dq" class="inline-form wide"><label class="sr-only" for="dq-i">${tr("decode_title")}</label>
      <input id="dq-i" class="text" list="dq-list" placeholder="${esc(tr("decode_ph"))}" value="${esc(q)}" autocomplete="off">
      <datalist id="dq-list">${(pp?.purposes || []).slice(0, 80).map((r) => `<option value="${esc(r.text)}">`).join("")}</datalist>
      <button class="btn btn-red">${tr("decode_go")}</button></form>
    <div id="dq-out" class="result" aria-live="polite"></div>
    ${top.length ? `<div class="card" style="margin-top:22px"><h2>${tr("decode_common")}</h2><div class="hbars">
      ${top.map(([k, n]) => `<a class="hbar" href="#/decode?q=${encodeURIComponent(stageText(stageBy[k]).t)}&k=${k}"><span class="hb-l">${esc(stageText(stageBy[k]).t)}</span>
        <span class="hb-t"><span style="width:${((n / top[0][1]) * 100).toFixed(1)}%"></span></span><span class="hb-v">${pct(n / total)}</span></a>`).join("")}</div>
      <p class="note">${tr("based_on", { n: fmtN(total) })} · ${esc(pp.note)}</p></div>` : ""}
    <div class="card" style="margin-top:22px"><h2>${tr("decode_all")}</h2>
      ${STAGES.map((st) => `<details><summary>${esc(stageText(st).t)}</summary><p>${esc(stageText(st).m)}</p><p class="note">${esc(stageText(st).n)}</p></details>`).join("")}</div>
    <p class="note">${tr("not_advice")}</p></section>`;
  $("#dq").addEventListener("submit", (e) => { e.preventDefault(); go("/decode", { q: $("#dq-i").value.trim() }); });
  if (!q) return;
  const st = params.get("k") ? stageBy[params.get("k")] : decodePurpose(q);
  const out = $("#dq-out");
  if (!st) { out.innerHTML = `<div class="card"><p>${tr("decode_none")}</p><a class="btn btn-dark" href="#/lawyer">${tr("ns_lawyer")} <span class="arrow">→</span></a></div>`; return; }
  const tx = stageText(st);
  const share = total && byStage[st.key] ? tr("decode_share", { share: pct(byStage[st.key] / total), stage: tx.t }) : "";
  const g = st.group === "any" ? null : st.group;
  const qs = g ? (QUESTIONS[g][state.lang] || QUESTIONS[g].en) : QUESTIONS.any[state.lang].slice(0, 3);
  out.innerHTML = `<div class="card decode"><div class="kicker">“${esc(q)}”</div><h2>${esc(tx.t)}</h2>
    <h3>${tr("decode_means")}</h3><p>${esc(tx.m)}</p>
    <h3>${tr("decode_next")}</h3><p>${esc(tx.n)}</p>
    <h3>${tr("decode_ask")}</h3><ul class="plain">${qs.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
    ${share ? `<p class="note">${esc(share)}</p>` : ""}
    <a class="btn btn-dark" href="#/lawyer${g ? `?g=${g}` : ""}">${tr("ns_lawyer")} <span class="arrow">→</span></a></div>`;
}

function pageLawyer(params) {
  const g = STAGE_GROUPS.includes(params.get("g")) ? params.get("g") : "evidence";
  const qs = questionsFor(g, state.lang);
  const label = (k) => GROUP_LABEL[k][state.lang] || GROUP_LABEL[k].en;
  const text = `${tr("lawyer_title")} (${label(g)}):\n` + qs.map((x, i) => `${i + 1}. ${x}`).join("\n");
  $("#main").innerHTML = `<section class="wrap page">${backHead(tr("lawyer_title"))}
    <p class="lead">${tr("lawyer_intro")}</p>
    <div class="chips" aria-label="${tr("lawyer_stage")}">${STAGE_GROUPS.map((k) => `<a aria-current="${k === g ? "true" : "false"}" class="chip ${k === g ? "on" : ""}" href="#/lawyer?g=${k}">${esc(label(k))}</a>`).join("")}</div>
    <div class="card printable"><h2>${esc(label(g))}</h2>
      <ol class="checklist">${qs.map((x, i) => `<li><input type="checkbox" id="q${i}"><label for="q${i}">${esc(x)}</label></li>`).join("")}</ol>
      <div class="form-actions no-print">
        <button class="btn btn-red" id="l-print" type="button">${tr("lawyer_print")}</button>
        <a class="btn btn-dark" href="https://wa.me/?text=${encodeURIComponent(text)}" target="_blank" rel="noopener">${tr("lawyer_share")}</a>
        <button class="btn btn-ghost" id="l-copy" type="button">${tr("lawyer_copy")}</button></div>
      <p class="note">${tr("lawyer_tip")}</p></div>
    <p class="note">${tr("not_advice")}</p></section>`;
  $("#l-print").addEventListener("click", () => window.print());
  $("#l-copy").addEventListener("click", async (e) => {
    try { await navigator.clipboard.writeText(text); e.target.textContent = tr("copied"); } catch (_) { /* clipboard blocked */ }
  });
}

async function pageCost(params) {
  const s = params.get("s") || "", d = params.get("d") || "", c = params.get("c") || "";
  const kindOf = (cat) => (CRIMINAL_CATS.has(cat) ? "criminal" : "civil");
  const def = (cat) => DAKSH[kindOf(cat)].spend + DAKSH[kindOf(cat)].lost;
  const per = params.get("per") != null && params.get("per") !== "" ? Math.max(0, Number(params.get("per")) || 0) : def(c);
  const ppl = Math.max(1, Math.min(20, Number(params.get("p")) || 1));
  $("#main").innerHTML = `<section class="wrap page">${backHead(tr("cost_title"))}
    <p class="lead">${tr("cost_intro")}</p>
    <form id="f">${selectorHTML({ s, d, c })}
      <div class="form-grid" style="margin-top:14px">
        <div class="field"><label for="i-per">${tr("cost_perday")}</label><input class="text" type="number" min="0" step="50" id="i-per" value="${per}"></div>
        <div class="field"><label for="i-p">${tr("cost_people")}</label><input class="text" type="number" min="1" max="20" id="i-p" value="${ppl}"></div></div>
      <p class="note" id="def-note"></p>
      <div class="form-actions"><button class="btn btn-red">${tr("cost_go")} <span class="arrow">→</span></button></div>
      <ul class="errors" id="errs"></ul></form><div id="out" class="result"></div></section>`;
  wireSelectors($("#main"));
  let dirty = params.get("per") != null;
  const showDef = (cat) => { const k = kindOf(cat); $("#def-note").textContent = tr("cost_default", { kind: tr("cost_kind_" + k), spend: DAKSH[k].spend, lost: DAKSH[k].lost }); };
  showDef(c);
  $("#i-per").addEventListener("input", () => { dirty = true; });
  $("#sel-c").addEventListener("change", (e) => { showDef(e.target.value); if (!dirty) $("#i-per").value = def(e.target.value); });
  $("#f").addEventListener("submit", (e) => {
    e.preventDefault();
    const v = readSel();
    if (!v.s || !v.d || !v.c) { $("#errs").innerHTML = `<li>${tr("err_select")}</li>`; return; }
    go("/cost", { ...v, per: $("#i-per").value, p: $("#i-p").value });
  });
  if (!(s && d && c)) return;
  const { level, stats, district } = await statsFor(s, d, c);
  const tt = stats?.time_to_decision_days || {};
  const beyond = tt.p50 == null;
  const dur = beyond ? tt.max_followup : tt.p50;
  const gap = stats?.next_hearing_gap_days?.p50;
  const est = costEstimate({ durationDays: dur, gapDays: gap, perDay: per, people: ppl });
  if (!est) { $("#out").innerHTML = `<p>${tr("suppressed")}</p>`; return; }
  const money = "₹" + Math.round(est.total).toLocaleString("en-IN");
  $("#out").innerHTML = `<div class="crumb">${esc(catName(c))} · ${esc(district?.name || "")}, ${esc(district?.state_name || "")}</div>
    <div class="card cost"><div class="cost-big">${esc(tr("cost_money", { money }))}</div>
      <div class="cost-sub">${esc(tr("cost_result", { h: fmtN(est.hearings) }))}</div>
      <p>${esc(tr("cost_explain", { cat: catName(c), dur: formatDuration(dur, state.lang), gap: formatDuration(est.gap, state.lang), h: fmtN(est.hearings), per: fmtN(per), p: ppl }))}</p>
      ${beyond ? `<p class="note">${esc(tr("cost_beyond", { dur: formatDuration(dur, state.lang) }))}</p>` : ""}
      <p class="note">${tr("cost_caveat")} <a href="${DAKSH.source}" target="_blank" rel="noopener">DAKSH</a></p></div>
    ${levelNote(level, stats.n)}<p class="note">${tr("not_advice")}</p>`;
}

async function pageRights(params) {
  const s = params.get("s") || "", d = params.get("d") || "";
  $("#main").innerHTML = `<section class="wrap page">${backHead(tr("rights_title"))}
    <div class="grid-2 even">
      <div class="card"><h2>${tr("aid_title")}</h2><p>${tr("aid_intro")}</p>
        <ul class="ticks">${tr("aid_list").split("|").map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
        <p><b>${tr("aid_how")}</b></p>
        <ul class="links"><li><a href="tel:15100">${icons.scales}NALSA 15100<span class="go">☎</span></a></li>
        <li><a href="${LINKS.dlsa}" target="_blank" rel="noopener">${icons.globe}nalsa.gov.in<span class="go">↗</span></a></li></ul></div>
      <div class="card"><h2>${tr("limits_title")}</h2><p class="note">${tr("limits_intro")}</p>
        <ul class="plain">${["lim_ws", "lim_adj", "lim_crim", "lim_maint", "lim_cheque", "lim_undertrial", "lim_hc"].map((k) => `<li>${esc(tr(k))}</li>`).join("")}</ul></div>
    </div>
    <div class="card"><h2>${tr("real_title")}</h2>
      <form id="f">${selectorHTML({ withCategory: false, s, d })}<div class="form-actions"><button class="btn btn-red">${tr("real_pick")} <span class="arrow">→</span></button></div></form>
      <div id="out"></div></div>
    <p class="note">${tr("not_advice")}</p></section>`;
  wireSelectors($("#main"));
  $("#f").addEventListener("submit", (e) => { e.preventDefault(); const v = readSel(); if (v.s) go("/rights", { s: v.s, d: v.d }); });
  if (!s) return;
  const rows = [["maintenance", "target_maint"], ["cheque_bounce", "target_cheque"], ["bail", "target_bail"]];
  const res = await Promise.all(rows.map(([c]) => statsFor(s, d, c)));
  const lv = { district: tr("level_district"), state: tr("level_state"), national: tr("level_national") };
  $("#out").innerHTML = `<div class="table-scroll"><table class="data" style="margin-top:14px"><thead><tr><th>${tr("col_type")}</th><th>${tr("real_cat_target")}</th><th class="num">${tr("real_cat_median")}</th><th class="num">${tr("col_n")}</th></tr></thead><tbody>
    ${rows.map(([c, tk], i) => { const r = res[i]; const st = r.stats;
      return `<tr><td>${esc(catName(c))}<div class="note">${esc(st ? tr("stats_from", { level: lv[r.level] || "" }) : "")}</div></td><td>${tr(tk)}</td>
        <td class="num">${st ? esc(headlineOrBeyond(st.time_to_decision_days?.p50, st)) : "–"}</td><td class="num">${st ? fmtN(st.n) : "–"}</td></tr>`; }).join("")}
    </tbody></table></div>${(res[2].stats?.time_to_decision_days?.p50 ?? 0) > 182 || (res[2].stats && res[2].stats.time_to_decision_days?.p50 == null) ? `<p class="note warn">${esc(tr("bail_note"))}</p>` : ""}<p class="note">${dataYearsNote()}</p>`;
}



/* ---------------- account + sync (Firebase; optional) ---------------- */
const lastJson = new Map(); // case id -> JSON at last change, to know what to stamp and push
const snap = (c) => JSON.stringify({ ...c, updated: 0 });
const sync = { cloud: null, off: false, ready: false, user: null, status: "", at: 0, pushed: new Map() };
const D = () => {
  if (!diary) { diary = loadDiary(); diary.cases.forEach((c) => lastJson.set(c.id, snap(c))); }
  return diary;
};
function stamp() {
  for (const c of D().cases) { const j = snap(c); if (lastJson.get(c.id) !== j) { c.updated = Date.now(); lastJson.set(c.id, j); } }
}
function persist() { stamp(); if (!saveDiary(diary)) alert(tr("diary_save_fail")); cloudPush(); }

async function cloudPush() {
  const u = sync.user;
  if (!sync.cloud || !u || !u.emailVerified) return;
  try {
    const ids = new Set(D().cases.map((c) => c.id));
    for (const c of D().cases) if (sync.pushed.get(c.id) !== c.updated) { await sync.cloud.putCase(u.uid, c); sync.pushed.set(c.id, c.updated); }
    for (const id of [...sync.pushed.keys()]) if (!ids.has(id)) { await sync.cloud.removeCase(u.uid, id); sync.pushed.delete(id); }
    sync.status = "ok"; sync.at = Date.now();
  } catch (e) { sync.status = "error"; console.warn("sync failed", e?.code || e); }
  paintChip();
}
async function onUser(u) {
  sync.user = u; sync.ready = true; sync.pushed.clear(); sync.status = "";
  if (u && u.emailVerified) {
    try {
      const remote = sanitizeDiary({ cases: await sync.cloud.pull(u.uid) })?.cases || [];
      const m = mergeCases(D().cases, remote);
      diary.cases = m.cases;
      remote.forEach((c) => sync.pushed.set(c.id, c.updated));
      m.cases.forEach((c) => lastJson.set(c.id, snap(c)));
      saveDiary(diary);
      await cloudPush();
    } catch (e) { sync.status = "error"; console.warn("sync failed", e?.code || e); }
  }
  paintChip();
  render();
}
function paintChip() {
  const a = $("#acct"); if (!a) return;
  const u = sync.user;
  a.textContent = u ? (u.email || "").split("@")[0].slice(0, 14) || tr("acct_me") : tr("acct_signin");
  a.classList.toggle("on", !!u);
}
function authMsg(e) {
  const k = "ae_" + String(e?.code || "").replace("auth/", "").replace(/-/g, "_");
  const s = tr(k);
  return s === k ? tr("ae_other") : s;
}

function pageAccount() {
  if (sync.off) { $("#main").innerHTML = `<section class="wrap page">${backHead(tr("acct_title"), "#/")}<p>${tr("acct_unavailable")}</p></section>`; return; }
  if (!sync.ready) { $("#main").innerHTML = `<section class="wrap page">${backHead(tr("acct_title"), "#/")}<p class="note">${tr("loading")}</p></section>`; return; }
  const u = sync.user;
  if (!u) {
    $("#main").innerHTML = `<section class="wrap page">${backHead(tr("acct_title"), "#/")}
      <p class="lead">${tr("acct_intro")}</p><div class="notice">${tr("acct_local_ok")}</div>
      <div class="card"><label class="consent"><input type="checkbox" id="consent"><span>${tr("acct_consent")} <a href="#/privacy">${tr("privacy_title")}</a></span></label>
        <div class="form-actions"><button class="btn btn-dark" id="g" type="button">${tr("acct_google")}</button></div>
        <p class="note" style="text-align:center">${tr("acct_or")}</p>
        <form id="ef"><div class="form-grid">
          <div class="field"><label for="a-email">${tr("acct_email")}</label><input class="text" id="a-email" type="email" autocomplete="email" required></div>
          <div class="field"><label for="a-pw">${tr("acct_password")}</label><input class="text" id="a-pw" type="password" autocomplete="current-password" minlength="8"></div></div>
          <div class="form-actions"><button class="btn btn-red" id="si">${tr("acct_signin")}</button>
            <button class="btn btn-ghost" id="su" type="button">${tr("acct_create")}</button>
            <button class="link-btn" id="rp" type="button">${tr("acct_forgot")}</button></div>
          <p class="note">${tr("acct_pw_hint")}</p><ul class="errors" id="errs" aria-live="polite"></ul><p class="note ok" id="info" aria-live="polite"></p></form></div>
      <p class="note"><a href="#/privacy">${tr("privacy_title")}</a></p></section>`;
    const err = (m) => { $("#errs").innerHTML = m ? `<li>${esc(m)}</li>` : ""; $("#info").textContent = ""; };
    const needConsent = () => { if ($("#consent").checked) return false; err(tr("acct_need_consent")); return true; };
    const run = async (fn) => { err(""); try { await fn(); } catch (e) { err(authMsg(e)); } };
    $("#g").addEventListener("click", () => { if (!needConsent()) run(() => sync.cloud.signInGoogle().then(() => go("/diary"))); });
    $("#ef").addEventListener("submit", (e) => { e.preventDefault(); run(() => sync.cloud.signIn($("#a-email").value.trim(), $("#a-pw").value).then(() => go("/diary"))); });
    $("#su").addEventListener("click", () => {
      if (!$("#ef").reportValidity() || needConsent()) return;
      run(async () => { await sync.cloud.signUp($("#a-email").value.trim(), $("#a-pw").value); go("/account"); });
    });
    $("#rp").addEventListener("click", () => {
      const em = $("#a-email").value.trim();
      if (!em) { err(tr("ae_invalid_email")); return; }
      run(async () => { await sync.cloud.resetPassword(em); $("#info").textContent = tr("acct_reset_sent"); });
    });
    return;
  }
  const n = D().cases.length;
  const statusTxt = !u.emailVerified ? tr("acct_unverified") : sync.status === "error" ? tr("acct_sync_err") : tr("acct_sync_ok", { n, t: sync.at ? new Date(sync.at).toLocaleTimeString(state.lang === "hi" ? "hi-IN" : "en-IN") : "" });
  $("#main").innerHTML = `<section class="wrap page">${backHead(tr("acct_title"), "#/")}
    <div class="card"><h2>${esc(u.email || "")}</h2><p class="${sync.status === "error" || !u.emailVerified ? "warn" : "ok"}">${esc(statusTxt)}</p>
      ${u.emailVerified ? "" : `<p>${tr("acct_verify_help", { e: esc(u.email) })}</p><div class="form-actions"><button class="btn btn-red" id="vr" type="button">${tr("acct_verified_btn")}</button>
        <button class="btn btn-ghost" id="vs" type="button">${tr("acct_resend")}</button></div>`}
      <p class="note" id="info" aria-live="polite"></p><ul class="errors" id="errs" aria-live="polite"></ul></div>
    <div class="form-actions"><a class="btn btn-dark" href="#/diary">${tr("nav_diary")}</a><button class="btn btn-ghost" id="out" type="button">${tr("acct_signout")}</button></div>
    <div class="card danger-zone" style="margin-top:22px"><h2>${tr("acct_delete_t")}</h2><p>${tr("acct_delete_p")}</p>
      <button class="btn btn-ghost danger" id="del" type="button">${tr("acct_delete")}</button></div>
    <p class="note"><a href="#/privacy">${tr("privacy_title")}</a></p></section>`;
  const err = (m) => { $("#errs").innerHTML = m ? `<li>${esc(m)}</li>` : ""; };
  $("#out").addEventListener("click", () => sync.cloud.logout());
  $("#vr")?.addEventListener("click", async () => { try { await onUser(await sync.cloud.refreshUser()); if (!sync.user.emailVerified) $("#info").textContent = tr("acct_still_unverified"); } catch (e) { err(authMsg(e)); } });
  $("#vs")?.addEventListener("click", async () => { try { await sync.cloud.resendVerification(); $("#info").textContent = tr("acct_resent"); } catch (e) { err(authMsg(e)); } });
  $("#del").addEventListener("click", async () => {
    if (!confirm(tr("acct_delete_q"))) return;
    try { await sync.cloud.deleteAccount(); alert(tr("acct_deleted")); go("/"); }
    catch (e) { err(e?.code === "auth/requires-recent-login" ? tr("acct_reauth") : authMsg(e)); }
  });
}

function pagePrivacy() {
  const hi = state.lang === "hi";
  $("#main").innerHTML = `<section class="wrap page prose"><h1>${tr("privacy_title")}</h1>
  ${hi ? `<p><b>सारांश:</b> खाते के बिना आपकी डायरी केवल आपके डिवाइस पर रहती है। खाता बनाने पर आपका ईमेल और आपकी केस डायरी (मामले के नाम, तारीखें, नोट्स) Google Firebase (मुंबई क्षेत्र) में सहेजी जाती है ताकि वह दूसरे डिवाइस पर खुल सके। कोई विज्ञापन, विश्लेषण या डेटा बिक्री नहीं। आप ऐप में ही खाता और सारा क्लाउड डेटा हटा सकते हैं। यह नोटिस सरल भाषा का मसौदा है और किसी वकील ने इसकी समीक्षा नहीं की है। विवरण नीचे अंग्रेज़ी में है।</p>` : ""}
  <p class="note">Last updated 14 November 2026. This is a plain-language draft and has not been reviewed by a lawyer.</p>
  <h2>Who runs this</h2><p>Case Clock is a free, non-commercial project run by an individual (the "project owner"). Contact for privacy questions or requests: <a href="https://github.com/faizdevx/Tareekh_Radar/issues" rel="noopener">open an issue on the project's GitHub page</a>. Please do not put case details in a public issue.</p>
  <h2>Without an account</h2><p>The delay checker, estimates, deadline calculator and all other tools run in your browser. Your case diary is saved only on your device. Nothing you type is sent to us.</p>
  <h2>With an account: what we store</h2><ul><li>Your email address and sign-in method (Google or email and password).</li><li>The case diary you choose to save: case names, optional CNR, court, filing date, hearing dates, purposes, adjournment notes and anything you write in your notes.</li></ul>
  <p>We do not collect your name, phone number, location, device identifiers or browsing activity. There are no advertising or analytics tools on this site.</p>
  <h2>Why</h2><p>Only to let you sign in and open your diary on more than one device. We do not use it for anything else, and we do not sell or share it.</p>
  <h2>Where and who</h2><p>Accounts and diary data are held by Google Firebase (Authentication and Cloud Firestore) in the Mumbai region (asia-south1). Google acts as our service provider. Data is encrypted in transit. Access rules allow each signed-in user to read and write only their own diary. The project owner can technically open the database through the Firebase console but does not read users' diaries.</p>
  <h2>Please be careful what you write</h2><p>Do not enter other people's names, phone numbers, addresses or identity numbers, or anything you would not want stored online. Case names can be nicknames ("Cheque case 1"). If you want nothing stored online, do not create an account.</p>
  <h2>"Ask an AI" (optional)</h2><p>The "Ask an AI" panel builds a question from numbers on this site and the timing details you entered (case type, district, case age, stage). It never includes your CNR, names or diary notes unless you type them. You can read and edit the text, and nothing happens until you tick the box and press a button. The text then goes from your browser straight to the AI app you choose (for example ChatGPT or Claude) and is handled under that company's own privacy policy. We do not receive it or the answer.</p>
  <h2>Your choices</h2><ul><li>Use every tool without an account.</li><li>Export a backup file of your diary at any time (My cases → Export backup).</li><li>Delete your account and all your cloud data yourself, in the app (Account → Delete my account and cloud data). A copy kept on your own device is not touched.</li><li>Withdraw consent by deleting your account. To ask for a correction or deletion another way, contact us as above.</li></ul>
  <h2>How long</h2><p>Until you delete it.</p>
  <h2>If something goes wrong</h2><p>If we learn of a breach affecting your data, we will tell affected users and the authorities as the law requires. No online service can promise perfect security.</p>
  <h2>Children</h2><p>This service is meant for adults. Please do not create an account if you are under 18.</p>
  <h2>Changes</h2><p>If this notice changes in a way that matters, we will say so on this page and in the sign-in screen.</p></section>`;
}

/* ---------------- my case diary (this device, synced to your account if you sign in) ---------------- */
let diary = null;
const fmtDate = (iso) => (iso ? new Date(iso + "T00:00:00Z").toLocaleDateString(state.lang === "hi" ? "hi-IN" : "en-IN",
  { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }) : "–");
function dueText(next) {
  if (!next) return tr("diary_no_next");
  const n = daysBetween(todayISO(), next);
  return n < 0 ? tr("diary_passed", { d: fmtDate(next) }) : n === 0 ? tr("diary_today") : tr("diary_in_days", { n, d: fmtDate(next) });
}
function districtName(c) {
  const st = state.meta.states.find((x) => x.code === c.s);
  return st?.districts.find((x) => x.id === c.d)?.name || "";
}
const caseMeta = (c) => [c.cnr, c.c ? catName(c.c) : "", districtName(c), c.court].filter(Boolean).join(" · ");

function caseFormHTML(c = {}) {
  return `<div class="form-grid">
      <div class="field"><label for="c-label">${tr("f_label")}</label><input class="text" id="c-label" maxlength="120" value="${esc(c.label || "")}" required></div>
      <div class="field"><label for="c-cnr">${tr("f_cnr")}</label><input class="text" id="c-cnr" maxlength="24" value="${esc(c.cnr || "")}" autocomplete="off" spellcheck="false" autocapitalize="characters"></div>
      <div class="field"><label for="c-filed">${tr("f_filed")}</label><input type="date" id="c-filed" value="${esc(c.filed || "")}"></div></div>
    <div style="margin-top:14px">${selectorHTML({ s: c.s, d: c.d, c: c.c })}</div>
    <div class="field" style="margin-top:14px"><label for="c-court">${tr("f_court")}</label><input class="text" id="c-court" maxlength="160" value="${esc(c.court || "")}"></div>`;
}
/** Read and validate the case form; returns [fields, errors]. */
function readCaseForm() {
  const v = { label: $("#c-label").value.trim(), cnr: $("#c-cnr").value.trim(), filed: $("#c-filed").value, court: $("#c-court").value.trim(), ...readSel() };
  const errs = [];
  if (!v.label) errs.push(tr("err_label"));
  if (v.cnr) { const r = parseCNR(v.cnr); if (r.ok) v.cnr = r.value; else errs.push(tr("err_cnr")); }
  if (v.filed && v.filed > todayISO()) errs.push(tr("err_future"));
  return [{ label: v.label, cnr: v.cnr.toUpperCase(), filed: v.filed, court: v.court, s: v.s, d: v.d, c: v.c }, errs];
}

function pageDiary() {
  const cases = [...D().cases].sort((a, b) => (caseSummary(a).next || "9999").localeCompare(caseSummary(b).next || "9999"));
  $("#main").innerHTML = `<section class="wrap page">${backHead(tr("diary_title"), "#/")}
    <p class="lead">${tr("diary_intro")}</p>
    <div class="notice">${tr("diary_private")}</div>
    ${cases.length ? `<div class="case-list">${cases.map((c) => {
      const s = caseSummary(c); const n = s.next ? daysBetween(todayISO(), s.next) : null;
      return `<a class="case-card ${n != null && n < 0 ? "overdue" : n != null && n <= 7 ? "soon" : ""}" href="#/case?id=${encodeURIComponent(c.id)}">
        <div><h3>${esc(c.label)}</h3><div class="note">${esc(caseMeta(c))}</div></div>
        <div class="due"><b>${esc(dueText(s.next))}</b>${s.purpose ? `<span class="note">${esc(s.purpose)}</span>` : ""}</div><span class="go">→</span></a>`;
    }).join("")}</div>` : `<div class="card empty"><p>${tr("diary_empty")}</p></div>`}
    <details class="card add-case" ${cases.length ? "" : "open"}><summary>${tr("diary_add")}</summary>
      <form id="addc">${caseFormHTML()}<div class="form-actions"><button class="btn btn-red">${tr("f_save")}</button></div><ul class="errors" id="errs"></ul></form></details>
    <div class="form-actions"><button class="btn btn-ghost" id="exp" type="button" ${cases.length ? "" : "disabled"}>${tr("diary_export")}</button>
      <label class="btn btn-ghost" for="imp">${tr("diary_import")}</label><input type="file" id="imp" accept="application/json,.json" class="sr-only"></div>
    <p class="note">${tr("diary_backup_note")}</p></section>`;
  wireSelectors($("#main"));
  $("#addc").addEventListener("submit", (e) => {
    e.preventDefault();
    const [v, errs] = readCaseForm();
    if (errs.length) { $("#errs").innerHTML = errs.map((x) => `<li>${x}</li>`).join(""); return; }
    const c = { id: newId(), ...v, entries: [] };
    D().cases.push(c); persist(); go("/case", { id: c.id });
  });
  $("#exp").addEventListener("click", () => download(`case-clock-diary-${todayISO()}.json`, JSON.stringify(D(), null, 1), "application/json"));
  $("#imp").addEventListener("change", async (e) => {
    const f = e.target.files?.[0]; if (!f) return;
    let data = null;
    try { data = f.size < 5e6 ? sanitizeDiary(JSON.parse(await f.text())) : null; } catch (_) { data = null; }
    if (!data || !data.cases.length) { alert(tr("diary_import_bad")); return; }
    if (!confirm(tr("diary_import_confirm", { n: data.cases.length }))) return;
    const byId = new Map(D().cases.map((c) => [c.id, c]));
    for (const c of data.cases) byId.set(c.id, c);
    diary.cases = [...byId.values()]; persist(); render();
  });
}

async function pageCase(params) {
  const c = D().cases.find((x) => x.id === params.get("id"));
  if (!c) { $("#main").innerHTML = `<section class="wrap page">${backHead(tr("diary_title"), "#/diary")}<p>${tr("diary_notfound")}</p></section>`; return; }
  const s = caseSummary(c);
  const stage = decodePurpose(s.purpose);
  const pp = await purposes();
  const ages = c.filed ? formatDuration(daysBetween(c.filed, todayISO()), state.lang) : "–";
  const entries = sortedEntries(c).reverse();
  $("#main").innerHTML = `<section class="wrap page">${backHead(esc(c.label), "#/diary")}
    <div class="crumb">${esc(caseMeta(c)) || tr("diary_add_details")}${c.filed ? ` · ${tr("filing_date")}: ${fmtDate(c.filed)}` : ""}</div>
    <div class="grid-2 even">
      <div class="card next-card"><h2>${tr("diary_next")}</h2>
        <div class="next-date">${s.next ? fmtDate(s.next) : "–"}</div><div class="due-line">${esc(dueText(s.next))}</div>
        ${s.purpose ? `<p><b>${esc(s.purpose)}</b>${stage ? ` → ${esc(stageText(stage).t)}: ${esc(stageText(stage).m)}` : ""}</p>` : ""}
        <div class="form-actions no-print">
          ${s.next ? `<button class="btn btn-red" id="ics" type="button">${tr("diary_add_ics")}</button>` : ""}
          <a class="btn btn-dark" href="#/lawyer${stage && stage.group !== "any" ? `?g=${stage.group}` : ""}">${tr("ns_lawyer")}</a></div></div>
      <div class="card"><h2>${tr("diary_stats")}</h2>
        <div class="two-stats"><div class="statbox"><div class="k">${tr("diary_hearings")}</div><div class="v">${fmtN(s.hearings)}</div></div>
          <div class="statbox"><div class="k">${tr("diary_age")}</div><div class="v" style="font-size:26px">${esc(ages)}</div></div></div>
        <div class="k">${tr("diary_adj")}</div>
        <ul class="adj">${["mine", "other", "court", "unknown"].map((k) => `<li><span>${tr("adj_" + k)}</span><b>${fmtN(s.adj[k])}</b></li>`).join("")}</ul></div>
    </div>
    <div id="stuck"></div>
    <div class="card no-print" style="margin-top:18px"><h2>${tr("diary_log")}</h2>
      <form id="loge"><div class="form-grid">
        <div class="field"><label for="e-date">${tr("f_hdate")}</label><input type="date" id="e-date" value="${todayISO()}" max="${todayISO()}" required></div>
        <div class="field"><label for="e-next">${tr("f_next")}</label><input type="date" id="e-next"></div>
        <div class="field"><label for="e-adj">${tr("f_adj")}</label><select id="e-adj">${ADJ_BY.map((k) => `<option value="${k}">${tr("adj_" + k)}</option>`).join("")}</select></div></div>
        <div class="field" style="margin-top:14px"><label for="e-purpose">${tr("f_purpose")}</label><input class="text" id="e-purpose" maxlength="200" list="e-plist" autocomplete="off">
          <datalist id="e-plist">${(pp?.purposes || []).slice(0, 80).map((r) => `<option value="${esc(r.text)}">`).join("")}</datalist></div>
        <div class="field" style="margin-top:14px"><label for="e-happened">${tr("f_happened")}</label><textarea id="e-happened" rows="3" maxlength="2000"></textarea></div>
        <div class="form-actions"><button class="btn btn-red">${tr("f_log_save")}</button></div><ul class="errors" id="errs"></ul></form></div>
    <div class="card" style="margin-top:18px"><h2>${tr("diary_timeline")}</h2>
      ${entries.length ? `<ol class="timeline">${entries.map((e) => `<li><div class="t-date">${fmtDate(e.date)}</div><div class="t-body">
        ${e.purpose ? `<b>${esc(e.purpose)}</b>` : ""}${e.adjBy !== "none" ? ` <span class="badge">${tr("adj_short")}: ${tr("adj_" + e.adjBy)}</span>` : ""}
        ${e.happened ? `<p>${esc(e.happened)}</p>` : ""}${e.next ? `<div class="note">${tr("f_next")}: ${fmtDate(e.next)}</div>` : ""}</div>
        <button class="link-btn no-print" data-del="${esc(e.id)}" type="button">${tr("diary_del_entry")}</button></li>`).join("")}</ol>` : `<p class="note">${tr("diary_no_entries")}</p>`}</div>
    <details class="card no-print" style="margin-top:18px"><summary>${tr("diary_edit")}</summary>
      <form id="editc">${caseFormHTML(c)}<div class="form-actions"><button class="btn btn-red">${tr("f_save")}</button></div><ul class="errors" id="errs2"></ul></form></details>
    <div class="form-actions no-print"><button class="btn btn-dark" id="print" type="button">${tr("diary_print")}</button>
      <button class="btn btn-ghost danger" id="delc" type="button">${tr("diary_del_case")}</button></div>
    <p class="note">${tr("diary_private")}</p></section>`;
  wireSelectors($("#editc"));

  $("#ics")?.addEventListener("click", () => download(`hearing-${s.next}.ics`, buildICS({
    uid: `${c.id}-${s.next}`, date: s.next, title: tr("ics_title", { label: c.label }),
    description: [s.purpose, stage ? stageText(stage).t : "", c.cnr && `CNR ${c.cnr}`, c.court, tr("ics_carry")].filter(Boolean).join("\n"),
  }), "text/calendar"));
  $("#loge").addEventListener("submit", (e) => {
    e.preventDefault();
    const v = { id: newId(), date: $("#e-date").value, next: $("#e-next").value, adjBy: $("#e-adj").value,
      purpose: $("#e-purpose").value.trim(), happened: $("#e-happened").value.trim() };
    const errs = [];
    if (!v.date) errs.push(tr("err_last")); else if (v.date > todayISO()) errs.push(tr("err_future"));
    if (v.next && v.date && v.next < v.date) errs.push(tr("err_next_before"));
    if (errs.length) { $("#errs").innerHTML = errs.map((x) => `<li>${x}</li>`).join(""); return; }
    c.entries.push(v); persist(); render();
  });
  $("#main").querySelectorAll("[data-del]").forEach((b) => b.addEventListener("click", () => {
    if (!confirm(tr("diary_del_entry_q"))) return;
    c.entries = c.entries.filter((x) => x.id !== b.dataset.del); persist(); render();
  }));
  $("#editc").addEventListener("submit", (e) => {
    e.preventDefault();
    const [v, errs] = readCaseForm();
    if (errs.length) { $("#errs2").innerHTML = errs.map((x) => `<li>${x}</li>`).join(""); return; }
    Object.assign(c, v); persist(); render();
  });
  $("#print").addEventListener("click", () => window.print());
  $("#delc").addEventListener("click", () => {
    if (!confirm(tr("diary_del_case_q"))) return;
    diary.cases = diary.cases.filter((x) => x.id !== c.id); persist(); go("/diary");
  });

  // Compare with real cases once the case has enough details.
  if (!(c.s && c.d && c.c && c.filed && s.last)) { $("#stuck").innerHTML = `<p class="note" style="margin-top:14px">${tr("diary_check_need")}</p>`; return; }
  const { level, stats, district } = await statsFor(c.s, c.d, c.c);
  const res = checkCase({ filing: c.filed, last: s.last, next: s.next || null }, stats, new Date(todayISO() + "T00:00:00Z"));
  if (res.errors.length || !stats) return;
  const vText = { longer: tr("v_longer"), somewhat: tr("v_somewhat"), usual: tr("v_usual"), insufficient: tr("v_insufficient") }[res.verdict];
  $("#stuck").innerHTML = `<div class="verdict ${res.verdict}" style="margin-top:18px">${icons.hourglass}<span>${esc(vText)}</span></div>
    <div style="margin-top:14px">${timeLeftHTML(stats, res.ageDays)}</div>${stuckMeter(res, stats)}
    <div id="ai-slot" class="no-print" style="margin-top:14px"></div>
    <ul class="links no-print" style="margin-top:14px">${nextSteps(res, c.c).map((k) => `<li><a href="${stepHref(k, c, c.c)}">${STEP_ICONS[k] || icons.doc}${esc(tr(k))}<span class="go">→</span></a></li>`).join("")}</ul>`;
  mountAskAI($("#ai-slot"), aiFacts({ stats, level, district, c: c.c, res, purposeText: s.purpose, diaryStats: { hearings: s.hearings, adj: s.adj } }));
}

function pageDeadlines(params) {
  const k = DEADLINES.some((x) => x.key === params.get("k")) ? params.get("k") : "";
  const from = /^\d{4}-\d{2}-\d{2}$/.test(params.get("from") || "") ? params.get("from") : "";
  const dl = (x) => x[state.lang] || x.en;
  $("#main").innerHTML = `<section class="wrap page">${backHead(tr("dl_title"))}
    <p class="lead">${tr("dl_intro")}</p>
    <form id="f"><div class="form-grid">
      <div class="field" style="grid-column: span 2"><label for="dl-k">${tr("dl_what")}</label><select id="dl-k"><option value="">${tr("dl_pick")}</option>
        ${DEADLINES.map((x) => `<option value="${x.key}" ${x.key === k ? "selected" : ""}>${esc(dl(x).t)}</option>`).join("")}</select></div>
      <div class="field"><label for="dl-from" id="dl-from-l">${k ? esc(dl(DEADLINES.find((x) => x.key === k)).from) : tr("dl_from")}</label><input type="date" id="dl-from" value="${from}"></div></div>
      <div class="form-actions"><button class="btn btn-red">${tr("dl_go")} <span class="arrow">→</span></button></div><ul class="errors" id="errs"></ul></form>
    <div id="out" class="result"></div>
    <div class="card" style="margin-top:22px"><h2>${tr("dl_rules")}</h2><ul class="plain">${["dl_rule_1", "dl_rule_2", "dl_rule_3", "dl_rule_4"].map((x) => `<li>${esc(tr(x))}</li>`).join("")}</ul></div>
    <p class="note">${tr("not_advice")}</p></section>`;
  $("#dl-k").addEventListener("change", (e) => { const x = DEADLINES.find((d) => d.key === e.target.value); $("#dl-from-l").textContent = x ? dl(x).from : tr("dl_from"); });
  $("#f").addEventListener("submit", (e) => {
    e.preventDefault();
    const v = { k: $("#dl-k").value, from: $("#dl-from").value };
    if (!v.k || !v.from) { $("#errs").innerHTML = `<li>${tr("dl_err")}</li>`; return; }
    go("/deadlines", v);
  });
  if (!(k && from)) return;
  const x = DEADLINES.find((d) => d.key === k);
  const last = applySteps(from, x.steps);
  const left = daysBetween(todayISO(), last);
  const weekday = new Date(last + "T00:00:00Z").toLocaleDateString(state.lang === "hi" ? "hi-IN" : "en-IN", { weekday: "long", timeZone: "UTC" });
  $("#out").innerHTML = `<div class="card cost ${left < 0 ? "late" : ""}"><div class="kicker">${esc(dl(x).t)}</div>
    <div class="cost-sub">${tr("dl_last")}</div><div class="cost-big">${fmtDate(last)}</div><div class="due-line">${esc(weekday)} · ${esc(
      left < 0 ? tr("dl_over", { n: -left }) : left === 0 ? tr("dl_today") : tr("dl_left", { n: left }))}</div>
    ${left < 0 ? `<p class="warn"><b>${tr("dl_late")}</b></p>` : left <= 7 ? `<p class="warn"><b>${tr("dl_soon")}</b></p>` : ""}
    ${dl(x).note ? `<p>${esc(dl(x).note)}</p>` : ""}${x.appeal ? `<p class="note">${tr("dl_copy")}</p>` : ""}
    <p class="note">${tr("dl_law")}: ${esc(x.law)}</p>
    <div class="form-actions no-print">${left >= 0 ? `<button class="btn btn-red" id="ics" type="button">${tr("diary_add_ics")}</button>` : ""}</div></div>`;
  $("#ics")?.addEventListener("click", () => download(`deadline-${last}.ics`, buildICS({
    uid: `dl-${k}-${last}`, date: last, title: tr("dl_ics", { t: dl(x).t }), description: `${x.law}\n${tr("not_advice")}`,
  }), "text/calendar"));
}


/* ---------------- time left + "ask an AI" ---------------- */
function timeLeftHTML(stats, ageDays) {
  const r = remainingTime(stats?.curve_monthly_share_decided, ageDays);
  const dur = (m) => formatDuration(m * MONTH_DAYS, state.lang);
  const age = dur(r.ageMonths ?? Math.max(0, Math.floor(ageDays / MONTH_DAYS)));
  let body;
  if (r.status === "none") body = `<p>${tr("tl_none")}</p>`;
  else if (r.status === "beyond") body = `<p>${tr("tl_beyond", { max: dur(r.followupMonths) })}</p>`;
  else {
    const part = (m) => (m == null ? tr("not_reached", { d: dur(r.moreThan) }) : dur(m));
    body = `<div class="two-stats"><div class="statbox"><div class="k">${tr("tl_half")}</div><div class="v">${esc(part(r.p50))}</div></div>
      <div class="statbox"><div class="k">${tr("tl_nine")}</div><div class="v">${esc(part(r.p90))}</div></div></div>
      ${r.next12 != null ? `<p>${esc(tr("tl_next12", { p: pct(r.next12) }))}</p>` : ""}${r.thin ? `<p class="warn">${tr("tl_thin")}</p>` : ""}`;
  }
  return `<div class="card timeleft"><h3>${tr("tl_title")}</h3>${r.status === "none" ? "" : `<p class="note">${esc(tr("tl_sub", { age }))}</p>`}${body}<p class="note">${tr("tl_note")}</p></div>`;
}

/** Facts for the AI prompt: aggregates and the person's own timing only (never names, CNR or notes). */
function aiFacts({ stats, level, district, c, res, purposeText, diaryStats }) {
  const en = (k) => t("en", k);
  const dur = (d) => formatDuration(d, "en");
  const tt = stats.time_to_decision_days || {};
  const head = (d) => (d == null ? `more than ${formatHeadline(tt.max_followup, "en")}` : formatHeadline(d, "en"));
  const gap = stats.next_hearing_gap_days;
  const m = state.meta;
  const f = {
    years: m.filing_years.length > 2 ? `${m.filing_years[0]}-${m.filing_years[m.filing_years.length - 1]}` : m.filing_years.join(", "),
    category: m.categories[c]?.en ?? c, place: [district?.name, district?.state_name].filter(Boolean).join(", "),
    source: { district: "this district", state: "the whole state", national: "all covered states" }[level], n: stats.n,
    half: head(tt.p50), nine: head(tt.p90), gapMedian: gap ? dur(gap.p50) : null, gapP95: gap ? dur(gap.p95) : null,
    outcomes: Object.entries(stats.outcomes || {}).filter(([k, v]) => v >= 0.05 && k !== "unspecified").slice(0, 4)
      .map(([k, v]) => `${m.outcome_groups?.[k]?.en ?? k} ${pct(v)}`),
  };
  if (res) {
    f.age = dur(res.ageDays); f.sinceLast = dur(res.gapDays);
    f.scheduled = res.scheduledGapDays != null ? dur(res.scheduledGapDays) : null;
    f.verdict = en({ longer: "v_longer", somewhat: "v_somewhat", usual: "v_usual", insufficient: "v_insufficient" }[res.verdict]);
    f.reasons = res.reasons.map((k) => en(k));
    f.left = describeLeft(remainingTime(stats.curve_monthly_share_decided, res.ageDays));
  }
  if (purposeText) { const st = decodePurpose(purposeText); f.stage = { text: purposeText, meaning: st ? st.en.t : "" }; }
  if (diaryStats) { f.hearings = diaryStats.hearings; f.adj = diaryStats.adj; }
  return f;
}

/** Renders the "Ask an AI" panel into `el`. The person sees and can edit the exact text, and must tick a box. */
function mountAskAI(el, facts) {
  if (!el) return;
  el.innerHTML = `<details class="card ask-ai"><summary>${tr("ai_title")}</summary>
    <p>${tr("ai_intro")}</p>
    <div class="field"><label for="ai-q">${tr("ai_q_label")}</label><input class="text" id="ai-q" maxlength="500" placeholder="${esc(tr("ai_q_ph"))}" autocomplete="off"></div>
    <label class="note" for="ai-t" style="display:block;margin-top:12px">${tr("ai_preview")}</label>
    <textarea id="ai-t" rows="14" spellcheck="false"></textarea>
    <label class="consent"><input type="checkbox" id="ai-ok"><span>${tr("ai_consent")}</span></label>
    <div class="form-actions"><button class="btn btn-red" id="ai-gpt" type="button">${tr("ai_chatgpt")}</button>
      <button class="btn btn-dark" id="ai-cl" type="button">${tr("ai_claude")}</button>
      <button class="btn btn-ghost" id="ai-cp" type="button">${tr("ai_copy")}</button></div>
    <p class="note" id="ai-msg" aria-live="polite"></p><p class="note">${tr("ai_note")}</p></details>`;
  const ta = $("#ai-t", el), q = $("#ai-q", el), ok = $("#ai-ok", el), msg = $("#ai-msg", el);
  let edited = false;
  const fill = () => { if (!edited) ta.value = buildPrompt({ ...facts, question: q.value }, state.lang); check(); };
  const check = () => { msg.textContent = aiLinks(ta.value).direct ? "" : tr("ai_too_long"); };
  const open = (which) => {
    if (!ok.checked) { msg.textContent = tr("ai_need_consent"); return; }
    const l = aiLinks(ta.value);
    if (!l.direct) { msg.textContent = tr("ai_too_long"); return; }
    window.open(l[which], "_blank", "noopener,noreferrer");
  };
  q.addEventListener("input", fill);
  ta.addEventListener("input", () => { edited = true; check(); });
  $("#ai-gpt", el).addEventListener("click", () => open("chatgpt"));
  $("#ai-cl", el).addEventListener("click", () => open("claude"));
  $("#ai-cp", el).addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(ta.value); msg.textContent = tr("copied"); } catch (_) { ta.select(); document.execCommand?.("copy"); msg.textContent = tr("copied"); }
  });
  fill();
}

/* ---------------- router ---------------- */
async function render() {
  const { path, params } = parseHash();
  try { await meta(); } catch (e) {
    $("#main").innerHTML = `<section class="wrap page"><p>${tr("no_data")}</p><p class="note">${esc(e.message)}</p></section>`;
    renderChrome(path);
    return;
  }
  renderChrome(path);
  const pages = { "/": pageHome, "/estimate": pageEstimate, "/check": pageCheck, "/district": pageDistrict, "/method": pageMethod, "/about": pageAbout,
    "/help": pageHelp, "/find": pageFind, "/decode": pageDecode, "/lawyer": pageLawyer, "/cost": pageCost, "/rights": pageRights,
    "/diary": pageDiary, "/case": pageCase, "/deadlines": pageDeadlines, "/account": pageAccount, "/privacy": pagePrivacy };
  const fn = pages[path] || pageHome;
  try { await fn(params); } catch (e) {
    $("#main").innerHTML = `<section class="wrap page"><p>${tr("no_data")}</p><p class="note">${esc(e.message)}</p></section>`;
  }
  window.scrollTo(0, 0);
}

state.lang = loadLang();
import("./cloud.js").then((m) => { sync.cloud = m; m.watch(onUser); }).catch((e) => { sync.off = true; console.warn("cloud unavailable", e); });
$("#lang-toggle").addEventListener("click", () => { state.lang = state.lang === "en" ? "hi" : "en"; saveLang(state.lang); render(); });
window.addEventListener("hashchange", render);
render();

export { MONTH_DAYS, shareDecidedAt };
