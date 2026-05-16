# Product Information Retrieval

Pipeline d'enrichissement de produits industriels et électriques à partir d'un GTIN/EAN.

## Ce que ça fait

1. Reçoit un GTIN (8, 12, 13 ou 14 chiffres)
2. Cherche le produit sur le web (Tavily / SerpAPI)
3. Extrait les informations avec un LLM (Groq — Llama 3.1)
4. Stocke le résultat en base de données
5. Retourne : fabricant, MPN, nom du produit, catégorie, specs techniques

Produits hors scope (alimentaire, habillement, électronique grand public) → rejetés automatiquement.

## Lancer le projet

```bash
cp .env.example .env
# Remplir les clés API dans .env

pip install -e .
uvicorn product_retrieval.api:app --reload
```

## Endpoints

| Méthode | Route | Description |
|---------|-------|-------------|
| `POST` | `/retrieve` | Enrichissement d'un GTIN |
| `POST` | `/debug/retrieve` | Idem avec détails internes |
| `GET` | `/runs` | Historique des appels pipeline |
| `GET` | `/metrics` | Métriques Prometheus |
| `GET` | `/health` | Healthcheck |

## Stack

- **FastAPI** — API REST
- **Groq (Llama 3.1 8B)** — extraction LLM
- **Tavily** — recherche web
- **PostgreSQL / SQLite** — stockage (Postgres via Docker, SQLite en local)
- **Langfuse** — observabilité LLM

## Docker

```bash
docker compose up --build
```

## Tests

```bash
pytest
```
