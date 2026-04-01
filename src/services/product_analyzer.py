"""
Product Analyzer Service

Layer 1 analysis: Normalizes the products array from the wizard (name, description,
price, image_asset_id) into a compact product insights summary for use in Brand DNA
synthesis and plan structure generation.

This is lightweight (no LLM needed) — it structures the product list into a
standardized format and adds contextual hints used by downstream prompts.
"""

import logging
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)

MAX_PRODUCTS = 20


def analyze_products(products: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Normalize and analyze the products list.

    Input product keys:
        name, description, price, image_asset_id (optional)

    Returns:
        {
            "product_list": [...normalized products with hints...],
            "has_images": bool,
            "price_range": {"min": float, "max": float} | None,
            "summary": str   # compact string for LLM prompts
        }
    """
    if not products:
        return {
            "product_list": [],
            "has_images": False,
            "price_range": None,
            "summary": "Chưa có sản phẩm cụ thể.",
        }

    limited = products[:MAX_PRODUCTS]
    normalized = []
    prices = []
    has_images = False

    for p in limited:
        name = (p.get("name") or "").strip()
        if not name:
            continue

        description = (p.get("description") or "").strip()
        price_raw = p.get("price")
        image_asset_id = p.get("image_asset_id") or p.get("imageAssetId")

        # Parse price
        price_float: Optional[float] = None
        if price_raw is not None:
            try:
                price_float = float(
                    str(price_raw)
                    .replace(",", "")
                    .replace(".", "")
                    .replace("đ", "")
                    .replace("$", "")
                    .strip()
                )
                if price_float > 0:
                    prices.append(price_float)
            except (ValueError, AttributeError):
                pass

        if image_asset_id:
            has_images = True

        # Content type hint (for post generation)
        content_hint = _guess_content_hint(name, description)

        normalized.append(
            {
                "name": name,
                "description": description,
                "price": price_float,
                "image_asset_id": image_asset_id,
                "content_hint": content_hint,
            }
        )

    price_range = None
    if prices:
        price_range = {"min": min(prices), "max": max(prices)}

    summary = _build_summary(normalized, price_range)

    logger.info(
        f"✅ Product analysis: {len(normalized)} products, has_images={has_images}"
    )
    return {
        "product_list": normalized,
        "has_images": has_images,
        "price_range": price_range,
        "summary": summary,
    }


def _guess_content_hint(name: str, description: str) -> str:
    """Guess the best content type for a product based on name/description."""
    combined = f"{name} {description}".lower()
    if any(
        w in combined
        for w in ("combo", "set", "bundle", "trọn bộ", "khuyến mãi", "sale", "giảm")
    ):
        return "promotion"
    if any(w in combined for w in ("mới", "ra mắt", "launch", "new", "phiên bản")):
        return "launch"
    if any(
        w in combined
        for w in ("hướng dẫn", "cách dùng", "công thức", "tips", "review", "đánh giá")
    ):
        return "educational"
    return "showcase"


def _build_summary(
    products: List[Dict[str, Any]],
    price_range: Optional[Dict[str, float]],
) -> str:
    """
    Build a compact product summary string for LLM prompts.
    """
    if not products:
        return "Chưa có sản phẩm."

    lines = []
    for p in products:
        name = p["name"]
        desc = (
            p["description"][:60] + "..."
            if len(p.get("description", "")) > 60
            else p.get("description", "")
        )
        price_str = f" | Giá: {p['price']:,.0f}đ" if p.get("price") else ""
        content_hint = p.get("content_hint", "")
        lines.append(f"- {name}{price_str}: {desc} [hint: {content_hint}]")

    price_note = ""
    if price_range:
        if price_range["min"] == price_range["max"]:
            price_note = f"\nKhoảng giá: {price_range['min']:,.0f}đ"
        else:
            price_note = (
                f"\nKhoảng giá: {price_range['min']:,.0f}đ – {price_range['max']:,.0f}đ"
            )

    return "\n".join(lines) + price_note


def format_products_for_plan_prompt(products: List[Dict[str, Any]]) -> str:
    """
    Format product list for use in plan structure generation prompts.
    Returns only name + content_hint (minimal context).
    """
    if not products:
        return "Không có sản phẩm cụ thể."
    return ", ".join(
        f"{p['name']} ({p.get('content_hint', 'showcase')})"
        for p in products
        if p.get("name")
    )
