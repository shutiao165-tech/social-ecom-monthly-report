#!/usr/bin/env python3
"""Enrich XHS merged_raw + DY pulse details with commerce signals (TikHub)."""
from __future__ import annotations

import json
import re
import subprocess
import time
import urllib.parse
from pathlib import Path

from commerce_detect import (
    merge_commerce_record,
    parse_dy_video_detail,
    parse_xhs_note_info,
    summarize_commerce,
)

ROOT = Path(__file__).resolve().parent.parent
XHS_RAW = ROOT / "data" / "xhs-monthly" / "merged_raw.json"
DY_ANALYSIS = ROOT / "data" / "douyin-monthly" / "analysis.json"
DY_CACHE = ROOT / "data" / "douyin-monthly" / "commerce_cache.json"
API = "https://api.tikhub.io"
PULSE_GLOB = Path.home() / ".claude/skills/social-ecom-decoder/output"


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
        raise RuntimeError(f"TikHub error: {data.get('message_zh') or data.get('message') or data}")
    return data


def fetch_xhs_commerce(note_id: str) -> dict:
    data = _api_get("/api/v1/xiaohongshu/app/get_note_info", {"note_id": note_id})
    return parse_xhs_note_info(data)


def fetch_dy_commerce(aweme_id: str) -> dict:
    data = _api_get("/api/v1/douyin/web/fetch_one_video", {"aweme_id": aweme_id})
    return parse_dy_video_detail(data)


def _title_key(title: str) -> str:
    return re.sub(r"\s+", "", (title or ""))[:48]


def _xhs_commerce_targets(raw: dict, top_n: int = 30) -> list[dict]:
    """L3 商业复核：品类 TOP10 + 全局 TOP30 + 品牌池全量。"""
    category_pool = raw.get("category_pool") or []
    brand_pool = raw.get("brand_pool") or []
    platform_pool = raw.get("platform_pool") or category_pool or raw.get("notes") or []
    global_top = sorted(platform_pool, key=lambda n: n.get("likes", 0), reverse=True)[:top_n]

    by_id: dict[str, dict] = {}
    for n in sorted(category_pool, key=lambda x: x.get("likes", 0), reverse=True)[:10]:
        fid = n.get("feed_id")
        if fid:
            by_id[fid] = n
    for n in global_top:
        fid = n.get("feed_id")
        if fid:
            by_id[fid] = n
    for n in brand_pool:
        fid = n.get("feed_id")
        if fid:
            by_id[fid] = n
    return list(by_id.values())


def enrich_xhs(top_n: int = 30) -> dict:
    if not XHS_RAW.exists():
        raise SystemExit(f"Missing {XHS_RAW}")
    raw = json.loads(XHS_RAW.read_text(encoding="utf-8"))
    targets = _xhs_commerce_targets(raw, top_n=top_n)
    errors = []
    enriched = 0

    print(f"== XHS commerce enrich {len(targets)} targets (cat10+top{top_n}+brand) ==", flush=True)
    for i, n in enumerate(targets, 1):
        fid = n.get("feed_id")
        if not fid:
            continue
        if n.get("commerce") and n["commerce"].get("commerce_type"):
            enriched += 1
            continue
        try:
            hard = fetch_xhs_commerce(fid)
            n["commerce"] = merge_commerce_record(
                "xhs", hard, n.get("title", ""), n.get("top_comments") or []
            )
            enriched += 1
            if i % 10 == 0:
                print(f"  · {i}/{len(targets)}", flush=True)
            time.sleep(0.35)
        except Exception as e:
            errors.append(f"{fid}: {e}")
            n["commerce"] = merge_commerce_record("xhs", {}, n.get("title", ""), n.get("top_comments") or [])

    raw["_meta"]["commerce_enriched"] = enriched
    raw["_meta"]["commerce_errors"] = errors
    raw["_meta"]["commerce_schema"] = "dual-pool-c"
    XHS_RAW.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    stats = summarize_commerce([n.get("commerce", {}) for n in targets if n.get("commerce")])
    print(f"✓ XHS {enriched}/{len(targets)} | 挂品 {stats['挂品挂车']} · 合作 {stats['品牌合作']}", flush=True)
    return stats


def _find_pulse_details() -> Path | None:
    if not PULSE_GLOB.exists():
        return None
    candidates = sorted(PULSE_GLOB.glob("*/douyin-pulse/raw/details.json"), reverse=True)
    return candidates[0] if candidates else None


def _load_dy_cache() -> dict:
    if not DY_CACHE.exists():
        return {"by_aweme_id": {}, "by_title_key": {}}
    payload = json.loads(DY_CACHE.read_text(encoding="utf-8"))
    return payload


def enrich_douyin_from_pulse() -> dict:
    details_path = _find_pulse_details()
    if not details_path:
        raise SystemExit("No douyin-pulse details.json found under social-ecom-decoder/output")

    details = json.loads(details_path.read_text(encoding="utf-8"))
    by_id: dict[str, dict] = {}
    by_title: dict[str, dict] = {}

    print(f"== DY commerce from {details_path.parent.parent.name} ({len(details)} videos) ==", flush=True)
    for aweme_id, resp in details.items():
        if not isinstance(resp, dict):
            continue
        detail = ((resp.get("data") or {}).get("aweme_detail") or {})
        title = detail.get("desc") or ""
        hard = parse_dy_video_detail(resp)
        record = merge_commerce_record("dy", hard, title)
        record["aweme_id"] = aweme_id
        record["title"] = title[:120]
        by_id[aweme_id] = record
        by_title[_title_key(title)] = record

    DY_CACHE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "_meta": {
            "source": str(details_path),
            "count": len(by_id),
        },
        "by_aweme_id": by_id,
        "by_title_key": by_title,
    }
    DY_CACHE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    stats = summarize_commerce(list(by_id.values()))
    print(f"✓ DY cache → {DY_CACHE} | 挂车 {stats['挂品挂车']} · 露出 {stats['品牌露出']}", flush=True)
    return stats


def enrich_dy_category_top(top_n: int = 10) -> dict:
    """品类池 TOP10 补拉 fetch_one_video（不在 pulse details 时）。"""
    if not DY_ANALYSIS.exists():
        raise SystemExit(f"Missing {DY_ANALYSIS}")

    analysis = json.loads(DY_ANALYSIS.read_text(encoding="utf-8"))
    cache = _load_dy_cache()
    by_id = dict(cache.get("by_aweme_id") or {})
    by_title = dict(cache.get("by_title_key") or {})
    targets = (analysis.get("category_top") or [])[:top_n]
    errors = []
    fetched = 0

    print(f"== DY category TOP{top_n} commerce补拉 ==", flush=True)
    for i, v in enumerate(targets, 1):
        aid = str(v.get("aweme_id") or "")
        title = v.get("title") or ""
        tk = _title_key(title)
        if aid and aid in by_id:
            continue
        if tk and tk in by_title:
            continue
        if not aid:
            errors.append(f"no aweme_id: {title[:40]}")
            continue
        try:
            hard = fetch_dy_commerce(aid)
            record = merge_commerce_record("dy", hard, title)
            record["aweme_id"] = aid
            record["title"] = title[:120]
            by_id[aid] = record
            by_title[tk] = record
            fetched += 1
            if i % 3 == 0:
                print(f"  · {i}/{len(targets)}", flush=True)
            time.sleep(0.4)
        except Exception as e:
            errors.append(f"{aid}: {e}")

    payload = {
        "_meta": {
            **(cache.get("_meta") or {}),
            "category_top_fetched": fetched,
            "category_errors": errors,
        },
        "by_aweme_id": by_id,
        "by_title_key": by_title,
    }
    DY_CACHE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    stats = summarize_commerce(list(by_id.values()))
    print(f"✓ DY category +{fetched} | cache {len(by_id)} | 挂车 {stats['挂品挂车']}", flush=True)
    return stats


def main():
    import argparse

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--xhs-top", type=int, default=30, help="XHS global top N in commerce batch")
    p.add_argument("--dy-cat-top", type=int, default=10, help="DY category top N to API-fetch")
    p.add_argument("--skip-xhs", action="store_true")
    p.add_argument("--skip-dy", action="store_true")
    p.add_argument("--skip-dy-cat", action="store_true")
    args = p.parse_args()

    if not args.skip_xhs:
        enrich_xhs(args.xhs_top)
    if not args.skip_dy:
        enrich_douyin_from_pulse()
    if not args.skip_dy_cat:
        enrich_dy_category_top(args.dy_cat_top)


if __name__ == "__main__":
    main()
