# Product Information Retrieval

Pipeline for enriching industrial and electrical products from a GTIN/EAN barcode.

## What it does

1. Receives a GTIN (8, 12, 13, or 14 digits)
2. Searches the web for product information (Tavily / SerpAPI)
3. Extracts structured data with an LLM (Groq — Llama 3.1)
4. Stores the result in a database
5. Returns: manufacturer, MPN, product name, category, technical specs

Out-of-scope products (food, clothing, consumer electronics) are automatically rejected.

## Getting started

```bash
cp .env.example .env
# Fill in your API keys in .env

pip install -e .
uvicorn product_retrieval.api:app --reload
```

## Endpoints

| Method | Route | Description |
|--------|-------|-------------|
| `POST` | `/retrieve` | Enrich a GTIN |
| `POST` | `/debug/retrieve` | Same with internal details |
| `GET` | `/runs` | Pipeline call history |
| `GET` | `/metrics` | Prometheus metrics |
| `GET` | `/health` | Health check |

## Stack

- **FastAPI** — REST API
- **Groq (Llama 3.1 8B)** — LLM extraction
- **Tavily** — web search
- **PostgreSQL / SQLite** — storage (Postgres via Docker, SQLite locally)
- **Langfuse** — LLM observability

## Docker

```bash
docker compose up --build
```

## Tests

```bash
pytest
```
