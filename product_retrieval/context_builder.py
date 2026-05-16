from __future__ import annotations

from product_retrieval.models import SearchResult


def build_evidence_text(search_results: list[SearchResult]) -> str:
    blocks = []
    for index, result in enumerate(search_results, start=1):
        blocks.append(
            "\n".join(
                [
                    f"RESULT {index}",
                    f"TITLE: {result.title}",
                    f"URL: {result.url}",
                    f"SNIPPET: {result.snippet}",
                ]
            )
        )
    return "\n\n".join(blocks)
