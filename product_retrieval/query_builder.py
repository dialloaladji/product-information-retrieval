from __future__ import annotations


def build_product_query(gtin: str) -> str:
    normalized = " ".join(gtin.strip().split())
    return f'"{normalized}"'
