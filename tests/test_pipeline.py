from __future__ import annotations

from pathlib import Path

from llm.extractor import MockProductExtractor
from product_retrieval.config import Settings
from product_retrieval.models import SearchResult
from product_retrieval.pipeline import ProductEnrichmentPipeline, select_evidence_items
from product_retrieval.query_builder import build_product_query
from product_retrieval.storage import StorageCoordinator


class Client:
    def __init__(self, results: list[SearchResult]) -> None:
        self.results = results
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, max_results: int) -> list[SearchResult]:
        self.calls.append((query, max_results))
        return self.results


def results(count: int, source: str = "tavily") -> list[SearchResult]:
    return [
        SearchResult(title=f"R{i}", url=f"https://example.com/{i}", snippet="snippet", source=source)
        for i in range(count)
    ]


def test_query_builder_builds_enriched_query() -> None:
    assert build_product_query("6438177516927") == "6438177516927 manufacturer product specifications datasheet"


def test_primary_search_keeps_top_three(monkeypatch, tmp_path: Path) -> None:
    primary = Client(results(5))
    fallback = Client(results(2, "serpapi"))
    monkeypatch.setattr(
        "product_retrieval.pipeline.create_search_client",
        lambda provider, settings: primary if provider == "tavily" else fallback,
    )
    settings = Settings(use_mock_llm=True, sqlite_path=str(tmp_path / "db.sqlite3"))
    pipeline = ProductEnrichmentPipeline(settings, MockProductExtractor(), StorageCoordinator(settings))
    result = pipeline.run("6438177516927")
    assert len(result.raw_search_results) == 3
    assert fallback.calls == []


def test_fallback_runs_only_when_primary_empty(monkeypatch, tmp_path: Path) -> None:
    primary = Client([])
    fallback = Client(results(2, "serpapi"))
    monkeypatch.setattr(
        "product_retrieval.pipeline.create_search_client",
        lambda provider, settings: primary if provider == "tavily" else fallback,
    )
    settings = Settings(use_mock_llm=True, sqlite_path=str(tmp_path / "db.sqlite3"))
    pipeline = ProductEnrichmentPipeline(settings, MockProductExtractor(), StorageCoordinator(settings))
    debug = pipeline.debug_run("6438177516927")
    assert debug.built_query == "6438177516927 manufacturer product specifications datasheet"
    assert debug.fallback_provider_used == "serpapi"
    assert len(debug.top_3_evidence_items) == 2


def test_evidence_prefers_results_containing_gtin() -> None:
    all_results = [
        SearchResult(title="ABB product", url="https://abb.example/product", snippet="GTIN 6438177516927", source="tavily"),
        SearchResult(title="Barcode guide", url="https://barcode.example", snippet="generic", source="tavily"),
    ]

    evidence = select_evidence_items("6438177516927", all_results)

    assert [item.url for item in evidence] == ["https://abb.example/product"]
