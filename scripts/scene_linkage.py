#!/usr/bin/env python3
"""L3 关联层：场景桥接趋势 × 竞品 × SKU，及可跟投候选子集。"""
from __future__ import annotations

import re
from typing import Any

COMMERCE_ACTIONABLE = {"已挂商品", "品牌合作"}


from brand_config import norm_brand_key as _norm_brand


def _match_playbook(topic: str, scene: str, playbook: list) -> dict | None:
    blob = f"{topic} {scene}"
    for pb in playbook:
        if any(s in blob for s in pb.get("signals", [])[:8]):
            return pb
        head = (pb.get("topic") or "").split("/")[0].strip()
        if head and head in blob:
            return pb
    return None


def build_scene_links(
    trend_signals: list,
    competitor_actions: list,
    opportunity_matrix: list,
    playbook: list,
) -> list[dict]:
    """场景关联表：不要求同一条 content id。"""
    comps = [c for c in competitor_actions if not c.get("is_self")]
    links = []
    seen_topics: set[str] = set()

    for opp in opportunity_matrix[:6]:
        topic = opp.get("topic", "")
        if topic in seen_topics:
            continue
        seen_topics.add(topic)
        pb = _match_playbook(topic, opp.get("scene", ""), playbook) or {}
        sig = next((t for t in trend_signals if topic[:8] in t.get("topic", "")), None)
        matched = []
        for c in comps:
            blob = " ".join([
                c.get("scene", ""),
                (c.get("xhs") or {}).get("title", ""),
                (c.get("dy") or {}).get("title", ""),
            ])
            if any(s in blob for s in (pb.get("signals") or [])[:6]):
                matched.append(c["brand"])
            elif opp.get("scene") and opp["scene"] in c.get("scene", ""):
                matched.append(c["brand"])
        links.append({
            "scene": opp.get("scene") or topic.split("/")[0].strip(),
            "topic": topic,
            "trend_arrow": sig.get("arrow", "→") if sig else opp.get("arrow", "→"),
            "trend_status": sig.get("status", "") if sig else "",
            "competitors": list(dict.fromkeys(matched))[:4] or opp.get("competitors", [])[:3],
            "own_brand_skus": opp.get("own_brand_skus", [])[:3],
            "decision": opp.get("decision", ""),
            "bridge": "场景匹配（非同视频求交）",
        })

    return links


def build_follow_candidates(
    xhs_trend: list,
    xhs_hall: list,
    dy_trend: list,
    dy_hall: list,
    scene_links: list,
    limit: int = 12,
) -> list[dict]:
    """
    可跟投候选：品类池内 + 已确认商业行为（挂品/挂车/合作）。
    可为空——不强行填充。
    """
    rows: list[dict] = []
    seen: set[str] = set()

    def add(platform: str, r: dict, source: str):
        key = f"{platform}:{r.get('title', '')[:40]}"
        if key in seen:
            return
        seen.add(key)
        ct = r.get("commerce_type", "")
        if ct not in COMMERCE_ACTIONABLE:
            return
        scene = r.get("cat") or r.get("category") or ""
        link = next(
            (lk for lk in scene_links if any(s in (r.get("title") or "") for s in lk.get("topic", "").split("/")[0][:4])),
            {},
        )
        rows.append({
            "platform": platform,
            "source": source,
            "title": (r.get("title") or "")[:80],
            "likes": r.get("likes", 0),
            "commerce_type": ct,
            "commerce_label": r.get("commerce_label", ""),
            "trend_tag": r.get("trend_tag", ""),
            "velocity_label": r.get("velocity_label", ""),
            "scene": scene,
            "related_competitors": link.get("competitors", [])[:3],
            "own_brand_skus": link.get("own_brand_skus", [])[:2],
            "why": f"{platform} 品类池 · {ct} · {source}",
        })

    for r in xhs_trend[:10]:
        add("小红书", r, "趋势榜")
    for r in dy_trend[:10]:
        add("抖音", r, "趋势榜")
    for r in xhs_hall[:5]:
        if r.get("commerce_type") in COMMERCE_ACTIONABLE:
            add("小红书", r, "殿堂榜")

    rows.sort(key=lambda x: (
        0 if x["commerce_type"] == "已挂商品" else 1,
        -int(x.get("likes") or 0),
    ))
    return rows[:limit]
