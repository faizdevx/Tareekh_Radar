import { t } from "./i18n.js";
import { icons, logo, hero, brush, vignetteScales, vignetteHourglass, vignettePen, courthouse } from "./art.js";
import { pickStats, checkCase, formatDuration, formatHeadline, pct, shareDecidedAt, MONTH_DAYS } from "./logic.js";

const OUTCOME_COLORS = {
  compromise: "#4b8a3c", lok_adalat: "#8fb35d", allowed: "#2f6f8f", dismissed: "#b8ad9e", withdrawn: "#ddd3c4",
  convicted: "#e3a23b", acquitted: "#e07b39", closed: "#8a7f74", unspecified: "#cfc6b8",
};
const LINKS = {
  dlsa: "https://nalsa.gov.in/",
  lok: "https://nalsa.gov.in/",
  ecourts: "https://services.ecourts.gov.in/",
};

const state = { lang: "en", meta: null, national: null, states: {}, districts: {} };
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
  const nav = [["/estimate", "nav_estimate"], ["/check", "nav_check"], ["/district", "nav_districts"], ["/method", "nav_method"], ["/about", "nav_about"]];
  $("#main-nav").innerHTML = nav.map(([p, k]) => `<a href="#${p}" class="${path === p ? "active" : ""}">${tr(k)}</a>`).join("");
  $("#lang-toggle").innerHTML = state.lang === "en" ? "<b>EN</b> / हिंदी" : "EN / <b>हिंदी</b>";
  const bn = [["/", "nav_home", icons.home], ["/estimate", "nav_estimate", icons.hg], ["/check", "nav_check_short", icons.calsm], ["/district", "nav_districts", icons.barsm]];
  $("#bottom-nav").innerHTML = bn.map(([p, k, ic]) => `<a href="#${p}" class="${path === p ? "active" : ""}">${ic}<span>${tr(k)}</span></a>`).join("");
  $("#disclaimer").textContent = tr("disclaimer");
  const m = state.meta;
  const years = m ? m.filing_years.join("–") : "";
  $("#footer").innerHTML = `<a class="brand" href="#/">${logo("#fff")}<span><div class="brand-name">${tr("brand")}</div><div class="brand-hi">${tr("brand_hi")}</div></span></a>
    <div class="fnote">${tr("footer_note")} ${years ? `(${esc(years)})` : ""}</div>
    <nav><a href="#/about">${tr("nav_about")}</a><a href="#/method">${tr("nav_method")}</a><a href="${m ? esc(m.source_url) : "#/method"}" rel="noopener">Data</a></nav>
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
  return tr("data_years", { years: m.filing_years.join(", "), snap: snaps.filter(Boolean)[Math.floor(snaps.filter(Boolean).length / 2)]?.slice(0, 4) || "" });
}
async function statsFor(s, d, c) {
  const [dd, ss, nn] = await Promise.all([d ? districtData(d).catch(() => null) : null, s ? stateData(s).catch(() => null) : null, national()]);
  return { ...pickStats(c, dd, ss, nn), district: dd, stateObj: ss };
}

/* ---------------- pages ---------------- */
async function pageHome() {
  const m = state.meta;
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
    <div class="hero-art">${hero()}</div>
    <div class="hero-copy"><div>
      <h1 class="hero-title">${tr("hero_title_1")}<br>${tr("hero_title_2")}</h1>${brush()}
      <p class="hero-sub">${tr("hero_sub")}</p>
      <a class="btn btn-dark" href="#/check">${tr("cta_check")} <span class="arrow">→</span></a></div>
      <div class="vignettes"><div class="vignette">${vignetteHourglass()}</div><div class="vignette red">${vignetteScales()}</div><div class="vignette">${vignettePen()}</div></div>
    </div>
  </section>
  <div class="scallop"></div>
  <section class="wrap"><div class="features">
    <a class="feature" href="#/estimate">${icons.hourglass}<div><h3>${tr("f_estimate_t")}</h3><p>${tr("f_estimate_s")}</p></div></a>
    <a class="feature" href="#/check">${icons.calendar}<div><h3>${tr("f_check_t")}</h3><p>${tr("f_check_s")}</p></div></a>
    <a class="feature" href="#/district">${icons.bars}<div><h3>${tr("f_district_t")}</h3><p>${tr("f_district_s")}</p></div></a>
  </div>
  <div class="how"><div><h2>${tr("how_title")}</h2><div class="steps">
    <div class="step"><span class="num">1</span>${tr("how_1")}</div><div class="step"><span class="num">2</span>${tr("how_2")}</div><div class="step"><span class="num">3</span>${tr("how_3")}</div>
  </div></div><div class="how-art">${courthouse()}</div></div>
  <div class="band"><div class="band-art">${courthouse()}</div>
    <div><div class="big">${fmtN(m.totals.cases)}</div><div class="lbl">${tr("band_cases")} (${tr("band_years")} ${esc(m.filing_years.join("–"))})</div></div>
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
    ${levelNote(level, stats.n)}<p class="note">${tr("not_advice")}</p>`;
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
      <div class="form-actions"><button class="btn btn-red">${tr("check_go")} <span class="arrow">→</span></button><span class="note">${tr("privacy_note")}</span></div>
      <ul class="errors" id="errs"></ul></form><div id="out" class="result"></div></section>`;
  wireSelectors($("#main"));
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
    renderCheckResult(res, stats, level, district, v.c);
  });
}

function renderCheckResult(res, stats, level, district, c) {
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
    <h2 class="section-title" style="margin-top:20px;font-size:20px">${tr("steps_title")}</h2>
    <ul class="links">
      <li><a href="${LINKS.ecourts}" target="_blank" rel="noopener">${icons.globe}${tr("step_ecourts")}<span class="go">→</span></a></li>
      <li><a href="${LINKS.dlsa}" target="_blank" rel="noopener">${icons.doc}${tr("step_early")}<span class="go">→</span></a></li>
      <li><a href="${LINKS.dlsa}" target="_blank" rel="noopener">${icons.scales}${tr("step_dlsa")}<span class="go">→</span></a></li>
      <li><a href="${LINKS.lok}" target="_blank" rel="noopener">${icons.building}${tr("step_lok")}<span class="go">→</span></a></li>
    </ul>${levelNote(level, stats?.n)}<p class="note">${tr("not_advice")}</p>`;
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
  const years = state.meta.filing_years.join("–");
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
    ${byYear.length ? `<h3>${tr("by_year")}</h3>${yearChart(byYear, sts.by_filing_year)}` : ""}
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
  <p>Coverage on this site: cases <b>filed in ${esc(m.filing_years.join(" and "))}</b>, ${fmtN(m.totals.cases)} cases in ${fmtN(m.totals.states)} states and ${fmtN(m.totals.districts)} districts, as recorded when the data was collected (mostly early 2019, some records updated in 2020). ${esc(dataYearsNote())} These are <b>historical patterns</b>, not live case status.</p>
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

/* ---------------- router ---------------- */
async function render() {
  const { path, params } = parseHash();
  try { await meta(); } catch (e) {
    $("#main").innerHTML = `<section class="wrap page"><p>${tr("no_data")}</p><p class="note">${esc(e.message)}</p></section>`;
    renderChrome(path);
    return;
  }
  renderChrome(path);
  const pages = { "/": pageHome, "/estimate": pageEstimate, "/check": pageCheck, "/district": pageDistrict, "/method": pageMethod, "/about": pageAbout };
  const fn = pages[path] || pageHome;
  try { await fn(params); } catch (e) {
    $("#main").innerHTML = `<section class="wrap page"><p>${tr("no_data")}</p><p class="note">${esc(e.message)}</p></section>`;
  }
  window.scrollTo(0, 0);
}

state.lang = loadLang();
$("#lang-toggle").addEventListener("click", () => { state.lang = state.lang === "en" ? "hi" : "en"; saveLang(state.lang); render(); });
window.addEventListener("hashchange", render);
render();

export { MONTH_DAYS, shareDecidedAt };
