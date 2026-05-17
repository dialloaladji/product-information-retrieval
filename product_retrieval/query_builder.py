from __future__ import annotations


def build_product_query(gtin: str, context: str | None = None) -> str:
    normalized = gtin.strip()
    if context and context.strip():
        return f"{normalized} {context.strip()} manufacturer specifications"
    return f"{normalized} manufacturer product specifications datasheet"
