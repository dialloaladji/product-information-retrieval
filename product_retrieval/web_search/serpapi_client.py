from __future__ import annotations

import json
from urllib import parse, request

from product_retrieval.models import SearchResult
from product_retrieval.web_search.base import WebSearchClient


class SerpApiClient(WebSearchClient):
    def __init__(self, api_key: str, timeout_seconds: int = 30) -> None:
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        params = parse.urlencode(
            {
                "engine": "google",
                "q": query,
                "api_key": self.api_key,
                "num": max_results,
            }
        )
        with request.urlopen(f"https://serpapi.com/search.json?{params}", timeout=self.timeout_seconds) as response:  # nosec B310 — fixed HTTPS URL
            data = json.loads(response.read().decode("utf-8"))

        return [
            SearchResult(
                title=item.get("title") or "",
                url=item["link"],
                snippet=item.get("snippet") or "",
                source="serpapi",
            )
            for item in data.get("organic_results", [])
            if item.get("link")
        ]
