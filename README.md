# 小红书 × 抖音 · 双平台爆款月报

> 作者：[shutiao165-tech](https://github.com/shutiao165-tech)  
> 仓库：https://github.com/shutiao165-tech/social-ecom-monthly-report

用 **TikHub API** 拉取小红书 / 抖音近 30 天爆款样本，经**品类池 + 品牌池**双轨采集、商业复核与关联层计算，输出单文件 **`monthly-report.html`**（趋势榜、竞品动作板、机会矩阵、scene_links）。

默认示例赛道为**家清品类**（可 fork 后改 `scripts/brand_config.py` 监测词与竞品）。

---

## 功能一览

| 模块 | 说明 |
|------|------|
| 双池采集 | 品类词 TOP30 + 品牌组合词代表片 |
| 商业复核 | 挂品 / 挂车 / 品牌 tag 打标 |
| 竞品动作板 §02 | 每品牌每平台最多 3 条代表片，有品前置 |
| scene_links | 趋势场景 × 竞品 × SKU 关联 |
| follow_candidates | 可跟投候选（为空则前端隐藏） |
| Cursor Skill | `cursor-skills/social-ecom-monthly-report/` |

---

## 环境要求

- **Python** 3.10+
- **TikHub** 付费 API Key（[tikhub.io](https://tikhub.io)）
- **social-ecom-decoder**（本地 `douyin-pulse` CLI，见 [SETUP.md](docs/SETUP.md)）
- **Cursor**（可选，用于 Agent Skill）

---

## 快速开始

```bash
git clone https://github.com/shutiao165-tech/social-ecom-monthly-report.git ~/social-ecom-monthly-report
cd ~/social-ecom-monthly-report

cp .env.example .env
mkdir -p ~/.config/tikhub
echo "YOUR_TIKHUB_KEY" > ~/.config/tikhub/key

# 1) 安装上游 decoder（本地 clone 你的 social-ecom-decoder 路径）
#    export SOCIAL_ECOM_DECODER=~/.claude/skills/social-ecom-decoder

# 2) 改监测词 / 竞品（唯一真源）
#    vim scripts/brand_config.py

# 3) 一键月报
bash scripts/run_monthly_pipeline.sh
open monthly-report.html
```

### 安装 Cursor Skill

```bash
mkdir -p ~/.cursor/skills
cp -R cursor-skills/social-ecom-monthly-report ~/.cursor/skills/
```

---

## 目录结构

```
├── scripts/           # 拉数、合并、写 HTML
├── templates/         # Brief 表模板（示例，无内部 SKU）
├── data/              # 运行产物（git 忽略）
├── monthly-report.html
├── cursor-skills/     # 复制到 ~/.cursor/skills/
└── docs/
```

---

## 隐私与数据

- 仓库**不含**真实月报数据、`merged_raw.json` 等大文件
- 请勿提交 `.env`、`~/.config/tikhub/key`、含内部 SKU 的 brief JSON
- 首次运行后 `data/` 会含平台公开内容，自行决定是否归档

---

## 相关项目

- [dingtalk-stock-watch](https://github.com/shutiao165-tech/dingtalk-stock-watch) — 钉钉 A 股盯盘助手（同类开源范式）
- social-ecom-decoder — 抖音 pulse / 小红书爆款子 skill 集合（需单独安装）

---

## License

MIT — 见 [LICENSE](LICENSE)
