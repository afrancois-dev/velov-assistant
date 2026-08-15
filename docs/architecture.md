# Vélo'v Assistant — System Architecture

End-to-end LLM-powered assistant for the Lyon Vélo'v bike-sharing network:

1. **RAG** — answers policy / pricing / rules questions from the official FAQ.
2. **Function calling** — real-time station availability & nearest-bike lookups.

---

## 1. System Architecture

```mermaid
flowchart TB
    subgraph Sources["External data sources"]
        FAQ["Vélo'v FAQ<br/>Cyclocity API<br/>(api.cyclocity.fr)"]
        STATIONS["Grand Lyon Data<br/>jcd_jcdecaux.jcdvelov (real-time)"]
        GEO["Grand Lyon geocoder<br/>(photon-bal, place -> lat/lng)"]
    end

    subgraph Ingestion["Ingestion (dlt)"]
        FETCH["FAQ fetch<br/>(client-token exchange)"]
        CHUNK["chunk + clean"]
        DLT["dlt pipeline<br/>qdrant_adapter(embed=content)"]
    end

    subgraph Store["Storage"]
        QDRANT[("Qdrant<br/>dense vectors + payload")]
    end

    subgraph App["Application (FastAPI)"]
        API["/chat endpoint"]
        ROUTER["intent router<br/>(RAG vs tool)"]
        REWRITE["query rewriting (pydantic-ai)"]
        RETR["hybrid retriever<br/>dense + BM25 + RRF"]
        RERANK["cross-encoder rerank"]
        LLM["LLM (pydantic-ai<br/>-> OpenCode Zen)"]
        TOOLS["function calling<br/>get_station_availability<br/>find_nearest_bikes(place)"]
    end

    subgraph Obs["Observability"]
        LOGFIRE["Pydantic Logfire<br/>traces + metrics"]
    end

    FAQ --> FETCH --> CHUNK --> DLT --> QDRANT

    API --> ROUTER
    ROUTER --> REWRITE --> RET --> RERANK --> LLM
    ROUTER --> TOOLS --> STATIONS
    TOOLS --> GEO

    API -.traces + metrics.-> LOGFIRE
```

## 2. Component workflow

### 2.1 Ingestion (`dlt` → Qdrant)
1. **Fetch** the FAQ from the Cyclocity API (the same backend the velov.grandlyon.com
   SPA calls): a public client `code`/`key` pair is posted to
   `/auth/environments/PRD/client_tokens` to obtain a short-lived access token, which
   then authorizes `/contracts/lyon/faqs/search`. Falls back to the cached
   `data/faq/faq.json` for reproducibility if the live fetch fails.
2. **Chunk** each Q/A into self-contained `content` strings (topic + question + answer).
3. **Embed & load** with dlt's Qdrant destination:
   - `qdrant_adapter(resource, embed="content")` marks the field to vectorize;
   - the destination generates **dense** embeddings via FastEmbed (`model` config).

### 2.2 Query path (RAG)
1. **Query rewriting** — a pydantic-ai agent expands the raw user question into 1–3
   retrieval variants.
2. **Retrieval** (three modes, evaluable):
   - `dense` — vector search on the dlt-embedded dense vectors (Qdrant);
   - `sparse` — BM25 over the in-memory FAQ corpus;
   - `hybrid` — reciprocal-rank fusion (RRF) of dense + sparse.
3. **Re-ranking** — a cross-encoder scores the fused top-K and reorders.
4. **Generation** — top documents are injected into the prompt and answered by the LLM
   (a `pydantic_ai.Agent` with the retrieval/FAQ system prompt and the station tools).

### 2.3 Tool path (real-time, no station DB)
1. The LLM calls `get_station_availability(station_name_or_location)` or
   `find_nearest_bikes(place)`; **the LLM never produces raw coordinates**.
2. Tools geocode the place with the **Grand Lyon Photon-based** geocoder
   (`download.data.grandlyon.com/geocoding/photon-bal/api`) and fetch the real-time
   `jcd_jcdecaux.jcdvelov` snapshot (name, `lat`/`lng`, `available_bikes`,
   `available_bike_stands`, `status`, `last_update`) — no stations stored locally.
3. Results are returned to the LLM to compose a natural-language answer.

### 2.4 Observability
- `app/main.py` calls `logfire.configure()` at startup (token optional).
- The app emits **metrics** (requests, latency, tokens, errors, feedback) directly to
  Logfire; charts are built in the Logfire UI.

---

## 3. Directory structure

```
.                              # repo root = single project home (dlthub workspace + app)
├── pyproject.toml             # app + dlthub dependencies (pinned) + [project.scripts]
├── uv.lock
├── .dlt/                      # dlt config (config.toml / secrets.toml)
├── docker-compose.yml         # qdrant + app + ingestion
├── Dockerfile                 # app image
├── .dockerignore
├── .env.example               # template for secrets/config
├── docs/
│   └── architecture.md        # this document
├── ingestion/                 # dlt pipelines
│   └── faq_pipeline.py        # FAQ (Cyclocity API) -> chunk -> embed -> Qdrant
├── app/                       # FastAPI service
│   ├── main.py                # /chat, /feedback, /health + logfire.configure()
│   ├── config.py              # pydantic-settings
│   ├── schemas.py             # request/response models
│   ├── rag/
│   │   ├── retriever.py       # dense/sparse/hybrid + rerank
│   │   └── llm.py             # pydantic-ai model (OpenCode Zen) + query rewriting
│   ├── tools/
│   │   ├── grandlyon.py       # Grand Lyon datapusher HTTP client + Photon geocoder
│   │   └── stations.py        # function schemas + impl
│   └── monitoring/
│       └── metrics.py         # Logfire metrics
├── evaluation/
│   ├── data_gen.py            # ground-truth generation (eval-gen)
│   ├── retrieval_eval.py      # hit rate / MRR (dense vs sparse vs hybrid)
│   ├── llm_eval.py            # LLM-as-a-judge
│   └── data/ground_truth.json # (legacy) sample eval set
├── scripts/
│   └── sample_query.py        # end-to-end demo
└── data/faq/
    ├── faq.json               # cached FAQ (reproducible fallback)
    └── ground_truth.json      # sample eval set
```

---

## 4. Implementation plan (module-by-module)

### 4.1 `ingestion/faq_pipeline.py`
- Fetches the FAQ from the Cyclocity API (client-token exchange) with
  `data/faq/faq.json` fallback.
- `@dlt.resource` yields FAQ chunks (`{id, topic, question, answer, content}`).
- `qdrant_adapter(resource, embed="content")` → dense embedding by FastEmbed.
- `dlt.pipeline("velov_faq", destination="qdrant", dataset_name="velov")` → collection `velov_faq`.

### 4.2 `app/rag/retriever.py`
- `search_dense(query)` — Qdrant vector search (dlt-embedded vectors).
- `search_sparse(query)` — in-memory BM25 over the FAQ corpus.
- `hybrid(query)` — RRF fusion of dense + sparse; `Reranker` cross-encoder on top.
- `retrieve(query, mode="hybrid")` returns top-k with scores + payload.

### 4.3 `app/rag/llm.py`
- `get_model()` — `OpenAIChatModel` over `OpenAIProvider` pointing at the OpenCode Zen
  endpoint (`https://opencode.ai/zen/v1/`).
- `rewrite_query(q)` — pydantic-ai agent returns 1–3 variants; retrieved per variant,
  merged and deduped.

### 4.4 `app/tools/stations.py`
- Tool schemas for `get_station_availability(station_name_or_location)` and
  `find_nearest_bikes(place)` (place geocoded via Photon, no raw coords from the LLM).
- `grandlyon.py` fetches `jcd_jcdecaux.jcdvelov/all.json?maxfeatures=-1` and geocodes
  via `download.data.grandlyon.com/geocoding/photon-bal/api`.

### 4.5 `app/monitoring/`
- `metrics.py` — Logfire counters/histograms: requests, latency, tokens, errors, feedback.

### 4.6 `evaluation/`
- `data_gen.py` — LLM-generated ground-truth questions (`uv run eval-gen`).
- `retrieval_eval.py` — hit rate & MRR over `data/faq/ground_truth.json` for all 3 modes.
- `llm_eval.py` — LLM-as-a-judge scoring.

---

## 5. Monitoring (Logfire, ≥ 5 charts)

| # | Panel | Logfire metric |
|---|-------|----------------|
| 1 | Total queries & requests over time | `velov.requests` |
| 2 | Latency breakdown (retrieval vs LLM) | `velov.latency.retrieval_ms` / `velov.latency.llm_ms` |
| 3 | User feedback distribution (up/down) | `velov.feedback{rating=up\|down}` |
| 4 | Vector search vs function calling ratio | `velov.requests{intent=rag\|tool}` |
| 5 | Error rate & token consumption | `velov.errors`, `velov.tokens` |

---

## 6. Reproducibility

- All package versions pinned in `pyproject.toml` (via `uv.lock`).
- One-command start: `docker compose up --build`.
- Commands via `uv run <script>` (see `[project.scripts]` in `pyproject.toml`).
