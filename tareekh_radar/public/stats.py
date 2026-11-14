"""Statistics for the public site.

Time to decision is estimated with the Kaplan-Meier estimator. Cases still pending are
*right-censored*: we know only that they took at least that long, so they are neither
dropped nor treated as decided. DDL does not publish when each record was collected (most
were collected in early 2019, some updated in 2020), so a pending case is censored at its
own last recorded listing date - the latest date we KNOW it was still pending. This is a
lower bound: it can only make courts look faster, never slower. Cases transferred to / committed to
another court are censored at that date: their outcome is decided elsewhere.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Outcome groups shown to the public. Keys are lower-cased DDL disposal names.
OUTCOME_GROUPS: dict[str, dict[str, str]] = {
    "compromise": {"en": "Compromise / settled", "hi": "समझौता / निपटारा"},
    "lok_adalat": {"en": "Lok Adalat", "hi": "लोक अदालत"},
    "allowed": {"en": "Allowed / decreed / granted", "hi": "स्वीकृत / डिक्री / मंज़ूर"},
    "dismissed": {"en": "Dismissed / rejected", "hi": "खारिज / अस्वीकृत"},
    "withdrawn": {"en": "Withdrawn / not pressed", "hi": "वापस लिया गया"},
    "convicted": {"en": "Convicted / pleaded guilty / fined", "hi": "दोषसिद्ध / दोष स्वीकार / जुर्माना"},
    "acquitted": {"en": "Acquitted / discharged / quashed", "hi": "बरी / उन्मोचित / रद्द"},
    "closed": {"en": "Closed without a decision on merits", "hi": "गुण-दोष पर निर्णय बिना बंद"},
    "unspecified": {"en": "Disposed (outcome not specified)", "hi": "निपटाया गया (परिणाम अनिर्दिष्ट)"},
}
MOVED = {"transferred", "committed", "converted"}
_OUTCOME_MAP = {
    "compromise": "compromise", "compounded": "compromise", "settled": "compromise",
    "disposal in lok adalat": "lok_adalat", "referred to lok adalat": "lok_adalat",
    "allowed": "allowed", "award": "allowed", "partly decreed": "allowed", "contest-allowed": "allowed",
    "ex-parte": "allowed", "uncontested": "allowed", "appeal accepted": "allowed", "bail granted": "allowed",
    "dismissed": "dismissed", "reject": "dismissed", "bail refused": "dismissed", "bail rejected": "dismissed",
    "withdrawn": "withdrawn", "not press": "withdrawn",
    "convicted": "convicted", "plead guilty": "convicted", "fine": "convicted", "prison": "convicted",
    "probation": "convicted", "plea bargaining": "convicted", "confession": "convicted",
    "acquitted": "acquitted", "258 crpc": "acquitted", "quash": "acquitted",
    "abated": "closed", "died": "closed", "absconded": "closed", "untrace": "closed", "sine die": "closed",
    "stayed": "closed", "p.o. consign": "closed", "closed": "closed", "procedural": "closed", "cancelled": "closed",
}


def outcome_group(nature) -> str | None:
    if nature is None or (isinstance(nature, float) and np.isnan(nature)):
        return None
    k = str(nature).strip().lower()
    if k in MOVED:
        return "moved"
    return _OUTCOME_MAP.get(k, "unspecified")


def kaplan_meier(durations: np.ndarray, events: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return (unique event/censor times, survival S(t) just after each time)."""
    durations = np.asarray(durations, dtype=float)
    events = np.asarray(events, dtype=bool)
    if len(durations) == 0:
        return np.array([]), np.array([])
    order = np.argsort(durations, kind="mergesort")
    d, e = durations[order], events[order]
    times, idx = np.unique(d, return_index=True)
    n = len(d)
    at_risk = n - idx
    deaths = np.add.reduceat(e.astype(int), idx)
    surv = np.cumprod(1.0 - deaths / at_risk)
    return times, surv


def km_quantile(times: np.ndarray, surv: np.ndarray, q: float) -> float | None:
    """Smallest t with share decided (1 - S) >= q; None if not reached within follow-up."""
    hit = np.nonzero(1.0 - surv >= q - 1e-12)[0]
    return float(times[hit[0]]) if len(hit) else None


def km_curve(times: np.ndarray, surv: np.ndarray, max_month: int) -> list[float | None]:
    """Share decided at each whole month 0..max_month (None beyond the last observed time)."""
    out: list[float | None] = []
    last = times[-1] if len(times) else 0
    for m in range(max_month + 1):
        t = m * 30.4375
        if t > last:
            out.append(None)
            continue
        i = np.searchsorted(times, t, side="right") - 1
        out.append(round(float(1.0 - (surv[i] if i >= 0 else 1.0)), 4))
    return out


def durations_events(df: pd.DataFrame, snapshot: pd.Timestamp | None = None) -> tuple[np.ndarray, np.ndarray, int]:
    """Durations (days from filing) and event flags. Returns (durations, events, n_excluded).

    Pending cases are censored at their own last listing date (`snapshot` is unused and kept
    for backwards compatibility); pending cases without a valid last listing are excluded."""
    f = df["filing_date"]
    d = df["disposal_date"]
    status = df["case_status"]
    moved = df["outcome_group"].eq("moved")
    dur = pd.Series(np.nan, index=df.index)
    ev = pd.Series(False, index=df.index)
    dec = (status == "DISPOSED") & d.notna() & f.notna()
    dur[dec] = (d[dec] - f[dec]).dt.days
    ev[dec & ~moved] = True
    ll = df["last_listing_date"]
    pend = (status == "PENDING") & f.notna() & ll.notna()
    dur[pend] = (ll[pend] - f[pend]).dt.days
    ok = dur.notna() & (dur >= 0)
    return dur[ok].to_numpy(), ev[ok].to_numpy(), int((~ok).sum())


def quantiles(values: pd.Series, qs=(0.5, 0.75, 0.9, 0.95)) -> dict[str, float | None]:
    v = values.dropna()
    return {f"p{int(q * 100)}": (round(float(v.quantile(q)), 1) if len(v) else None) for q in qs}


def group_stats(df: pd.DataFrame, snapshot: pd.Timestamp, min_n: int, max_month: int) -> dict:
    """All public statistics for one group of cases (e.g. district x category)."""
    n = int(len(df))
    out: dict = {"n": n, "n_pending": int((df["case_status"] == "PENDING").sum()),
                 "n_decided": int(((df["case_status"] == "DISPOSED") & ~df["outcome_group"].eq("moved")).sum()),
                 "n_moved": int(df["outcome_group"].eq("moved").sum())}
    if n < min_n:
        out["suppressed"] = True
        return out
    out["suppressed"] = False
    dur, ev, excl = durations_events(df, snapshot)
    out["n_excluded_bad_dates"] = excl
    times, surv = kaplan_meier(dur, ev)
    out["time_to_decision_days"] = {
        "p50": km_quantile(times, surv, 0.5), "p75": km_quantile(times, surv, 0.75),
        "p90": km_quantile(times, surv, 0.9), "max_followup": float(times[-1]) if len(times) else None,
    }
    out["share_undecided_at_3y"] = (round(1.0 - km_curve(times, surv, 36)[36], 4)
                                    if km_curve(times, surv, 36)[36] is not None else None)
    out["curve_monthly_share_decided"] = km_curve(times, surv, max_month)
    disposed = df[(df["case_status"] == "DISPOSED") & df["outcome_group"].notna() & ~df["outcome_group"].eq("moved")]
    out["n_outcomes"] = int(len(disposed))
    if len(disposed) >= min_n:
        sh = disposed["outcome_group"].value_counts(normalize=True)
        out["outcomes"] = {k: round(float(v), 4) for k, v in sh.items()}
    ttf = (df["first_listing_date"] - df["filing_date"]).dt.days
    ttf = ttf[ttf >= 0]
    out["days_to_first_listing"] = quantiles(ttf, (0.5, 0.9)) if len(ttf) >= min_n else None
    pend = df[df["case_status"] == "PENDING"]
    gap = (pend["next_listing_date"] - pend["last_listing_date"]).dt.days
    gap = gap[gap >= 0]
    out["next_hearing_gap_days"] = ({"n": int(len(gap)), **quantiles(gap)} if len(gap) >= min_n else None)
    # Share of pending cases whose next hearing was set more than 6 months after the last one.
    # Needs no collection date, unlike "time since last hearing".
    out["pending_next_gap_over_6m_share"] = round(float((gap > 182).mean()), 4) if len(gap) >= min_n else None
    return out
