# 小红书 × 抖音 · 品牌内容爆款月报

> 作者：[shutiao165-tech](https://github.com/shutiao165-tech)  
> 仓库：https://github.com/shutiao165-tech/social-ecom-monthly-report

**架构与模型开源**：用 TikHub + 双池采集（品类词 + 品牌词），输出单文件 `monthly-report.html`——趋势榜、竞品动作板、机会矩阵、scene_links。

本仓库**不包含**任何真实品类、品牌或 SKU 数据；fork 后只需改 `config/niche_config.py`。

---

## 模型概览（方案 C）

```
┌─────────────────┐     ┌─────────────────┐
│   品类池        │     │   品牌池        │
│ CATEGORY_KEYWORDS│     │ BRAND_SEARCH_*  │
│ 每词 TOP30      │     │ 每品牌 TOP3–5   │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     ▼
            enrich_commerce（挂品/挂车）
                     ▼
         merge + build_unified_monthly
                     ▼
              monthly-report.html
         （竞品板 · 机会矩阵 · scene_links）
```

| 层级 | 说明 |
|------|------|
| L1 双池 | 品类热点 vs 品牌动作，并行不混比 |
| L2 商业 | 挂品 / 挂车 / 品牌 tag 复核 |
| L3 关联 | scene_links、follow_candidates（可空则隐藏） |
| L4 决策 | 竞品动作板 + 自有品牌机会矩阵 |

---

## 快速开始

```bash
git clone https://github.com/shutiao165-tech/social-ecom-monthly-report.git ~/brand-viral-monthly-report
cd ~/brand-viral-monthly-report

cp config/niche_config.example.py config/niche_config.py
# 编辑 config/niche_config.py

mkdir -p ~/.config/tikhub
echo "YOUR_TIKHUB_KEY" > ~/.config/tikhub/key

export SOCIAL_ECOM_DECODER=~/.claude/skills/social-ecom-decoder  # douyin-pulse 上游

bash scripts/run_monthly_pipeline.sh
open monthly-report.html
```

### Cursor Skill

```bash
mkdir -p ~/.cursor/skills
cp -R cursor-skills/brand-viral-monthly-report ~/.cursor/skills/
```

---

## 你需要改的唯一文件

`config/niche_config.py`（从 example 复制）—— 赛道名、自有品牌、竞品、品类词、分类规则、playbook、报告文案。

详见 [config/README.md](config/README.md) 与 [docs/SETUP.md](docs/SETUP.md)。

---

## 目录

| 路径 | 作用 |
|------|------|
| `config/niche_config.example.py` | 配置模板（占位品牌 BrandAlpha / CompetitorB…） |
| `scripts/brand_config.py` | 配置加载出口（勿手改列表） |
| `scripts/build_unified_monthly.py` | 汇总 DATA、patch HTML |
| `monthly-report.html` | 报告壳（DATA 由 pipeline 写入） |
| `cursor-skills/` | 复制到 `~/.cursor/skills/` |

---

## 隐私

- 不提交 `.env`、`config/niche_config.py`、`data/` 运行产物
- 不含飞书/秒搭内链、真实 SKU brief

---

## 相关

- [dingtalk-stock-watch](https://github.com/shutiao165-tech/dingtalk-stock-watch) — 同类开源范式（盯盘助手）

MIT — [LICENSE](LICENSE)
