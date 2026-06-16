#!/usr/bin/env python3
"""Detect commercial behavior (挂车/挂品/品牌合作) from TikHub note & video payloads."""
from __future__ import annotations

import json
import re
from typing import Any

from brand_config import BRAND_CANONICAL  # noqa: E402

BRAND_KEYWORDS = list(BRAND_CANONICAL)

_SOFT_TITLE = ("好物", "种草", "推荐", "清单", "同款", "测评", "爱用", "必买", "链接")
_SOFT_COMMENT = ("同款商品", "笔记同款", "链接", "怎么买", "求购", "哪里买", "蹲一个", "多少钱")


def _brand_in_text(text: str) -> str:
    for b in BRAND_KEYWORDS:
        if b in (text or ""):
            return b
    return ""


def parse_xhs_note_info(api_response: dict) -> dict:
    """Extract commerce signals from get_note_info / get_video_note_detail response."""
    payload = api_response.get("data") or {}
    note = {}

    if isinstance(payload, dict):
        if "data" in payload and isinstance(payload["data"], list) and payload["data"]:
            block = payload["data"][0]
            if isinstance(block, dict):
                nl = block.get("note_list") or []
                if nl:
                    note = nl[0]
        if not note and isinstance(payload.get("data"), dict):
            note = payload["data"]
        if not note:
            note = payload

    goods_info = note.get("goods_info") or {}
    if isinstance(goods_info, dict) and not goods_info:
        goods_info = {}
    cooperate = note.get("cooperate_binds") or []
    related_num = int(note.get("related_goods_num") or 0)
    has_goods = bool(note.get("has_related_goods")) or related_num > 0

    product_names: list[str] = []
    if isinstance(goods_info, dict) and goods_info:
        name = goods_info.get("name") or goods_info.get("title") or ""
        if name:
            product_names.append(str(name))
    if isinstance(goods_info, list):
        for g in goods_info:
            if isinstance(g, dict):
                n = g.get("name") or g.get("title") or ""
                if n:
                    product_names.append(str(n))

    coop_brands: list[str] = []
    for c in cooperate:
        if not isinstance(c, dict):
            continue
        bn = (
            c.get("brand_name")
            or (c.get("brand") or {}).get("name")
            or c.get("name")
            or ""
        )
        if bn:
            coop_brands.append(str(bn))

    return {
        "has_related_goods": has_goods,
        "related_goods_num": related_num or len(product_names),
        "product_names": product_names[:3],
        "cooperate_binds": cooperate,
        "coop_brands": coop_brands[:3],
        "has_cooperation": bool(cooperate),
    }


def parse_dy_video_detail(api_response: dict) -> dict:
    """Extract commerce signals from fetch_one_video response."""
    detail = ((api_response.get("data") or {}).get("aweme_detail") or {})
    anchor = detail.get("anchor_info") or {}
    extra = anchor.get("extra") or ""
    products: list[dict] = []

    if extra and extra not in ("{}", "[]", ""):
        try:
            parsed = json.loads(extra) if isinstance(extra, str) else extra
            if isinstance(parsed, list):
                products = [p for p in parsed if isinstance(p, dict)]
        except (json.JSONDecodeError, TypeError):
            products = []

    product_names = [str(p.get("title") or p.get("name") or "")[:40] for p in products if p]
    product_names = [n for n in product_names if n]
    has_cart = bool(products) or bool(anchor.get("id"))

    return {
        "has_cart": has_cart,
        "product_count": len(products),
        "product_names": product_names[:3],
        "anchor_type": detail.get("original_anchor_type"),
        "promotions_count": len(detail.get("promotions") or []),
    }


def classify_xhs_commerce(
    hard: dict,
    title: str = "",
    comments: list | None = None,
) -> dict:
    """Return {commerce_type, commerce_label, commerce_detail}."""
    comments = comments or []
    title = title or ""
    brand = _brand_in_text(title)

    if hard.get("has_related_goods") or hard.get("related_goods_num", 0) > 0:
        names = hard.get("product_names") or []
        n = hard.get("related_goods_num") or len(names) or 1
        label = f"挂品×{n}"
        if names:
            label = f"挂品·{names[0][:14]}"
        return {
            "commerce_type": "已挂商品",
            "commerce_label": label,
            "commerce_detail": "笔记关联商品（API 确认）",
        }

    if hard.get("has_cooperation") or hard.get("coop_brands"):
        coop = ", ".join(hard.get("coop_brands") or [])[:24] or "品牌报备"
        return {
            "commerce_type": "品牌合作",
            "commerce_label": f"合作·{coop}" if coop else "品牌合作",
            "commerce_detail": "cooperate_binds 命中",
        }

    for c in comments[:15]:
        text = c.get("content", "") if isinstance(c, dict) else str(c)
        if any(s in text for s in _SOFT_COMMENT):
            return {
                "commerce_type": "疑似种草",
                "commerce_label": "评论求链/同款",
                "commerce_detail": "评论区出现购链信号",
            }

    if brand:
        return {
            "commerce_type": "品牌露出",
            "commerce_label": f"含#{brand}",
            "commerce_detail": "标题品牌 tag，未确认挂品",
        }

    if any(w in title for w in _SOFT_TITLE):
        return {
            "commerce_type": "疑似种草",
            "commerce_label": "好物/种草体",
            "commerce_detail": "文案形态偏种草，未挂品",
        }

    return {
        "commerce_type": "无商业",
        "commerce_label": "无",
        "commerce_detail": "未检测到挂品或合作",
    }


def classify_dy_commerce(hard: dict, title: str = "") -> dict:
    title = title or ""
    brand = _brand_in_text(title)

    if hard.get("has_cart") or hard.get("product_count", 0) > 0:
        names = hard.get("product_names") or []
        label = f"挂车×{hard.get('product_count') or 1}"
        if names:
            label = f"挂车·{names[0][:14]}"
        return {
            "commerce_type": "已挂商品",
            "commerce_label": label,
            "commerce_detail": "anchor_info 含推广商品",
        }

    if brand:
        return {
            "commerce_type": "品牌露出",
            "commerce_label": f"含#{brand}",
            "commerce_detail": "标题品牌 tag，未确认挂车",
        }

    if any(w in title for w in _SOFT_TITLE):
        return {
            "commerce_type": "疑似种草",
            "commerce_label": "好物/清单体",
            "commerce_detail": "文案偏种草，未挂车",
        }

    return {
        "commerce_type": "无商业",
        "commerce_label": "无",
        "commerce_detail": "未检测到小黄车",
    }


def merge_commerce_record(
    platform: str,
    hard: dict,
    title: str = "",
    comments: list | None = None,
) -> dict:
    if platform == "xhs":
        classified = classify_xhs_commerce(hard, title, comments)
    else:
        classified = classify_dy_commerce(hard, title)
    return {**hard, **classified, "platform": platform}


def summarize_commerce(rows: list[dict]) -> dict:
    """Aggregate stats from list of commerce records."""
    types = [r.get("commerce_type", "无商业") for r in rows]
    counts: dict[str, int] = {}
    for t in types:
        counts[t] = counts.get(t, 0) + 1
    return {
        "total": len(rows),
        "挂品挂车": counts.get("已挂商品", 0),
        "品牌合作": counts.get("品牌合作", 0),
        "品牌露出": counts.get("品牌露出", 0),
        "疑似种草": counts.get("疑似种草", 0),
        "无商业": counts.get("无商业", 0),
        "by_type": counts,
    }


def commerce_priority_score(commerce_type: str) -> int:
    """Higher = more commercially actionable for brand intel."""
    return {
        "已挂商品": 4,
        "品牌合作": 3,
        "品牌露出": 2,
        "疑似种草": 1,
        "无商业": 0,
    }.get(commerce_type, 0)
