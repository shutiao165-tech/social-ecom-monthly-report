#!/usr/bin/env python3
"""Fetch XHS monthly data via TikHub API (faster than browser MCP)."""
import json
import subprocess
import sys
import time
import urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path

from env_paths import DECODER_ROOT

SKILL_ROOT = DECODER_ROOT
sys.path.insert(0, str(SKILL_ROOT))

from shared.lib import analyze  # noqa: E402
from commerce_detect import merge_commerce_record, parse_xhs_note_info  # noqa: E402
from brand_config import xhs_brand_keywords_flat  # noqa: E402

CATEGORY_KEYWORDS = [
    "除湿袋", "空气清新剂", "除甲醛", "冰箱除味剂", "厕所香薰", "除湿盒",
    "消毒喷雾", "冰箱清洁剂", "鞋柜除臭神器", "洗洁精", "空调清洗剂",
    "洁厕灵", "洗衣机清洗剂", "马桶清洁剂", "管道疏通剂", "地板清洁剂",
    "下水道强力疏通剂", "油污净", "洁厕宝",
]
BRAND_KEYWORDS = xhs_brand_keywords_flat()
KEYWORDS = list(dict.fromkeys(CATEGORY_KEYWORDS + BRAND_KEYWORDS))

JIAQING_CATEGORIES = [
    ("好物推荐", ["好物", "爱用", "推荐", "清单", "种草", "年度", "补货", "同款", "分享"]),
    ("卫生间清洁", ["马桶", "洁厕", "厕所", "浴室", "卫生间", "淋浴", "挂厕", "洁厕宝", "洁厕灵"]),
    ("厨房清洁", ["厨房", "油污", "灶台", "冰箱", "抽油烟", "油污净"]),
    ("除味香氛", ["香薰", "除臭", "除味", "香氛", "留香", "空气清新", "鞋柜"]),
    ("洗衣液", ["洗衣", "洗衣液", "凝珠", "威露士", "清洗剂"]),
    ("清洁妙招", ["妙招", "一招", "别买", "省钱", "碱", "白醋", "听劝"]),
    ("管道疏通", ["疏通", "下水道", "管道", "堵塞"]),
    ("除湿除霉", ["除湿", "霉", "回南", "潮湿", "除湿袋", "除湿盒"]),
    ("品牌竞品", ["网易严选", "沫檬", "老管家", "滴露", "椰放", "蔬果园", "水卫士", "晴天大白", "papi", "维嘉"]),
]

JIAQING_PAIN_BUCKETS = [
    ("异味困扰", ["臭", "味", "气味", "霉味", "汗味", "下水道", "回潮", "潮", "刺鼻"]),
    ("清洁残留", ["残留", "划痕", "擦不掉", "刷不干净", "漂不干净", "残胶", "痕迹"]),
    ("操作麻烦", ["麻烦", "费力", "费劲", "懒得", "懒人", "手动", "搓", "刷"]),
    ("效果质疑", ["有用", "鸡肋", "智商税", "效果", "立竿见影", "没效果", "踩雷"]),
    ("安全顾虑", ["刺激", "化学", "致癌", "母婴", "孩子", "宝宝", "孕", "有害"]),
    ("价格敏感", ["贵", "便宜", "性价比", "白买", "肉疼", "链接", "多少钱"]),
    ("香味偏好", ["香", "味道", "留香", "好闻", "难闻", "呛"]),
    ("求购链接", ["链接", "求购", "哪里买", "姐妹", "同款", "蹲"]),
]

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "xhs-monthly"
WINDOW_DAYS = 30
TOP_N = 30
CATEGORY_TOP_PER_KW = 30
BRAND_TOP_PER_KW = 10
API = "https://api.tikhub.io"


def _key() -> str:
    return (Path.home() / ".config/tikhub/key").read_text().strip()


def _api_get(path: str, params: dict) -> dict:
    qs = urllib.parse.urlencode(params)
    url = f"{API}{path}?{qs}"
    proc = subprocess.run(
        ["curl", "-sS", "-H", f"Authorization: Bearer {_key()}", url],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"curl exit {proc.returncode}")
    data = json.loads(proc.stdout)
    if data.get("code") != 200:
        raise RuntimeError(f"TikHub error: {data.get('message', data)}")
    return data


def _today_cst() -> str:
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")


def _window_ms(days: int = WINDOW_DAYS):
    tz = timezone(timedelta(hours=8))
    end = datetime.now(tz).replace(hour=23, minute=59, second=59, microsecond=999999)
    start = (end - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    label = f"{start.strftime('%m.%d')} – {end.strftime('%m.%d')}"
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000), label


def search_notes(keyword: str, page: int = 1) -> list:
    data = _api_get(
        "/api/v1/xiaohongshu/app/search_notes",
        {
            "keyword": keyword,
            "page": page,
            "sort_type": "popularity_descending",
            "filter_note_time": "半年内",
        },
    )
    inner = data.get("data", {})
    if isinstance(inner, dict) and "data" in inner:
        inner = inner["data"]
    return inner.get("items") or []


def search_notes_top(keyword: str, target: int = CATEGORY_TOP_PER_KW) -> list:
    """Paginate category keyword search until ~target notes or empty page."""
    out: list = []
    seen: set[str] = set()
    for page in range(1, 8):
        batch = search_notes(keyword, page=page)
        if not batch:
            break
        for item in batch:
            n = item.get("note") or item
            fid = n.get("id", "")
            if fid and fid not in seen:
                seen.add(fid)
                out.append(item)
        if len(out) >= target:
            break
        time.sleep(0.3)
    return out[:target]


def fetch_note_commerce(note_id: str) -> dict:
    """Commerce flags via note detail API."""
    try:
        data = _api_get("/api/v1/xiaohongshu/app/get_note_info", {"note_id": note_id})
        return parse_xhs_note_info(data)
    except Exception:
        return {}


def parse_note(item: dict, keyword: str) -> dict:
    n = item.get("note") or item
    user = n.get("user") or {}
    fid = n.get("id", "")
    ts = n.get("update_time") or n.get("last_update_time")
    note_type = "video" if n.get("type") == "video" else "normal"
    return {
        "feed_id": fid,
        "title": n.get("title") or n.get("desc") or "",
        "note_type": note_type,
        "likes": int(n.get("liked_count") or 0),
        "collects": int(n.get("collected_count") or 0),
        "comments_count": int(n.get("comments_count") or 0),
        "shares": int(n.get("shared_count") or 0),
        "author_id": user.get("user_id") or user.get("userid") or "",
        "author_nickname": user.get("nickname") or user.get("name") or "",
        "follower_count": int(user.get("fans") or user.get("fans_count") or 0),
        "publish_ts": ts,
        "url": f"https://www.xiaohongshu.com/explore/{fid}",
        "keywords_matched": [keyword],
        "keyword_pools": [],
        "content_excerpt": (n.get("desc") or n.get("title") or "")[:500],
        "top_comments": [],
        "xsec_token": item.get("xsec_token") or n.get("xsec_token") or "",
    }


def fetch_note_comments(note_id: str, share_text: str) -> list:
    """Top comments via TikHub app_v2 (paid)."""
    try:
        data = _api_get(
            "/api/v1/xiaohongshu/app_v2/get_note_comments",
            {
                "note_id": note_id,
                "share_text": share_text,
                "sort_strategy": "like_count",
            },
        )
    except Exception:
        return []
    payload = data.get("data") or {}
    if isinstance(payload, dict) and "data" in payload:
        payload = payload["data"]
    raw = []
    if isinstance(payload, dict):
        raw = payload.get("comments") or payload.get("items") or []
    elif isinstance(payload, list):
        raw = payload
    out = []
    for c in raw[:20]:
        if not isinstance(c, dict):
            continue
        text = (c.get("content") or c.get("text") or "").strip()
        if len(text) < 6:
            continue
        out.append({
            "content": text,
            "likeCount": int(c.get("like_count") or c.get("likeCount") or 0),
            "ipLocation": c.get("ip_location") or c.get("ipLocation") or "",
        })
    return out


def _merge_note(all_notes: dict, note: dict, kw: str, pool: str) -> None:
    fid = note["feed_id"]
    if pool not in note.get("keyword_pools", []):
        note.setdefault("keyword_pools", []).append(pool)
    if fid in all_notes:
        ex = all_notes[fid]
        if kw not in ex["keywords_matched"]:
            ex["keywords_matched"].append(kw)
        for p in note.get("keyword_pools", []):
            if p not in ex.setdefault("keyword_pools", []):
                ex["keyword_pools"].append(p)
        return
    all_notes[fid] = note


def _commerce_targets(category_pool: list, brand_pool: list, global_top: list) -> list:
    """L3 商业复核：品类 TOP10 + 全局 TOP30 + 品牌池全量代表。"""
    by_id: dict[str, dict] = {}
    cat_sorted = sorted(category_pool, key=lambda n: n.get("likes", 0), reverse=True)
    for n in cat_sorted[:10]:
        by_id[n["feed_id"]] = n
    for n in global_top[:TOP_N]:
        by_id[n["feed_id"]] = n
    for n in brand_pool:
        by_id[n["feed_id"]] = n
    return list(by_id.values())


def main():
    out_dir = OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    start_ms, end_ms, window_label = _window_ms()

    print(f"== XHS monthly (TikHub) {window_label} ==", flush=True)
    all_notes: dict[str, dict] = {}
    errors = []

    print(f"  [品类池] {len(CATEGORY_KEYWORDS)} 词 × 目标 {CATEGORY_TOP_PER_KW}/词", flush=True)
    for i, kw in enumerate(CATEGORY_KEYWORDS, 1):
        print(f"    [{i}/{len(CATEGORY_KEYWORDS)}] {kw}...", flush=True)
        try:
            items = search_notes_top(kw, CATEGORY_TOP_PER_KW)
            for item in items:
                note = parse_note(item, kw)
                if not note["feed_id"]:
                    continue
                _merge_note(all_notes, note, kw, "category")
            time.sleep(0.35)
        except Exception as e:
            errors.append(f"cat:{kw}: {e}")
            print(f"      ⚠ {e}", flush=True)

    print(f"  [品牌池] {len(BRAND_KEYWORDS)} 词", flush=True)
    for i, kw in enumerate(BRAND_KEYWORDS, 1):
        print(f"    [{i}/{len(BRAND_KEYWORDS)}] {kw}...", flush=True)
        try:
            items = search_notes(kw)[:BRAND_TOP_PER_KW]
            for item in items:
                note = parse_note(item, kw)
                if not note["feed_id"]:
                    continue
                _merge_note(all_notes, note, kw, "brand")
            time.sleep(0.35)
        except Exception as e:
            errors.append(f"brand:{kw}: {e}")
            print(f"      ⚠ {e}", flush=True)

    notes = list(all_notes.values())
    category_pool = [n for n in notes if "category" in n.get("keyword_pools", [])]
    brand_pool = [n for n in notes if "brand" in n.get("keyword_pools", [])]

    def in_window(n):
        ts = n.get("publish_ts")
        return ts and start_ms <= int(ts) <= end_ms

    cat_in_window = [n for n in category_pool if in_window(n)]
    cat_in_window.sort(key=lambda x: x["likes"], reverse=True)
    print(
        f"  Total: {len(notes)} | 品类池 {len(category_pool)} | 品牌池 {len(brand_pool)} | "
        f"品类30d内 {len(cat_in_window)}",
        flush=True,
    )

    platform_pool = cat_in_window if len(cat_in_window) >= TOP_N else sorted(category_pool, key=lambda x: x["likes"], reverse=True)
    platform_pool = platform_pool[: max(TOP_N * 3, 120)]

    global_top = sorted(platform_pool, key=lambda x: x["likes"], reverse=True)[:TOP_N]
    commerce_targets = _commerce_targets(category_pool, brand_pool, global_top)

    print(f"  Fetching comments + commerce for {len(commerce_targets)} targets...", flush=True)
    comment_errors = []
    for i, n in enumerate(commerce_targets, 1):
        try:
            if n in global_top[:TOP_N]:
                n["top_comments"] = fetch_note_comments(n["feed_id"], n["url"])
            elif not n.get("top_comments"):
                n["top_comments"] = []
            if not n.get("commerce"):
                hard = fetch_note_commerce(n["feed_id"])
                n["commerce"] = merge_commerce_record(
                    "xhs", hard, n.get("title", ""), n.get("top_comments") or []
                )
            if i % 10 == 0:
                print(f"    · {i}/{len(commerce_targets)}", flush=True)
            time.sleep(0.4)
        except Exception as e:
            comment_errors.append(f"{n['feed_id']}: {e}")
            n.setdefault("top_comments", [])
            n["commerce"] = merge_commerce_record("xhs", {}, n.get("title", ""), n.get("top_comments") or [])

    analysis = analyze.build_analysis(
        platform_pool,
        keywords=KEYWORDS,
        top_n=TOP_N,
        pain_buckets=JIAQING_PAIN_BUCKETS,
        categories=JIAQING_CATEGORIES,
        report_date=_today_cst(),
        fresh_window_days=WINDOW_DAYS,
        fresh_top_n=10,
    )
    analysis["_meta"]["window_label"] = window_label
    analysis["_meta"]["window_days"] = WINDOW_DAYS
    analysis["_meta"]["platform"] = "xiaohongshu"
    analysis["_meta"]["report_type"] = "monthly"
    analysis["_meta"]["data_source"] = "tikhub"
    analysis["_meta"]["schema"] = "dual-pool-c"
    analysis["_meta"]["category_keywords"] = CATEGORY_KEYWORDS
    analysis["_meta"]["brand_keywords"] = BRAND_KEYWORDS
    analysis["_meta"]["category_top_per_kw"] = CATEGORY_TOP_PER_KW
    analysis["_meta"]["errors"] = errors + comment_errors
    analysis["_meta"]["raw_total"] = len(notes)
    analysis["_meta"]["category_pool_count"] = len(category_pool)
    analysis["_meta"]["brand_pool_count"] = len(brand_pool)
    analysis["_meta"]["in_window_count"] = len(cat_in_window)

    raw_path = out_dir / "merged_raw.json"
    analysis_path = out_dir / "analysis.json"
    raw_path.write_text(json.dumps({
        "_meta": analysis["_meta"],
        "notes": notes,
        "category_pool": category_pool,
        "brand_pool": brand_pool,
        "platform_pool": platform_pool,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    analysis_path.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✓ Raw → {raw_path}", flush=True)
    print(f"✓ Analysis → {analysis_path}", flush=True)
    if analysis["top"]:
        print(f"  TOP1: {analysis['top'][0]['likes']} likes — {analysis['top'][0]['title'][:40]}", flush=True)


if __name__ == "__main__":
    main()
