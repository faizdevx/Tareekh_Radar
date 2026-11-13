"""Tareekh Radar - Streamlit research interface.

Run from the repository root:  streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tareekh_radar import DISCLAIMER  # noqa: E402
from tareekh_radar.anomaly import FEATURE_LABELS, mode_config  # noqa: E402
from tareekh_radar.config import load_config  # noqa: E402
from tareekh_radar.service import get_dataset, optional_csv, optional_json  # noqa: E402
from tareekh_radar.storage import list_datasets  # noqa: E402

st.set_page_config(page_title="Tareekh Radar", page_icon=":material/radar:", layout="wide")

PAGES = ["Court Overview", "Case Timeline", "Anomaly Radar", "Data Quality Monitor", "Research Evaluation"]
CLASS_COLORS = {"ADJOURNMENT": "#d1495b", "PROCEDURAL_PROGRESS": "#edae49", "SUBSTANTIVE_PROGRESS": "#00798c",
                "UNKNOWN": "#9e9e9e"}


def _cfg() -> dict:
    # TAREEKH_CONFIG may point to a YAML merged over config/default.yaml.
    return load_config(os.environ.get("TAREEKH_CONFIG") or None)


def fmt(v, nd=0, pct=False):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "n/a"
    return f"{v:.{nd}%}" if pct else f"{v:,.{nd}f}"


def provenance_banner(v) -> None:
    o = v.overview()
    if o["is_synthetic"]:
        st.error("SYNTHETIC DATA - not real court records.")
    level = ("Case-level records (one row per case; no per-hearing history)" if v.mode == "case"
             else "Hearing-level records")
    st.info(f"**Dataset:** {v.name} | **Source:** {o['source']}  \n"
            f"**Scope:** {o['geographic_scope']}  \n**Granularity:** {level} | "
            f"**Snapshot/reference date:** {o['reference_date']} | **Licence:** {o['license']}")


def hbar(series: pd.Series, xlabel: str, ylabel: str, title: str) -> None:
    if series.empty:
        st.write(f"**{title}:** none recorded.")
        return
    df = pd.DataFrame({ylabel: series.index.astype(str), xlabel: series.to_numpy()})
    st.plotly_chart(px.bar(df, x=xlabel, y=ylabel, orientation="h", title=title), width="stretch")


def disclaimer() -> None:
    st.caption(DISCLAIMER)


# ---------------------------------------------------------------- pages

def page_overview(v) -> None:
    st.header("Court Overview")
    provenance_banner(v)
    o = v.overview()
    a = v.anomalies
    c = st.columns(5)
    c[0].metric("Cases analysed", fmt(o["total_cases"]))
    c[1].metric("Recorded hearings", fmt(o["total_hearings"]) if v.mode == "hearing" else "not in source")
    c[2].metric("Scored vs peers", fmt(o["scored_cases"]))
    c[3].metric("Unusual patterns flagged", fmt(o["flagged_cases"]),
                help="Statistical flags relative to comparable cases - not findings of wrongdoing.")
    c[4].metric("Mean data completeness", fmt(o["mean_data_completeness"], 0, pct=True))
    if v.mode == "hearing":
        c = st.columns(4)
        c[0].metric("Confirmed adjournments", fmt(o.get("confirmed_adjournments")))
        c[1].metric("Procedural progress", fmt(o.get("procedural_progress_events")))
        c[2].metric("Substantive progress", fmt(o.get("substantive_progress_events")))
        c[3].metric("Unknown records", f"{fmt(o.get('unknown_events'))} ({fmt(o.get('unknown_record_pct'), 1)}%)")
    else:
        c = st.columns(4)
        c[0].metric("Median duration, disposed (days)", fmt(o.get("median_case_age_days_disposed")))
        c[1].metric("Median age, pending (days)", fmt(o.get("median_case_age_days_pending")))
        c[2].metric("Median days since last listing (pending)", fmt(o.get("median_days_since_last_listing_pending")))
        c[3].metric("Median days to first listing", fmt(o.get("median_days_to_first_listing")))
        st.caption("Adjournment counts cannot be observed in this source: it records only filing, first/last/next "
                   "listing and decision dates per case. Those metrics are shown as unavailable, not as zero.")
    st.caption(f"Flags on cases whose source record has data-quality problems: {fmt(o['flagged_with_quality_issue'])} "
               f"of {fmt(o['flagged_cases'])} (see Data Quality Monitor).")

    left, right = st.columns(2)
    with left:
        s = a["case_status"].value_counts().reset_index()
        s.columns = ["status", "cases"]
        st.plotly_chart(px.bar(s, x="status", y="cases", title="Case status"), width="stretch")
    with right:
        sev = a.loc[a["flagged"], "severity"].value_counts().reindex(["low", "medium", "high"]).fillna(0).reset_index()
        sev.columns = ["severity", "cases"]
        st.plotly_chart(px.bar(sev, x="severity", y="cases", title="Flagged cases by severity"), width="stretch")
    by_court = (a.groupby(["court_id", "court_name"], dropna=False)
                .agg(cases=("case_id", "size"), scored=("score_status", lambda s: (s == "scored").sum()),
                     flagged=("flagged", "sum"), completeness=("data_completeness", "mean")).reset_index())
    by_court["flag_rate_%"] = (100 * by_court["flagged"] / by_court["scored"].replace(0, np.nan)).round(2)
    st.subheader("By court establishment")
    st.dataframe(by_court.sort_values("cases", ascending=False), width="stretch", hide_index=True)
    if v.mode == "hearing" and len(v.hearings):
        ec = v.hearings["event_class"].value_counts().reset_index()
        ec.columns = ["event_class", "hearings"]
        st.plotly_chart(px.pie(ec, names="event_class", values="hearings", color="event_class",
                               color_discrete_map=CLASS_COLORS, title="Hearing event classes"), width="stretch")
    disclaimer()


def page_timeline(v) -> None:
    st.header("Case Timeline")
    provenance_banner(v)
    default = st.session_state.get("selected_case", "")
    case_id = st.text_input("Pseudonymised case id", value=default, placeholder="e.g. C-1A2B3C4D5E").strip()
    if not case_id:
        flagged = v.anomaly_table(limit=20)
        if len(flagged):
            st.write("Or pick one of the highest-scoring flagged cases:")
            case_id = st.selectbox("Flagged case", [""] + flagged["case_id"].tolist())
    if not case_id:
        st.stop()
    try:
        row = v.case_row(case_id)
        tl = v.timeline(case_id)
    except KeyError:
        st.warning(f"No case with id {case_id!r} in this dataset.")
        st.stop()
    st.session_state["selected_case"] = case_id
    c = st.columns(5)
    c[0].metric("Court", str(row.get("court_name") or row["court_id"]))
    c[1].metric("Case type (normalised)", str(row["case_type"]))
    c[2].metric("Status", str(row["case_status"]))
    c[3].metric("Anomaly score", fmt(row.get("anomaly_score"), 2))
    c[4].metric("Data completeness", fmt(row.get("data_completeness"), 0, pct=True))
    st.caption(f"Source record: `{row.get('source_reference')}` | quality flags: `{row.get('case_quality_status')}`")

    if v.mode == "hearing":
        t = tl.dropna(subset=["hearing_date"])
        if len(t):
            fig = px.scatter(t, x="hearing_date", y="stage_norm", color="event_class", color_discrete_map=CLASS_COLORS,
                             hover_data=["last_order", "event_reason", "data_quality_status"],
                             title="Hearings by recorded stage")
            fig.update_traces(marker=dict(size=11))
            st.plotly_chart(fig, width="stretch")
        undated = tl["hearing_date"].isna().sum()
        if undated:
            st.warning(f"{undated} hearing record(s) have no usable date and are listed at the end.")
    else:
        t = tl.dropna(subset=["date"])
        if len(t):
            fig = go.Figure(go.Scatter(x=t["date"], y=[1] * len(t), mode="markers+text+lines", text=t["event"],
                                       textposition="top center", marker=dict(size=13)))
            fig.update_yaxes(visible=False)
            fig.update_layout(title="Recorded case dates", height=280)
            st.plotly_chart(fig, width="stretch")
        bad = tl[tl["date"].isna()]
        if len(bad):
            st.warning("Dates missing or rejected as invalid: " + ", ".join(
                f"{r.event} (raw: {r.raw_value!r}, status: {r.date_status})" for r in bad.itertuples()))
    st.dataframe(tl, width="stretch", hide_index=True)
    render_explanation(v.explanation(case_id))
    disclaimer()


def render_explanation(e: dict) -> None:
    st.subheader("Explanation")
    st.write(e["summary"])
    if e.get("peer_group"):
        p = e["peer_group"]
        st.markdown(f"**Peer group:** {p['definition']} ({p['size']:,} cases)")
    for c in e.get("contributions", []):
        with st.expander(f"{c['label']} - robust z {c['robust_z']:.1f}, peer percentile {c['peer_percentile']:.1%}",
                         expanded=True):
            st.write(c["sentence"])
            st.markdown("**Possible legitimate explanations:** " + "; ".join(c["possible_legitimate_explanations"]))
            if c.get("supporting_hearing_ids"):
                st.markdown("**Supporting hearing records:** " + ", ".join(map(str, c["supporting_hearing_ids"][:30])))
            if c.get("supporting_record"):
                st.markdown(f"**Supporting record:** `{c['supporting_record']}` - "
                            + ", ".join(f"{k}: {v}" for k, v in c.get("supporting_fields", {}).items()))
    dc = e.get("data_completeness", {})
    def shown(v):
        return v not in (None, {}, "") and not (isinstance(v, float) and np.isnan(v)) and str(v) != "nan"

    st.markdown("**Data completeness:** " + ", ".join(f"{k}: {v}" for k, v in dc.items() if shown(v)))
    with st.expander("Model limitations"):
        for lim in e.get("limitations", []):
            st.write("- " + lim)


def page_radar(v) -> None:
    st.header("Anomaly Radar")
    provenance_banner(v)
    a = v.anomalies
    f = st.columns(6)
    court = f[0].selectbox("Court", [""] + sorted(a["court_id"].dropna().unique().tolist()),
                           format_func=lambda c: c if not c else f"{c} - {a.loc[a.court_id == c, 'court_name'].iloc[0]}")
    ctype = f[1].selectbox("Case type", [""] + a.loc[a["flagged"], "case_type"].value_counts().index.tolist())
    stage = f[2].selectbox("Recorded stage", [""] + sorted(a["current_stage"].dropna().astype(str).unique().tolist()))
    sev = f[3].multiselect("Severity", ["high", "medium", "low"], default=["high", "medium", "low"])
    comp = f[4].slider("Min. data completeness", 0.0, 1.0, 0.0, 0.05)
    n_q = int(a.get("flag_has_quality_issue", pd.Series(False)).sum())
    excl = f[5].checkbox(f"Hide flags on records with data-quality issues ({n_q:,})", value=True,
                         help="These cases are flagged, but their source record has inconsistent or invalid dates, "
                              "so the pattern may be a data artefact. Untick to include them.")
    t = v.anomaly_table(court or None, ctype or None, stage or None, sev, comp, True, excl, limit=None)
    st.write(f"**{len(t):,}** flagged cases match. Ranked by anomaly score (max one-sided robust z vs peer group).")
    show = t.head(500).copy()
    show["contributing_features"] = show["contributing_features"].map(
        lambda s: ", ".join(FEATURE_LABELS.get(x, x) for x in json.loads(s)))
    st.dataframe(show.drop(columns=["anomaly_explanation"]), width="stretch", hide_index=True)
    if len(t):
        pick = st.selectbox("Open case", t["case_id"].head(500).tolist())
        render_explanation(v.explanation(pick))
        if st.button("Open chronological case history"):
            st.session_state["selected_case"] = pick
            st.session_state["page"] = "Case Timeline"
            st.rerun()
    disclaimer()


def page_quality(v) -> None:
    st.header("Data Quality Monitor")
    provenance_banner(v)
    q = v.quality
    st.markdown("Data-quality problems are reported here **separately** from analytical findings. "
                "Anomaly scores never use completeness as an input; flags on records with quality problems are marked.")
    rows = q["rows"]
    c = st.columns(5)
    c[0].metric("Case rows (raw)", fmt(rows["cases_raw"]))
    c[1].metric("Case rows (clean)", fmt(rows["cases_clean"]))
    c[2].metric("Rejected rows", fmt(rows["rejected"]))
    c[3].metric("Duplicate case rows", fmt(q["duplicates"]["case_duplicate_rows"]))
    c[4].metric("Duplicate hearing rows", fmt(q["duplicates"]["hearing_duplicate_rows"]))
    left, right = st.columns(2)
    with left:
        mc = pd.Series(q["missingness_pct"]["cases"], dtype=float).dropna().sort_values()
        hbar(mc, "% missing", "field", "Missingness by field (cases)")
    with right:
        fc = pd.Series(q["cases"]["case_flag_counts"], dtype=float).drop("ok", errors="ignore").sort_values()
        hbar(fc, "cases", "flag", "Case-level quality flags (invalid dates, chronology)")
    ds = pd.DataFrame(q["cases"]["date_status"]).fillna(0).astype(int).T
    st.subheader("Date validity by field")
    st.dataframe(ds, width="stretch")
    cov = q["case_coverage"]
    st.subheader("Coverage")
    c = st.columns(4)
    c[0].metric("Sufficient history", f"{fmt(cov['cases_with_sufficient_history_pct'], 1)}%",
                help=cov.get("sufficient_history_definition"))
    c[1].metric("Eligible for analysis", f"{fmt(cov['cases_eligible_for_anomaly_analysis_pct'], 1)}%")
    c[2].metric("Scored", f"{fmt(cov['cases_scored_pct'], 1)}%")
    c[3].metric("No comparable peer group", fmt(cov["cases_without_peer_group"]))
    if cov.get("ineligible_reasons"):
        st.write("Reasons cases were not analysed:")
        st.dataframe(pd.Series(cov["ineligible_reasons"], name="cases"), width="stretch")
    st.write(f"Distinct case types: {q['cases']['distinct_case_types_raw']:,} raw spellings -> "
             f"{q['cases']['distinct_case_types_normalized']:,} after orthographic normalisation.")
    st.dataframe(pd.Series(q["cases"]["current_purpose_stage_distribution"], name="cases"), width="stretch")
    cl = q.get("classification", {})
    if cl.get("applicable") is False:
        st.info("Hearing classification uncertainty: not applicable - " + cl.get("note", ""))
    else:
        st.subheader("Hearing descriptions and classification uncertainty")
        st.json({k: q["hearings"].get(k) for k in ("hearings_missing_description_pct", "hearing_invalid_dates",
                                                     "hearing_missing_dates", "hearings_unknown_stage_pct")})
        st.json(cl)
    with st.expander("Validation warnings"):
        for w in q["validation"]["warnings"]:
            st.write("- " + w)
    disclaimer()


def page_research(v) -> None:
    st.header("Research Evaluation")
    provenance_banner(v)
    cfg = _cfg()
    a = v.anomalies
    ev = optional_json(cfg, v.name, "evaluation")
    fspec = mode_config(cfg, v.mode)["features"]
    scored = a[a["score_status"] == "scored"]

    st.subheader("Anomaly score distributions")
    c1, c2 = st.columns(2)
    c1.plotly_chart(px.histogram(scored, x="anomaly_score", nbins=60, log_y=True,
                                 title="Statistical score (max robust z vs peers)"), width="stretch")
    c2.plotly_chart(px.histogram(scored.dropna(subset=["if_score"]), x="if_score", nbins=60, log_y=True,
                                 title="Isolation Forest score (experimental)"), width="stretch")
    samp = scored.dropna(subset=["if_score"])
    samp = samp.sample(min(len(samp), 5000), random_state=0)
    st.plotly_chart(px.scatter(samp, x="anomaly_score", y="if_score", color="flagged", opacity=0.5,
                               title="Statistical vs Isolation Forest (sample of 5,000 scored cases)"),
                    width="stretch")
    st.subheader("Feature distributions")
    feat = st.selectbox("Feature", list(fspec), format_func=lambda f: FEATURE_LABELS.get(f, f))
    st.plotly_chart(px.histogram(a.dropna(subset=[feat]), x=feat, color="case_status", nbins=80, log_y=True,
                                 barmode="overlay"), width="stretch")

    if ev is None:
        st.info(f"No evaluation run yet. Run: `python -m tareekh_radar.cli evaluate --dataset {v.name}`")
    else:
        comp = ev["anomaly_comparison"]
        st.subheader("Baseline comparison")
        c = st.columns(3)
        c[0].metric("Flagged (statistical)", fmt(comp["n_flagged_statistical"]))
        c[1].metric("Flagged (Isolation Forest, top fraction)", fmt(comp["n_flagged_isolation_forest"]))
        c[2].metric("Flagged by both", fmt(comp["flag_agreement"]["both"]))
        rc = pd.Series(comp["rank_correlation"], name="Spearman rho").dropna()
        st.dataframe(rc, width="stretch")
        tk = pd.Series(comp["topk_jaccard"], name="top-k Jaccard overlap").dropna()
        st.dataframe(tk, width="stretch")
        st.write("Concentration of top-ranked cases in single courts (peer normalisation vs raw ranking):")
        st.dataframe(pd.DataFrame(comp["top_ranked_court_concentration"]).T, width="stretch")
        hr = ev.get("human_review")
        st.subheader("Human validation")
        if hr:
            st.json(hr)
            if comp.get("labelled_evaluation"):
                st.json(comp["labelled_evaluation"])
        else:
            st.info("No completed human review yet. Export a blind review sheet with "
                    f"`python -m tareekh_radar.cli review-export --dataset {v.name}`, fill `reviewer_verdict`, then "
                    "re-run `evaluate --review-file <file>`. No validation numbers are shown until humans review cases.")
        st.subheader("Classification performance")
        st.info(ev.get("classification", ""))
        sens = optional_csv(cfg, v.name, "sensitivity.csv")
        if sens is not None:
            st.subheader("Sensitivity to missing records")
            agg = sens.groupby(["perturbation", "rate"]).mean(numeric_only=True).reset_index()
            ycol = st.selectbox("Metric", [c for c in agg.columns if c not in ("perturbation", "rate", "repeat")])
            st.plotly_chart(px.line(agg, x="rate", y=ycol, color="perturbation", markers=True), width="stretch")
        gc = optional_csv(cfg, v.name, "group_comparison.csv")
        if gc is not None:
            st.subheader("Comparison across courts and case types")
            dim = st.radio("Dimension", sorted(gc["dimension"].unique()), horizontal=True)
            st.dataframe(gc[gc["dimension"] == dim].sort_values("cases", ascending=False), width="stretch",
                         hide_index=True)
    disclaimer()


def main() -> None:
    cfg = _cfg()
    st.sidebar.title("Tareekh Radar")
    st.sidebar.caption("Explainable detection of unusual case-progression patterns in court records.")
    names = list_datasets(cfg)
    if not names:
        st.title("Tareekh Radar")
        st.warning("No processed dataset found in data/processed. See README: download the DDL eCourts data, "
                   "run `ddl-extract` and `process`, then reload.")
        disclaimer()
        return
    name = st.sidebar.selectbox("Dataset", names)
    page = st.sidebar.radio("Module", PAGES, index=PAGES.index(st.session_state.get("page", PAGES[0])))
    st.session_state["page"] = page
    try:
        v = get_dataset(cfg, name)
    except Exception as exc:  # pragma: no cover - surfaced to the user
        st.error(f"Could not load dataset {name!r}: {exc}")
        return
    st.sidebar.markdown(f"**Granularity:** {v.mode}-level  \n**Cases:** {len(v.anomalies):,}")
    {"Court Overview": page_overview, "Case Timeline": page_timeline, "Anomaly Radar": page_radar,
     "Data Quality Monitor": page_quality, "Research Evaluation": page_research}[page](v)


main()
