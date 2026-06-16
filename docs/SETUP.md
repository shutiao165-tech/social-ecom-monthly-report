# 安装与配置

## 1. TikHub

任选一种方式配置 Key：

```bash
mkdir -p ~/.config/tikhub
echo "sk-xxxxxxxx" > ~/.config/tikhub/key
chmod 600 ~/.config/tikhub/key
```

或 `export TIKHUB_API_KEY=sk-xxxxxxxx`（若脚本支持环境变量读取）。

余额不足时 XHS / DY 拉数会失败，需先充值。

## 2. social-ecom-decoder

本仓库的抖音侧依赖 `douyin-pulse`：

```bash
export SOCIAL_ECOM_DECODER=~/.claude/skills/social-ecom-decoder
cd "$SOCIAL_ECOM_DECODER"
# 按 decoder 仓库 README 安装依赖
python3 shared/lib/cli.py douyin-pulse --help
```

月报流水线会在 `$SOCIAL_ECOM_DECODER/output/<日期>/douyin-pulse/` 下寻找最新 pulse 结果；也可手动指定：

```bash
python3 scripts/merge_douyin_pulse.py \
  --category "$SOCIAL_ECOM_DECODER/output/2026-06-15/douyin-pulse/analysis_category.json" \
  --brand "$SOCIAL_ECOM_DECODER/output/2026-06-15/douyin-pulse/analysis_2026-06-15.json"
```

## 3. 品牌与品类词

**唯一真源**：`scripts/brand_config.py`

- `BRAND_CANONICAL`：监测的竞品品牌名
- `BRAND_SEARCH_KEYWORDS`：各品牌在小红书/抖音的搜索组合词
- 品类词列表在 `fetch_xhs_monthly_tikhub.py` 的 `CATEGORY_KEYWORDS`

将示例中的「网易严选」改成你的自有品牌名时，需同步改 `build_unified_monthly.py` 里的 `YANXUAN_NAMES` / 文案（或保持通用「自有品牌」表述）。

## 4. 流水线分步

```bash
python3 scripts/fetch_xhs_monthly_tikhub.py   # XHS 双池
python3 scripts/enrich_commerce.py            # 商业复核
# 手动或 decoder 跑 douyin-pulse 后：
python3 scripts/merge_douyin_pulse.py --category ... --brand ...
python3 scripts/build_unified_monthly.py      # 写 monthly-report.html
```

或：`bash scripts/run_monthly_pipeline.sh --build-only`（仅有 data 时只重渲染 HTML）。

## 5. 可选：SKU Brief

若要做 scene_links → SKU 映射，在 `templates/brief/` 放置：

- `product-index.json`
- `category-briefs.json`

或设置 `BRIEF_CATALOG_DIR`。未配置时关联层仍可用，SKU 字段为空。
