"""Pseudonymisation of case identifiers for research outputs.

Identifiers are replaced by a keyed hash (HMAC-SHA256). The key (salt) is never
written to outputs; without it pseudonyms cannot be reversed by dictionary attack
on public CNR formats. The id map is kept locally (gitignored) so a researcher with
authorised access can trace a result back to the source record.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from pathlib import Path

import pandas as pd

from .config import resolve_path


def get_salt(cfg: dict) -> bytes:
    env = os.environ.get(cfg["privacy"].get("salt_env_var", "TAREEKH_SALT"))
    if env:
        return env.encode("utf-8")
    path = resolve_path(cfg, "salt_file")
    if path.exists():
        return path.read_text(encoding="utf-8").strip().encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    salt = secrets.token_hex(32)
    path.write_text(salt, encoding="utf-8")
    return salt.encode("utf-8")


def pseudonym(value: str, salt: bytes, prefix: str = "C-", length: int = 10) -> str:
    digest = hmac.new(salt, str(value).encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{prefix}{digest[:length].upper()}"


def build_id_map(case_ids: pd.Series, cfg: dict, salt: bytes | None = None) -> pd.DataFrame:
    p = cfg["privacy"]
    salt = salt if salt is not None else get_salt(cfg)
    uniq = pd.Series(case_ids.dropna().unique())
    pids = uniq.map(lambda v: pseudonym(v, salt, p.get("pseudonym_prefix", "C-"), int(p.get("pseudonym_length", 10))))
    if pids.duplicated().any():  # pragma: no cover - astronomically unlikely
        raise RuntimeError("Pseudonym collision; increase privacy.pseudonym_length")
    return pd.DataFrame({"case_id": uniq, "case_pid": pids})


def apply_pseudonyms(df: pd.DataFrame, id_map: pd.DataFrame, id_col: str = "case_id") -> pd.DataFrame:
    """Replace case_id with case_pid; hearing ids derived from case ids are re-keyed too."""
    m = dict(zip(id_map["case_id"], id_map["case_pid"]))
    out = df.copy()
    if "hearing_id" in out.columns and id_col in out.columns:
        out["hearing_id"] = [
            (m.get(c, c) + str(h)[len(str(c)):]) if isinstance(h, str) and isinstance(c, str) and h.startswith(c)
            else f"{m.get(c, c)}#{hashlib.sha256(str(h).encode()).hexdigest()[:8]}"
            for h, c in zip(out["hearing_id"], out[id_col])
        ]
    if "source_reference" in out.columns and id_col in out.columns:
        out["source_reference"] = [
            s.replace(str(c), m.get(c, c)) if isinstance(s, str) and isinstance(c, str) else s
            for s, c in zip(out["source_reference"], out[id_col])
        ]
    out[id_col] = out[id_col].map(lambda v: m.get(v, v))
    return out
