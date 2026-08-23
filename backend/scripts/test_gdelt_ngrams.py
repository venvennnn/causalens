#!/usr/bin/env python3
"""Rank GDELT Web NGrams candidates without calling Bright Data."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.gdelt.pipeline import discover_ngrams, serialize_ranked  # noqa: E402


async def main() -> int:
    parser = argparse.ArgumentParser(description="Test GDELT NGrams discovery without Bright Data")
    parser.add_argument(
        "--query",
        default="AI infrastructure in Southeast Asia",
        help="Topic query used to build concept groups",
    )
    parser.add_argument("--max-snapshots", type=int, default=1)
    parser.add_argument("--min-score", type=float, default=None)
    parser.add_argument("--force", action="store_true", help="Rescan snapshots even if cached")
    args = parser.parse_args()

    result = await discover_ngrams(
        args.query,
        db=None,
        max_snapshots=args.max_snapshots,
        min_score=args.min_score,
        force_rescan=args.force,
    )
    print(f"topic={result.topic}")
    print(f"snapshots={','.join(result.snapshots) or '(none found)'}")
    for stat in result.stats:
        print(
            f"[GDELT] snapshot={stat.snapshot} ngram_rows={stat.ngram_rows} "
            f"relevant_docids={stat.relevant_docids} tech_docids={stat.tech_docids} "
            f"geo_docids={stat.geo_docids} qualified_candidates={stat.qualified_candidates} "
            f"rejected_index_pages={stat.rejected_index_pages} "
            f"rejected_low_relevance={stat.rejected_low_relevance} from_cache={int(stat.from_cache)}"
        )
    print(f"[GDELT] sent_to_brightdata=0")
    top = serialize_ranked(result.ranked, limit=10)
    if not top:
        print("No candidates above the relevance cutoff.")
        return 0
    print("\nTop candidates:")
    for item in top:
        breakdown = item["scoreBreakdown"]
        print(f"- {item['relevanceScore']:.1f}  {item['title']}")
        print(f"    {item['domain']}  {item['url']}")
        print(
            f"    tech={breakdown['tech']} geo={breakdown['geography']} "
            f"entities={breakdown['entities']} title={breakdown['title']} "
            f"source={breakdown['source']} penalties={breakdown['penalties']}"
        )
        print(f"    tech_terms={item['matchedTechTerms']}")
        print(f"    geo_terms={item['matchedGeoTerms']}")
    print("\nJSON:")
    print(json.dumps(top[:5], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
