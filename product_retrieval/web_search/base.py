from __future__ import annotations

from abc import ABC, abstractmethod

from product_retrieval.models import SearchResult


class WebSearchClient(ABC):
    @abstractmethod
    def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        """Return search snippets and source URLs. No business extraction here."""

