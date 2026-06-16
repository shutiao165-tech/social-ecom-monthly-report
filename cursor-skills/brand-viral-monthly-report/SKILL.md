---
name: brand-viral-monthly-report
description: >-
  小红书 + 抖音品牌内容爆款月报架构（方案 C：品类/品牌双池、商业复核、竞品动作板、scene_links）。
  仅提供模型与流水线，赛道/品牌由 config/niche_config.py 配置。Use when 双平台品牌月报 / 竞品看板 / scene_links / TikHub monthly report。
---

# 品牌内容爆款月报 — Cursor Skill

## 定位

**开源的是架构与模型**，不是某一品类或某一品牌的数据。所有业务配置在 `config/niche_config.py`。

## 文档

- **人类可读**：[docs/USAGE.md](../../docs/USAGE.md)（入门）、[docs/WORKFLOW.md](../../docs/WORKFLOW.md)（流水线）
- **配置字段**：[config/README.md](../../config/README.md)

## 仓库

- https://github.com/shutiao165-tech/social-ecom-monthly-report
- 推荐路径：`~/brand-viral-monthly-report`

## 安装

```bash
git clone https://github.com/shutiao165-tech/social-ecom-monthly-report.git ~/brand-viral-monthly-report
cp ~/brand-viral-monthly-report/config/niche_config.example.py ~/brand-viral-monthly-report/config/niche_config.py
mkdir -p ~/.cursor/skills
cp -R ~/brand-viral-monthly-report/cursor-skills/brand-viral-monthly-report ~/.cursor/skills/
```

## 配置（必做）

编辑 `config/niche_config.py`：

- `NICHE_LABEL` — 赛道名
- `OWN_BRAND` + `OWN_BRAND_ALIASES` — 自有品牌
- `BRAND_CANONICAL` + `BRAND_SEARCH_KEYWORDS` — 监测竞品
- `CATEGORY_KEYWORDS` — 品类池搜索词
- `DIRECTION_PLAYBOOK` — 机会矩阵话题（可选整表替换）
- `BRAND_DY_AMBIGUOUS` / `NICHE_*_ANCHORS` — 歧义品牌与噪声过滤（v0.2+，见 CHANGELOG）

TikHub Key：`~/.config/tikhub/key` · 注册 [user.tikhub.io/register?ref=YS1mhMDA](https://user.tikhub.io/register?ref=YS1mhMDA)（推荐码 **YS1mhMDA**）  
抖音 pulse：`SOCIAL_ECOM_DECODER` 指向 social-ecom-decoder  
抖音品牌池关键词：`python3 -c "from scripts.brand_config import dy_brand_keywords_csv; print(dy_brand_keywords_csv())"`

## 流水线

```bash
cd ~/brand-viral-monthly-report
bash scripts/run_monthly_pipeline.sh
# 仅重渲染：--build-only
```

产出：`monthly-report.html`

## 架构铁律

1. **双池不混比**：品类 UGC 爆款 ≠ 品牌代表片赞数
2. **品牌命中**：标题/正文含品牌名或搜索词；禁止仅凭入库标签
3. **歧义品牌**（v0.2）：`BRAND_DY_AMBIGUOUS` + `relevance_filter` 过滤 DY/XHS 噪声
4. **舆情分流**（v0.2）：种草代表片与舆情/资讯分开展示
5. **竞品板**：每品牌每平台最多 3 条代表片，有品优先
6. **follow_candidates 为空** → 前端隐藏该板块

详细见仓库 `README.md` · 版本记录见 `CHANGELOG.md`。
