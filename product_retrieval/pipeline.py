from __future__ import annotations

import logging
import time

from llm.extractor import MockProductExtractor, ProductExtractor
from product_retrieval.config import Settings
from product_retrieval.models import DebugRetrieveOutput, PipelineResult, ProductEnrichmentOutput, SearchResult, StorageStatus
from product_retrieval.monitoring import metrics, timed_stage
from product_retrieval.query_builder import build_product_query
from product_retrieval.storage import StorageCoordinator
from product_retrieval.web_search import create_search_client

logger = logging.getLogger(__name__)


class ProductEnrichmentPipeline:
    def __init__(
        self,
        settings: Settings | None = None,
        extractor: ProductExtractor | MockProductExtractor | None = None,
        storage: StorageCoordinator | None = None,
    ) -> None:
        self.settings = settings or Settings.from_env()
        self.extractor = extractor or (
            MockProductExtractor() if self.settings.use_mock_llm else ProductExtractor(self.settings)
        )
        self.storage = storage or StorageCoordinator(self.settings)

    def run(self, gtin: str) -> PipelineResult:
        result, _ = self._execute(gtin)
        return result

    def debug_run(self, gtin: str) -> DebugRetrieveOutput:
        result, debug = self._execute(gtin)
        return DebugRetrieveOutput(
            built_query=debug["built_query"],
            primary_provider_used=self.settings.web_search_primary,
            fallback_provider_used=debug["fallback_provider_used"],
            raw_search_results=result.raw_search_results,
            top_3_evidence_items=result.evidence_items,
            raw_llm_output=debug["raw_llm_output"],
            parsed_output=result.enrichment,
            storage_status=result.storage_status,
            timings_ms=result.timings_ms,
        )

    def _execute(self, gtin: str) -> tuple[PipelineResult, dict]:
        cached = self.storage.load(gtin)
        if cached is not None:
            logger.info("Cache hit for GTIN %s", gtin)
            metrics.increment("pipeline_requests_total", endpoint="retrieve")
            metrics.increment("pipeline_cache_hits_total")
            self.storage.log_run(
                gtin,
                cache_hit=True,
                confidence_score=cached.confidence_score,
                timings_ms={"total": 0.0},
                search_results_count=0,
                fallback_provider=None,
                error=None,
            )
            return (
                PipelineResult(
                    enrichment=cached,
                    raw_search_results=[],
                    evidence_items=[],
                    storage_status=StorageStatus(),
                    timings_ms={"total": 0.0},
                ),
                {"built_query": gtin, "fallback_provider_used": None, "raw_llm_output": None},
            )

        timings_ms: dict[str, float] = {}
        started_at = time.perf_counter()
        with timed_stage("query_builder", timings_ms):
            query = build_product_query(gtin)
        with timed_stage("web_search", timings_ms):
            raw_results, fallback_provider_used = self._search(query)
        evidence_items = select_evidence_items(gtin, raw_results)
        with timed_stage("llm_extractor", timings_ms):
            enrichment, raw_llm_output = self.extractor.extract(gtin, evidence_items)
        with timed_stage("storage", timings_ms):
            storage_status = self.storage.save(enrichment, evidence_items)
        timings_ms["total"] = round((time.perf_counter() - started_at) * 1000, 3)
        metrics.increment("pipeline_requests_total", endpoint="retrieve")
        metrics.gauge("search_results_count", len(raw_results))
        metrics.gauge("confidence_score", enrichment.confidence_score)
        result_label = "success" if enrichment.confidence_score > 0 else "failure"
        metrics.increment("extraction_success_total", result=result_label)
        self.storage.log_run(
            gtin,
            cache_hit=False,
            confidence_score=enrichment.confidence_score,
            timings_ms=timings_ms,
            search_results_count=len(raw_results),
            fallback_provider=fallback_provider_used,
            error=None,
        )
        return (
            PipelineResult(
                enrichment=enrichment,
                raw_search_results=raw_results,
                evidence_items=evidence_items,
                storage_status=storage_status,
                timings_ms=timings_ms,
            ),
            {
                "built_query": query,
                "fallback_provider_used": fallback_provider_used,
                "raw_llm_output": raw_llm_output,
            },
        )

    def _search(self, query: str) -> tuple[list[SearchResult], str | None]:
        primary = create_search_client(self.settings.web_search_primary, self.settings)
        primary_results = primary.search(query, max_results=self.settings.web_search_max_results)
        if primary_results:
            return primary_results[:3], None
        fallback = create_search_client(self.settings.web_search_fallback, self.settings)
        fallback_results = fallback.search(query, max_results=self.settings.web_search_max_results)
        return fallback_results[:3], self.settings.web_search_fallback


def select_evidence_items(gtin: str, results: list[SearchResult]) -> list[SearchResult]:
    exact_matches = [
        result
        for result in results
        if gtin in f"{result.title}\n{result.url}\n{result.snippet}"
    ]
    return (exact_matches or results)[:3]
