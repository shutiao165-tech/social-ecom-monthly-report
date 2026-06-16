#!/usr/bin/env bash
# 双平台品牌内容爆款月报 — 标准流水线（方案 C：双池 + 关联层）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DECODER="${SOCIAL_ECOM_DECODER:-$HOME/.claude/skills/social-ecom-decoder}"
BUILD_ONLY=0
SKIP_XHS=0
SKIP_DY_MERGE=0
DY_CAT=""
DY_BRAND=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --build-only) BUILD_ONLY=1; shift ;;
    --skip-xhs) SKIP_XHS=1; shift ;;
    --skip-dy-merge) SKIP_DY_MERGE=1; shift ;;
    --dy-category) DY_CAT="$2"; shift 2 ;;
    --dy-brand) DY_BRAND="$2"; shift 2 ;;
    *) echo "Unknown: $1"; exit 1 ;;
  esac
done

cd "$ROOT"

if [[ "$BUILD_ONLY" -eq 0 ]]; then
  if [[ "$SKIP_XHS" -eq 0 ]]; then
    echo "==> XHS fetch (TikHub dual pool)"
    python3 scripts/fetch_xhs_monthly_tikhub.py
    echo "==> XHS commerce enrich"
    python3 scripts/enrich_commerce.py
  fi

  if [[ "$SKIP_DY_MERGE" -eq 0 ]]; then
    if [[ -z "$DY_CAT" || -z "$DY_BRAND" ]]; then
      LATEST="$(ls -td "$DECODER"/output/*/douyin-pulse 2>/dev/null | head -1 || true)"
      if [[ -n "$LATEST" ]]; then
        DY_CAT="${DY_CAT:-$LATEST/analysis_category.json}"
        for f in "$LATEST"/analysis_*.json; do
          [[ "$(basename "$f")" != "analysis_category.json" ]] && DY_BRAND="$f" && break
        done
      fi
    fi
    if [[ -f "$DY_CAT" && -f "$DY_BRAND" ]]; then
      echo "==> Merge DY pulse"
      python3 scripts/merge_douyin_pulse.py --category "$DY_CAT" --brand "$DY_BRAND"
    else
      echo "WARN: DY analysis not found; skip merge (use --dy-category / --dy-brand)"
    fi
  fi
fi

echo "==> Build unified HTML"
python3 scripts/build_unified_monthly.py
echo "Done: $ROOT/monthly-report.html"
