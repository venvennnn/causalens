#!/usr/bin/env python3
"""Immediate Bright Data collector health check for CausaLens SEA."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.clients.brightdata import BrightDataClient
from app.services.health import validate_article
from app.sources.adapters import normalize_article, normalize_discovery
from app.sources.registry import SOURCE_REGISTRY


async def probe_source(client: BrightDataClient, source_key: str) -> bool:
    source = SOURCE_REGISTRY[source_key]
    print(f"\n=== {source['name']} ({source_key}) ===")
    print(f"Discovery collector: {source['discovery_collector']}")
    records = await client.run_collector(source["discovery_collector"], source["discovery_url"])
    candidates = []
    for record in records:
        candidate = normalize_discovery(source_key, record)
        if candidate:
            candidates.append(candidate)
    if not candidates:
        print("NO CANDIDATES")
        print(json.dumps(records[:1], default=str)[:800])
        return False
    print("First two candidates:")
    for candidate in candidates[:2]:
        print(f"  - {candidate.title}")
        print(f"    {candidate.url}")
    first = candidates[0]
    print(f"Article collector: {source['article_collector']}")
    article_rows = await client.run_collector(source["article_collector"], first.url)
    record = article_rows[0] if article_rows else {}
    article = normalize_article(source_key, record, url=first.url, candidate=first)
    health = validate_article(article)
    print("TITLE:", article.title)
    print("SOURCE:", article.source)
    print("COUNTRY:", article.country)
    print("BODY LENGTH:", len(article.body or ""))
    print("URL:", article.url)
    print("HEALTH:", "OK" if health.healthy else health.failures)
    return health.healthy


async def main() -> int:
    client = BrightDataClient()
    results = []
    for key in ("cna", "edge", "vir"):
        try:
            results.append(await probe_source(client, key))
        except Exception as exc:
            print(f"{key} FAILED: {type(exc).__name__}: {exc}")
            results.append(False)
    if all(results):
        print("\nBRIGHT DATA PIPELINE HEALTHY")
        return 0
    print("\nBRIGHT DATA PIPELINE DEGRADED")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
