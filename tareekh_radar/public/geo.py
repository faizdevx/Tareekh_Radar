"""Build the India district map for the site from a district-boundary GeoJSON.

Pure Python (no GIS libraries): Douglas–Peucker simplification, a simple equal-ish projection
(longitude scaled by cos(mean latitude)), SVG path strings, and name matching between the
boundary file's districts and the eCourts (DDL) districts used by the site.
"""

from __future__ import annotations

import difflib
import json
import math
import re
from pathlib import Path

# State names as written in the DDL data -> as commonly written in boundary files.
STATE_ALIASES = {
    "orissa": "odisha", "dnh at silvasa": "dadra and nagar haveli", "diu and daman": "daman and diu",
    "andaman and nicobar": "andaman and nicobar islands", "pondicherry": "puducherry", "delhi": "nct of delhi",
    "uttaranchal": "uttarakhand", "arunanchal pradesh": "arunachal pradesh", "dadara and nagar havelli": "dadra and nagar haveli",
    "andaman and nicobar island": "andaman and nicobar islands",
}
# District spelling differences seen between eCourts and Census-style names (normalised forms).
DISTRICT_ALIASES = {
    "ananthapur": "anantapur", "gurugram": "gurgaon", "nuh": "mewat", "prayagraj": "allahabad", "ayodhya": "faizabad",
    "kanpur dehat": "kanpur dehat", "sant ravidas nagar": "bhadohi", "kheda": "kheda", "ahmednagar": "ahmadnagar",
    "beed": "bid", "raigad": "raigarh", "gondia": "gondiya", "buldhana": "buldana", "kancheepuram": "kancheepuram",
    "tiruvallur": "thiruvallur", "nilgiris": "the nilgiris", "bengaluru": "bangalore", "mysuru": "mysore",
    "belagavi": "belgaum", "kalaburagi": "gulbarga", "vijayapura": "bijapur", "shivamogga": "shimoga",
    "tumakuru": "tumkur", "ballari": "bellary", "chikkamagaluru": "chikmagalur", "hosur": "krishnagiri",
    "calcutta": "kolkata", "coochbehar": "koch bihar", "balasore": "baleshwar", "hooghly": "hugli", "howrah": "haora",
    "kadapa": "y s r", "khurda": "khordha", "kanker": "uttar bastar kanker", "kawardha": "kabeerdham",
    "dantewada": "dakshin bastar dantewada", "boudh": "baudh", "deogarh": "debagarh", "lakhimpur": "kheri",
    "khandwa": "east nimar", "mandleshwar": "west nimar", "bettiah": "pashchim champaran", "daltonganj": "palamu",
    "east singhbhum": "purbi singhbhum", "dahod": "dohad", "dholpur": "dhaulpur", "hathras": "mahamaya nagar",
    "bhadohi sr nagar": "sant ravidas nagar", "gangtok": "east", "gyalshing": "west", "mangan": "north", "namchi": "south",
    "mahabubnagar": "mahbubnagar", "kamrup metro": "kamrup metropolitan", "janjgir": "janjgir champa",
    "motihari": "purba champaran", "chapra": "saran", "arrah": "bhojpur", "sasaram": "rohtas", "bihar sharif": "nalanda",
    "boudh": "bauda", "bengaluru rural": "bangalore rural", "balotra barmer": "barmer", "merta": "nagaur", "narnaul": "mahendragarh",
    "sri muktsar sahib": "muktsar", "narsinghpur": "narsimhapur", "nellore": "sri potti sriramulu nellore",
    "north twenty four parganas": "north parganas", "south twenty four parganas": "south parganas",
    "north dinajpur": "uttar dinajpur", "south dinajpur": "dakshin dinajpur", "purba bardhaman": "barddhaman", "paschim bardhaman": "barddhaman",
    "pauri garhwal": "garhwal", "poonch": "punch", "shopian": "shupiyan", "mohali": "sahibzada ajit singh nagar",
    "sbs nagar": "shahid bhagat singh nagar", "seraikella": "saraikela kharsawan", "sonepur": "subarnapur", "silvassa": "dadra and nagar haveli",
    "rohtas sasaram": "rohtas", "west singhbhum": "pashchimi singhbhum", "chaibasa": "pashchimi singhbhum",
    "mumbai cmm courts": "mumbai", "mumbai city civil": "mumbai",
    "dhalai tripura": "dhalai", "southtripura": "south tripura", "khowai tripura": "khowai", "sepahijala tripura": "sepahijala", "unakoti tripura": "unakoti",
}
# Court establishments that are not geographic districts (tribunals, family courts): never on a map.
NON_GEOGRAPHIC = re.compile(r"tribunal|family courts|cooperative|industrial and lab|appellat", re.I)


# States split or created after the 2011 boundaries: districts may be listed under the new state in eCourts.
SPLIT_FROM = {"andhra pradesh": ("telangana",), "jammu and kashmir": ("ladakh",)}


def snorm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z ]+", " ", str(s or "").lower().replace("&", " and "))).strip()


def norm(s: str) -> str:
    s = str(s or "").lower().replace("&", " and ")
    s = re.sub(r"\s+at\s+.*$", "", s)  # "Kheda at Nadiad" -> "Kheda"
    s = re.sub(r"\(.*?\)", " ", s)  # "Saran (chhapra)" -> "Saran"
    if not s.startswith("kamrup"):
        s = re.sub(r"\s+(metro ii|metro)\s*$", "", s)  # "Jaipur Metro" -> "Jaipur"
    s = re.sub(r"\b(district|dist|sessions|division|court|the)\b", " ", s)
    s = re.sub(r"[^a-z ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


_DIR = re.compile(r"\b(north|south|east|west|upper|lower|purba|purbi|paschim|pashchim|pashchimi|uttar|dakshin|middle|central)\b")


def _dirs(name: str) -> frozenset:
    return frozenset(_DIR.findall(name))


def _dp(points: list, tol: float) -> list:
    """Douglas–Peucker line simplification (iterative)."""
    if len(points) < 4:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        a, b = stack.pop()
        (x1, y1), (x2, y2) = points[a], points[b]
        dx, dy = x2 - x1, y2 - y1
        norm2 = dx * dx + dy * dy
        best, idx = -1.0, -1
        for i in range(a + 1, b):
            px, py = points[i]
            if norm2 == 0:
                d = (px - x1) ** 2 + (py - y1) ** 2
            else:
                t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / norm2))
                d = (px - x1 - t * dx) ** 2 + (py - y1 - t * dy) ** 2
            if d > best:
                best, idx = d, i
        if best > tol * tol and idx > 0:
            keep[idx] = True
            stack += [(a, idx), (idx, b)]
    return [p for p, k in zip(points, keep) if k]


def _rings(geom: dict) -> list:
    if geom["type"] == "Polygon":
        return [geom["coordinates"][0]]  # outer ring only; holes are invisible at this scale
    if geom["type"] == "MultiPolygon":
        return [poly[0] for poly in geom["coordinates"]]
    return []


def build_map(geojson_path: str | Path, out_dir: str | Path, state_prop: str, district_prop: str,
              attribution: str, licence: str, tol_deg: float = 0.02, width: int = 1000) -> dict:
    """Write `india_map.json` (SVG paths + matched DDL district ids) and `india_map_match.json` (audit)."""
    gj = json.loads(Path(geojson_path).read_text(encoding="utf-8"))
    meta = json.loads((Path(out_dir) / "meta.json").read_text(encoding="utf-8"))
    feats = [f for f in gj["features"] if f.get("geometry")]
    lats = [pt[1] for f in feats for r in _rings(f["geometry"]) for pt in r]
    lons = [pt[0] for f in feats for r in _rings(f["geometry"]) for pt in r]
    k = math.cos(math.radians((min(lats) + max(lats)) / 2))
    minx, maxx, miny, maxy = min(lons) * k, max(lons) * k, -max(lats), -min(lats)
    scale = width / (maxx - minx)
    height = round((maxy - miny) * scale)

    def proj(pt):
        return ((pt[0] * k - minx) * scale, (-pt[1] - miny) * scale)

    # DDL districts by normalised state.
    ddl = {}
    for st in meta["states"]:
        sname = STATE_ALIASES.get(snorm(st["name"]), snorm(st["name"]))
        for d in st["districts"]:
            ddl.setdefault(sname, []).append({"id": d["id"], "name": d["name"], "n": d["n"], "st": sname, "key": DISTRICT_ALIASES.get(norm(d["name"]), norm(d["name"]))})
    all_ddl = [d for v in ddl.values() for d in v if not NON_GEOGRAPHIC.search(d["name"])]

    out_feats, audit, used = [], [], {}
    for f in feats:
        props = f.get("properties") or {}
        gst = snorm(props.get(state_prop))
        gst = STATE_ALIASES.get(gst, gst)
        gdn = norm(props.get(district_prop))
        gdn_key = DISTRICT_ALIASES.get(gdn, gdn)
        pool = ddl.get(gst, [])
        cand = {}
        for d in sorted(pool, key=lambda x: x["n"]):  # on a name collision, the district with more cases wins
            cand[d["key"]] = d
            cand[d["key"].replace(" ", "")] = d
        hit = cand.get(gdn_key) or cand.get(gdn_key.replace(" ", ""))
        how = "exact" if hit else ""
        if not hit and pool:
            m = difflib.get_close_matches(gdn_key, list(cand), n=1, cutoff=0.82)
            if m and _dirs(m[0]) == _dirs(gdn_key):  # never match "South Garo Hills" to "West Garo Hills"
                hit, how = cand[m[0]], "fuzzy"
        if not hit:  # state renamed or split since the boundary vintage (e.g. Telangana): unique name anywhere
            same = sorted([d for d in all_ddl if d["key"] == gdn_key and d["st"] in SPLIT_FROM.get(gst, ())], key=lambda x: -x["n"])
            if same:  # e.g. Telangana and Ladakh districts sit under AP and J&K in the 2011 file
                hit, how = same[0], "name-only"
        paths = []
        for ring in _rings(f["geometry"]):
            pts = [proj(p) for p in _dp([tuple(p[:2]) for p in ring], tol_deg)]
            if len(pts) < 3:
                continue
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            if max(xs) - min(xs) < 0.6 and max(ys) - min(ys) < 0.6:  # specks smaller than a pixel
                continue
            paths.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + "Z")
        if not paths:
            continue
        did = hit["id"] if hit else None
        if did:
            used.setdefault(did, 0)
            used[did] += 1
        out_feats.append({"id": did, "st": props.get(state_prop), "dn": props.get(district_prop), "d": "".join(paths)})
        audit.append({"geo_state": props.get(state_prop), "geo_district": props.get(district_prop), "ddl_id": did,
                      "ddl_name": hit["name"] if hit else None, "how": how or "unmatched"})
    matched_ids = {a["ddl_id"] for a in audit if a["ddl_id"]}
    payload = {"viewBox": f"0 0 {width} {height}", "attribution": attribution, "licence": licence,
               "note": "District shapes simplified for display. Grey = no matching eCourts district or too few cases.",
               "features": out_feats}
    (Path(out_dir) / "india_map.json").write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    summary = {"geo_features": len(out_feats), "geo_matched": sum(1 for a in audit if a["ddl_id"]),
               "ddl_districts": len(all_ddl), "ddl_on_map": len(matched_ids),
               "ddl_missing": sorted(f'{d["name"]} ({d["id"]})' for d in all_ddl if d["id"] not in matched_ids)}
    (Path(out_dir) / "india_map_match.json").write_text(json.dumps({"summary": summary, "rows": audit}, ensure_ascii=False, indent=1), encoding="utf-8")
    return summary
