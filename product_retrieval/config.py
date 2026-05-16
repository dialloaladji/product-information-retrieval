from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_dotenv(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    use_mock_llm: bool = False
    llama_cpp_base_url: str = "http://127.0.0.1:8080/v1"
    llama_cpp_model: str = "qwen"
    llama_cpp_api_key: str = "dummy"
    llm_max_tokens: int = 258
    web_search_primary: str = "tavily"
    web_search_fallback: str = "serpapi"
    web_search_max_results: int = 3
    tavily_api_key: str | None = None
    serpapi_api_key: str | None = None
    database_url: str | None = None
    sqlite_path: str = "product_enrichment.sqlite3"
    qdrant_url: str | None = None
    qdrant_api_key: str | None = None
    qdrant_collection: str = "product_enrichment"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = "https://cloud.langfuse.com"

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        return cls(
            use_mock_llm=parse_bool(os.getenv("USE_MOCK_LLM"), cls.use_mock_llm),
            llama_cpp_base_url=os.getenv("LLAMA_CPP_BASE_URL", cls.llama_cpp_base_url),
            llama_cpp_model=os.getenv("LLAMA_CPP_MODEL", cls.llama_cpp_model),
            llama_cpp_api_key=os.getenv("LLAMA_CPP_API_KEY", cls.llama_cpp_api_key),
            llm_max_tokens=int(os.getenv("LLM_MAX_TOKENS", str(cls.llm_max_tokens))),
            web_search_primary=os.getenv("WEB_SEARCH_PRIMARY", cls.web_search_primary),
            web_search_fallback=os.getenv("WEB_SEARCH_FALLBACK", cls.web_search_fallback),
            web_search_max_results=int(os.getenv("WEB_SEARCH_MAX_RESULTS", str(cls.web_search_max_results))),
            tavily_api_key=os.getenv("TAVILY_API_KEY") or None,
            serpapi_api_key=os.getenv("SERPAPI_API_KEY") or None,
            database_url=os.getenv("DATABASE_URL") or None,
            sqlite_path=os.getenv("SQLITE_PATH", cls.sqlite_path),
            qdrant_url=os.getenv("QDRANT_URL") or None,
            qdrant_api_key=os.getenv("QDRANT_API_KEY") or None,
            qdrant_collection=os.getenv("QDRANT_COLLECTION", cls.qdrant_collection),
            langfuse_public_key=os.getenv("LANGFUSE_PUBLIC_KEY", ""),
            langfuse_secret_key=os.getenv("LANGFUSE_SECRET_KEY", ""),
            langfuse_base_url=os.getenv("LANGFUSE_BASE_URL", cls.langfuse_base_url),
        )
