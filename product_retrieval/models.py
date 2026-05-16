from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

_VALID_GTIN_LENGTHS = {8, 12, 13, 14}


class RetrieveRequest(BaseModel):
    gtin: str = Field(min_length=1)

    @field_validator("gtin")
    @classmethod
    def validate_gtin(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned.isdigit() or len(cleaned) not in _VALID_GTIN_LENGTHS:
            raise ValueError(
                f"Invalid GTIN '{cleaned}': must be 8, 12, 13, or 14 digits."
            )
        return cleaned


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    source: str


class ProductEnrichmentOutput(BaseModel):
    model_config = {"extra": "forbid"}

    original_reference: str
    product_name: str | None
    manufacturer: str | None
    manufacturer_product_id: str | None
    serial_number: str | None
    item_class: str | None
    category: str | None
    description: str | None
    technical_specs: dict[str, str] = Field(default_factory=dict)
    source_urls: list[str]
    confidence_score: float = Field(ge=0, le=1)
    missing_fields: list[str] = Field(default_factory=list)
    is_electrical_or_industrial_product: bool = True


class StorageStatus(BaseModel):
    sqlite_id: int | None = None
    qdrant_id: str | None = None


class PipelineResult(BaseModel):
    enrichment: ProductEnrichmentOutput
    raw_search_results: list[SearchResult]
    evidence_items: list[SearchResult]
    storage_status: StorageStatus
    timings_ms: dict[str, float] = Field(default_factory=dict)


class DebugRetrieveOutput(BaseModel):
    built_query: str
    primary_provider_used: str
    fallback_provider_used: str | None = None
    raw_search_results: list[SearchResult]
    top_3_evidence_items: list[SearchResult]
    raw_llm_output: str | None = None
    parsed_output: ProductEnrichmentOutput | None = None
    storage_status: StorageStatus | None = None
    error: str | None = None
    timings_ms: dict[str, float] = Field(default_factory=dict)
