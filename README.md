# CausaLens SEA

Causal intelligence for Southeast Asian business, technology, investment, supply-chain and economic news.

Normal news products answer *what happened*. CausaLens answers **why it happened**, **what happens downstream**, and **which Southeast Asian markets could be affected**.

## Problem

Regional markets move through chains that a headline never shows. A Singapore power constraint becomes a Johor data-centre boom. A Vietnam factory expansion shows up in Malaysian packaging utilisation. A Chinese hyperscaler fundraising changes Singapore wholesale cloud pricing. Journalists cover fragments. Traders, operators and policymakers need the causal map.

## Solution

CausaLens SEA is a live causal-intelligence system. It continuously ingests curated Southeast Asian sources through Bright Data Scraper Studio collectors, broadens discovery with GDELT, converts articles into **deduplicated real-world events**, extracts **evidence-backed causal edges**, and renders them as an interactive directed graph.

The three product motions:

- **WHY?** — traverse upstream causes
- **WHAT NEXT?** — traverse downstream consequences
- **REGIONAL RIPPLE** — highlight cross-border effects across Southeast Asia

Every edge is auditable. Click a node and the supporting articles are attached to the relationship, not hidden behind a model score.

## Why causal graphs

Articles are not the unit of analysis. Events are. Multiple outlets can cover the same factory expansion, fundraising or policy change. CausaLens merges those into a single event node, then draws only relationships the evidence can support: `CAUSES`, `CONTRIBUTES_TO`, `TRIGGERS`, `RESPONDS_TO`, `AFFECTS`.

Observed edges are solid. Inferred edges are dashed. Predicted effects are dotted and labelled as **not established fact**.

## Why Southeast Asia

Capital, manufacturing, power and policy now couple Singapore, Malaysia, Vietnam, Indonesia and Thailand in a single operating theatre. China-plus-one electronics, Johor-Singapore compute, and Indonesian incentive races do not stay inside one border. A regional causal graph is the right primitive.

## Architecture

```text
                       ┌──────────────────────┐
                       │  GDELT Web NGrams    │
                       │  + snapshot TOC      │
                       └──────────┬───────────┘
                                  │ concept match → DOCID aggregate
                                  │ relevance filter / dedupe
                                  ▼
                    High-quality article candidates
                                  │
      ┌───────────────────────────┼───────────────────────────┐
      ▼                           ▼                           ▼
CNA article collector     Edge article collector      VIR article collector
Bright Data               Bright Data                 Bright Data
(only configured domains above MIN_BRIGHTDATA_RELEVANCE_SCORE)
      │                           │                           │
      └───────────────────────────┼───────────────────────────┘
                                  ▼
                         Normalized Articles
                                  │
                                  ▼
                           Deduplication
                                  │
                                  ▼
                          Event Extraction
                                  │
                                  ▼
                         Causal Extraction
                                  │
                                  ▼
                         Directed Event Graph
                        ↙          ↓          ↘
                      WHY?     WHAT NEXT?    RIPPLE
```

- **Frontend:** Next.js, TypeScript, Tailwind CSS, React Flow, dagre
- **Backend:** FastAPI, Pydantic, SQLAlchemy/SQLite, NetworkX, httpx, tenacity
- **LLM:** provider abstraction (OpenAI / Anthropic / Gemini) with JSON repair

## Bright Data integration

Bright Data Scraper Studio is the curated live-source spine. CausaLens does **not** replace these collectors with generic `requests` or BeautifulSoup scraping.

`backend/app/clients/brightdata.py` exposes one interface:

```python
async def run_collector(self, collector_id: str, url: str) -> list[dict]
```

Two transports sit behind it:

- **CLI** (`BRIGHTDATA_TRANSPORT=cli`) — `npx -p @brightdata/cli bdata scraper run <collector_id> <url> --pretty`. JSON is recovered even if the CLI prints status lines first.
- **HTTP** — `POST https://api.brightdata.com/dca/trigger?collector=<id>` then poll `GET https://api.brightdata.com/dca/dataset?id=<collection_id>` until the snapshot is ready.

If HTTP credentials are missing, the client falls back to CLI. Collector IDs stay visible in the UI under **Show technical details**.

## Collector IDs

| Source | Market | Discovery | Article |
| --- | --- | --- | --- |
| CNA | Singapore / regional | `c_mt5waa7y28okohy2bb` | `c_mt5xrjlvou8e3hv9h` |
| The Edge Malaysia | Malaysia | `c_mt5x5mxs1yk83lb2ss` | `c_mt5xjcc52lzzkhyte1` |
| Vietnam Investment Review | Vietnam | `c_mt5x1ux81pzkfi3gzf` | `c_mt5xxz1h12rsttjaza` |

Discovery URLs:

- CNA: https://www.channelnewsasia.com/business
- The Edge: https://theedgemalaysia.com/
- VIR: https://vir.com.vn/

Source-specific adapters normalise the observed collector schemas (CNA `product_page_url` vs `/fast/` URLs, promotional widget stripping, Edge uploader lines, sparse VIR discovery).

## GDELT integration

GDELT **Web NGrams + TOC** is the default broad discovery layer. It does not replace Bright Data.

Each snapshot is a pair of files under `https://storage.googleapis.com/data.gdeltproject.org/gdeltv5/weblegacy/ngrams/`:

- `{YYYYMMDDHHMM00}.ngrams.txt.gz` — `DOCID<TAB>QUADGRAM<TAB>COUNT`
- `{YYYYMMDDHHMM00}.toc.json.gz` — JSONL mapping snapshot-local DOCIDs to URL / title / date / language

The worker looks a few minutes behind UTC, treats HTTP 404 as a normal missing minute, streams ngram rows, and only keeps articles that match **technology AND Southeast Asia geography**. Entities such as Nvidia boost the score but never qualify an article by themselves. Index/category pages and known aggregators are rejected or heavily penalized. Only candidates above `MIN_BRIGHTDATA_RELEVANCE_SCORE` on CNA / The Edge / VIR are sent to Bright Data article collectors.

The old GDELT DOC 2.0 `ArtList` API is **not** the default. Set `GDELT_DISCOVERY_MODE=doc` or `GDELT_DOC_FALLBACK=true` if you need it.

Debug discovery without consuming Bright Data credits:

```bash
cd backend
python scripts/test_gdelt_ngrams.py --query "AI infrastructure in Southeast Asia"
# or
curl "http://localhost:8000/debug/gdelt-discovery?query=AI%20infrastructure%20in%20Southeast%20Asia"
```

## Evidence-backed causality

LLM confidence is not the product metric.

```text
evidence_score = min(1.0, 0.70 * model_confidence + 0.30 * independent_source_component)
```

The UI shows **Evidence 87%** and **3 supporting reports**, plus the article cards that justify the edge.

## Regional Ripple

An edge is cross-border when the source and target events have non-empty, non-identical country sets. **REGIONAL RIPPLE** walks downstream descendants that pass through at least one cross-border edge and groups them by market.

## Self-healing story

Pipeline health is first-class: `HEALTHY`, `DEGRADED`, `FAILED`, `HEALED`.

Bright Data healing is **not invented**. If a collector is repaired during the demo, record it:

```http
POST /pipeline/healing-event
{
  "source": "cna",
  "collector_id": "c_mt5xrjlvou8e3hv9h",
  "message": "Article body extraction recovered after scraper healing."
}
```

The **Scraper Pulse** timeline only shows events that were actually stored. Technical details in the live pipeline panel expose a **Record collector repair** control for the demo video.

## Local setup

Requires Python 3.11+, Node 20+, and `npx` (for Bright Data CLI transport).

```bash
git clone <repo>
cd causalens
cp .env.example .env
```

Fill in at least one LLM key for live extraction. Bright Data CLI uses the same account that published the collectors. The app still boots and demos from a cached evidence graph if live APIs fail.

### Environment variables

See `.env.example`. Required for a fully live run:

| Variable | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | Event + causal extraction. Claude keys (`sk-ant-...`) are routed to Anthropic; keep this variable name. |
| `BRIGHTDATA_API_TOKEN` | HTTP transport and CLI auth |
| `BRIGHTDATA_TRANSPORT` | `cli` (default) or `http` |
| `USE_CACHED_DEMO_ON_FAILURE` | `true` — never crash a live demo |
| `NEXT_PUBLIC_API_URL` | Frontend → API, default `http://localhost:8000` |

Never put API keys in the frontend. Collector IDs are public configuration, not secrets.

### Running backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Health check: `GET http://localhost:8000/health`

Bright Data smoke test (uses live collectors; needs CLI/token):

```bash
cd backend
python scripts/test_brightdata.py
```

If all three sources pass, the script prints `BRIGHT DATA PIPELINE HEALTHY`.

GDELT NGrams discovery (no Bright Data):

```bash
cd backend
python scripts/test_gdelt_ngrams.py
```

### Running frontend

```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

Open http://localhost:3000

## Deploy online

The production build is **one Docker image**. FastAPI serves the exported Next.js UI on the same origin, so a judge only needs one URL.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/venvennnn/causalens)

### Render (recommended)

This is **not** a Django app. Do not use `gunicorn your_application.wsgi`.

**Option A — Docker (preferred)**

On the Render create-service screen, change the runtime/language from Python to **Docker**, then:

| Field | Value |
| --- | --- |
| Language | Docker |
| Branch | `cursor/causalens-sea-mvp-15e9` |
| Dockerfile path | `Dockerfile` |
| Docker build context | `.` |
| Instance type | **Starter** (required) |
| Build command | leave empty |
| Start command | leave empty |

**Option B — Python native (the form you are on)**

| Field | Value |
| --- | --- |
| Language | Python 3 |
| Branch | `cursor/causalens-sea-mvp-15e9` |
| Root directory | leave empty |
| Build command | `bash bin/render-build.sh` |
| Start command | `bash bin/render-start.sh` |
| Instance type | **Starter** (required) |

Environment variables (optional; demo still works without keys):

- `OPENAI_API_KEY`
- `BRIGHTDATA_API_TOKEN`
- `BRIGHTDATA_TRANSPORT=http`
- `USE_CACHED_DEMO_ON_FAILURE=true`
- `CORS_ORIGINS=*`

Health check path: `/health`

`render.yaml` in the repo pre-fills Docker settings if you use **Deploy to Render**.

### Railway

New project → Deploy from GitHub → this repo. Railway reads `railway.toml` and the root `Dockerfile`. Set the same env vars. Open the generated `*.up.railway.app` URL.

### Fly.io

```bash
fly launch --copy-config --yes
fly secrets set OPENAI_API_KEY=sk-... BRIGHTDATA_API_TOKEN=...
fly deploy
```

### Docker (any VPS / Cloud Run)

```bash
docker build -t causalens-sea .
docker run --rm -p 8000:8000 \
  -e OPENAI_API_KEY=sk-... \
  -e BRIGHTDATA_API_TOKEN=... \
  -e BRIGHTDATA_TRANSPORT=http \
  causalens-sea
```

Then http://localhost:8000 — or put a TLS proxy in front.

Without LLM or Bright Data keys the site still loads the cached SEA graph and labels it **CACHED**.

## Demo flow

Recommended query: **AI infrastructure in Southeast Asia**

90-second sequence:

1. Land on “Understand why Southeast Asia moves.”
2. Click **AI infrastructure in Southeast Asia**.
3. Watch DISCOVER → EXTRACT → VALIDATE → EVENTS → CAUSAL GRAPH.
4. Click **Alibaba plans US$10.2B share placement for AI development**.
5. Press **WHY?** — upstream AI capex and financing mechanism.
6. Press **REGIONAL RIPPLE** — Singapore constraints, Johor campuses, Indonesia incentives.
7. Open **Show technical details** and **Scraper Pulse** so Bright Data collector IDs are on screen.

## Limitations

- Live Bright Data runs consume collector credits and typically take minutes, not milliseconds.
- GDELT returns metadata, not full text, for domains without a configured article collector.
- Causal extraction is an LLM over supplied evidence, not a statistical causal identifier.
- Predicted edges are hypotheses and are visually separated from observed facts.
- This MVP has no auth, billing, or multi-user workspaces on purpose.

## Future work

As the historical graph grows, **temporal graph neural networks** can be used to rank plausible emerging relationships and regional propagation patterns. CausaLens does not currently use a GNN; the live product is evidence extraction plus a directed event graph.

Further work: streaming collector webhooks, analyst-in-the-loop edge verification, and commodity-specific overlays (nickel, semiconductors, power).
