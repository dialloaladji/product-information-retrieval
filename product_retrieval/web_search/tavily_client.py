from __future__ import annotations

import json
from urllib import request

from product_retrieval.models import SearchResult
from product_retrieval.web_search.base import WebSearchClient


_BARCODE_LOOKUP_SITES = [
    "gtin.info",
    "barcodelookup.com",
    "buycott.com",
    "digit-eyes.com",
    "ean-search.org",
    "open.fda.gov",
    "upcitemdb.com",
    "go-upc.com",
    "dynamsoft.com",
]


class TavilyClient(WebSearchClient):
    def __init__(self, api_key: str, timeout_seconds: int = 30) -> None:
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": "basic",
            "include_answer": False,
            "include_raw_content": False,
            "max_results": max_results,
            "exclude_domains": _BARCODE_LOOKUP_SITES,
        }
        http_request = request.Request(
            "https://api.tavily.com/search",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(http_request, timeout=self.timeout_seconds) as response:  # nosec B310 — fixed HTTPS URL
            data = json.loads(response.read().decode("utf-8"))

        return [
            SearchResult(
                title=item.get("title") or "",
                url=item["url"],
                snippet=item.get("content") or item.get("raw_content") or "",
                source="tavily",
            )
            for item in data.get("results", [])
            if item.get("url")
        ]
