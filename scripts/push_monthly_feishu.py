#!/usr/bin/env python3
"""Push 品类爆款月报 summary card to Feishu via cursor2号 bot.

Card format mirrors cursor2号 2026-06-16 push to 家清官旗冲锋队:
  title + hero img_key + 秒搭链接 + TOP1 / 升温赛道 / 竞品 / 机会矩阵 / 平台打法

Usage:
  python3 push_monthly_feishu.py --category jiaqing          # 默认私聊
  python3 push_monthly_feishu.py --project-root ... --chat-id oc_xxx  # 确认格式后推群
  python3 push_monthly_feishu.py --category pet --dry-run
  python3 push_monthly_feishu.py --category jiaqing --print-only
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2] if (SCRIPT_DIR.parents[2] / "项目").exists() else SCRIPT_DIR.parents[1]
CONFIG_PATH = SCRIPT_DIR / "feishu_push_config.json"

PROJECT_CATEGORY = {
    "家清爆款报告": "jiaqing",
    "居家爆款报告": "juju",
    "宠物爆款报告": "pet",
}


def _load_config() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _fmt_count(n: int | float) -> str:
    n = int(n or 0)
    if n >= 10000:
        s = f"{n / 10000:.1f}w"
        return s.replace(".0w", "w")
    return f"{n:,}"


def _short(text: str, limit: int = 22) -> str:
    text = re.sub(r"#\S+", "", (text or "").strip())
    text = re.sub(r"\s+", " ", text)
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


def _extract_data(html_path: Path) -> dict:
    html = html_path.read_text(encoding="utf-8")
    m = re.search(r"const DATA = (\{.*?\});", html, re.S)
    if not m:
        raise SystemExit(f"未在 {html_path} 中找到 const DATA")
    return json.loads(m.group(1))


def _window_label(overview: dict) -> str:
    w = (overview.get("window") or "").replace("（近30天）", "").strip()
    return w.replace(" – ", "–").replace(" - ", "–")


def _dy_trend_top(data: dict) -> dict:
    dy = data.get("dy") or {}
    ranks = dy.get("TREND_RANKS") or dy.get("category_top") or []
    return ranks[0] if ranks else {}


def _dy_metric_line(item: dict) -> str:
    likes = int(item.get("likes") or 0)
    shares = int(item.get("shares") or 0)
    score = item.get("trend_score")
    if likes >= 50000 or shares >= 10000:
        if shares > 0:
            return f"**{_fmt_count(likes)} · 分享 {_fmt_count(shares)}**"
        return f"**{_fmt_count(likes)}**"
    if score not in (None, "", 0):
        return f"**{_fmt_count(likes)} · 赞粉比 {score}**"
    return f"**{_fmt_count(likes)}**"


def _signal_count(evidence: str) -> str:
    m = re.search(r"近7天(?:命中)?\s*(\d+)\s*条", evidence or "")
    return m.group(1) if m else "—"


def _format_trend_line(s: dict) -> str:
    topic = (s.get("topic") or "").strip()
    evidence = s.get("evidence") or ""
    if "黑马" in topic:
        vel = re.search(r"([\d,]+/天)", evidence)
        title_m = re.match(r"《([^》]+)", evidence)
        label = title_m.group(1)[:12] if title_m else "增速黑马"
        if vel:
            return f"↑ {label}｜{vel.group(1)}"
        return f"↑ 小红书黑马｜{topic.replace('小红书增速黑马', '').strip() or label}"
    short_topic = topic.split("/")[0].strip()
    cnt = _signal_count(evidence)
    return f"↑ {short_topic}｜近7天 {cnt} 条"


def _build_competitor_block(data: dict, self_label: str) -> list[str]:
    actions = data.get("competitor_actions") or []
    active = [
        a for a in actions
        if not a.get("is_self") and a.get("status") not in ("静默", "自有")
    ]
    active.sort(key=lambda x: int(x.get("total_likes") or 0), reverse=True)

    high_threat = [a for a in active if a.get("threat") == "高"]
    header = "**⚔️ 竞品声量**"
    if active:
        if high_threat and len(high_threat) >= max(2, len(active) // 2):
            header += f"（{len(active)} 家活跃，威胁均高）"
        else:
            header += f"（{len(active)} 家活跃）"

    lines = [header]
    chunk: list[str] = []
    for a in active[:8]:
        note = ""
        ca = a.get("commerce_action") or ""
        if "剧情" in ca:
            note = "（剧情号挂车，威胁高）"
        elif "挂车" in ca:
            note = "（挂车）"
        chunk.append(f"{a['brand']} **{_fmt_count(a.get('total_likes', 0))}**{note}")
        if len(chunk) == 3:
            lines.append("> " + " · ".join(chunk))
            chunk = []
    if chunk:
        lines.append("> " + " · ".join(chunk))

    cart_names = [
        a["brand"] for a in active
        if "挂车" in (a.get("commerce_action") or "")
    ]
    if cart_names:
        lines.append("> " + " / ".join(cart_names[:5]) + " 已挂车")

    yv = data.get("yanxuan_voice") or {}
    status = yv.get("status") or "—"
    total = int(yv.get("total_likes") or 0)
    if status in ("未监测", "静默") or total <= 0:
        lines.append(f"> {self_label} **未监测到内容**，需补内容布局")
    elif total < 50000:
        lines.append(f"> {self_label} **{_fmt_count(total)}**，监测内有声偏弱")
    else:
        summary = yv.get("summary") or status
        lines.append(f"> {self_label} **{_fmt_count(total)}** · {summary}")

    return lines


def _matrix_emoji(row: dict) -> str:
    decision = row.get("decision") or ""
    arrow = row.get("arrow") or "→"
    if decision in ("加速切入", "抢先布局", "差异化跟打") or arrow == "↑":
        return "🔥"
    return "🟡"


def _matrix_suffix(row: dict) -> str:
    arrow = row.get("arrow") or "→"
    return arrow if arrow in ("↑", "→") else "→"


def _lark_md(content: str) -> dict:
    return {"tag": "div", "text": {"tag": "lark_md", "content": content}}


def _hero_img(img_key: str, alt: str) -> dict:
    return {
        "tag": "img",
        "img_key": img_key,
        "alt": {"tag": "plain_text", "content": alt[:50]},
        "mode": "fit_horizontal",
    }


def _build_body_sections(
    category_cfg: dict,
    data: dict,
    *,
    miaoda_base: str,
) -> list[str]:
    """Return markdown section blocks (no card wrapper)."""
    ov = data.get("overview") or {}
    sections: list[str] = []

    file_id = (category_cfg.get("miaoda_file_id") or "").strip()
    if file_id:
        url = f"{miaoda_base.rstrip('/')}/{file_id}"
        sections.append(f"🔗 **完整看板**：[点击打开]({url})")

    top_lines = ["**🏆 TOP1 爆款**"]
    xhs_t = ov.get("xhs_trend_top1") or {}
    xhs_h = ov.get("xhs_hall_top1") or {}
    dy_item = _dy_trend_top(data) or ov.get("dy_trend_top1") or ov.get("dy_top1") or {}
    vel = (xhs_t.get("extra") or "").split("·")[0].strip()
    if not vel and xhs_t.get("likes"):
        vel = _fmt_count(xhs_t["likes"])
    top_lines.append(
        f"📕 *小红书 增速*｜{_short(xhs_t.get('title', ''))}｜**{vel or '—'}**"
    )
    top_lines.append(
        f"📕 *小红书 殿堂*｜{_short(xhs_h.get('title', ''))}｜**{_fmt_count(xhs_h.get('likes', 0))}**"
    )
    top_lines.append(
        f"🎵 *抖音 双榜*｜{_short(dy_item.get('title', ''))}｜{_dy_metric_line(dy_item)}"
    )
    sections.append("\n".join(top_lines))

    signals = [s for s in (ov.get("trend_signals") or []) if s.get("arrow") == "↑"]
    show_signals = signals[:4]
    trend_lines = [f"**🔥 {len(show_signals) or len(signals)} 条升温赛道**"]
    for s in show_signals:
        trend_lines.append(_format_trend_line(s))
    if not show_signals and signals:
        trend_lines.append(_format_trend_line(signals[0]))
    sections.append("\n".join(trend_lines))

    sections.append(
        "\n".join(_build_competitor_block(data, category_cfg.get("self_brand_label", "自有品牌")))
    )

    matrix = (data.get("opportunity_matrix") or [])[:6]
    accel = sum(
        1 for r in matrix
        if r.get("decision") in ("加速切入", "抢先布局", "差异化跟打")
    )
    suffix = "（全部加速切入）" if accel == len(matrix) and matrix else ""
    matrix_lines = [f"**🎯 {len(matrix)} 个机会矩阵**{suffix}"]
    for row in matrix:
        topic = (row.get("topic") or row.get("scene") or "").split("/")[0].strip()
        skus = row.get("yanxuan_skus") or []
        sku_hint = f"｜{skus[0]}" if skus else ""
        matrix_lines.append(
            f"{_matrix_emoji(row)} {topic}{sku_hint} {_matrix_suffix(row)}"
        )
    sections.append("\n".join(matrix_lines))

    sections.append(
        "**📐 平台打法**\n"
        "📕 *收藏向* → 步骤/清单体\n"
        "🎵 *分享向* → 短痛点+反差，主钩子数字钩"
    )
    return sections


def build_interactive_card(
    category_cfg: dict,
    data: dict,
    *,
    vol: int,
    miaoda_base: str,
) -> dict:
    """飞书 interactive 卡片 JSON（header 标题 + img 首屏 + lark_md 分区）。"""
    ov = data.get("overview") or {}
    window = _window_label(ov)
    title = (
        f"{category_cfg['emoji']} {category_cfg['title']} "
        f"Vol.{vol:02d} | {window}"
    )
    header_tpl = category_cfg.get("header_template") or "blue"

    elements: list[dict] = []
    img_key = (category_cfg.get("hero_img_key") or "").strip()
    if img_key:
        elements.append(_hero_img(img_key, category_cfg.get("hero_label", "月报首屏")))

    for i, block in enumerate(_build_body_sections(category_cfg, data, miaoda_base=miaoda_base)):
        if elements and (i > 0 or img_key):
            elements.append({"tag": "hr"})
        elements.append(_lark_md(block))

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": title},
            "template": header_tpl,
        },
        "elements": elements,
    }


def send_card(
    card: dict,
    *,
    profile: str,
    identity: str,
    user_id: str = "",
    chat_id: str = "",
    dry_run: bool = False,
) -> None:
    if bool(user_id) == bool(chat_id):
        raise SystemExit("推送目标二选一：指定 --user-id（私聊）或 --chat-id（群聊）")

    payload = json.dumps(card, ensure_ascii=False)
    cmd = [
        "lark-cli",
        "--profile",
        profile,
        "im",
        "+messages-send",
        "--as",
        identity,
    ]
    if user_id:
        cmd.extend(["--user-id", user_id])
    else:
        cmd.extend(["--chat-id", chat_id])
    cmd.extend(["--msg-type", "interactive", "--content", payload])
    if dry_run:
        cmd.append("--dry-run")
    target = f"私聊 {user_id}" if user_id else f"群 {chat_id}"
    print(f"→ lark-cli im +messages-send interactive ({target}) …", flush=True)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.stdout:
        print(proc.stdout)
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        raise SystemExit(proc.returncode)


def resolve_push_target(args: argparse.Namespace, cfg: dict) -> tuple[str, str, str]:
    """Return (user_id, chat_id, target_label)."""
    if args.chat_id:
        return "", args.chat_id, f"群 {args.chat_id}"
    if args.user_id:
        return args.user_id, "", f"私聊 {args.user_id}"

    env_uid = (
        os.getenv("FEISHU_PUSH_OPEN_ID")
        or os.getenv("TARGET_FEISHU_OPEN_ID")
        or ""
    ).strip()
    if env_uid:
        name = cfg.get("default_user_name") or env_uid
        return env_uid, "", f"私聊 {name}（env）"

    uid = (cfg.get("default_user_open_id") or "").strip()
    if not uid:
        raise SystemExit(
            "未配置私聊对象：请设置 feishu_push_config.json 的 default_user_open_id，"
            "或传 --user-id / --chat-id"
        )
    name = cfg.get("default_user_name") or uid
    return uid, "", f"私聊 {name}"


def resolve_category(args: argparse.Namespace, cfg: dict) -> tuple[str, dict, Path]:
    if args.category:
        key = args.category
    elif args.project_root:
        name = Path(args.project_root).name
        key = PROJECT_CATEGORY.get(name)
        if not key:
            raise SystemExit(f"无法从目录名推断品类: {name}")
    else:
        raise SystemExit("请指定 --category 或 --project-root")

    cat_cfg = cfg["categories"].get(key)
    if not cat_cfg:
        raise SystemExit(f"未知品类: {key}")

    if args.project_root:
        root = Path(args.project_root).resolve()
    else:
        root = (REPO_ROOT / cat_cfg["project_dir"]).resolve()

    html = root / cat_cfg["html_file"]
    if not html.exists():
        raise SystemExit(f"HTML 不存在: {html}")
    return key, cat_cfg, html


def main() -> None:
    parser = argparse.ArgumentParser(description="Push 爆款月报 card via cursor2号")
    parser.add_argument(
        "--category",
        help="品类 key（见 feishu_push_config.json → categories）",
    )
    parser.add_argument("--project-root", help="项目根目录（自动推断 category）")
    parser.add_argument("--vol", type=int, default=1, help="期号 Vol.NN")
    parser.add_argument(
        "--user-id",
        help="私聊 open_id（默认读配置 / TARGET_FEISHU_OPEN_ID）",
    )
    parser.add_argument(
        "--chat-id",
        help="推送到群（仅在你确认卡片格式后使用；未指定则私聊）",
    )
    parser.add_argument("--dry-run", action="store_true", help="只预览 lark-cli 请求")
    parser.add_argument("--print-only", action="store_true", help="只打印 card 正文")
    args = parser.parse_args()

    cfg = _load_config()
    if args.category and args.category not in cfg.get("categories", {}):
        known = ", ".join(sorted(cfg.get("categories", {})))
        raise SystemExit(f"未知品类: {args.category}（可选: {known or '无'}）")
    _key, cat_cfg, html_path = resolve_category(args, cfg)
    data = _extract_data(html_path)

    if not cat_cfg.get("miaoda_file_id"):
        print(
            f"WARN: {cat_cfg['title']} 尚未配置 miaoda_file_id，卡片将不含秒搭链接",
            file=sys.stderr,
        )

    card = build_interactive_card(
        cat_cfg,
        data,
        vol=args.vol,
        miaoda_base=cfg["miaoda_base"],
    )

    if args.print_only:
        print(json.dumps(card, ensure_ascii=False, indent=2))
        return

    user_id, chat_id, target_label = resolve_push_target(args, cfg)
    send_card(
        card,
        user_id=user_id,
        chat_id=chat_id,
        profile=cfg["lark_profile"],
        identity=cfg.get("identity", "bot"),
        dry_run=args.dry_run,
    )
    if not args.dry_run:
        print(f"✓ 已推送到 {target_label}（cursor2号）")


if __name__ == "__main__":
    main()
