from __future__ import annotations

from product_retrieval.config import Settings
from product_retrieval.models import ProductEnrichmentOutput, SearchResult, StorageStatus
from product_retrieval.storage.qdrant_store import QdrantStore
from product_retrieval.storage.sqlite_store import SQLiteStore
from product_retrieval.storage.postgres_store import PostgresStore


class StorageCoordinator:
    def __init__(self, settings: Settings) -> None:
        if settings.database_url:
            self.store = PostgresStore(settings.database_url)
        else:
            self.store = SQLiteStore(settings.sqlite_path)
        self.qdrant = (
            QdrantStore(
                url=settings.qdrant_url,
                collection=settings.qdrant_collection,
                api_key=settings.qdrant_api_key,
            )
            if settings.qdrant_url
            else None
        )

    def load(self, gtin: str) -> ProductEnrichmentOutput | None:
        return self.store.load(gtin)

    def log_run(self, gtin: str, **kwargs) -> None:
        self.store.log_run(gtin, **kwargs)

    def save(self, output: ProductEnrichmentOutput, evidence: list[SearchResult]) -> StorageStatus:
        row_id = self.store.save(output, evidence)
        qdrant_id: str | None = None
        if self.qdrant:
            qdrant_id = self.qdrant.save(output, evidence)
        return StorageStatus(sqlite_id=row_id, qdrant_id=qdrant_id)
