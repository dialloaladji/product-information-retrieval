from __future__ import annotations

import pytest

from llm.extractor import (
    _catalog_desc_from_snippet,
    _enrich_from_evidence,
    _looks_like_internal_id,
)
from product_retrieval.models import SearchResult


def _abb_evidence() -> list[SearchResult]:
    return [
        SearchResult(
            title="ACH580-BCR-240A-4+B056 | ABB",
            url="https://new.abb.com/products/3AUA0000225805/ach580-bcr-240a-4b056",
            snippet=(
                "6438177516927. Catalog Description: HVAC packaged drive with e-clipse bypass"
                " and circuit breaker disconnect. Number of Phases: 3-phase."
            ),
            source="tavily",
        )
    ]


def _empty_payload(gtin: str = "6438177516927") -> dict:
    return {
        "original_reference": gtin,
        "product_name": None,
        "manufacturer": None,
        "manufacturer_product_id": None,
        "serial_number": None,
        "item_class": None,
        "category": None,
        "description": None,
        "technical_specs": {},
        "source_urls": [],
        "confidence_score": 0.0,
        "missing_fields": ["product_name", "manufacturer", "manufacturer_product_id"],
    }


# --- _catalog_desc_from_snippet ---

def test_catalog_desc_extracted_before_next_sentence():
    snippet = (
        "6438177516927. Catalog Description: HVAC packaged drive with e-clipse bypass"
        " and circuit breaker disconnect. Number of Phases: 3-phase."
    )
    assert _catalog_desc_from_snippet(snippet) == (
        "HVAC packaged drive with e-clipse bypass and circuit breaker disconnect"
    )


def test_catalog_desc_strips_trailing_ellipsis():
    snippet = "Catalog Description: HVAC packaged ..."
    assert _catalog_desc_from_snippet(snippet) == "HVAC packaged"


def test_catalog_desc_returns_none_when_absent():
    assert _catalog_desc_from_snippet("No relevant content here.") is None


# --- _looks_like_internal_id ---

def test_all_alphanumeric_long_is_internal():
    assert _looks_like_internal_id("3AUA0000225805") is True


def test_mpn_with_hyphens_is_not_internal():
    assert _looks_like_internal_id("ACH580-BCR-240A-4+B056") is False


def test_short_value_is_not_internal():
    assert _looks_like_internal_id("ABC123") is False


# --- _enrich_from_evidence: ABB golden path ---

def test_fills_product_name_from_catalog_description():
    result = _enrich_from_evidence(_empty_payload(), _abb_evidence())
    assert result["product_name"] == (
        "HVAC packaged drive with e-clipse bypass and circuit breaker disconnect"
    )


def test_fills_manufacturer_product_id_from_title():
    result = _enrich_from_evidence(_empty_payload(), _abb_evidence())
    assert result["manufacturer_product_id"] == "ACH580-BCR-240A-4+B056"


def test_fills_manufacturer_from_title():
    result = _enrich_from_evidence(_empty_payload(), _abb_evidence())
    assert result["manufacturer"] == "ABB"


def test_stores_abb_internal_id_in_technical_specs():
    result = _enrich_from_evidence(_empty_payload(), _abb_evidence())
    assert result["technical_specs"]["abb_product_id"] == "3AUA0000225805"


def test_overrides_internal_id_with_title_mpn():
    payload = _empty_payload()
    payload["manufacturer_product_id"] = "3AUA0000225805"  # internal ID from LLM
    result = _enrich_from_evidence(payload, _abb_evidence())
    assert result["manufacturer_product_id"] == "ACH580-BCR-240A-4+B056"
    assert result["technical_specs"]["abb_product_id"] == "3AUA0000225805"


def test_keeps_proper_mpn_from_llm_when_title_absent():
    payload = _empty_payload()
    payload["manufacturer_product_id"] = "ACH580-BCR-240A-4"
    evidence = [
        SearchResult(
            title="Some generic page",
            url="https://example.com/product",
            snippet="A product.",
            source="tavily",
        )
    ]
    result = _enrich_from_evidence(payload, evidence)
    assert result["manufacturer_product_id"] == "ACH580-BCR-240A-4"


def test_removes_filled_fields_from_missing_fields():
    result = _enrich_from_evidence(_empty_payload(), _abb_evidence())
    assert "product_name" not in result["missing_fields"]
    assert "manufacturer" not in result["missing_fields"]
    assert "manufacturer_product_id" not in result["missing_fields"]


def test_catalog_desc_overrides_existing_product_name():
    # Catalog description is authoritative — replaces even a non-empty LLM-extracted name
    payload = _empty_payload()
    payload["product_name"] = "ACH580-BCR-240A-4+B056"  # MPN mistakenly used as name by LLM
    result = _enrich_from_evidence(payload, _abb_evidence())
    assert result["product_name"] == (
        "HVAC packaged drive with e-clipse bypass and circuit breaker disconnect"
    )


def test_product_name_preserved_when_no_catalog_desc():
    payload = _empty_payload()
    payload["product_name"] = "Already extracted name"
    evidence = [
        SearchResult(
            title="Some generic page",
            url="https://example.com/product",
            snippet="A product.",
            source="tavily",
        )
    ]
    result = _enrich_from_evidence(payload, evidence)
    assert result["product_name"] == "Already extracted name"


def test_title_without_pipe_is_ignored_for_mpn():
    evidence = [
        SearchResult(
            title="UPC Barcode Search — Look up any UPC, EAN, or ISBN",
            url="https://go-upc.com/barcode-lookup",
            snippet="No catalog description here.",
            source="tavily",
        )
    ]
    result = _enrich_from_evidence(_empty_payload(), evidence)
    assert result["manufacturer_product_id"] is None
    assert result["manufacturer"] is None


def test_multi_word_title_left_side_is_not_treated_as_mpn():
    # "UPC Barcode Guide & Free Lookup Tool | GTIN.info" — left side has spaces
    evidence = [
        SearchResult(
            title="UPC Barcode Guide & Free Lookup Tool | GTIN.info",
            url="https://www.gtin.info/upc/",
            snippet="No catalog description.",
            source="tavily",
        )
    ]
    result = _enrich_from_evidence(_empty_payload(), evidence)
    assert result["manufacturer_product_id"] is None
