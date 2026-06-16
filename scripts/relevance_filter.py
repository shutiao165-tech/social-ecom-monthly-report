"""Config-driven niche content relevance filter (XHS + DY shared)."""
from __future__ import annotations

import re

from brand_config import keywords_for_brand
from load_niche import cfg


def strip_hashtags(text: str) -> str:
    t = re.sub(r"#\S+", " ", text or "")
    return re.sub(r"\s+", " ", t).strip()


def _anchors(name: str, default: tuple[str, ...] = ()) -> tuple[str, ...]:
    raw = getattr(cfg(), name, None)
    if not raw:
        return default
    return tuple(raw)


def _brand_context_required() -> dict[str, tuple[str, ...]]:
    raw = getattr(cfg(), "BRAND_CONTEXT_REQUIRED", None) or {}
    out: dict[str, tuple[str, ...]] = {}
    for brand, terms in raw.items():
        out[brand] = tuple(terms) if terms else ()
    return out


def _brands_requiring_strong() -> frozenset[str]:
    raw = getattr(cfg(), "BRANDS_REQUIRING_STRONG_ANCHOR", None) or ()
    return frozenset(raw)


def _has_relevance_config() -> bool:
    c = cfg()
    return bool(
        getattr(c, "NICHE_STRONG_ANCHORS", None)
        or getattr(c, "NICHE_WEAK_ANCHORS", None)
        or getattr(c, "NICHE_NEGATIVE_TERMS", None)
        or getattr(c, "BRAND_CONTEXT_REQUIRED", None)
        or getattr(c, "BRANDS_REQUIRING_STRONG_ANCHOR", None)
    )


def brand_context_ok(text: str, brand: str) -> bool:
    req = _brand_context_required().get(brand)
    if not req:
        return True
    low = (text or "").lower()
    return any(k.lower() in low for k in req)


def is_niche_relevant(text: str, *, brand: str = "") -> bool:
    """标题/描述是否赛道相关；歧义品牌须强锚点 + 上下文共现（由 niche_config 配置）。"""
    if not _has_relevance_config():
        return True

    body = text or ""
    strong = _anchors("NICHE_STRONG_ANCHORS")
    weak = _anchors("NICHE_WEAK_ANCHORS")
    negative = _anchors("NICHE_NEGATIVE_TERMS")
    brands_need_strong = _brands_requiring_strong()

    has_strong = any(k in body for k in strong)
    has_weak = any(k in body for k in weak)

    if brand in brands_need_strong:
        if not has_strong:
            return False
    elif strong or weak:
        if not (has_strong or has_weak):
            return False

    if any(bad in body for bad in negative) and not has_strong:
        return False
    if brand and not brand_context_ok(body, brand):
        return False
    return True


def mentions_brand(text: str, brand: str) -> bool:
    """正文/标题须自然提及品牌（禁止仅靠 hashtag 蹭词）。"""
    body = text or ""
    plain = strip_hashtags(body)
    head = body.split("#", 1)[0]

    def _token_ok(token: str) -> bool:
        if token not in body:
            return False
        if token not in plain and token not in head:
            return False
        return is_niche_relevant(body, brand=brand)

    if brand in body:
        return _token_ok(brand)

    for kw in keywords_for_brand(brand):
        if kw == brand or kw not in body:
            continue
        if kw not in plain and kw not in head:
            continue
        return is_niche_relevant(body, brand=brand)
    return False
