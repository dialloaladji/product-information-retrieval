from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from product_retrieval.models import ProductEnrichmentOutput, SearchResult


class SQLiteStore:
    def __init__(self, path: str) -> None:
        self.path = path
        self._init_schema()

    def load(self, gtin: str) -> ProductEnrichmentOutput | None:
        with sqlite3.connect(self.path) as connection:
            row = connection.execute(
                """SELECT payload_json FROM product_enrichment
                   WHERE original_reference = ?
                   ORDER BY id DESC LIMIT 1""",
                (gtin,),
            ).fetchone()
        if row is None:
            return None
        result = ProductEnrichmentOutput(**json.loads(row[0]))
        if result.confidence_score == 0.0:
            return None
        return result

    def save(self, output: ProductEnrichmentOutput, evidence: list[SearchResult]) -> int:
        payload = output.model_dump(mode="json")
        evidence_payload = [item.model_dump(mode="json") for item in evidence]
        with sqlite3.connect(self.path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO product_enrichment
                (original_reference, manufacturer_product_id, manufacturer, payload_json, evidence_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    output.original_reference,
                    output.manufacturer_product_id,
                    output.manufacturer,
                    json.dumps(payload, ensure_ascii=False),
                    json.dumps(evidence_payload, ensure_ascii=False),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            return int(cursor.lastrowid)

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
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                INSERT INTO pipeline_runs (
                    gtin, timestamp, cache_hit, confidence_score,
                    duration_ms_total, duration_ms_query_builder,
                    duration_ms_web_search, duration_ms_llm_extractor,
                    duration_ms_storage, search_results_count,
                    fallback_provider, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    gtin,
                    datetime.now(timezone.utc).isoformat(),
                    int(cache_hit),
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
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS product_enrichment (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_reference TEXT NOT NULL,
                    manufacturer_product_id TEXT,
                    manufacturer TEXT,
                    payload_json TEXT NOT NULL,
                    evidence_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_product_reference ON product_enrichment(original_reference)"
            )
            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(product_enrichment)").fetchall()
            }
            if "evidence_json" not in columns:
                connection.execute(
                    "ALTER TABLE product_enrichment ADD COLUMN evidence_json TEXT NOT NULL DEFAULT '[]'"
                )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS pipeline_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    gtin TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    cache_hit INTEGER NOT NULL,
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
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_runs_gtin ON pipeline_runs(gtin)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_runs_timestamp ON pipeline_runs(timestamp)"
            )
