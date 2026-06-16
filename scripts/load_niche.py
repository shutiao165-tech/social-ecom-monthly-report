#!/usr/bin/env python3
"""Load config/niche_config.py (user) or niche_config.example.py (default)."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent.parent
USER_CFG = ROOT / "config" / "niche_config.py"
EXAMPLE_CFG = ROOT / "config" / "niche_config.example.py"

_cfg: ModuleType | None = None


def _load_module() -> ModuleType:
    path = USER_CFG if USER_CFG.exists() else EXAMPLE_CFG
    if not path.exists():
        raise FileNotFoundError(f"Missing niche config: {path}")
    spec = importlib.util.spec_from_file_location("niche_config", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


def cfg() -> ModuleType:
    global _cfg
    if _cfg is None:
        _cfg = _load_module()
    return _cfg


def own_brand_names() -> set[str]:
    c = cfg()
    names = {c.OWN_BRAND, getattr(c, "OWN_BRAND_DISPLAY", c.OWN_BRAND)}
    names.update(getattr(c, "OWN_BRAND_ALIASES", []) or [])
    return {n for n in names if n}


def format_report_copy(**extra) -> dict[str, str]:
    c = cfg()
    ctx = {
        "niche": c.NICHE_LABEL,
        "nich": c.NICHE_LABEL,
        "own_brand": c.OWN_BRAND,
        "brand_count": len(c.BRAND_CANONICAL),
        **extra,
    }
    out: dict[str, str] = {}
    for k, v in (c.REPORT_COPY or {}).items():
        try:
            out[k] = v.format(**ctx)
        except KeyError:
            out[k] = v
    return out
