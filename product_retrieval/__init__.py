__all__ = ["ProductEnrichmentPipeline"]


def __getattr__(name: str):
    if name == "ProductEnrichmentPipeline":
        from product_retrieval.pipeline import ProductEnrichmentPipeline

        return ProductEnrichmentPipeline
    raise AttributeError(name)
