#!/usr/bin/env python3
"""Optional SKU brief catalog — load from local JSON or skip."""
import json
from pathlib import Path
from typing import Dict, List, Optional

from env_paths import PROJECT_ROOT

# Override with BRIEF_CATALOG_DIR or place files under templates/brief/
BRIEF_ROOT = Path(
    __import__("os").environ.get("BRIEF_CATALOG_DIR", str(PROJECT_ROOT / "templates" / "brief"))
)
CAT_PATH = BRIEF_ROOT / "category-briefs.json"
INDEX_PATH = BRIEF_ROOT / "product-index.json"

# Example topic → product mapping (edit for your SKU set)
TOPIC_BRIEF_PRODUCTS: Dict[str, List[str]] = {
    "toilet_odor": ["示例洁厕挂篮", "示例马桶清洁剂"],
    "kitchen_oil": ["示例洗洁精", "示例油污净"],
    "dehumid": ["示例除湿袋", "示例防霉香包"],
    "scent": ["示例空间香氛", "示例车载香薰"],
}


def load_catalog() -> dict:
    products: list = []
    topics: dict = {}
    if INDEX_PATH.exists():
        try:
            products = json.loads(INDEX_PATH.read_text(encoding="utf-8")).get("products") or []
        except (json.JSONDecodeError, OSError):
            pass
    if CAT_PATH.exists():
        try:
            topics = json.loads(CAT_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"products": products, "topics": topics}


def resolve_products(catalog: dict, topic_key: str) -> List[str]:
    names = TOPIC_BRIEF_PRODUCTS.get(topic_key) or []
    if not names and catalog.get("topics"):
        return list(catalog["topics"].get(topic_key) or [])
    return names
