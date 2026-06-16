#!/usr/bin/env python3
"""Rebuild monthly-report.html DATA from xhs + douyin analysis.json."""
import json
import re
import statistics
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from brief_catalog import load_catalog, resolve_products  # noqa: E402
from commerce_detect import (  # noqa: E402
    merge_commerce_record,
    summarize_commerce,
)
from competitor_enrich import enrich_clip, is_public_sentiment, is_industry_news  # noqa: E402
from brand_config import (  # noqa: E402
    BRAND_CANONICAL,
    BRAND_SCENE_HINTS,
    BRAND_SEARCH_KEYWORDS,
    DEFAULT_SCENE,
    DIRECTION_PLAYBOOK,
    NICHE_LABEL,
    OWN_BRAND,
    OWN_BRAND_ALIASES,
    OWN_BRAND_DISPLAY,
    is_own_brand,
    keywords_for_brand,
    norm_brand_key,
)
from env_paths import HTML_OUTPUT  # noqa: E402
from load_niche import format_report_copy  # noqa: E402
from relevance_filter import mentions_brand as _text_mentions_brand  # noqa: E402

try:
    from merge_douyin_pulse import (  # noqa: E402
        rebuild_dy_brands,
        sanitize_dy_brand_rows,
        refresh_dy_brand_markdown,
        _find_latest_pulse_raw,
    )
    from scene_linkage import build_scene_links, build_follow_candidates  # noqa: E402
except ImportError:
    rebuild_dy_brands = None
    sanitize_dy_brand_rows = None
    refresh_dy_brand_markdown = None
    _find_latest_pulse_raw = lambda: None
    build_scene_links = None
    build_follow_candidates = None
XHS = ROOT / "data" / "xhs-monthly" / "analysis.json"
XHS_RAW = ROOT / "data" / "xhs-monthly" / "merged_raw.json"
DY = ROOT / "data" / "douyin-monthly" / "analysis.json"
DY_COMMERCE = ROOT / "data" / "douyin-monthly" / "commerce_cache.json"
HTML = HTML_OUTPUT
CST = timezone(timedelta(hours=8))


def _fmt(n: int) -> str:
    if n >= 10000:
        return f"{n/10000:.1f}万".replace(".0万", "万")
    return f"{n:,}"


def _short_pattern(p: str) -> str:
    m = re.match(r"(P\d+)", p or "")
    return m.group(1) if m else "P10"


def _parse_count(val) -> int:
    if isinstance(val, (int, float)):
        return int(val)
    s = str(val or "").replace(",", "").strip()
    if not s:
        return 0
    if "万" in s:
        return int(float(s.replace("万", "")) * 10000)
    digits = re.sub(r"[^\d.]", "", s)
    return int(float(digits)) if digits else 0


def _title_key(title: str) -> str:
    return re.sub(r"\s+", "", (title or ""))[:48]


def _load_xhs_commerce_by_feed() -> dict:
    if not XHS_RAW.exists():
        return {}
    raw = json.loads(XHS_RAW.read_text(encoding="utf-8"))
    out = {}
    for n in raw.get("notes") or []:
        fid = n.get("feed_id")
        if not fid:
            continue
        if n.get("commerce"):
            out[fid] = n["commerce"]
        else:
            hard = {}
            out[fid] = merge_commerce_record(
                "xhs", hard, n.get("title", ""), n.get("top_comments") or []
            )
    return out


def _load_dy_commerce_maps() -> tuple[dict, dict]:
    if not DY_COMMERCE.exists():
        return {}, {}
    data = json.loads(DY_COMMERCE.read_text(encoding="utf-8"))
    return data.get("by_aweme_id") or {}, data.get("by_title_key") or {}


def _lookup_dy_commerce(
    title: str,
    by_title: dict,
    aweme_id: str | None = None,
    by_id: dict | None = None,
) -> dict:
    by_id = by_id or {}
    if aweme_id and aweme_id in by_id:
        return by_id[aweme_id]
    key = _title_key(title)
    if key in by_title:
        return by_title[key]
    for k, v in by_title.items():
        if k and (k in key or key in k):
            return v
    return merge_commerce_record("dy", {}, title)


def _commerce_fields(record: dict | None) -> dict:
    r = record or {}
    return {
        "commerce_type": r.get("commerce_type", "无商业"),
        "commerce_label": r.get("commerce_label", "无"),
        "commerce_detail": r.get("commerce_detail", ""),
        "product_names": r.get("product_names") or [],
    }


REP_CLIP_TOP = 3


def _clip_has_product(c: dict) -> bool:
    return bool(
        c.get("product_line")
        or c.get("commerce_type") == "已挂商品"
        or c.get("product_names")
    )


def _is_sentiment_clip(c: dict) -> bool:
    return c.get("content_lane") == "sentiment" or c.get("action_type") == "舆情"


def _is_news_clip(c: dict) -> bool:
    return c.get("content_lane") == "news" or c.get("action_type") == "资讯"


def _order_rep_clips(clips: list, limit: int = REP_CLIP_TOP) -> list:
    """展示序：排除舆情/资讯；有单品/挂品优先，同档按赞数。"""
    if not clips:
        return []
    content = [c for c in clips if not _is_sentiment_clip(c) and not _is_news_clip(c)]
    ordered = sorted(
        content,
        key=lambda c: (1 if _clip_has_product(c) else 0, c.get("likes", 0) or 0),
        reverse=True,
    )[:limit]
    out = []
    for i, c in enumerate(ordered):
        row = dict(c)
        row["rank"] = i + 1
        out.append(row)
    return out


def _enrich_platform_clip(
    title: str,
    brand: str,
    commerce: dict,
    platform: str,
    *,
    likes: int = 0,
    likes_label: str = "",
    duration: str = "",
    category: str = "",
    rank: int = 1,
    aweme_id: str = "",
    content_excerpt: str = "",
    author_nickname: str = "",
) -> dict:
    return enrich_clip(
        title, brand, commerce, platform,
        likes=likes, likes_label=likes_label, duration=duration,
        category=category, rank=rank, aweme_id=aweme_id,
        content_excerpt=content_excerpt, author_nickname=author_nickname,
    )


def _enrich_note_clip(note: dict, brand: str, comm: dict, rank: int) -> dict:
    title = (note.get("title") or "")[:160]
    return _enrich_platform_clip(
        title, brand, comm, "xiaohongshu",
        likes=note.get("likes", 0),
        likes_label=_fmt(note.get("likes", 0)),
        category=note.get("category", ""),
        rank=rank,
        content_excerpt=note.get("content_excerpt") or "",
        author_nickname=note.get("author_nickname") or "",
    )


def _window_end_dt(meta: dict) -> datetime:
    date_s = (meta or {}).get("date")
    if date_s:
        return datetime.strptime(str(date_s)[:10], "%Y-%m-%d").replace(tzinfo=CST)
    label = (meta or {}).get("window_label", "")
    m = re.search(r"(\d{2})\.(\d{2})\s*$", label.strip())
    if m:
        mo, day = int(m.group(1)), int(m.group(2))
        yr = datetime.now(CST).year
        return datetime(yr, mo, day, 23, 59, 59, tzinfo=CST)
    return datetime.now(CST)


def _publish_meta(note: dict, end_dt: datetime, pub_map: dict) -> tuple[int, str, datetime | None]:
    ts = note.get("publish_ts")
    if ts is None and note.get("feed_id"):
        d = pub_map.get(note["feed_id"])
        if d:
            pub_dt = datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=CST)
            days = max((end_dt - pub_dt).days + 1, 1)
            return days, d, pub_dt
    if ts is not None:
        try:
            pub_dt = datetime.fromtimestamp(int(ts) / 1000, tz=CST)
            days = max((end_dt - pub_dt).days + 1, 1)
            return days, pub_dt.strftime("%Y-%m-%d"), pub_dt
        except (TypeError, ValueError, OSError):
            pass
    return 30, "—", None


def _trend_score(likes: int, days: int, pub_dt: datetime | None, end_dt: datetime) -> float:
    base = likes / max(days, 1)
    if pub_dt and (end_dt - pub_dt).days <= 6:
        base *= 1.6
    elif pub_dt and (end_dt - pub_dt).days <= 13:
        base *= 1.25
    if days <= 3:
        base *= 1.2
    return base


def _classify_trend_tag(likes: int, days: int, velocity: float, vel_median: float, likes_rank: int) -> str:
    if days <= 10 and velocity >= vel_median * 1.15:
        return "本月新兴"
    if likes_rank <= 5 and velocity < vel_median * 0.6:
        return "持续高位"
    if days >= 18:
        return "常青累积"
    return "稳步上涨"


def _load_xhs_pool(xhs_raw: dict, pool: str = "category") -> list:
    if XHS_RAW.exists():
        payload = json.loads(XHS_RAW.read_text(encoding="utf-8"))
        if pool == "category":
            notes = payload.get("platform_pool") or payload.get("category_pool")
            if not notes:
                notes = [
                    n for n in (payload.get("notes") or [])
                    if "category" in n.get("keyword_pools", [])
                ]
            if notes:
                return notes
        elif pool == "brand":
            brand_notes = payload.get("brand_pool")
            if brand_notes:
                return brand_notes
        notes = payload.get("notes") or []
        if notes:
            return notes
    return xhs_raw.get("top") or []


def _xhs_publish_map(xhs_raw: dict) -> dict:
    pub_map = {}
    for block in (xhs_raw.get("fresh_trend") or {},):
        for n in block.get("top") or []:
            if n.get("feed_id") and n.get("publish_date"):
                pub_map[n["feed_id"]] = n["publish_date"]
    for n in xhs_raw.get("top") or []:
        if n.get("feed_id") and n.get("publish_date"):
            pub_map[n["feed_id"]] = n["publish_date"]
    return pub_map


def _score_xhs_notes(notes: list, xhs_raw: dict) -> list:
    meta = xhs_raw.get("_meta") or {}
    end_dt = _window_end_dt(meta)
    pub_map = _xhs_publish_map(xhs_raw)
    scored = []
    seen = set()
    for n in notes:
        fid = n.get("feed_id", "")
        if fid and fid in seen:
            continue
        if fid:
            seen.add(fid)
        likes = _parse_count(n.get("likes") or n.get("likes_n"))
        if likes <= 0:
            continue
        days, pub_date, pub_dt = _publish_meta(n, end_dt, pub_map)
        velocity = _trend_score(likes, days, pub_dt, end_dt)
        scored.append({
            **n,
            "likes": likes,
            "collects": _parse_count(n.get("collects") or n.get("collects_n")),
            "comments": _parse_count(n.get("comments") or n.get("comments_count")),
            "author": n.get("author") or n.get("author_nickname", ""),
            "category": n.get("category", "其他"),
            "pattern": n.get("pattern", ""),
            "note_type": n.get("note_type", ""),
            "fans": _parse_count(n.get("fans") or n.get("follower_count")),
            "_days": days,
            "_pub_date": pub_date,
            "_pub_dt": pub_dt,
            "_velocity": velocity,
            **(_commerce_fields(n.get("commerce")) if n.get("commerce") else _commerce_fields(
                merge_commerce_record("xhs", {}, n.get("title", ""), n.get("top_comments") or [])
            )),
        })
    return scored


def _format_xhs_rank(n: dict, rank: int, pool: str) -> dict:
    nt = "视频" if n.get("note_type") == "video" else "图文"
    vel = int(n.get("_velocity", 0))
    days = n.get("_days", 0)
    tag = n.get("_trend_tag", "")
    return {
        "rank": rank,
        "title": n.get("title", ""),
        "likes": n["likes"],
        "fav": n.get("collects", 0),
        "cmt": n.get("comments", 0),
        "author": n.get("author", ""),
        "cat": n.get("category", "其他"),
        "type": nt,
        "formula": _short_pattern(n.get("pattern", "")),
        "pool": pool,
        "trend_tag": tag,
        "velocity": vel,
        "velocity_label": f"{vel:,}/天",
        "publish_date": n.get("_pub_date", "—"),
        "days_live": days,
        "commerce_type": n.get("commerce_type", "无商业"),
        "commerce_label": n.get("commerce_label", "无"),
        "detail": (
            f"{tag} · 发布 {n.get('_pub_date', '—')} · 日均 {vel:,} 赞"
            if pool == "trend"
            else f"总赞殿堂 · 发布 {n.get('_pub_date', '—')} · 已发酵 {days} 天"
        ),
    }


def build_xhs_dual_pools(xhs_raw: dict) -> tuple[list, list]:
    pool = _score_xhs_notes(_load_xhs_pool(xhs_raw), xhs_raw)
    if not pool:
        return [], []

    velocities = [n["_velocity"] for n in pool]
    vel_median = statistics.median(velocities) if velocities else 0
    hall_sorted = sorted(pool, key=lambda x: x["likes"], reverse=True)
    trend_sorted = sorted(pool, key=lambda x: x["_velocity"], reverse=True)

    likes_rank = {n.get("feed_id", id(n)): i + 1 for i, n in enumerate(hall_sorted)}
    for n in pool:
        rk = likes_rank.get(n.get("feed_id", id(n)), 99)
        n["_trend_tag"] = _classify_trend_tag(n["likes"], n["_days"], n["_velocity"], vel_median, rk)

    trend = [_format_xhs_rank(n, i + 1, "trend") for i, n in enumerate(trend_sorted[:10])]
    hall = [_format_xhs_rank(n, i + 1, "hall") for i, n in enumerate(hall_sorted[:10])]
    return trend, hall


def _score_dy_videos(videos: list) -> list:
    scored = []
    for v in videos:
        likes = _parse_count(v.get("likes"))
        fans = _parse_count(v.get("fans"))
        shares = _parse_count(v.get("shares"))
        if likes <= 0:
            continue
        breakout = likes / max(fans, 500)
        viral = shares / max(likes, 1)
        trend_score = breakout * (1 + min(viral, 1.5))
        tag = "低粉爆款" if fans < 20000 and likes >= 1000 else "高分享传播"
        if breakout < 0.05 and likes >= 50000:
            tag = "殿堂累积"
        scored.append({**v, "_trend_score": trend_score, "_trend_tag": tag, "_fans_n": fans})
    return scored


def build_dy_dual_pools(dy_raw: dict, dy_by_title: dict | None = None) -> tuple[list, list]:
    videos = dy_raw.get("category_top") or []
    dy_by_title = dy_by_title or {}
    scored = []
    for v in videos:
        base = _score_dy_videos([v])
        if not base:
            continue
        item = base[0]
        comm = _lookup_dy_commerce(v.get("title", ""), dy_by_title)
        item.update(_commerce_fields(comm))
        scored.append(item)
    if not scored:
        return [], []

    trend_sorted = sorted(scored, key=lambda x: x["_trend_score"], reverse=True)
    hall_sorted = sorted(scored, key=lambda x: x["likes"], reverse=True)

    def _fmt_dy(v: dict, rank: int, pool: str) -> dict:
        return {
            "rank": rank,
            "title": v.get("title", ""),
            "likes": v.get("likes", 0),
            "shares": v.get("shares", 0),
            "comments": v.get("comments", 0),
            "duration": v.get("duration", ""),
            "author": v.get("author", ""),
            "fans": v.get("fans", ""),
            "hook": v.get("hook", ""),
            "category": v.get("category", ""),
            "pool": pool,
            "trend_tag": v.get("_trend_tag", ""),
            "trend_score": round(v.get("_trend_score", 0), 2),
            "commerce_type": v.get("commerce_type", "无商业"),
            "commerce_label": v.get("commerce_label", "无"),
            "detail": (
                f"{v.get('_trend_tag', '')} · 赞粉比 {v.get('_trend_score', 0):.1f}"
                if pool == "trend"
                else f"总赞殿堂 · {v.get('likes', 0):,} 赞"
            ),
        }

    trend = [_fmt_dy(v, i + 1, "trend") for i, v in enumerate(trend_sorted[:10])]
    hall = [_fmt_dy(v, i + 1, "hall") for i, v in enumerate(hall_sorted[:10])]
    return trend, hall


def build_trend_signals(
    xhs_scored: list,
    xhs_trend: list,
    xhs_hall: list,
    dy_trend: list,
    dy_hall: list,
    end_dt: datetime,
) -> list:
    """Monthly trend arrows: what's rising vs what's just big."""
    signals = []
    recent = [n for n in xhs_scored if n.get("_pub_dt") and (end_dt - n["_pub_dt"]).days <= 7]
    recent_cats = Counter(n.get("category", "其他") for n in recent)
    ranked_pb = []

    for pb in _DIRECTION_PLAYBOOK:
        sig_hits = sum(1 for s in pb["signals"] if any(s in (n.get("title") or "") for n in recent))
        cat_hits = sum(recent_cats.get(c, 0) for c in pb["cats"])
        dy_hits = sum(1 for v in dy_trend[:5] if any(s in (v.get("title") or "") for s in pb["signals"]))
        score = sig_hits * 3 + cat_hits * 2 + dy_hits * 4
        if score <= 0:
            continue
        ranked_pb.append({**pb, "_score": score, "_recent": sig_hits + cat_hits})

    ranked_pb = sorted(ranked_pb, key=lambda x: -x["_score"])[:3]

    hall_titles = {r["title"][:20] for r in xhs_hall[:5]}
    trend_only = [r for r in xhs_trend[:5] if r["title"][:20] not in hall_titles]

    for pb in ranked_pb:
        arrow = "↑" if pb["_recent"] >= 2 else "→"
        evidence_parts = []
        if pb["_recent"]:
            evidence_parts.append(f"近7天命中 {pb['_recent']} 条")
        dy_match = next((v for v in dy_trend[:5] if any(s in v["title"] for s in pb["signals"])), None)
        if dy_match:
            evidence_parts.append(f"抖音趋势榜：{dy_match['title'][:22]}…")
        xhs_match = next((r for r in trend_only if any(s in r["title"] for s in pb["signals"])), None)
        if xhs_match:
            evidence_parts.append(f"小红书增速：{xhs_match['velocity_label']}（{xhs_match['publish_date']}）")
        signals.append({
            "arrow": arrow,
            "topic": pb["topic"],
            "status": "本月新兴" if arrow == "↑" else "持续活跃",
            "evidence": " · ".join(evidence_parts) or "双平台信号命中",
            "action": pb.get("feed", pb.get("xhs", ""))[:80],
        })

    if trend_only and len(signals) < 4:
        r = trend_only[0]
        if not any(r["title"][:12] in s["evidence"] for s in signals):
            signals.append({
                "arrow": "↑",
                "topic": "小红书增速黑马",
                "status": r.get("trend_tag", "本月新兴"),
                "evidence": f"《{r['title'][:28]}…》· {r['velocity_label']} · 发布 {r['publish_date']}",
                "action": "优先拆解该条结构测钩子，总量榜可能尚未反映",
            })

    stale_giants = [r for r in xhs_hall[:3] if r.get("trend_tag") in ("持续高位", "常青累积")]
    for r in stale_giants[:2]:
        if any(r["title"][:12] in s["evidence"] for s in signals):
            continue
        signals.append({
            "arrow": "→",
            "topic": "高位常青内容",
            "status": r.get("trend_tag", "持续高位"),
            "evidence": f"《{r['title'][:28]}…》· 总赞 {r['likes']:,} · 已发酵 {r['days_live']} 天",
            "action": "学结构可以，但不等于本月趋势；跟拍需换角度或场景",
        })
        if len(signals) >= 5:
            break

    return signals[:5]


def build_xhs(data: dict) -> dict:
    trend_ranks, hall_ranks = build_xhs_dual_pools(data)
    ranks = hall_ranks  # backward compat: RANKS = 殿堂榜
    stats = data.get("stats") or {}
    pat_examples = data.get("pattern_examples") or {}

    quotes = []
    pain = data.get("pain_quotes") or {}
    if isinstance(pain, dict):
        for bucket, items in pain.items():
            for q in items[:2]:
                quotes.append({
                    "text": f"「{q.get('quote', q.get('text', ''))[:140]}」",
                    "src": f"{q.get('ip') or '网友'} · {_fmt(q.get('likes', 0))} 赞",
                    "note": f"《{q.get('from_note', '')[:28]}》",
                    "more": f"痛点桶：{bucket}",
                })
    quotes.sort(key=lambda x: int(re.search(r"([\d,]+)\s*赞", x["src"]).group(1).replace(",", "")) if re.search(r"([\d,]+)\s*赞", x["src"]) else 0, reverse=True)
    if not quotes:
        for n in hall_ranks[:6]:
            quotes.append({
                "text": f"「{n['title'][:80]}」",
                "src": f"{n.get('author', '')} · {_fmt(n['likes'])} 赞",
                "note": "标题/内容洞察（评论未拉取）",
                "more": f"分类：{n.get('cat', '')} · {n.get('formula', '')}",
            })
    quotes = quotes[:8]

    demand_raw = data.get("demand_insights") or {}
    demand = {
        "video": [re.sub(r"\*\*([^*]+)\*\*", r"\1", ln) for ln in (demand_raw.get("video_directions") or [])[:6]],
        "product": [re.sub(r"\*\*([^*]+)\*\*", r"\1", ln) for ln in (demand_raw.get("product_directions") or [])[:5]],
    }

    brands = _parse_xhs_brands(data.get("competitor_summary") or [])

    cat_dist = stats.get("category_distribution_top") or {}
    cats = sorted(cat_dist.items(), key=lambda x: -x[1])[:6]
    cat_chart = [{"n": k.replace("/测评", "")[:8], "v": v, "key": k} for k, v in cats]

    formula_examples = {}
    for pid, examples in pat_examples.items():
        short = _short_pattern(pid)
        if short not in formula_examples and examples:
            formula_examples[short] = examples[:3]

    return {
        "RANKS": ranks,
        "TREND_RANKS": trend_ranks,
        "HALL_RANKS": hall_ranks,
        "FORMULA_EXAMPLES": formula_examples,
        "QUOTES": quotes,
        "DEMAND": demand,
        "BRANDS": brands,
        "CATS": cat_chart,
    }


XHS_BRAND_NAMES = BRAND_CANONICAL

XHS_BRAND_NAMES = BRAND_CANONICAL


def _note_mentions_brand(note: dict, name: str) -> bool:
    """标题/正文/话题须出现品牌名或该品牌组合搜索词；禁止仅凭 keywords_matched 入库标签认定。"""
    text = f"{note.get('title') or ''} {note.get('content_excerpt') or ''}"
    if is_own_brand(name):
        plain = text
        if name in plain or any(a in plain for a in OWN_BRAND_ALIASES if a):
            return _text_mentions_brand(text, name) if _has_relevance_config() else True
    return _text_mentions_brand(text, name)


def _has_relevance_config() -> bool:
    from relevance_filter import _has_relevance_config as _hr
    return _hr()


def build_xhs_brands_from_raw(merged_raw: dict, xhs_by_title: dict | None = None) -> list:
    """品牌池：每品牌种草代表笔记（标题/正文含品牌名；舆情/资讯单独分流）。"""
    xhs_by_title = xhs_by_title or {}
    notes = merged_raw.get("notes") or []
    brands = []
    for name in XHS_BRAND_NAMES:
        display = OWN_BRAND_DISPLAY if is_own_brand(name) else name
        hits = [n for n in notes if _note_mentions_brand(n, name)]
        content_hits = [
            n for n in hits
            if not is_public_sentiment(
                n.get("title") or "",
                n.get("content_excerpt") or "",
                n.get("author_nickname") or "",
            )
            and not is_industry_news(
                n.get("title") or "",
                n.get("content_excerpt") or "",
                n.get("author_nickname") or "",
            )
        ]
        sentiment_hits = [
            n for n in hits
            if is_public_sentiment(
                n.get("title") or "",
                n.get("content_excerpt") or "",
                n.get("author_nickname") or "",
            )
        ]
        news_hits = [
            n for n in hits
            if (not is_public_sentiment(
                n.get("title") or "",
                n.get("content_excerpt") or "",
                n.get("author_nickname") or "",
            )) and is_industry_news(
                n.get("title") or "",
                n.get("content_excerpt") or "",
                n.get("author_nickname") or "",
            )
        ]
        content_hits.sort(key=lambda x: x.get("likes", 0), reverse=True)
        sentiment_hits.sort(key=lambda x: x.get("likes", 0), reverse=True)
        news_hits.sort(key=lambda x: x.get("likes", 0), reverse=True)
        if not hits:
            brands.append({
                "brand": norm_brand_key(name),
                "display": display,
                "active": False,
                "note": "本批样本未命中（标题/正文须含品牌名）",
                "likes": "—",
                "cat": "—",
                "title": "—",
                "count": 0,
                "top_notes": [],
                "sentiment_notes": [],
                "news_notes": [],
                "data_scope": "合并池内检索；品牌词搜索噪声已过滤",
            })
            continue
        top_notes = []
        for i, n in enumerate(content_hits[:5]):
            title = n.get("title", "")[:160]
            comm = n.get("commerce") or xhs_by_title.get(_title_key(title)) or {}
            if not comm.get("commerce_type"):
                comm = merge_commerce_record("xhs", {}, title, n.get("top_comments") or [])
            top_notes.append(_enrich_note_clip(n, norm_brand_key(name), comm, i + 1))
        sentiment_notes = []
        for i, n in enumerate(sentiment_hits[:2]):
            title = n.get("title", "")[:160]
            comm = n.get("commerce") or xhs_by_title.get(_title_key(title)) or {}
            if not comm.get("commerce_type"):
                comm = merge_commerce_record("xhs", {}, title, n.get("top_comments") or [])
            sentiment_notes.append(_enrich_note_clip(n, norm_brand_key(name), comm, i + 1))
        news_notes = []
        for i, n in enumerate(news_hits[:2]):
            title = n.get("title", "")[:160]
            comm = n.get("commerce") or xhs_by_title.get(_title_key(title)) or {}
            if not comm.get("commerce_type"):
                comm = merge_commerce_record("xhs", {}, title, n.get("top_comments") or [])
            news_notes.append(_enrich_note_clip(n, norm_brand_key(name), comm, i + 1))
        rep_hits = content_hits or sentiment_hits
        best = rep_hits[0]
        lead = top_notes[0] if top_notes else (sentiment_notes[0] if sentiment_notes else {})
        brands.append({
            "brand": norm_brand_key(name),
            "display": display,
            "active": True,
            "count": len(hits),
            "likes": lead.get("likes_label") or _fmt(best.get("likes", 0)),
            "likes_n": best.get("likes", 0),
            "cat": best.get("category", ""),
            "title": lead.get("title_clean") or (best.get("title") or "")[:72],
            "note": "本批无种草代表片，仅舆情声量" if sentiment_hits and not content_hits else "",
            "data_scope": "标题/正文含品牌名（合并池检索）",
            "top_notes": top_notes,
            "sentiment_notes": sentiment_notes,
            "news_notes": news_notes,
        })
    return brands


def _parse_xhs_brands(lines: list) -> list:
    """Parse competitor_summary markdown lines into brand cards."""
    brands = []
    for raw in lines:
        line = raw.lstrip("- ").strip()
        dead = "本月无高赞" in line
        m = re.match(
            r"\*\*([^*]+)\*\*(?:（(\d+) 篇）TOP：([\d,]+)赞 · ([^·]+) · 「([^」]+)」)?",
            line,
        )
        if not m:
            continue
        name = m.group(1)
        if dead or not m.group(2):
            brands.append({
                "brand": name.replace("香氛", "").replace("家清", "") if len(name) > 6 else name,
                "display": name,
                "active": False,
                "note": "本月无高赞挂品牌笔记",
                "likes": "—",
                "cat": "—",
                "title": "—",
                "count": 0,
            })
        else:
            brands.append({
                "brand": name.split("香氛")[0].split("家清")[0] or name,
                "display": name,
                "active": True,
                "count": int(m.group(2)),
                "likes": m.group(3),
                "likes_n": _parse_count(m.group(3)),
                "cat": m.group(4).strip(),
                "title": m.group(5)[:72],
                "note": "",
                "data_scope": "品牌词搜索·标题/正文含品牌名",
            })
    return brands


def _shared_cats(xhs_cats: list, dy_dist: dict) -> list:
    xhs_keys = {c["key"] if isinstance(c, dict) else c[0] for c in xhs_cats}
    dy_keys = set(dy_dist.keys())
    overlap = []
    for k in xhs_keys:
        nk = k.replace("卫生间/马桶清洁", "卫生间清洁").replace("好物推荐", "清洁妙招")
        for dk in dy_keys:
            if k in dk or dk in k or nk == dk:
                overlap.append(dk)
                break
    return list(dict.fromkeys(overlap))[:3]


_BRAND_SCENE_HINTS = BRAND_SCENE_HINTS


def _norm_brand_key(name: str) -> str:
    return norm_brand_key(name)


def _is_own_brand(name: str) -> bool:
    return is_own_brand(name)


def _infer_scene(title: str, cat: str = "") -> str:
    title = title or ""
    for pb in _DIRECTION_PLAYBOOK:
        if any(s in title for s in pb["signals"]):
            return pb["topic"].split("/")[0].strip()
    if cat and cat not in ("其他", "好物推荐", "品牌竞品"):
        return cat
    return DEFAULT_SCENE


def _infer_tactic(title: str, hook: str = "", platform: str = "") -> str:
    if hook:
        return f"{hook}开场"
    title = title or ""
    if any(w in title for w in ["滂臭", "异味", "臭", "祛味"]):
        return "痛点场景种草"
    if any(w in title for w in ["邪修", "0成本", "妙招", "小技巧"]):
        return "清单/教程体"
    if any(w in title for w in ["体香", "夯爆了", "高级香"]):
        return "情绪概念种草"
    if "沉浸式" in title or "vlog" in title.lower():
        return "消耗补货 vlog"
    if platform == "douyin":
        return "挂 tag 信息流"
    return "好物测评体"


def _threat_level(score: int, is_self: bool = False) -> str:
    if is_self:
        return "自有"
    if score >= 5000:
        return "高"
    if score >= 800:
        return "中"
    if score > 0:
        return "低"
    return "静默"


def build_competitor_actions(
    xhs_brands: list,
    dy_brands: list,
    dy_by_title: dict | None = None,
    xhs_by_title: dict | None = None,
    dy_by_id: dict | None = None,
) -> list:
    """Merge XHS + DY brand monitoring into competitor action cards."""
    dy_by_title = dy_by_title or {}
    dy_by_id = dy_by_id or {}
    xhs_by_title = xhs_by_title or {}
    merged: dict[str, dict] = {}

    for b in xhs_brands or []:
        key = _norm_brand_key(b.get("display") or b.get("brand", ""))
        if not key:
            continue
        likes = _parse_count(b.get("likes")) if b.get("active") else 0
        entry = merged.setdefault(key, {
            "brand": key,
            "xhs": None,
            "dy": None,
            "xhs_likes": 0,
            "dy_likes": 0,
            "active": False,
        })
        if b.get("active"):
            entry["active"] = True
            entry["xhs_likes"] = likes
            top_notes = b.get("top_notes") or []
            sentiment_notes = b.get("sentiment_notes") or []
            news_notes = b.get("news_notes") or []
            if top_notes and top_notes[0].get("title_clean"):
                lead = top_notes[0]
            elif sentiment_notes:
                lead = sentiment_notes[0]
            elif news_notes:
                lead = news_notes[0]
            else:
                title = b.get("title", "")[:160]
                xhs_comm = xhs_by_title.get(_title_key(title)) or merge_commerce_record("xhs", {}, title)
                lead = _enrich_platform_clip(
                    title, key, xhs_comm, "xiaohongshu",
                    likes=likes, likes_label=b.get("likes", "0"),
                    category=b.get("cat", ""),
                )
            top_notes = _order_rep_clips(top_notes, REP_CLIP_TOP)
            xhs_payload = {
                **lead,
                "scene": b.get("cat", "") or lead.get("category", ""),
                "count": b.get("count", 0),
                "tactic": _infer_tactic(lead.get("title_raw") or lead.get("title_clean", ""), platform="xiaohongshu"),
                "data_scope": b.get("data_scope", "标题/正文含品牌名"),
                "top_notes": top_notes,
            }
            if sentiment_notes:
                xhs_payload["sentiment_notes"] = sentiment_notes[:2]
            if news_notes:
                xhs_payload["news_notes"] = news_notes[:2]
            entry["xhs"] = xhs_payload

    for b in dy_brands or []:
        key = _norm_brand_key(b.get("brand", ""))
        if not key:
            continue
        likes = _parse_count(b.get("top_likes_n") or b.get("top_likes"))
        entry = merged.setdefault(key, {
            "brand": key,
            "xhs": None,
            "dy": None,
            "xhs_likes": 0,
            "dy_likes": 0,
            "active": False,
        })
        tag_n = _parse_count(str(b.get("tag_count", "0")).split("→")[0])
        top_videos = []
        for v in b.get("top_videos") or []:
            vt = v.get("title") or v.get("title_raw") or ""
            vc = _lookup_dy_commerce(vt, dy_by_title, v.get("aweme_id"), dy_by_id)
            top_videos.append(_enrich_platform_clip(
                vt, key, vc, "douyin",
                likes=v.get("likes", 0),
                likes_label=v.get("likes_label", ""),
                duration=v.get("duration", ""),
                rank=v.get("rank", 1),
                aweme_id=v.get("aweme_id", ""),
            ))
        has_rep = likes > 0 or (
            b.get("top_title") and not str(b.get("top_title", "")).startswith("（本批")
        )
        if has_rep:
            entry["active"] = True
            entry["dy_likes"] = likes
            if top_videos:
                lead = top_videos[0]
            else:
                title = b.get("top_title", "")[:160]
                dy_comm = _lookup_dy_commerce(
                    title, dy_by_title, b.get("aweme_id"), dy_by_id,
                )
                lead = _enrich_platform_clip(
                    title, key, dy_comm, "douyin",
                    likes=likes, likes_label=b.get("top_likes", "0"),
                    duration=b.get("duration", ""),
                    aweme_id=b.get("aweme_id", ""),
                )
            rep_title = lead.get("title_raw") or lead.get("title_clean") or b.get("top_title", "")
            top_videos = _order_rep_clips(top_videos, REP_CLIP_TOP)
            entry["dy"] = {
                **lead,
                "scene": _infer_scene(rep_title),
                "tag_count": tag_n,
                "tactic": _infer_tactic(rep_title, platform="douyin"),
                "data_scope": b.get("data_scope", "描述须含品牌名"),
                "top_videos": top_videos,
            }

    actions = []
    for key, entry in merged.items():
        total = entry["xhs_likes"] + entry["dy_likes"]
        scene = ""
        if entry.get("xhs"):
            scene = entry["xhs"].get("scene") or ""
        if not scene and entry.get("dy"):
            scene = entry["dy"].get("scene") or ""
        scene = scene or _BRAND_SCENE_HINTS.get(key, DEFAULT_SCENE)

        platforms = []
        if entry.get("xhs"):
            platforms.append("小红书")
        if entry.get("dy"):
            platforms.append("抖音")

        if _is_own_brand(key):
            if total <= 0:
                implication = "双平台品牌内容近乎失语，竞品在抢场景声量"
                status = "失语"
            elif total < 500:
                implication = "有挂品牌内容但流量极弱，需加大达人/信息流投放"
                status = "弱声"
            else:
                implication = "品牌内容有曝光，继续放大高效场景"
                status = "有声"
        elif not entry.get("active"):
            implication = "本月监测范围内无高赞动作，可观察但不急于跟打"
            status = "静默"
        else:
            xhs_p = (entry.get("xhs") or {}).get("product_line", "")
            dy_p = (entry.get("dy") or {}).get("product_line", "")
            prod_hint = "、".join(p for p in [xhs_p, dy_p] if p and p != "未标明单品")[:30]
            top_plat = "小红书" if entry["xhs_likes"] >= entry["dy_likes"] else "抖音"
            top_likes = max(entry["xhs_likes"], entry["dy_likes"])
            if entry["xhs_likes"] >= 3000 and entry["dy_likes"] < 500:
                implication = (
                    f"小红书 {scene} 有声（{_fmt(entry['xhs_likes'])} 赞"
                    f"{f'·{xhs_p}' if xhs_p else ''}），"
                    f"抖音多为低赞挂车片{f'（{dy_p}）' if dy_p else ''}——分平台跟打"
                )
            else:
                implication = (
                    f"{top_plat} {scene} 占位（{_fmt(top_likes)} 赞"
                    f"{f'·{prod_hint}' if prod_hint else ''}），{OWN_BRAND}需差异化切入同场景"
                )
            status = "活跃"

        tactic_parts = []
        if entry.get("xhs"):
            tactic_parts.append(f"小红书·{entry['xhs']['tactic']}")
        if entry.get("dy"):
            tactic_parts.append(f"抖音·{entry['dy']['tactic']}")

        comm_parts = []
        xhs_ct = (entry.get("xhs") or {}).get("commerce_type")
        dy_ct = (entry.get("dy") or {}).get("commerce_type")
        if xhs_ct == "已挂商品":
            comm_parts.append("XHS挂品")
        elif xhs_ct in ("品牌合作", "品牌露出", "疑似种草"):
            comm_parts.append(f"XHS·{xhs_ct}")
        if dy_ct == "已挂商品":
            comm_parts.append("DY挂车")
        elif dy_ct in ("品牌露出", "疑似种草"):
            comm_parts.append(f"DY·{dy_ct}")
        if not comm_parts:
            commerce_action = "无确认商业动作" if entry.get("active") else "—"
        elif "XHS挂品" in comm_parts and "DY挂车" in comm_parts:
            commerce_action = "双平台带货"
        else:
            commerce_action = " / ".join(comm_parts)

        actions.append({
            "brand": key,
            "is_self": _is_own_brand(key),
            "status": status,
            "threat": _threat_level(total, _is_own_brand(key)),
            "scene": scene,
            "platforms": platforms,
            "total_likes": total,
            "xhs": entry.get("xhs"),
            "dy": entry.get("dy"),
            "tactic": " / ".join(tactic_parts) or "—",
            "commerce_action": commerce_action,
            "data_scope": "品牌监测代表片（非全网爆款榜）",
            "implication": implication,
        })

    actions.sort(key=lambda x: (x["is_self"], -x["total_likes"], x["brand"]))
    # 自有品牌排最前，其余按声量
    actions.sort(key=lambda x: (0 if x["is_self"] else 1, -x["total_likes"]))
    return actions


def _match_playbook_to_scene(scene: str, topic: str) -> dict | None:
    for pb in _DIRECTION_PLAYBOOK:
        head = pb["topic"].split("/")[0].strip()
        if head in scene or head in topic or topic.startswith(pb["topic"][:6]):
            return pb
        if any(s in scene for s in pb["signals"][:4]):
            return pb
    return None


def build_opportunity_matrix(
    directions: list,
    competitor_actions: list,
    trend_signals: list,
) -> list:
    """自有品牌机会矩阵：趋势 × 竞品空白 × SKU × 品牌决策。"""
    competitors = [a for a in competitor_actions if not a["is_self"]]
    own_brand = next((a for a in competitor_actions if a["is_self"]), None)
    trend_map = {t["topic"]: t for t in trend_signals}

    rows = []
    for i, d in enumerate(directions[:6]):
        topic = d.get("topic", "")
        pb = _match_playbook_to_scene(topic, topic) or {}
        scene = (pb.get("topic") or topic).split("/")[0].strip()

        active_comps = []
        for c in competitors:
            if c.get("status") == "静默":
                continue
            title_blob = " ".join(
                filter(None, [
                    (c.get("xhs") or {}).get("title", ""),
                    (c.get("dy") or {}).get("title", ""),
                    c.get("scene", ""),
                ])
            )
            if any(s in title_blob or s in topic for s in (pb.get("signals") or [])[:6]):
                active_comps.append(c)
            elif scene and scene in c.get("scene", ""):
                active_comps.append(c)

        if not active_comps:
            active_comps = [c for c in competitors if c.get("status") != "静默" and c["total_likes"] > 0][:2]

        comp_lines = []
        max_comp_likes = 0
        for c in sorted(active_comps, key=lambda x: -x["total_likes"])[:3]:
            comp_lines.append(f"{c['brand']} {_fmt(c['total_likes'])}赞")
            max_comp_likes = max(max_comp_likes, c["total_likes"])

        own_likes = own_brand["total_likes"] if own_brand else 0

        ts = next((t for t in trend_signals if topic.split("/")[0].strip() in t.get("topic", "")), None)
        arrow = ts["arrow"] if ts else "→"

        if own_likes <= 0 and max_comp_likes >= 1000:
            gap = f"{OWN_BRAND}本月无声，竞品已占位"
            decision = "加速切入"
        elif own_likes < max_comp_likes * 0.1 and max_comp_likes > 500:
            gap = f"{OWN_BRAND}弱声（{_fmt(own_likes)} vs 竞品 {_fmt(max_comp_likes)}）"
            decision = "差异化跟打"
        elif arrow == "↑":
            gap = "赛道升温，品牌窗口期"
            decision = "抢先布局"
        else:
            gap = "竞品声量有限，可小步试投"
            decision = "小步验证"

        sku_names = [p["name"] for p in d.get("products", []) if p.get("priority")][:3]
        if not sku_names:
            sku_names = [p["name"] for p in d.get("products", [])][:2]

        rows.append({
            "priority": i + 1,
            "arrow": arrow,
            "topic": topic,
            "scene": scene,
            "heat": d.get("heat", ""),
            "competitors": comp_lines or ["本月无明确竞品占位"],
            "gap": gap,
            "decision": decision,
            "own_brand_skus": sku_names,
            "sell_anchor": d.get("sell_anchor", ""),
            "play": {
                "feed": (d.get("content") or {}).get("feed", ""),
                "xhs": (d.get("content") or {}).get("xhs", ""),
                "dy": (d.get("content") or {}).get("dy", ""),
            },
        })

    return rows


def build_own_brand_voice(competitor_actions: list) -> dict:
    own = next((a for a in competitor_actions if a["is_self"]), None)
    if not own:
        return {"status": "未监测", "summary": f"未找到{OWN_BRAND}品牌数据", "total_likes": 0}
    return {
        "status": own["status"],
        "summary": own["implication"],
        "total_likes": own["total_likes"],
        "xhs": own.get("xhs"),
        "dy": own.get("dy"),
        "threat": own["threat"],
    }


def build_overview(
    xhs_data: dict,
    dy_data: dict,
    xhs_block: dict,
    dy_trend: list,
    dy_hall: list,
    trend_signals: list,
    competitor_actions: list,
    opportunity_matrix: list,
    own_brand_voice: dict,
    commerce_summary: dict | None = None,
) -> dict:
    meta_x = xhs_data.get("_meta") or {}
    meta_d = dy_data.get("_meta") or {}
    window = meta_d.get("window_label") or meta_x.get("window_label", "")
    xhs_trend_top = (xhs_block.get("TREND_RANKS") or [{}])[0]
    xhs_hall_top = (xhs_block.get("HALL_RANKS") or [{}])[0]
    dy_trend_top = (dy_trend or [{}])[0]
    dy_top = (dy_hall or dy_data.get("category_top") or [{}])[0]
    xhs_stats = xhs_data.get("stats") or {}
    dy_stats = dy_data.get("stats") or {}

    xhs_cat = sorted(
        (xhs_stats.get("category_distribution_top") or {}).items(),
        key=lambda x: -x[1],
    )[:6]
    dy_cat = sorted(
        (dy_stats.get("category_distribution") or {}).items(),
        key=lambda x: -x[1],
    )
    hook_items = sorted(
        (dy_data.get("hook_distribution") or {}).items(),
        key=lambda x: -x[1],
        reverse=True,
    )
    shared = _shared_cats(xhs_cat, dy_stats.get("category_distribution") or {})

    other_hook = (dy_data.get("hook_distribution") or {}).get("其他", 0)
    cat_n = len(dy_data.get("category_top") or [])
    top_hook = hook_items[0][0] if hook_items else "数字钩"

    active_comps = [a for a in competitor_actions if a.get("status") not in ("静默", "自有") and not a["is_self"]]
    cart_comps = [
        a for a in active_comps
        if "挂车" in a.get("commerce_action", "") or "挂品" in a.get("commerce_action", "")
    ]
    top_comp = active_comps[0] if active_comps else None
    accel_ops = [r for r in opportunity_matrix if r.get("decision") in ("加速切入", "抢先布局", "差异化跟打")]

    insights_platform = [
        {
            "layer": "platform",
            "title": "趋势榜 ≠ 总量榜：跟投看增速，殿堂只拆结构",
            "evidence": (
                f"小红书增速 TOP「{xhs_trend_top.get('title', '')[:18]}…」"
                f"（{xhs_trend_top.get('velocity_label', '')}）"
                f" vs 殿堂「{xhs_hall_top.get('title', '')[:18]}…」"
                f"（{xhs_hall_top.get('likes', 0):,} 赞 · {xhs_hall_top.get('trend_tag', '')}）"
            ),
            "action": "内容跟拍优先趋势榜；邪修清洁类 UGC 学结构，不直接当 SKU 机会",
        },
        {
            "layer": "platform",
            "title": f"抖音品类天花板：{dy_top.get('likes', 0):,} 赞 · 钩子以 {top_hook} 为主",
            "evidence": (
                f"品类榜 TOP「{dy_top.get('title', '')[:22]}…」"
                f" · 分享 {_fmt(dy_top.get('shares', 0))}"
                + (f" · 钩子分布：{'、'.join(f'{k}{v}' for k,v in hook_items[:3])}" if hook_items else "")
            ),
            "action": "信息流测 3 条统一首帧句式；品类热点与品牌挂车片分开看",
        },
        {
            "layer": "platform",
            "title": "小红书重收藏、抖音重分享——同题材分平台叙事",
            "evidence": (
                f"XHS 殿堂收藏 {_fmt(xhs_hall_top.get('fav', 0))} vs "
                f"DY 殿堂分享 {_fmt(dy_top.get('shares', 0))} · "
                f"共同分类 {', '.join(shared) if shared else '见双榜交叉'}"
            ),
            "action": "小红书出步骤/清单可收藏体；抖音出短痛点 + 高分享反差",
        },
    ]

    insights_brand = [
        {
            "layer": "brand",
            "title": f"{OWN_BRAND}本月社媒声量偏弱，竞品在抢场景",
            "evidence": (
                f"{OWN_BRAND}「{own_brand_voice.get('status', '—')}」"
                f"（双平台品牌代表片合计 {_fmt(own_brand_voice.get('total_likes', 0))} 赞）"
                + (f"；监测范围内声量最高 {top_comp['brand']} {_fmt(top_comp['total_likes'])} 赞" if top_comp else "")
            ),
            "action": "见 §03 机会矩阵；补品牌内容/投放，不只跟 UGC",
        },
        {
            "layer": "brand",
            "title": f"本月 {len([t for t in trend_signals if t.get('arrow') == '↑'])} 条赛道升温",
            "evidence": "；".join(
                f"{t['topic'][:14]}…" for t in trend_signals if t.get("arrow") == "↑"
            )[:120] or "见 §04 趋势信号",
            "action": "升温赛道绑定主推 SKU，窗口期有限",
        },
        {
            "layer": "brand",
            "title": f"竞品带货动作：{len(cart_comps)} 家确认挂车/挂品",
            "evidence": (
                (f"{'、'.join(c['brand'] for c in cart_comps[:4])}" if cart_comps else "多为品牌 tag 露出")
                + " · 品牌代表片赞数常低于品类爆款（挂车分销片 vs UGC）"
            ),
            "action": "跟打对标已挂车竞品片；纯爆款只借钩子不借货盘",
        },
    ]

    insights = insights_platform + insights_brand

    data_methodology = {
        "platform_pool": (
            "品类词（见 niche_config.CATEGORY_KEYWORDS）每词 TOP30 翻页搜索，合并去重后按总赞/增速排序——"
            f"反映全网{NICHE_LABEL}热点，不强制出现品牌名"
        ),
        "brand_pool": (
            "品牌词搜索 + 标题/正文含品牌名；每品牌保留 TOP3–5 代表片——"
            "反映品牌动作与挂车，不代表品牌全网最高声量"
        ),
        "commerce_review": "商业复核：品类榜 TOP10 + 品牌代表片全量 API 打标",
        "scene_links": "关联层 scene_links：趋势场景 × 竞品 × SKU（非同视频求交）",
        "follow_candidates": "可跟投子集：品类热点 ∩ 已确认挂品/挂车（可为空）",
        "do_not_mix": "勿用品牌代表片赞数与品类 UGC 爆款直接比大小",
    }

    return {
        "window": f"{window}（近30天）",
        "total_samples": len(xhs_block["RANKS"]) + meta_d.get("category_sample", 0) + meta_d.get("brand_sample", 0),
        "xhs_trend_top1": {
            "likes": xhs_trend_top.get("likes", 0),
            "title": xhs_trend_top.get("title", ""),
            "extra": f"{xhs_trend_top.get('velocity_label', '')} · {xhs_trend_top.get('trend_tag', '')}",
        },
        "xhs_hall_top1": {
            "likes": xhs_hall_top.get("likes", 0),
            "title": xhs_hall_top.get("title", ""),
            "extra": f"收藏 {_fmt(xhs_hall_top.get('fav', 0))} · {xhs_hall_top.get('trend_tag', '')}",
        },
        "dy_trend_top1": {
            "likes": dy_trend_top.get("likes", 0),
            "title": dy_trend_top.get("title", ""),
            "extra": f"{dy_trend_top.get('trend_tag', '')} · 赞粉比 {dy_trend_top.get('trend_score', '')}",
        },
        "dy_top1": {
            "likes": dy_top.get("likes", 0),
            "title": dy_top.get("title", ""),
            "extra": f"作者 {dy_top.get('author', '')}",
        },
        "trend_signals": trend_signals,
        "own_brand_voice": own_brand_voice,
        "brand_kpi": {
            "competitor_active": len(active_comps),
            "competitor_cart": len(cart_comps),
            "opportunity_accel": len(accel_ops),
            "rising_trends": len([t for t in trend_signals if t.get("arrow") == "↑"]),
            "own_brand_status": own_brand_voice.get("status", "—"),
            "xhs_cart": (commerce_summary or {}).get("xhs", {}).get("挂品挂车", 0),
            "dy_cart": (commerce_summary or {}).get("dy", {}).get("挂品挂车", 0),
        },
        "commerce_summary": commerce_summary or {},
        "platform_kpi": {
            "xhs_trend_likes": xhs_trend_top.get("likes", 0),
            "xhs_hall_likes": xhs_hall_top.get("likes", 0),
            "dy_trend_likes": dy_trend_top.get("likes", 0),
            "dy_hall_likes": dy_top.get("likes", 0),
            "xhs_median": xhs_stats.get("median_likes", 0),
            "dy_median": dy_stats.get("median_likes", 0),
            "total_samples": len(xhs_block.get("RANKS") or []) + meta_d.get("category_sample", 0),
        },
        "data_methodology": data_methodology,
        "insights_platform": insights_platform,
        "insights_brand": insights_brand,
        "xhs_median": xhs_stats.get("median_likes", 0),
        "dy_median": dy_stats.get("median_likes", 0),
        "shared_categories": shared,
        "xhs_cat_dist": [[k, v] for k, v in xhs_cat],
        "dy_cat_dist": [[k, v] for k, v in dy_cat],
        "dy_hook_dist": hook_items,
        "insights": insights,
    }


_DIRECTION_PLAYBOOK = DIRECTION_PLAYBOOK


def _top_pain_quote(xhs_raw: dict, keys: list) -> str:
    pain = xhs_raw.get("pain_quotes") or {}
    best = ("", 0)
    for k in keys:
        for q in pain.get(k, [])[:2]:
            likes = q.get("likes", 0)
            if likes > best[1]:
                best = (q.get("quote", "")[:80], likes)
    return best[0]


def _cat_count(stats: dict, cats: list) -> int:
    dist = stats.get("category_distribution_top") or {}
    return sum(dist.get(c, 0) for c in cats)


def build_monthly_directions(xhs_raw: dict, dy_raw: dict) -> list:
    """Synthesize monthly action cards: hot topic → brief 商品 → content angles."""
    catalog = load_catalog()
    top = xhs_raw.get("top") or []
    pool = " ".join(
        n.get("title", "") for n in top[:20]
    )
    for bucket, items in (xhs_raw.get("pain_quotes") or {}).items():
        for q in items[:2]:
            pool += " " + q.get("quote", "") + " " + bucket
    pool += " " + " ".join(w for w, _ in (xhs_raw.get("hot_topics") or [])[:15])
    pool += " " + " ".join(c.get("title", "") for c in dy_raw.get("category_top", []))

    pain_w = {
        k: sum(q.get("likes", 0) for q in v)
        for k, v in (xhs_raw.get("pain_quotes") or {}).items()
    }
    xhs_stats = xhs_raw.get("stats") or {}
    dy_dist = (dy_raw.get("stats") or {}).get("category_distribution") or {}

    scored = []
    for pb in _DIRECTION_PLAYBOOK:
        sig_score = sum(3 for s in pb["signals"] if s in pool)
        pain_score = sum(pain_w.get(k, 0) // 500 for k in pb["pain_keys"])
        cat_score = _cat_count(xhs_stats, pb["cats"]) * 4
        dy_score = sum(dy_dist.get(c, 0) * 5 for c in pb["dy_cats"])
        total = sig_score + pain_score + cat_score + dy_score
        if total <= 0:
            continue

        quote = _top_pain_quote(xhs_raw, pb["pain_keys"])
        hot_kw = [s for s in pb["signals"] if s in pool][:3]
        discuss = quote or (top[0]["title"][:60] if top else "")
        heat_parts = []
        if hot_kw:
            heat_parts.append("热词：" + " · ".join(hot_kw))
        if pb["pain_keys"]:
            pk = max(pb["pain_keys"], key=lambda k: pain_w.get(k, 0))
            if pain_w.get(pk):
                heat_parts.append(f"评论热议「{pk}」")
        if pb["dy_cats"] and any(dy_dist.get(c) for c in pb["dy_cats"]):
            heat_parts.append("抖音品类上榜")
        if pb["cats"] and _cat_count(xhs_stats, pb["cats"]):
            heat_parts.append(f"小红书 {_cat_count(xhs_stats, pb['cats'])} 篇入榜")

        products = resolve_products(pb["brief_id"], catalog)
        sell_anchor = next((p["tagline"] for p in products if p.get("tagline")), "")
        scored.append({
            "topic": pb["topic"],
            "heat": " · ".join(heat_parts) or "双平台信号命中",
            "discussion": discuss,
            "products": products,
            "sell_anchor": sell_anchor,
            "content": {
                "xhs": pb["xhs"],
                "dy": pb["dy"],
                "feed": pb["feed"] + (f"（brief 锚点：{sell_anchor}）" if sell_anchor else ""),
            },
            "_score": total,
        })

    scored.sort(key=lambda x: -x["_score"])
    for item in scored:
        del item["_score"]
    return scored[:6]


def _sanitize(obj):
    """Strip control chars that break inline JS strings (and re.sub repl escapes)."""
    if isinstance(obj, str):
        return re.sub(r"[\r\n\t]+", " ", obj).strip()
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj


def patch_html(data: dict, window_label: str, brand_count: int | None = None):
    html = HTML.read_text(encoding="utf-8")
    blob = json.dumps(_sanitize(data), ensure_ascii=False, separators=(",", ":"))
    copy = format_report_copy(brand_count=brand_count or len(BRAND_CANONICAL))
    html = re.sub(
        r"const DATA = \{.*?\};",
        lambda _m: f"const DATA = {blob};",
        html,
        count=1,
        flags=re.S,
    )
    html = re.sub(
        r'(<div class="sub">)[^<]+(</div>)',
        rf"\g<1>{window_label} · 近 30 天\g<2>",
        html,
        count=1,
    )
    if copy.get("html_title"):
        html = re.sub(r"<title>[^<]+</title>", f"<title>{copy['html_title']}</title>", html, count=1)
    if copy.get("nav_title"):
        html = re.sub(
            r'(<aside class="sidebar">.*?<h2>)[^<]+(</h2>)',
            rf"\g<1>{copy['nav_title']}\g<2>",
            html,
            count=1,
            flags=re.S,
        )
    if copy.get("kicker"):
        html = re.sub(
            r'(<div class="kicker">)[^<]+(</div>)',
            rf"\g<1>{copy['kicker']}\g<2>",
            html,
            count=1,
        )
    if copy.get("h1_line1") and copy.get("h1_sub"):
        html = re.sub(
            r'(<h1>)[^<]+(<br><span style="font-size:22px[^"]*">)[^<]+(</span></h1>)',
            rf"\g<1>{copy['h1_line1']}\g<2>{copy['h1_sub']}\g<3>",
            html,
            count=1,
        )
    if copy.get("lead"):
        html = re.sub(
            r'(<p class="lead" id="docLead">)[^<]+(</p>)',
            rf"\g<1>{copy['lead']}\g<2>",
            html,
            count=1,
        )
    HTML.write_text(html, encoding="utf-8")


def main():
    xhs_raw = json.loads(XHS.read_text(encoding="utf-8"))
    dy_raw = json.loads(DY.read_text(encoding="utf-8"))
    dy_by_id, dy_by_title = _load_dy_commerce_maps()

    # 刷新抖音品牌代表片：从 pulse raw 全量搜索取真 max，避免 top30 合并池低估
    pulse_raw = _find_latest_pulse_raw() if callable(_find_latest_pulse_raw) else None
    if rebuild_dy_brands and pulse_raw:
        pulse_dir = pulse_raw.parent
        brand_pulse_path = pulse_dir / f"analysis_{dy_raw.get('_meta', {}).get('date', '')}.json"
        if not brand_pulse_path.exists():
            cands = sorted(pulse_dir.glob("analysis*.json"), reverse=True)
            brand_pulse_path = next((p for p in cands if "category" not in p.name), cands[0] if cands else None)
        if brand_pulse_path and brand_pulse_path.exists():
            brand_pulse = json.loads(brand_pulse_path.read_text(encoding="utf-8"))
            names = [b["brand"] for b in dy_raw.get("brands") or []] or list(BRAND_CANONICAL)
            names = [b for b in names if b in BRAND_CANONICAL]
            if not names:
                names = list(BRAND_CANONICAL)
            dy_raw["brands"] = rebuild_dy_brands(brand_pulse, names, pulse_raw)
    if sanitize_dy_brand_rows:
        dy_raw["brands"] = sanitize_dy_brand_rows(dy_raw.get("brands") or [])
    if refresh_dy_brand_markdown:
        insights, summary = refresh_dy_brand_markdown(
            dy_raw.get("brands") or [], dy_raw.get("brand_insights")
        )
        dy_raw["brand_insights"] = insights
        dy_raw["competitor_summary"] = summary
    xhs_by_title = {}
    merged_raw = {}
    if XHS_RAW.exists():
        merged_raw = json.loads(XHS_RAW.read_text(encoding="utf-8"))
        for n in merged_raw.get("notes") or []:
            if n.get("commerce") and n.get("title"):
                xhs_by_title[_title_key(n["title"])] = n["commerce"]

    xhs_block = build_xhs(xhs_raw)
    if merged_raw.get("brand_pool") or merged_raw.get("notes"):
        xhs_brands = build_xhs_brands_from_raw(merged_raw, xhs_by_title)
        if xhs_brands:
            xhs_block["BRANDS"] = xhs_brands
    else:
        xhs_brands = xhs_block.get("BRANDS") or []

    dy_trend, dy_hall = build_dy_dual_pools(dy_raw, dy_by_title)
    end_dt = _window_end_dt((dy_raw.get("_meta") or {}) or (xhs_raw.get("_meta") or {}))
    xhs_scored = _score_xhs_notes(_load_xhs_pool(xhs_raw), xhs_raw)
    trend_signals = build_trend_signals(
        xhs_scored,
        xhs_block.get("TREND_RANKS") or [],
        xhs_block.get("HALL_RANKS") or [],
        dy_trend,
        dy_hall,
        end_dt,
    )
    directions = build_monthly_directions(xhs_raw, dy_raw)
    competitor_actions = build_competitor_actions(
        xhs_block.get("BRANDS") or [],
        dy_raw.get("brands") or [],
        dy_by_title,
        xhs_by_title,
        dy_by_id,
    )
    own_brand_voice = build_own_brand_voice(competitor_actions)
    opportunity_matrix = build_opportunity_matrix(
        directions, competitor_actions, trend_signals
    )
    scene_links = (
        build_scene_links(trend_signals, competitor_actions, opportunity_matrix, _DIRECTION_PLAYBOOK)
        if build_scene_links else []
    )
    follow_candidates = (
        build_follow_candidates(
            xhs_block.get("TREND_RANKS") or [],
            xhs_block.get("HALL_RANKS") or [],
            dy_trend,
            dy_hall,
            scene_links,
        )
        if build_follow_candidates else []
    )
    commerce_summary = {
        "xhs": summarize_commerce(
            [r for r in (xhs_block.get("TREND_RANKS") or []) + (xhs_block.get("HALL_RANKS") or [])]
        ),
        "dy": summarize_commerce(
            [r for r in dy_trend + dy_hall]
        ),
    }
    overview = build_overview(
        xhs_raw, dy_raw, xhs_block, dy_trend, dy_hall, trend_signals,
        competitor_actions, opportunity_matrix, own_brand_voice,
        commerce_summary,
    )
    dy_out = {**dy_raw, "TREND_RANKS": dy_trend, "HALL_RANKS": dy_hall}
    data = {
        "xhs": xhs_block,
        "dy": dy_out,
        "overview": overview,
        "competitor_actions": competitor_actions,
        "opportunity_matrix": opportunity_matrix,
        "scene_links": scene_links,
        "follow_candidates": follow_candidates,
        "own_brand_voice": own_brand_voice,
        "directions": directions,
    }
    window = (dy_raw.get("_meta") or {}).get("window_label", "")
    patch_html(data, window, len(BRAND_CANONICAL))
    print(
        f"✓ {HTML}  (window={window}, "
        f"competitors={len(competitor_actions)}, "
        f"opportunities={len(opportunity_matrix)}, "
        f"scene_links={len(scene_links)}, "
        f"follow={len(follow_candidates)}, "
        f"own_brand={own_brand_voice.get('status')}, "
        f"xhs_cart={commerce_summary['xhs'].get('挂品挂车', 0)}, "
        f"dy_cart={commerce_summary['dy'].get('挂品挂车', 0)})"
    )


if __name__ == "__main__":
    main()
