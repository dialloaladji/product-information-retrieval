from __future__ import annotations

from product_retrieval.config import Settings
from product_retrieval.web_search.base import WebSearchClient
from product_retrieval.web_search.serpapi_client import SerpApiClient
from product_retrieval.web_search.tavily_client import TavilyClient


def create_search_client(provider: str, settings: Settings) -> WebSearchClient:
    normalized = provider.lower()
    if normalized == "tavily":
        if not settings.tavily_api_key:
            raise ValueError("TAVILY_API_KEY is required for Tavily search.")
        return TavilyClient(settings.tavily_api_key)
    if normalized == "serpapi":
        if not settings.serpapi_api_key:
            raise ValueError("SERPAPI_API_KEY is required for SerpAPI search.")
        return SerpApiClient(settings.serpapi_api_key)
    raise ValueError(f"Unsupported web search provider: {provider}")

