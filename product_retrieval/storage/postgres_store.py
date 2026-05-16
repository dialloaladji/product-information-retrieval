from __future__ import annotations

import json
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

from product_retrieval.models import ProductEnrichmentOutput, SearchResult


class PostgresStore:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self._init_schema()

    def _conn(self):
        return psycopg2.connect(self.dsn)

    def load(self, gtin: str) -> ProductEnrichmentOutput | None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT payload_json FROM product_enrichment
                       WHERE original_reference = %s
                       ORDER BY id DESC LIMIT 1""",
                    (gtin,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        result = ProductEnrichmentOutput(**json.loads(row[0]))
        if result.confidence_score == 0.0:
            return None
        return result

    def save(self, output: ProductEnrichmentOutput, evidence: list[SearchResult]) -> int:
        payload = json.dumps(output.model_dump(mode="json"), ensure_ascii=False)
        evidence_payload = json.dumps([i.model_dump(mode="json") for i in evidence], ensure_ascii=False)
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO product_enrichment
                       (original_reference, manufacturer_product_id, manufacturer, payload_json, evidence_json, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
                    (
                        output.original_reference,
                        output.manufacturer_product_id,
                        output.manufacturer,
                        payload,
                        evidence_payload,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                return int(cur.fetchone()[0])

    def log_run(
        self,
        gtin: str,
        *,
        cache_hit: bool,
        confidence_score: float,
        timings_ms: dict[str, float],
        search_results_count: int,
        fallback_provider: str | None,
        error: str | None,
    ) -> None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO pipeline_runs (
                        gtin, timestamp, cache_hit, confidence_score,
                        duration_ms_total, duration_ms_query_builder,
                        duration_ms_web_search, duration_ms_llm_extractor,
                        duration_ms_storage, search_results_count,
                        fallback_provider, error
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        gtin,
                        datetime.now(timezone.utc).isoformat(),
                        cache_hit,
                        confidence_score,
                        timings_ms.get("total"),
                        timings_ms.get("query_builder"),
                        timings_ms.get("web_search"),
                        timings_ms.get("llm_extractor"),
                        timings_ms.get("storage"),
                        search_results_count,
                        fallback_provider,
                        error,
                    ),
                )

    def _init_schema(self) -> None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS product_enrichment (
                        id SERIAL PRIMARY KEY,
                        original_reference TEXT NOT NULL,
                        manufacturer_product_id TEXT,
                        manufacturer TEXT,
                        payload_json TEXT NOT NULL,
                        evidence_json TEXT NOT NULL DEFAULT '[]',
                        created_at TEXT NOT NULL
                    )
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_product_reference
                    ON product_enrichment(original_reference)
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS pipeline_runs (
                        id SERIAL PRIMARY KEY,
                        gtin TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        cache_hit BOOLEAN NOT NULL,
                        confidence_score REAL,
                        duration_ms_total REAL,
                        duration_ms_query_builder REAL,
                        duration_ms_web_search REAL,
                        duration_ms_llm_extractor REAL,
                        duration_ms_storage REAL,
                        search_results_count INTEGER,
                        fallback_provider TEXT,
                        error TEXT
                    )
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_runs_gtin ON pipeline_runs(gtin)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_runs_timestamp ON pipeline_runs(timestamp)
                """)
