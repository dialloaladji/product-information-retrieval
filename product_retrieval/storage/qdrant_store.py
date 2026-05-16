from __future__ import annotations

import hashlib
import json
from urllib import request

from product_retrieval.models import ProductEnrichmentOutput, SearchResult


class QdrantStore:
    def __init__(
        self,
        url: str,
        collection: str = "product_enrichment",
        api_key: str | None = None,
        timeout_seconds: int = 30,
    ) -> None:
        self.url = url.rstrip("/")
        self.collection = collection
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self._ensure_collection()

    def save(self, output: ProductEnrichmentOutput, evidence: list[SearchResult]) -> str:
        point_id = hashlib.sha256(output.original_reference.encode("utf-8")).hexdigest()
        payload = {
            "output": output.model_dump(mode="json"),
            "evidence": [item.model_dump(mode="json") for item in evidence],
        }
        body = {
            "points": [
                {
                    "id": point_id,
                    "vector": [float(output.confidence_score)],
                    "payload": payload,
                }
            ]
        }
        self._request("PUT", f"/collections/{self.collection}/points?wait=true", body)
        return point_id

    def _ensure_collection(self) -> None:
        body = {"vectors": {"size": 1, "distance": "Cosine"}}
        try:
            self._request("PUT", f"/collections/{self.collection}", body)
        except Exception:
            self._request("GET", f"/collections/{self.collection}", None)

    def _request(self, method: str, path: str, body: dict | None) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["api-key"] = self.api_key
        data = json.dumps(body).encode("utf-8") if body is not None else None
        http_request = request.Request(f"{self.url}{path}", data=data, headers=headers, method=method)
        with request.urlopen(http_request, timeout=self.timeout_seconds) as response:  # nosec B310 — fixed HTTPS URL
            return json.loads(response.read().decode("utf-8") or "{}")
