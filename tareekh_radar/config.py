"""Configuration loading with a stable hash for experiment tracking."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "default.yaml"


class ConfigError(ValueError):
    """Raised when a configuration file is missing or malformed."""


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def load_config(path: str | Path | None = None, overrides: dict | None = None) -> dict[str, Any]:
    """Load the default config, optionally merged with a user config and overrides."""
    if not DEFAULT_CONFIG_PATH.exists():
        raise ConfigError(f"Default config not found at {DEFAULT_CONFIG_PATH}")
    with open(DEFAULT_CONFIG_PATH, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}
    if path is not None:
        p = Path(path)
        if not p.exists():
            raise ConfigError(f"Config file not found: {p}")
        with open(p, encoding="utf-8") as fh:
            user = yaml.safe_load(fh) or {}
        if not isinstance(user, dict):
            raise ConfigError(f"Config file {p} must contain a mapping")
        cfg = _deep_merge(cfg, user)
    if overrides:
        cfg = _deep_merge(cfg, overrides)
    _validate(cfg)
    return cfg


def _validate(cfg: dict) -> None:
    required = ["paths", "privacy", "dates", "classification", "features", "anomaly"]
    missing = [k for k in required if k not in cfg]
    if missing:
        raise ConfigError(f"Config missing sections: {missing}")
    mode = cfg["classification"].get("mode")
    if mode not in {"rules", "ml", "hybrid"}:
        raise ConfigError(f"classification.mode must be rules|ml|hybrid, got {mode!r}")
    for mode, mcfg in cfg["anomaly"]["modes"].items():
        for level in mcfg["peer_levels"]:
            if "case_type" not in level and "case_category" not in level:
                raise ConfigError(
                    f"anomaly.modes.{mode}: every peer level must include case_type or case_category "
                    f"(got {level}); unrelated case types must not be compared."
                )
    for rule in cfg["classification"]["rules"]:
        for key in ("id", "category", "priority", "confidence", "patterns"):
            if key not in rule:
                raise ConfigError(f"Classification rule missing {key!r}: {rule}")
        if rule["category"] not in cfg["classification"]["categories"]:
            raise ConfigError(f"Rule {rule['id']} has unknown category {rule['category']}")


def config_hash(cfg: dict) -> str:
    """Short deterministic hash of the analytical config (paths excluded)."""
    relevant = {k: v for k, v in cfg.items() if k != "paths"}
    blob = json.dumps(relevant, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:12]


def resolve_path(cfg: dict, key: str) -> Path:
    """Resolve a configured path relative to the project root."""
    p = Path(cfg["paths"][key])
    return p if p.is_absolute() else PROJECT_ROOT / p
