# velov-assistant

An AI assistant for Lyon's self-service bike network (Vélo'v) with:

- **RAG** — answers about policies, pricing and rules from the official FAQ.
- **Function calling** — real-time station availability and nearest-bike lookups.

## Problem description

Tourists and newcomers in Lyon need quick information about how Vélo'v works. That
information lives in the FAQ on the Vélo'v website, which is tedious to browse. The
assistant answers FAQ questions and checks real-time bike availability, e.g.:

- "Which is the nearest station with bikes available near Part-Dieu?"
- "Can I book several bikes with one card?"

## Project layout

The repo root is the single project home — the dlthub workspace and the Velo'v
application live side by side. Run all commands from the repo root.

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the full mermaid diagram,
directory structure and module-by-module plan.

### Agent (runtime)

```mermaid
flowchart TB
    U(["User"]) --> UI["pydantic-ai<br/>web chat UI"]
    UI --> AG["<img src='https://cdn.simpleicons.org/pydantic' width='16'/> pydantic-ai Agent<br/>(system prompt + tools)"]

    subgraph TOOL["Tool path"]
        FAQ["search_faq<br/>(hybrid dense + BM25 + rerank)"]
        QD[("<img src='https://cdn.simpleicons.org/qdrant' width='16'/> Qdrant<br/>dense vectors")]
        ST["station tools<br/>geocode_place · stations_by_name · stations_nearby<br/>get_station_availability"]
        GL["Grand Lyon API<br/>stations (httpx + tenacity)"]
        GEO["Photon geocoder"]
    end

    AG --> FAQ --> QD
    AG --> ST --> GL
    ST --> GEO

    LLM["LLM<br/>(OpenCode Zen · deepseek)"]
    QD --> LLM
    GL --> LLM
    LLM --> ANS(["answer"])
```

### Ingestion (dlt)

```mermaid
flowchart TB
    subgraph SRC["Source — Cyclocity API"]
        AUTH["POST /auth/environments/PRD/client_tokens<br/>code + key → access token"]
        SEARCH["POST /contracts/lyon/faqs/search"]
    end

    FALLBACK[("data/faq/faq.json<br/>cached fallback")]

    subgraph PIPE["dlt pipeline — velov_faq"]
        RES["@dlt.resource faq<br/>primary_key=id, replace"]
        CHK["chunk + clean<br/>topic + question + answer → content"]
        ADAPTER["qdrant_adapter<br/>(embed='content')"]
    end

    EMBED["FastEmbed<br/>BAAI/bge-small-en-v1.5"]
    QD[("<img src='https://cdn.simpleicons.org/qdrant' width='16'/> Qdrant<br/>collection velov_faq")]

    AUTH --> SEARCH --> RES
    SEARCH -. on failure .-> FALLBACK --> RES
    RES --> CHK --> ADAPTER --> EMBED --> QD
```

> Tech logos come from [Simple Icons](https://simpleicons.org); they may not render in
> every markdown viewer, but the text labels stay readable.

## Quick start (Docker)

```bash
cp .env.example .env          # fill in OPENAI_API_KEY (OpenCode Zen) + LLM_MODEL
docker compose up --build
```

Services: Qdrant (`:6333`), app (`:8000`). Open http://localhost:8000 for the web chat UI.

## Local development

```bash
uv sync                                       # install deps
uv run ingest                                 # dlt: fetch FAQ -> chunk -> embed -> Qdrant
uv run chat                                   # local: web chat UI + local Qdrant (APP_ENV=local)
```

Two serving modes (selected via `APP_ENV`):

- **`local`** (default) — `agent.to_web()` web chat UI, Qdrant local (`http://localhost:6333`), config `.env`.
- **`dev`** — FastAPI endpoint streaming UI events (Vercel AI Data Stream protocol), Qdrant distant, config `.env.dev`:

```bash
APP_ENV=dev uv run chat   # POST /chat (SSE) + GET /health on :8000
```

Other commands: `uv run eval`, `uv run eval-gen`, `uv run eval-retrieval`, `uv run eval-llm`.
Lint/format: `uv run ruff check .` and `uv run ruff format .`.
Typing: `uv run ty check`
Pre-commit (optional only if you want to dev on this project): `prek install --config .pre-commit.yaml`

## Ingestion (dlt)

- `ingestion/faq_pipeline.py` — fetches the FAQ from the Cyclocity API (anonymous
  client-token exchange), chunks it and loads it into Qdrant with dense embeddings via
  `qdrant_adapter(resource, embed="content")` (FastEmbed model). Falls back to
  `data/faq/faq.json` if the live fetch fails.

Qdrant destination config lives in `.dlt/config.toml`; override with
`DESTINATION__QDRANT__QD_LOCATION` / `DESTINATION__QDRANT__MODEL`.

## Retrieval & RAG

- **FAQ search tool** (`app/main.py::search_faq`) — the agent calls it to answer policy/pricing/rules questions.
- **Hybrid search** (`app/rag/retriever.py`) — dense (FastEmbed, Qdrant) + sparse
  (BM25) fused with RRF; three modes evaluable separately.
- **Re-ranking** — cross-encoder re-scores the fused top-K.

## Evaluation

```bash
uv run eval-gen         # generate ground-truth questions from the FAQ
uv run eval-retrieval   # hit rate / MRR (dense vs sparse vs hybrid)
uv run eval-llm         # LLM-as-judge
uv run eval             # run retrieval + LLM evals together
```

## Reproducibility

All dependency versions are pinned in `pyproject.toml` (locked via `uv.lock`).
