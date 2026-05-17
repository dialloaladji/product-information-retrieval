from functools import lru_cache
import sqlite3
import time
from urllib.error import URLError

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.responses import PlainTextResponse

from llm.output_parser import OutputParserError
from product_retrieval.config import Settings
from product_retrieval.models import DebugRetrieveOutput, ProductEnrichmentOutput, RetrieveRequest
from product_retrieval.monitoring import metrics
from product_retrieval.pipeline import ProductEnrichmentPipeline


class HealthResponse(BaseModel):
    status: str


@lru_cache(maxsize=1)
def get_pipeline() -> ProductEnrichmentPipeline:
    return ProductEnrichmentPipeline(settings=Settings.from_env())


limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Product Information Retrieval")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def monitor_http_requests(request: Request, call_next):
    started_at = time.perf_counter()
    status_code = "500"
    metrics.increment_gauge("http_active_requests")
    try:
        response = await call_next(request)
        status_code = str(response.status_code)
        return response
    finally:
        elapsed_seconds = time.perf_counter() - started_at
        metrics.increment_gauge("http_active_requests", delta=-1.0)
        route = request.scope.get("route")
        path = getattr(route, "path", request.url.path)
        method = request.method
        metrics.increment("http_requests_total", method=method, path=path, status=status_code)
        if status_code.startswith(("4", "5")):
            metrics.increment("http_errors_total", method=method, path=path, status=status_code)
        metrics.observe(
            "http_request_latency_seconds",
            elapsed_seconds,
            method=method,
            path=path,
            status=status_code,
        )
        # rolling RPS gauge — updated on every request so /metrics always shows current rate
        metrics.record_rate("http_request_throughput_rps", method=method, path=path)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/metrics")
def prometheus_metrics() -> PlainTextResponse:
    return PlainTextResponse(metrics.render_prometheus(), media_type="text/plain; version=0.0.4")


@app.post("/retrieve", response_model=ProductEnrichmentOutput)
@limiter.limit("20/minute")
def retrieve(
    request: Request,
    body: RetrieveRequest,
    pipeline: ProductEnrichmentPipeline = Depends(get_pipeline),
) -> ProductEnrichmentOutput:
    try:
        result = pipeline.run(body.gtin, body.context)
        if not result.enrichment.is_electrical_or_industrial_product:
            raise HTTPException(
                status_code=422,
                detail="Out of scope: this GTIN does not appear to be an electrical or industrial product.",
            )
        return result.enrichment
    except HTTPException:
        raise
    except (URLError, OutputParserError) as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.get("/runs")
def list_runs(gtin: str | None = None, limit: int = 50) -> list[dict]:
    settings = Settings.from_env()
    with sqlite3.connect(settings.sqlite_path) as conn:
        conn.row_factory = sqlite3.Row
        if gtin:
            rows = conn.execute(
                "SELECT * FROM pipeline_runs WHERE gtin = ? ORDER BY id DESC LIMIT ?",
                (gtin, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [dict(row) for row in rows]


@app.post("/debug/retrieve", response_model=DebugRetrieveOutput)
@limiter.limit("20/minute")
def debug_retrieve(
    request: Request,
    body: RetrieveRequest,
    pipeline: ProductEnrichmentPipeline = Depends(get_pipeline),
) -> DebugRetrieveOutput:
    try:
        return pipeline.debug_run(body.gtin, body.context)
    except Exception as error:
        return DebugRetrieveOutput(
            built_query=body.gtin,
            primary_provider_used=pipeline.settings.web_search_primary,
            raw_search_results=[],
            top_3_evidence_items=[],
            error=str(error),
        )
