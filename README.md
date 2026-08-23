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
                       ┌──────────────┐
                       │    GDELT     │
                       │ broad search │
                       └──────┬───────┘
                              │
      ┌───────────────────────┼────────────────────────┐
      ▼                       ▼                        ▼
CNA Discovery           Edge Discovery           VIR Discovery
Bright Data             Bright Data              Bright Data
      │                       │                        │
      ▼                       ▼                        ▼
CNA Article             Edge Article              VIR Article
Bright Data             Bright Data              Bright Data
      │                       │                        │
      └───────────────────────┼────────────────────────┘
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

GDELT DOC 2.0 (`ArtList`) is the **broad** discovery layer. It does not replace Bright Data.

If a GDELT hit belongs to CNA, The Edge or VIR, CausaLens routes it to the matching Bright Data **article** collector. External domains stay as metadata-only context. The app does not bypass paywalls or scrape unsupported sites.

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
| `OPENAI_API_KEY` (or Anthropic / Gemini) | Event + causal extraction |
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

### Running frontend

```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

Open http://localhost:3000

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
