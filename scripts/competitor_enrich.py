#!/usr/bin/env python3
"""竞品动作板：标题净化、单品识别、内容形态标注、舆情/资讯分流。"""
from __future__ import annotations

import re

from brand_config import ENABLE_NEWS_LANE, ENABLE_SENTIMENT_LANE
from load_niche import cfg


def _sku_rules() -> list[tuple[str, list[str]]]:
    return list(getattr(cfg(), "SKU_RULES", []) or [])


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

    sku_rules = _sku_rules()
    tags = re.findall(r"#(\S+)", title or "")
    for tag in tags:
        for sku_label, kws in sku_rules:
            if any(k in tag for k in kws):
                return sku_label
        if brand and brand in tag:
            rest = re.sub(r"^#?", "", tag).replace(brand, "").strip("#/_-")
            if len(rest) >= 3 and not re.match(r"^[\d\W]+$", rest):
                for sku_label, kws in sku_rules:
                    if any(k in rest for k in kws):
                        return sku_label
                if len(rest) <= 12:
                    continue
                return rest[:18]

    plain = strip_hashtags(title)
    for sku_label, kws in sku_rules:
        if any(k in plain for k in kws):
            return sku_label
    for sku_label, kws in sku_rules:
        if any(k in (title or "") for k in kws):
            return sku_label

    if brand and brand in plain:
        return ""
    return ""


SENTIMENT_DEATH_KW = (
    "死亡", "身亡", "si亡", "致死", "全灭", "中毒", "惨死", "丧命", "遇难",
)
SENTIMENT_NEWS_KW = (
    "据报道", "媒体", "引发网友", "热议", "曝光", "维权", "起诉", "道歉", "翻车",
    "涉事", "通报", "立案", "投诉", "召回", "罚款", "黑猫", "消费者报", "监管",
)
SENTIMENT_MEDIA_AUTHORS = (
    "天眼查", "澎湃新闻", "红星", "新京报", "观察者", "头条", "法制", "新闻",
    "曝光台", "财经", "电视台", "日报", "晚报",
)

NEWS_KW = (
    "增收不增利", "财报", "营收", "同比", "环比", "市占", "融资", "并购", "上市",
    "新品发布", "新品", "行业", "赛道", "增长", "渠道", "破局", "战略",
)


def is_public_sentiment(
    title: str = "",
    content_excerpt: str = "",
    author_nickname: str = "",
) -> bool:
    """负面舆情/媒体报道，非种草代表片。"""
    if not ENABLE_SENTIMENT_LANE:
        return False
    t = title or ""
    body = content_excerpt or ""
    text = f"{t} {body}"
    author = author_nickname or ""

    if author and any(m in author for m in SENTIMENT_MEDIA_AUTHORS):
        return True
    if any(w in text for w in SENTIMENT_NEWS_KW):
        if any(w in text for w in SENTIMENT_DEATH_KW):
            return True
        if any(w in text for w in ("维权", "起诉", "翻车", "曝光", "道歉", "召回", "罚款")):
            return True
    if any(w in t for w in SENTIMENT_DEATH_KW):
        if "?" in t or "？" in t:
            if not any(w in text for w in ("好物", "推荐", "分享", "vlog", "日常", "测评")):
                return True
    return False


def is_industry_news(
    title: str = "",
    content_excerpt: str = "",
    author_nickname: str = "",
) -> bool:
    """行业资讯/媒体信息，非种草代表片（但不一定是负面）。"""
    if not ENABLE_NEWS_LANE:
        return False
    t = title or ""
    body = content_excerpt or ""
    text = f"{t} {body}"
    author = author_nickname or ""

    if is_public_sentiment(t, body, author):
        return False
    if author and any(m in author for m in SENTIMENT_MEDIA_AUTHORS):
        return True
    if any(w in text for w in NEWS_KW):
        return True
    return False


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
    content_excerpt: str = "",
    author_nickname: str = "",
) -> dict:
    commerce = commerce or {}
    clean = strip_hashtags(title)
    if len(clean) > 52:
        clean = clean[:52] + "…"
    sentiment = is_public_sentiment(title, content_excerpt, author_nickname)
    news = (not sentiment) and is_industry_news(title, content_excerpt, author_nickname)
    product = "" if (sentiment or news) else infer_product_line(title, brand, commerce)
    cat = category or ""
    fields = {
        "rank": rank,
        "title_raw": (title or "")[:160],
        "title_clean": clean or "（无标题）",
        "category": cat,
        "action_type": "舆情" if sentiment else ("资讯" if news else infer_action_type(title, platform)),
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
    if sentiment:
        fields["content_lane"] = "sentiment"
    elif news:
        fields["content_lane"] = "news"
    return fields
