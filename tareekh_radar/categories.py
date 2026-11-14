"""Public case categories derived from the recorded case type (and act/section when present).

eCourts case-type names are local abbreviations that differ between states, so this
mapping is deliberately conservative: a case only gets a specific category when its
recorded type name or act clearly says so; everything else stays in a broad bucket or
OTHER. Rules are ordered; the first match wins. The full mapping table (raw type ->
category, with counts) is published with the site data so it can be audited.

Known undercount: cheque-bounce (NI Act s.138) complaints filed under generic criminal
types (e.g. "S.C.C.", "C.C.") are only recognised when the act field says so.
"""

from __future__ import annotations

import re

import pandas as pd

CATEGORIES: dict[str, dict[str, str]] = {
    "cheque_bounce": {"en": "Cheque bounce (NI Act s.138)", "hi": "चेक बाउंस (एनआई एक्ट धारा 138)"},
    "motor_accident": {"en": "Motor accident claim", "hi": "मोटर दुर्घटना दावा"},
    "matrimonial": {"en": "Divorce / matrimonial", "hi": "तलाक / वैवाहिक"},
    "maintenance": {"en": "Maintenance", "hi": "भरण-पोषण"},
    "bail": {"en": "Bail application", "hi": "जमानत आवेदन"},
    "execution": {"en": "Execution of decree", "hi": "डिक्री का निष्पादन"},
    "appeal_revision": {"en": "Appeal / revision", "hi": "अपील / पुनरीक्षण"},
    "land_acquisition": {"en": "Land acquisition reference", "hi": "भूमि अधिग्रहण संदर्भ"},
    "civil_suit": {"en": "Civil / property / money suit", "hi": "दीवानी / संपत्ति / धन वाद"},
    "criminal_case": {"en": "Criminal case", "hi": "आपराधिक मामला"},
    "other": {"en": "Other / unclear type", "hi": "अन्य / अस्पष्ट प्रकार"},
}

# (category, regex on normalised type key). Keys are lower-case, punctuation -> space.
TYPE_RULES: list[tuple[str, str]] = [
    ("cheque_bounce", r"\bn ?i\b|\bnact\b|\bni act\b|\b138\b|negotiable|cheque"),
    ("motor_accident", r"\bm ?a ?c ?[tpc]\b|\bmcop\b|\bm ?v ?c\b|\bmvop\b|\bop ?mv\b|motor|accident"),
    ("matrimonial", r"\bh ?m ?a\b|marriage|matrimon|divorce|family"),
    ("maintenance", r"maintenance"),
    ("bail", r"\bbail\b|\bb ?a\b|\bba appl"),
    ("execution", r"\bep\b|\be p\b|\bex\b|\bexe\b|\bexe r\b|execution"),
    ("appeal_revision", r"appeal|revision|\bcra\b|\bcrr\b|\brca\b|\br c a\b|\br a\b|\bcrl a\b|\bcri rev\b"),
    ("land_acquisition", r"\bl ?a ?r\b|\bl ?a ?c\b|land acq"),
    ("civil_suit", r"\bo ?s\b|original (civil )?suits?|civil suits?|\bc ?s\b|title suit|money suit|\br ?c ?s\b|"
                   r"\bspl c s\b|\bciv suit\b|\bsuit\b|\bspcs\b|\breg civil suit\b"),
    ("criminal_case", r"\bcri(minal)? case\b|\bcrl case\b|\bcr case\b|\bc ?c\b|\br ?c ?c\b|\bs ?c ?c\b|\bs ?t\b|"
                      r"session|\bs ?c\b|\bg ?r\b|warrant|summons?|police|challan|complaint|\breg cri|\bstc\b|"
                      r"special trial|\bsum\b|penal code|\bipc\b"),
]

ACT_RULES: list[tuple[str, str, set[str] | None]] = [
    ("cheque_bounce", r"negotiable instruments", {"138", "142"}),
    ("motor_accident", r"motor vehicles", {"140", "163", "163a", "166"}),
    ("matrimonial", r"hindu marriage|special marriage|divorce act|family courts", None),
    ("maintenance", r"code of criminal procedure", {"125", "127", "128"}),
    ("bail", r"code of criminal procedure", {"436", "437", "438", "439"}),
]

_COMPILED = [(c, re.compile(p)) for c, p in TYPE_RULES]
_ACT_COMPILED = [(c, re.compile(p), s) for c, p, s in ACT_RULES]


def type_key(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", str(value).lower())).strip()


def category_from_type(value) -> str:
    k = type_key(value)
    if not k:
        return "other"
    for cat, pat in _COMPILED:
        if pat.search(k):
            return cat
    return "other"


def category_from_act(act, section) -> str | None:
    a = type_key(act)
    if not a:
        return None
    sec = type_key(section).replace(" ", "")
    for cat, pat, sections in _ACT_COMPILED:
        if pat.search(a) and (sections is None or sec in sections):
            return cat
    return None


def assign_categories(case_type: pd.Series, act: pd.Series | None = None, section: pd.Series | None = None) -> pd.Series:
    """Vectorised over distinct values: act/section (when recognised) override the type name."""
    ct = case_type.astype(object)
    by_type = ct.map({u: category_from_type(u) for u in pd.unique(ct)})
    if act is None:
        return by_type

    def txt(s: pd.Series | None) -> pd.Series:
        if s is None:
            return pd.Series("", index=case_type.index, dtype=object)
        v = s.astype(object)
        return v.where(v.notna(), "").map(str)

    pair = txt(act) + "\x00" + txt(section)
    lookup = {}
    for u in pd.unique(pair):
        a, _, s = str(u).partition("\x00")
        lookup[u] = category_from_act(None if a in ("", "None", "nan") else a, s)
    by_act = pair.map(lookup)
    return by_act.where(by_act.notna(), by_type).astype(object)
