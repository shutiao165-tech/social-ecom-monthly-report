#!/usr/bin/env python3
"""赛道 / 品牌配置模板 — fork 后复制为 niche_config.py 并按你的业务修改。

本仓库只提供「双平台品牌内容爆款月报」的架构与模型，不包含任何真实品类或品牌数据。
"""

# ── 赛道 ─────────────────────────────────────────────
NICHE_LABEL = "示例赛道"  # 报告中的赛道名，如「美妆」「宠物」「3C」
NICHE_SLUG = "example-niche"

# ── 自有品牌（监测列表中须包含，动作板会标为「自有」）────────
OWN_BRAND = "BrandAlpha"
OWN_BRAND_DISPLAY = "BrandAlpha"  # 动作板展示名，可与 canonical 不同
OWN_BRAND_ALIASES = ["BrandAlpha", "Brand Alpha", "BrandAlpha官方"]

# ── 监测品牌：自有 + 竞品（canonical 名，顺序建议自有放首位）──
BRAND_CANONICAL = [
    "BrandAlpha",
    "CompetitorB",
    "CompetitorC",
    "CompetitorD",
]

# canonical → 各平台搜索组合词（与 douyin-pulse 品牌 run 对齐）
BRAND_SEARCH_KEYWORDS: dict[str, list[str]] = {
    "BrandAlpha": ["BrandAlpha", "Brand Alpha"],
    "CompetitorB": ["CompetitorB", "CompetitorB 产品线"],
    "CompetitorC": ["CompetitorC", "CompetitorC 系列"],
    "CompetitorD": ["CompetitorD"],
}

# 抖音歧义品牌：裸词易命中非赛道内容；pulse 仅用组合词（见 dy_brand_keywords_csv）
BRAND_DY_AMBIGUOUS: list[str] = []  # 例：["CompetitorB"]

# 可选：内容相关性过滤（XHS + DY 共用；不配则仅做品牌名/hashtag 校验）
NICHE_STRONG_ANCHORS: list[str] = []  # 例：赛道强锚词
NICHE_WEAK_ANCHORS: list[str] = []
NICHE_NEGATIVE_TERMS: list[str] = []  # 命中且无强锚点时丢弃
BRANDS_REQUIRING_STRONG_ANCHOR: list[str] = []  # 歧义品牌须共现强锚词
BRAND_CONTEXT_REQUIRED: dict[str, list[str]] = {}  # 例：{"CompetitorB": ["产品线", "系列"]}

# 竞品动作板：舆情 / 行业资讯分流（默认开启）
ENABLE_SENTIMENT_LANE = True
ENABLE_NEWS_LANE = True

# SKU 识别规则（product_line 推断；空列表则仅靠挂品字段）
SKU_RULES: list[tuple[str, list[str]]] = [
    ("示例 SKU A", ["关键词A", "关键词A2"]),
    ("示例 SKU B", ["关键词B"]),
]

# 竞品动作板：品牌 → 主战场场景标签（可选，缺省为 DEFAULT_SCENE）
BRAND_SCENE_HINTS: dict[str, str] = {
    "CompetitorB": "场景A",
    "CompetitorC": "场景B",
    "BrandAlpha": "全品类",
}
DEFAULT_SCENE = "综合场景"

# ── 品类池：内容向搜索词（非品牌名）────────────────────
CATEGORY_KEYWORDS = [
    "示例关键词1",
    "示例关键词2",
    "示例关键词3",
    "示例关键词4",
    "示例关键词5",
]

# ── 小红书笔记分类规则（按标题/正文关键词打标）────────────
CONTENT_CATEGORIES = [
    ("好物推荐", ["好物", "爱用", "推荐", "清单", "种草", "年度", "补货", "同款", "分享"]),
    ("教程测评", ["教程", "测评", "对比", "实测", "步骤", "怎么"]),
    ("场景种草", ["场景", "日常", "vlog", "沉浸式"]),
    ("品牌竞品", []),  # 运行时自动注入 BRAND_CANONICAL
]

# ── 痛点桶（评论/标题洞察用，可按赛道增删）──────────────
PAIN_BUCKETS = [
    ("效果质疑", ["有用", "鸡肋", "智商税", "效果", "没效果", "踩雷"]),
    ("价格敏感", ["贵", "便宜", "性价比", "多少钱", "链接"]),
    ("操作门槛", ["麻烦", "费力", "懒人", "复杂", "难用"]),
    ("安全顾虑", ["刺激", "过敏", "有害", "宝宝", "孕"]),
    ("求购链接", ["链接", "求购", "哪里买", "同款", "蹲"]),
]

# ── douyin-pulse 元数据标签 ───────────────────────────
DY_NICHE_CATEGORY = "示例品类"
DY_NICHE_BRAND = "示例品牌竞品"

# ── 执行方向 playbook（机会矩阵 / scene_links 用，可整表替换）──
DIRECTION_PLAYBOOK = [
    {
        "id": "topic_a",
        "topic": "示例话题A / 场景痛点",
        "signals": ["关键词A", "关键词B", "痛点词"],
        "pain_keys": ["效果质疑", "价格敏感"],
        "cats": ["好物推荐"],
        "dy_cats": ["场景种草"],
        "brief_id": "topic_a",
        "xhs": "清单体：多场景对比实测，强调可收藏步骤",
        "dy": "数字钩 + 前后对比快剪",
        "feed": "30–45s：痛点反问 → 演示 → 口播利益点",
    },
    {
        "id": "topic_b",
        "topic": "示例话题B / 季节场景",
        "signals": ["季节词", "场景词"],
        "pain_keys": ["求购链接"],
        "cats": ["场景种草"],
        "dy_cats": [],
        "brief_id": "topic_b",
        "xhs": "季节预警体 + 备货款清单",
        "dy": "反差钩开箱实测",
        "feed": "多场景蒙太奇 + 产品特写",
    },
]

# ── 报告文案（patch_html 写入；{niche} {own_brand} {brand_count} 占位）──
REPORT_COPY = {
    "html_title": "品牌内容爆款月报 · 小红书 × 抖音",
    "nav_title": "品牌月报",
    "kicker": "Vol. 01 · {niche} · 品牌情报",
    "h1_line1": "品牌内容爆款月报",
    "h1_sub": "趋势监测 × 竞品动作 × 自有机会",
    "lead": (
        "从品牌经营视角解读{niche}：哪些场景在升温、竞品在做什么、"
        "{own_brand}该跟不跟、主推哪个 SKU。"
        "数据覆盖小红书 + 抖音近 30 天监测词与 {brand_count} 个监测品牌。"
    ),
    "pool_note": (
        "双层结构：<b>全网热点</b>（品类词）+ <b>品牌决策</b>（品牌词）并行，互不替代。"
    ),
}
