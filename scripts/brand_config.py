#!/usr/bin/env python3
"""竞品监测：品牌 canonical 名 ↔ 搜索词（XHS / DY 共用）。

Fork 后请改 BRAND_CANONICAL / BRAND_SEARCH_KEYWORDS；
示例中「网易严选」表示自有品牌，其余为家清赛道公开竞品名。
"""
from __future__ import annotations

BRAND_CANONICAL = [
    "滴露", "网易严选", "沫檬", "椰放",
    "水卫士", "晴天大白", "老管家", "蔬果园",
]

# canonical → 搜索词（与 douyin-pulse 品牌 run 对齐）
BRAND_SEARCH_KEYWORDS: dict[str, list[str]] = {
    "滴露": ["滴露", "滴露消毒液", "滴露衣物消毒"],
    "网易严选": ["网易严选", "网易严选香氛", "网易严选家清"],
    "沫檬": ["沫檬", "沫檬地板清洁", "沫檬地板清洁剂"],
    "椰放": ["椰放", "椰放香薰", "椰放车载香薰"],
    "水卫士": ["水卫士", "水卫士马桶", "水卫士管道疏通"],
    "晴天大白": ["晴天大白", "晴天大白车载", "晴天大白车载香薰"],
    "老管家": ["老管家", "老管家洗衣机", "老管家空调清洁"],
    "蔬果园": ["蔬果园", "蔬果园洗洁精", "蔬果园香薰"],
}


def xhs_brand_keywords_flat() -> list[str]:
    """去重保序，供 fetch_xhs 品牌池搜索。"""
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
