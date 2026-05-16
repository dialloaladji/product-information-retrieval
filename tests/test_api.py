from __future__ import annotations

from fastapi.testclient import TestClient

from product_retrieval.api import app, get_pipeline
from product_retrieval.models import (
    DebugRetrieveOutput,
    ProductEnrichmentOutput,
    SearchResult,
    StorageStatus,
)


def output(gtin: str) -> ProductEnrichmentOutput:
    return ProductEnrichmentOutput(
        original_reference=gtin,
        product_name="Test Product",
        manufacturer="ABB",
        manufacturer_product_id="MPN-1",
        serial_number=None,
        item_class=None,
        category=None,
        description=None,
        technical_specs={},
        source_urls=["https://example.com/product"],
        confidence_score=0.8,
        missing_fields=[],
    )


class StubPipeline:
    settings = type("Settings", (), {"web_search_primary": "tavily"})()

    def run(self, gtin: str):
        return type("Result", (), {"enrichment": output(gtin)})()

    def debug_run(self, gtin: str) -> DebugRetrieveOutput:
        evidence = [SearchResult(title="T", url="https://example.com/product", snippet="S", source="tavily")]
        return DebugRetrieveOutput(
            built_query=gtin,
            primary_provider_used="tavily",
            fallback_provider_used=None,
            raw_search_results=evidence,
            top_3_evidence_items=evidence,
            raw_llm_output='{"ok": true}',
            parsed_output=output(gtin),
            storage_status=StorageStatus(sqlite_id=1),
            timings_ms={"total": 1.0},
        )


def test_health_and_metrics() -> None:
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}
    assert "http_requests_total" in client.get("/metrics").text


def test_retrieve_uses_gtin_request_schema() -> None:
    app.dependency_overrides[get_pipeline] = lambda: StubPipeline()
    client = TestClient(app)
    response = client.post("/retrieve", json={"gtin": "6438177516927"})
    assert response.status_code == 200
    assert response.json()["original_reference"] == "6438177516927"
    app.dependency_overrides.clear()


def test_debug_retrieve_returns_simple_debug_shape() -> None:
    app.dependency_overrides[get_pipeline] = lambda: StubPipeline()
    client = TestClient(app)
    response = client.post("/debug/retrieve", json={"gtin": "6438177516927"})
    body = response.json()
    assert body["built_query"] == "6438177516927"
    assert body["primary_provider_used"] == "tavily"
    assert body["fallback_provider_used"] is None
    assert body["top_3_evidence_items"][0]["url"] == "https://example.com/product"
    app.dependency_overrides.clear()
