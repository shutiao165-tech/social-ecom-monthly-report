#!/usr/bin/env python3
"""竞品动作板：标题净化、单品识别、内容形态标注。"""
from __future__ import annotations

import re

SKU_RULES: list[tuple[str, list[str]]] = [
    ("衣物消毒液", ["衣物消毒", "消毒液"]),
    ("洗衣液", ["洗衣液", "洗衣凝珠"]),
    ("无火香薰", ["无火香薰", "香薰小花盆", "扩香"]),
    ("车载香薰", ["车载香薰", "固体香薰", "车用香薰"]),
    ("管道疏通剂", ["管道疏通", "疏通剂", "下水道"]),
    ("马桶洁厕", ["洁厕", "马桶清洁", "尿垢", "洁厕灵", "洁厕宝"]),
    ("空调清洁剂", ["空调清洁", "空调清洗"]),
    ("洗衣机槽清洁", ["洗衣机清洗", "洗衣机清洁", "洗衣机槽"]),
    ("洗洁精", ["洗洁精"]),
    ("地板清洁剂", ["地板清洁", "地板除菌"]),
    ("冰箱除味", ["冰箱除味", "除味剂"]),
    ("除湿盒/袋", ["除湿盒", "除湿袋"]),
    ("油污净", ["油污净", "油污"]),
    ("除甲醛", ["除甲醛", "甲醛"]),
    ("香氛除味", ["香氛", "除味", "除臭"]),
    ("鞋柜除味", ["鞋柜除味", "鞋柜除臭"]),
]


def strip_hashtags(text: str) -> str:
    t = re.sub(r"#\S+", "", text or "")
    t = re.sub(r"[「」""\"']", "", t)
    return re.sub(r"\s+", " ", t).strip()


def infer_product_line(title: str, brand: str, commerce: dict | None = None) -> str:
    commerce = commerce or {}
    names = commerce.get("product_names") or []
    if names:
        n = str(names[0])
        n = re.sub(r"^【[^】]+】", "", n)
        return n[:22] + ("…" if len(n) > 22 else "")

    label = commerce.get("commerce_label") or ""
    for prefix in ("挂车·", "挂品·", "合作·"):
        if prefix in label:
            part = label.split(prefix, 1)[1].strip()
            if part and part not in ("无", "含#"):
                return part[:22]

    tags = re.findall(r"#(\S+)", title or "")
    for tag in tags:
        for label, kws in SKU_RULES:
            if any(k in tag for k in kws):
                return label
        if brand and brand in tag:
            rest = re.sub(r"^#?", "", tag).replace(brand, "").strip("#/_-")
            if len(rest) >= 3 and not re.match(r"^[\d\W]+$", rest):
                for label, kws in SKU_RULES:
                    if any(k in rest for k in kws):
                        return label
                if len(rest) <= 12:
                    continue
                return rest[:18]

    plain = strip_hashtags(title)
    for label, kws in SKU_RULES:
        if any(k in plain for k in kws):
            return label
    for label, kws in SKU_RULES:
        if any(k in (title or "") for k in kws):
            return label

    if brand and brand in plain:
        return ""
    return ""


def infer_action_type(title: str, platform: str = "") -> str:
    t = title or ""
    if any(w in t for w in ("剧情", "反转", "朋友圈", "婚姻", "独立女性", "防不住")):
        return "剧情植入"
    if "沉浸式" in t:
        return "沉浸式 vlog"
    if any(w in t for w in ("实测", "测评", "区别", "怎么选", "怎么用")):
        return "测评科普"
    if any(w in t for w in ("邪修", "妙招", "小技巧", "0成本")):
        return "清洁妙招"
    if any(w in t for w in ("滂臭", "异味", "臭")):
        return "痛点种草"
    if platform == "douyin":
        return "挂车口播"
    return "好物种草"


def enrich_clip(
    title: str,
    brand: str,
    commerce: dict | None,
    platform: str,
    *,
    likes: int = 0,
    likes_label: str = "",
    duration: str = "",
    category: str = "",
    rank: int = 1,
    aweme_id: str = "",
) -> dict:
    commerce = commerce or {}
    clean = strip_hashtags(title)
    if len(clean) > 52:
        clean = clean[:52] + "…"
    product = infer_product_line(title, brand, commerce)
    cat = category or ""
    fields = {
        "rank": rank,
        "title_raw": (title or "")[:160],
        "title_clean": clean or "（无标题）",
        "category": cat,
        "action_type": infer_action_type(title, platform),
        "likes": likes,
        "likes_label": likes_label or str(likes),
        "duration": duration,
        "aweme_id": aweme_id,
        "commerce_type": commerce.get("commerce_type", "无商业"),
        "commerce_label": commerce.get("commerce_label", "无"),
        "commerce_detail": commerce.get("commerce_detail", ""),
        "product_names": commerce.get("product_names") or [],
    }
    if product:
        fields["product_line"] = product
    return fields
