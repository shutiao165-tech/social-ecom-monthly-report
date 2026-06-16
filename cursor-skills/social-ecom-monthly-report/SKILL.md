---
name: social-ecom-monthly-report
description: >-
  小红书 + 抖音双平台爆款月报（方案 C：品类/品牌双池、商业复核、竞品动作板、scene_links）。
  整合 TikHub 与 social-ecom-decoder 的 douyin-pulse。Use when 跑家清月报 / 双平台竞品看板 / scene_links / follow_candidates / monthly viral report。
---

# 双平台爆款月报 — Cursor Skill

## 项目信息

- 仓库：https://github.com/shutiao165-tech/social-ecom-monthly-report
- 推荐克隆路径：`~/social-ecom-monthly-report`
- 上游依赖：**social-ecom-decoder**（本地安装 `douyin-pulse` CLI，路径见 `SOCIAL_ECOM_DECODER`）

## 安装 Skill

```bash
git clone https://github.com/shutiao165-tech/social-ecom-monthly-report.git ~/social-ecom-monthly-report
mkdir -p ~/.cursor/skills
cp -R ~/social-ecom-monthly-report/cursor-skills/social-ecom-monthly-report ~/.cursor/skills/
```

## 配置

```bash
cd ~/social-ecom-monthly-report
cp .env.example .env
# TikHub：写入 ~/.config/tikhub/key 或 export TIKHUB_API_KEY
# 编辑 scripts/brand_config.py — 自有品牌 + 竞品列表
```

## 标准流水线

```bash
bash scripts/run_monthly_pipeline.sh
# 仅重渲染：bash scripts/run_monthly_pipeline.sh --build-only
```

产出：`monthly-report.html`（`const DATA` 全内嵌）

## 架构要点（方案 C）

| 池 | 小红书 | 抖音 |
|---|---|---|
| 品类池 | 每词 TOP30 | `douyin-pulse --top-n 30` |
| 品牌池 | 组合品牌词 TOP3–5 | `--per-brand-top 5` |
| 关联层 | `scene_links` / `follow_candidates` | 同上 |

**铁律**：小红书仅 TikHub（`fetch_xhs_monthly_tikhub.py`）；品牌词唯一真源 `scripts/brand_config.py`。

详细说明见仓库 `README.md` 与 `docs/SETUP.md`。
