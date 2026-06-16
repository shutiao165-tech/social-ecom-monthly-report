# 小红书 × 抖音 · 品牌内容爆款月报

> **📖 使用说明（从这里开始）**  
> • [docs/USAGE.md](docs/USAGE.md) — 第一次怎么用、每月重跑、报告怎么读  
> • [docs/WORKFLOW.md](docs/WORKFLOW.md) — 流水线逐步说明  
> • [config/README.md](config/README.md) — 配置 `niche_config.py` 填什么  

> 作者：[shutiao165-tech](https://github.com/shutiao165-tech) · 仓库：https://github.com/shutiao165-tech/social-ecom-monthly-report

**架构与模型开源**：用 TikHub + 双池采集（品类词 + 品牌词），输出单文件 `monthly-report.html`——趋势榜、竞品动作板、机会矩阵、scene_links。

本仓库**不包含**任何真实品类、品牌或 SKU 数据；fork 后只需改 `config/niche_config.py`。

**TikHub 注册（推荐码 `YS1mhMDA`）**：https://user.tikhub.io/register?ref=YS1mhMDA

---

## 文档（建议先看）

| 文档 | 适合 |
|------|------|
| **[docs/USAGE.md](docs/USAGE.md)** | 第一次用、每月重跑、报告怎么读、FAQ |
| [docs/WORKFLOW.md](docs/WORKFLOW.md) | 流水线逐步说明、文件落在哪 |
| [docs/SETUP.md](docs/SETUP.md) | TikHub / decoder 安装 |
| [config/README.md](config/README.md) | 配置字段说明 |

**看不懂从哪下手？** → 打开 [docs/USAGE.md](docs/USAGE.md)，按「第一次使用 5 步」走一遍。

---

## 这仓库解决什么问题？

| 你想知道… | 报告里看… |
|-----------|-----------|
| 赛道什么内容在火？ | 品类池趋势榜 / 殿堂榜 |
| 竞品在发什么、挂不挂车？ | §02 竞品动作板 |
| 自有品牌该不该跟、推什么 SKU？ | §03 机会矩阵 + scene_links |

---

## 模型概览（方案 C）

```
品类池 (CATEGORY_KEYWORDS)  ─┐
                              ├→ 商业复核 → 汇总 → monthly-report.html
品牌池 (BRAND_SEARCH_*)     ─┘
```

| 层级 | 说明 |
|------|------|
| L1 双池 | 品类热点 vs 品牌动作，并行不混比 |
| L2 商业 | 挂品 / 挂车 / 品牌 tag 复核 |
| L3 关联 | scene_links、follow_candidates（可空则隐藏） |
| L4 决策 | 竞品动作板 + 自有品牌机会矩阵 |

---

## 快速开始（极简版）

```bash
git clone https://github.com/shutiao165-tech/social-ecom-monthly-report.git ~/brand-viral-monthly-report
cd ~/brand-viral-monthly-report

cp config/niche_config.example.py config/niche_config.py
# 编辑 config/niche_config.py

mkdir -p ~/.config/tikhub && echo "YOUR_TIKHUB_KEY" > ~/.config/tikhub/key
export SOCIAL_ECOM_DECODER=~/.claude/skills/social-ecom-decoder

# ① 在上游跑 douyin-pulse（品类 + 品牌）— 见 docs/USAGE.md 第 3 步
# ② 再跑本仓库流水线：
bash scripts/run_monthly_pipeline.sh
open monthly-report.html
```

### Cursor Skill

```bash
mkdir -p ~/.cursor/skills
cp -R cursor-skills/brand-viral-monthly-report ~/.cursor/skills/
```

---

## 目录

| 路径 | 作用 |
|------|------|
| `config/niche_config.example.py` | 配置模板 |
| `config/niche_config.py` | 你的配置（不提交 Git） |
| `scripts/run_monthly_pipeline.sh` | 一键流水线 |
| `monthly-report.html` | 报告输出 |
| `docs/` | 使用说明与流程 |
| `cursor-skills/` | Cursor Agent Skill |

---

## 隐私

- 不提交 `.env`、`config/niche_config.py`、`data/` 运行产物
- 不含飞书/秒搭内链、真实 SKU brief

---

## 相关

- [dingtalk-stock-watch](https://github.com/shutiao165-tech/dingtalk-stock-watch) — 同类开源范式

MIT — [LICENSE](LICENSE)
