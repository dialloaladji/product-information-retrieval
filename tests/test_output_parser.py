from __future__ import annotations

from llm.output_parser import parse_llm_json
from llm.extractor import normalize_llm_payload
from product_retrieval.models import ProductEnrichmentOutput


def test_output_parser_validates_product_output() -> None:
    parsed = parse_llm_json(
        {
            "original_reference": "1",
            "product_name": None,
            "manufacturer": None,
            "manufacturer_product_id": None,
            "serial_number": None,
            "item_class": None,
            "category": None,
            "description": None,
            "technical_specs": {},
            "source_urls": [],
            "confidence_score": 0,
            "missing_fields": [],
        },
        ProductEnrichmentOutput,
    )
    assert parsed.original_reference == "1"


def test_normalize_ecommerce_shaped_output() -> None:
    normalized = normalize_llm_payload(
        {
            "brand": "ABB",
            "model": "ACH580",
            "price": 123,
            "currency": "EUR",
        },
        "6438177516927",
    )

    assert normalized == {
        "original_reference": "6438177516927",
        "product_name": None,
        "manufacturer": "ABB",
        "manufacturer_product_id": "ACH580",
        "serial_number": None,
        "item_class": None,
        "category": None,
        "description": None,
        "technical_specs": {},
        "source_urls": [],
        "confidence_score": 0.0,
        "missing_fields": [],
        "is_electrical_or_industrial_product": True,
    }


def test_normalize_removes_urls_not_in_evidence() -> None:
    normalized = normalize_llm_payload(
        {
            "original_reference": "http://example.com/product123",
            "technical_specs": None,
            "confidence_score": None,
            "source_urls": ["http://example.com/product123", "https://abb.example/product"],
        },
        "6438177516927",
        ["https://abb.example/product"],
    )

    assert normalized["original_reference"] == "6438177516927"
    assert normalized["technical_specs"] == {}
    assert normalized["confidence_score"] == 0.0
    assert normalized["source_urls"] == ["https://abb.example/product"]
