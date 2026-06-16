#!/usr/bin/env python3
"""Merge category + brand douyin-pulse analysis → data/douyin-monthly/analysis.json."""
import json
import re
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "douyin-monthly" / "analysis.json"

PER_BRAND_TOP = 5
CATEGORY_TOP_N = 30

# 品牌词搜索文件名 → 归属品牌（与 brand_config 同步）
from brand_config import BRAND_CANONICAL, BRAND_SEARCH_KEYWORDS as _BC_KWS  # noqa: E402
from env_paths import REPORT_AUTHORS  # noqa: E402

BRAND_SEARCH_STEMS: dict[str, list[str]] = _BC_KWS

CAT_RULES = [
    ("除湿除霉", ["除湿", "梅雨", "潮湿"]),
    ("厨房清洁", ["厨房", "油污", "油污净"]),
    ("除甲醛", ["甲醛", "装修"]),
    ("卫生间清洁", ["马桶", "洁厕", "卫生间"]),
    ("清洁妙招", ["清洁", "小技巧", "妙招", "0成本"]),
    ("除味香氛", ["香薰", "香氛", "除味", "异味"]),
    ("知识科普", ["化学", "实验", "科普"]),
]


def _fmt(n: int) -> str:
    if n >= 10000:
        return f"{n/10000:.1f}万".replace(".0万", "万")
    return f"{n:,}"


def _classify_cat(title: str) -> str:
    for cat, kws in CAT_RULES:
        if any(k in title for k in kws):
            return cat
    return "其他"


def _window_label(days: int = 30) -> str:
    tz = timezone(timedelta(hours=8))
    end = datetime.now(tz).date()
    start = end - timedelta(days=days - 1)
    return f"{start.strftime('%m.%d')} – {end.strftime('%m.%d')}"


def _clean(s: str) -> str:
    return re.sub(r"[\r\n\t]+", " ", s or "").strip()


def _meta_to_row(rank: int, m: dict) -> dict:
    dur_ms = m.get("duration_ms") or 0
    dur_s = round(dur_ms / 1000, 1) if dur_ms else 0
    title = _clean(m.get("desc") or "")[:80]
    return {
        "rank": rank,
        "title": title,
        "likes": m.get("digg_count", 0),
        "comments": m.get("comment_count", 0),
        "shares": m.get("share_count", 0),
        "duration": f"{dur_s}s",
        "author": m.get("author_nickname", ""),
        "fans": m.get("author_follower_count", 0),
        "hook": m.get("hook_type", "其他"),
        "playable_score": m.get("playable_score", 0),
        "category": _classify_cat(title),
        "aweme_id": str(m.get("aweme_id") or ""),
    }


def _pain_flat(pain_buckets: dict, limit: int = 8) -> list:
    rows = []
    for bucket, quotes in pain_buckets.items():
        for q in quotes[:2]:
            rows.append({
                "bucket": bucket,
                "text": f"「{q['text']}」 — {q.get('ip', '?')} · {q.get('likes', 0)} 赞",
            })
    rows.sort(key=lambda x: int(re.search(r"(\d+)\s*赞", x["text"]).group(1)) if re.search(r"(\d+)\s*赞", x["text"]) else 0, reverse=True)
    return rows[:limit]


def _extract_videos_from_search(resp: dict) -> list:
    """Parse TikHub v1/v2 search JSON into flat video dicts."""
    outer = resp.get("data", {}) or {}
    if isinstance(outer, dict) and "business_data" in outer:
        items = outer.get("business_data") or []
    else:
        inner = outer.get("data", outer) if isinstance(outer, dict) else outer
        if isinstance(inner, list):
            items = inner
        elif isinstance(inner, dict):
            items = inner.get("aweme_list") or inner.get("data") or []
        else:
            items = []
    videos = []
    for item in items:
        if not isinstance(item, dict):
            continue
        info = item.get("aweme_info") or (item.get("data") or {}).get("aweme_info") or item
        if not isinstance(info, dict):
            continue
        stats = info.get("statistics") or {}
        author = info.get("author") or {}
        dur = (info.get("video") or {}).get("duration") or info.get("duration") or 0
        videos.append({
            "desc": info.get("desc") or "",
            "digg_count": int(stats.get("digg_count") or info.get("digg_count") or 0),
            "duration_ms": int(dur) if dur else 0,
            "author_nickname": author.get("nickname") or "",
            "author_follower_count": int(author.get("follower_count") or 0),
            "aweme_id": str(info.get("aweme_id") or ""),
        })
    return videos


def _video_chip(v: dict, rank: int) -> dict:
    dur = round((v.get("duration_ms") or 0) / 1000, 1)
    likes = int(v.get("digg_count") or 0)
    return {
        "rank": rank,
        "title": _clean(v.get("desc") or "")[:80],
        "likes": likes,
        "likes_label": _fmt(likes),
        "aweme_id": v.get("aweme_id", ""),
        "duration": f"{dur}s" if dur else "—",
        "fans": _fmt(v.get("author_follower_count", 0)),
    }


def _brand_insights_from_rows(brands_rows: list[dict]) -> list[str]:
    """从合并后的品牌代表片生成洞察行（不沿用 pulse 旧 competitor_summary）。"""
    lines: list[str] = []
    for b in brands_rows:
        name = b["brand"]
        tc = str(b.get("tag_count") or "0")
        n = tc.split("→")[0] if "→" in tc else tc
        reps = b.get("top_videos") or []
        if not reps:
            lines.append(f"- **{name}**：本月样本无挂 tag 爆款（声量弱或走剧情号/非家清分发）")
            continue
        top = reps[0]
        title = (top.get("title") or b.get("top_title") or "")[:60]
        likes = top.get("likes", b.get("top_likes_n", 0))
        dur = top.get("duration") or b.get("duration") or "—"
        lines.append(f"- **{name}**（{n} 条挂 tag）代表片：{likes}赞 · {dur} · 「{title}」")
    return lines


def _scrub_removed_brands(lines: list) -> list:
    """过滤已下架监测品牌（如大公鸡）的 markdown 行。"""
    allowed = set(BRAND_CANONICAL)
    out: list = []
    for line in lines:
        s = line if isinstance(line, str) else str(line)
        mentioned = re.findall(r"\*\*([^*]+)\*\*", s)
        if mentioned and not any(m.split("（")[0].strip() in allowed for m in mentioned):
            continue
        if "大公鸡" in s:
            continue
        out.append(line if isinstance(line, str) else s)
    return out


def _brand_row_from_hit(brand: str, hits: list, per_top: int = PER_BRAND_TOP) -> dict:
    sorted_hits = sorted(hits, key=lambda x: x.get("digg_count", 0), reverse=True)
    top_videos = [_video_chip(v, i + 1) for i, v in enumerate(sorted_hits[:per_top])]
    best = sorted_hits[0] if sorted_hits else {}
    dur = round((best.get("duration_ms") or 0) / 1000, 1)
    likes = int(best.get("digg_count") or 0)
    return {
        "brand": brand,
        "tag_count": f"{len(hits)}→{min(len(hits), per_top)}",
        "top_title": _clean(best.get("desc") or "")[:80],
        "top_likes": _fmt(likes),
        "top_likes_n": likes,
        "aweme_id": best.get("aweme_id", ""),
        "duration": f"{dur}s" if dur else "—",
        "fans": _fmt(best.get("author_follower_count", 0)),
        "data_scope": "品牌词搜索·标题含品牌名",
        "top_videos": top_videos,
    }


def _brands_from_raw_searches(
    raw_dir: Path | None,
    brand_names: list,
    extra_dirs: list[Path] | None = None,
) -> dict[str, list]:
    """Scan search_*.json — desc 含品牌名；合并近几批 pulse raw 避免单次跑数缺文件。"""
    dirs: list[Path] = []
    if raw_dir and raw_dir.exists():
        dirs.append(raw_dir)
    for d in extra_dirs or []:
        if d.exists() and d not in dirs:
            dirs.append(d)
    if not dirs:
        return {b: [] for b in brand_names}

    by_brand: dict[str, list] = {b: [] for b in brand_names}
    seen: set[str] = set()

    def _brand_for_video(stem: str, desc: str) -> str | None:
        for b in brand_names:
            if b in desc:
                return b
        for b in brand_names:
            stems = BRAND_SEARCH_STEMS.get(b, [b])
            if any(s in stem for s in stems) and b in desc:
                return b
        return None

    for raw in dirs:
        for path in raw.glob("search_*.json"):
            stem = path.stem.replace("search_", "")
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            for v in _extract_videos_from_search(payload):
                aid = v.get("aweme_id") or v.get("desc", "")[:40]
                if aid in seen:
                    continue
                desc = v.get("desc") or ""
                brand = _brand_for_video(stem, desc)
                if not brand:
                    continue
                seen.add(aid)
                by_brand[brand].append(v)
    return by_brand


def _pulse_raw_dirs(limit: int = 4) -> list[Path]:
    root = Path.home() / ".claude/skills/social-ecom-decoder/output"
    if not root.exists():
        return []
    return sorted(root.glob("*/douyin-pulse/raw"), reverse=True)[:limit]


def rebuild_dy_brands(brand_analysis: dict, brand_names: list, raw_dir: Path | None = None) -> list:
    """Best brand-tagged video per brand: max(top30 merge, all raw searches)."""
    pulse_hits: dict[str, list] = {b: [] for b in brand_names}
    for m in brand_analysis.get("top30") or []:
        desc = m.get("desc") or ""
        for b in brand_names:
            if b in desc:
                pulse_hits[b].append(m)
                break

    pulse_dirs = _pulse_raw_dirs()
    primary = raw_dir if raw_dir and raw_dir.exists() else (pulse_dirs[0] if pulse_dirs else None)
    extra = [d for d in pulse_dirs if d != primary]
    raw_hits = _brands_from_raw_searches(primary, brand_names, extra_dirs=extra)

    rows = []
    for b in brand_names:
        merged = {v.get("aweme_id") or v.get("desc", "")[:48]: v for v in pulse_hits[b]}
        for v in raw_hits.get(b, []):
            key = v.get("aweme_id") or v.get("desc", "")[:48]
            old = merged.get(key)
            if not old or v.get("digg_count", 0) > old.get("digg_count", 0):
                merged[key] = v
        hits = list(merged.values())
        if hits:
            rows.append(_brand_row_from_hit(b, hits))
        else:
            rows.append({
                "brand": b,
                "tag_count": "0→0",
                "top_title": f"（本批样本：标题/描述未出现「{b}」）",
                "top_likes": "—",
                "top_likes_n": 0,
                "duration": "—",
                "fans": "—",
                "data_scope": "品牌词搜索·标题/描述须含品牌名（已过滤搜索噪声）",
            })
    return rows


def _brands_from_pulse(brand_analysis: dict, brand_names: list) -> list:
    raw_dir = _find_latest_pulse_raw()
    return rebuild_dy_brands(brand_analysis, brand_names, raw_dir)


def _find_latest_pulse_raw() -> Path | None:
    root = Path.home() / ".claude/skills/social-ecom-decoder/output"
    if not root.exists():
        return None
    cands = sorted(root.glob("*/douyin-pulse/raw"), reverse=True)
    return cands[0] if cands else None


def _recommend_duration(dist: dict) -> str:
    if not dist:
        return "35-60s"
    best = max(dist.items(), key=lambda x: x[1])[0]
    return best if best != "未知" else "35-60s"


def merge(category_path: Path, brand_path: Path) -> dict:
    cat = json.loads(category_path.read_text(encoding="utf-8"))
    brand = json.loads(brand_path.read_text(encoding="utf-8"))
    days = cat.get("meta", {}).get("window_days", 30)
    window = _window_label(days)
    date = cat.get("meta", {}).get("date", datetime.now().strftime("%Y-%m-%d"))

    top = sorted(cat.get("top30") or [], key=lambda m: m.get("digg_count", 0), reverse=True)
    category_top = [_meta_to_row(i + 1, m) for i, m in enumerate(top[:CATEGORY_TOP_N])]

    hook_dist = {}
    for v in category_top:
        hook_dist[v["hook"]] = hook_dist.get(v["hook"], 0) + 1

    ss = cat.get("script_stats") or {}
    dur_dist = ss.get("duration_distribution") or {}
    brand_names = brand.get("meta", {}).get("keywords") or list(BRAND_CANONICAL)
    brand_names = [b for b in brand_names if b in BRAND_CANONICAL]
    if not brand_names:
        brand_names = list(BRAND_CANONICAL)
    # normalize brand list from --brands if stored differently
    if brand.get("meta", {}).get("niche", "").find("品牌") >= 0:
        pass
    brands_list = list(BRAND_CANONICAL)

    likes_list = sorted([v["likes"] for v in category_top])
    cat_dist = {}
    for v in category_top:
        cat_dist[v["category"]] = cat_dist.get(v["category"], 0) + 1

    competitor = _scrub_removed_brands(
        brand.get("competitor_summary") or cat.get("competitor_summary") or []
    )
    demand = cat.get("demand_insights") or {}
    brands_data = _brands_from_pulse(brand, brands_list)
    brand_insights = _brand_insights_from_rows(brands_data)
    for line in (demand.get("video_directions") or [])[:2]:
        brand_insights.append(f"[视频向] {line}")
    for line in (demand.get("product_directions") or [])[:1]:
        brand_insights.append(f"[产品向] {line}")

    return {
        "_meta": {
            "platform": "douyin",
            "report_type": "monthly",
            "date": date,
            "window_label": window,
            "window_days": days,
            "doc_url": cat.get("meta", {}).get("doc_url", ""),
            "schema": "dual-pool-c",
            "category_sample": len(category_top),
            "brand_sample": len(brands_list),
            "authors": REPORT_AUTHORS,
        },
        "category_top": category_top,
        "hook_distribution": hook_dist,
        "script_stats": {
            "median_shots": ss.get("median_shots", 0),
            "median_duration_s": ss.get("median_duration_s", 0),
            "duration_distribution": dur_dist,
            "recommended_duration": _recommend_duration(dur_dist),
        },
        "pain_quotes": _pain_flat(cat.get("pain_buckets") or {}),
        "brands": brands_data,
        "brand_insights": brand_insights[:6],
        "stats": {
            "max_likes": max(likes_list) if likes_list else 0,
            "median_likes": likes_list[len(likes_list) // 2] if likes_list else 0,
            "mean_likes": int(statistics.mean(likes_list)) if likes_list else 0,
            "category_distribution": cat_dist,
        },
        "demand_insights": demand,
        "competitor_summary": competitor,
    }


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--category", required=True, help="category pulse analysis json")
    p.add_argument("--brand", required=True, help="brand pulse analysis json")
    args = p.parse_args()
    data = merge(Path(args.category), Path(args.brand))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ {OUT} ({data['_meta']['category_sample']} cat + {len(data['brands'])} brands)")


if __name__ == "__main__":
    main()
