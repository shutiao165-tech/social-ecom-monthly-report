# 安装与配置

## 1. 复制赛道配置（必做）

```bash
cp config/niche_config.example.py config/niche_config.py
```

在 `niche_config.py` 中填写你的赛道与品牌。**不要**改 `scripts/brand_config.py` 里的列表（它只是加载 config）。

## 2. TikHub

```bash
mkdir -p ~/.config/tikhub
echo "sk-xxxxxxxx" > ~/.config/tikhub/key
chmod 600 ~/.config/tikhub/key
```

## 3. social-ecom-decoder（抖音 pulse）

```bash
export SOCIAL_ECOM_DECODER=~/.claude/skills/social-ecom-decoder
python3 "$SOCIAL_ECOM_DECODER/shared/lib/cli.py" douyin-pulse --help
```

品类 run 示例（关键词来自你的 `CATEGORY_KEYWORDS`）：

```bash
python3 shared/lib/cli.py douyin-pulse \
  --keywords "词1,词2,词3" \
  --niche "你的品类标签" --days 30 --top-n 30 --min-likes 500
```

品牌 run 示例：

```bash
python3 shared/lib/cli.py douyin-pulse \
  --keywords "$(python3 -c "from brand_config import xhs_brand_keywords_flat; print(','.join(xhs_brand_keywords_flat()))")" \
  --brands "$(python3 -c "from brand_config import BRAND_CANONICAL; print(','.join(BRAND_CANONICAL))")" \
  --per-brand-top 5 --niche "品牌竞品" --days 30 --no-push
```

（需在项目 `scripts/` 目录下执行 `-c` 片段，或 `cd scripts && python3 -c ...`）

## 4. 流水线

```bash
bash scripts/run_monthly_pipeline.sh
python3 scripts/build_unified_monthly.py   # merge 后单独重渲染
```

## 5. 可选：SKU Brief

`templates/brief/` 放置 `product-index.json` / `category-briefs.json`，或设置 `BRIEF_CATALOG_DIR`。未配置时机会矩阵仍可运行，SKU 字段为空。

## 6. 报告文案

`niche_config.REPORT_COPY` 支持占位符 `{niche}` `{own_brand}` `{brand_count}`，由 `build_unified_monthly.patch_html` 写入 HTML。
