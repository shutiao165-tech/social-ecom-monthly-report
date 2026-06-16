#!/usr/bin/env python3
"""品牌监测配置 — 从 config/niche_config.py 读取（唯一真源）。"""
from __future__ import annotations

from load_niche import cfg, own_brand_names

_c = cfg()

NICHE_LABEL = _c.NICHE_LABEL
NICHE_SLUG = _c.NICHE_SLUG
OWN_BRAND = _c.OWN_BRAND
OWN_BRAND_DISPLAY = getattr(_c, "OWN_BRAND_DISPLAY", _c.OWN_BRAND)
OWN_BRAND_ALIASES = list(getattr(_c, "OWN_BRAND_ALIASES", []) or [])
OWN_BRAND_NAMES = own_brand_names()

BRAND_CANONICAL = list(_c.BRAND_CANONICAL)
BRAND_SEARCH_KEYWORDS: dict[str, list[str]] = dict(_c.BRAND_SEARCH_KEYWORDS)
BRAND_SCENE_HINTS: dict[str, str] = dict(getattr(_c, "BRAND_SCENE_HINTS", {}) or {})
DEFAULT_SCENE = getattr(_c, "DEFAULT_SCENE", "综合场景")

CATEGORY_KEYWORDS = list(_c.CATEGORY_KEYWORDS)
CONTENT_CATEGORIES = list(_c.CONTENT_CATEGORIES)
PAIN_BUCKETS = list(_c.PAIN_BUCKETS)
DIRECTION_PLAYBOOK = list(getattr(_c, "DIRECTION_PLAYBOOK", []) or [])

DY_NICHE_CATEGORY = getattr(_c, "DY_NICHE_CATEGORY", NICHE_LABEL)
DY_NICHE_BRAND = getattr(_c, "DY_NICHE_BRAND", "品牌竞品")


def xhs_brand_keywords_flat() -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for kws in BRAND_SEARCH_KEYWORDS.values():
        for kw in kws:
            if kw not in seen:
                seen.add(kw)
                out.append(kw)
    return out


def canonical_for_keyword(kw: str) -> str | None:
    for brand, kws in BRAND_SEARCH_KEYWORDS.items():
        if kw in kws:
            return brand
    return None


def keywords_for_brand(brand: str) -> list[str]:
    return BRAND_SEARCH_KEYWORDS.get(brand, [brand])


def is_own_brand(name: str) -> bool:
    n = (name or "").strip()
    if n == OWN_BRAND or n == OWN_BRAND_DISPLAY:
        return True
    return any(a in n for a in OWN_BRAND_ALIASES if len(a) >= 2)


def norm_brand_key(name: str) -> str:
    n = (name or "").strip()
    if is_own_brand(n):
        return OWN_BRAND
    for alias in sorted(OWN_BRAND_ALIASES, key=len, reverse=True):
        if alias and alias in n:
            return OWN_BRAND
    return n.strip() or name
