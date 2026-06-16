# Changelog

## v0.2 — 2026-06-16

对齐内部多赛道生产环境的核心过滤与分流能力，仍**不含**任何真实监测词表或运行数据。

### Added

- `scripts/relevance_filter.py` — 配置驱动的赛道相关性过滤（XHS + DY 共用）
- `BRAND_DY_AMBIGUOUS` + `dy_brand_keywords_flat()` / `dy_brand_keywords_csv()` — 抖音歧义品牌组合词
- 舆情 / 行业资讯分流：`ENABLE_SENTIMENT_LANE`、`ENABLE_NEWS_LANE`
- `SKU_RULES` — 可配置的竞品单品识别规则
- DY `sanitize_dy_brand_rows` / `refresh_dy_brand_markdown` — 合并后二次过滤与摘要刷新
- 竞品动作板 HTML：舆情 / 资讯独立展示条

### Changed

- `build_xhs_brands_from_raw` — 种草 / 舆情 / 资讯分池
- `merge_douyin_pulse` — 品牌命中改用 `mentions_brand`（hashtag 防蹭 + 相关性）
- `competitor_enrich.enrich_clip` — 支持 `content_excerpt` / `author_nickname`

## v0.1 — 初版

- 双池架构（品类 + 品牌）、商业复核、竞品动作板、scene_links
- `config/niche_config.example.py` 模板与 Cursor Skill
