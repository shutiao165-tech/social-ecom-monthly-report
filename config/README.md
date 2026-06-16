# 赛道配置

本仓库**只提供月报架构与模型**，不含真实品类/品牌数据。

## 首次使用

```bash
cp config/niche_config.example.py config/niche_config.py
# 编辑 niche_config.py：赛道名、自有品牌、竞品、品类搜索词、分类规则、playbook
```

`config/niche_config.py` 已加入 `.gitignore`，不会误提交内部配置。

## 配置项说明

| 区块 | 作用 |
|------|------|
| `NICHE_LABEL` | 报告标题中的赛道名 |
| `OWN_BRAND` / `OWN_BRAND_ALIASES` | 自有品牌及别名（动作板标「自有」） |
| `BRAND_CANONICAL` + `BRAND_SEARCH_KEYWORDS` | 监测品牌与搜索组合词 |
| `BRAND_DY_AMBIGUOUS` | 抖音歧义品牌（pulse 跳过裸词，用 `dy_brand_keywords_csv()`） |
| `NICHE_STRONG_ANCHORS` / `NICHE_NEGATIVE_TERMS` / `BRAND_CONTEXT_REQUIRED` | 可选：过滤搜索噪声（见 `scripts/relevance_filter.py`） |
| `ENABLE_SENTIMENT_LANE` / `ENABLE_NEWS_LANE` | 舆情 / 行业资讯分流（默认开） |
| `SKU_RULES` | 竞品动作板单品识别 |
| `CATEGORY_KEYWORDS` | 品类池 TikHub 搜索词（内容向，非品牌名） |
| `CONTENT_CATEGORIES` / `PAIN_BUCKETS` | XHS 笔记分类与痛点桶 |
| `DIRECTION_PLAYBOOK` | 机会矩阵 / scene_links 的话题 playbook |
| `REPORT_COPY` | HTML 页眉文案（支持 `{niche}` `{own_brand}` `{brand_count}`） |

脚本通过 `scripts/brand_config.py` 统一读取，**勿在多个脚本里重复写品牌列表**。
