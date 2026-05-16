from __future__ import annotations

from llm.prompts import SYSTEM_EXTRACTION_PROMPT
from llm.prompts import build_user_extraction_prompt


def test_system_prompt_has_no_unescaped_empty_template_variable() -> None:
    assert "{}" not in SYSTEM_EXTRACTION_PROMPT


def test_system_prompt_rejects_ecommerce_fields() -> None:
    assert "Do not return brand, model, price" in SYSTEM_EXTRACTION_PROMPT


def test_user_prompt_pins_gtin_and_evidence_urls() -> None:
    prompt = build_user_extraction_prompt("123", "evidence", "format")
    assert "original_reference must be exactly: 123" in prompt
    assert "source_urls must contain only URLs explicitly present in the evidence" in prompt
