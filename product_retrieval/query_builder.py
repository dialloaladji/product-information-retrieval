from __future__ import annotations


def build_product_query(gtin: str) -> str:
    normalized = gtin.strip()
    return f"{normalized} manufacturer product specifications datasheet"
