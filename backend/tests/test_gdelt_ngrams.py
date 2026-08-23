from __future__ import annotations

import gzip
import json
from datetime import datetime, timezone
from pathlib import Path

from app.gdelt.matching import DocAccumulator, TermMatcher, aggregate_hits, parse_ngram_line
from app.gdelt.pipeline import load_toc, process_snapshot_files, ranked_to_candidate
from app.gdelt.scoring import is_likely_article_page, score_document
from app.gdelt.snapshots import candidate_stamps, snapshot_stamp
from app.gdelt.topics import topic_from_query
from app.sources.adapters import canonicalize_url


def _topic():
    return topic_from_query("AI infrastructure in Southeast Asia")


def _accumulate(doc_id: int, ngrams: list[str]) -> DocAccumulator:
    matcher = TermMatcher(_topic())
    acc = DocAccumulator(doc_id=doc_id)
    for ngram in ngrams:
        for hit in matcher.match_ngram(ngram, 1):
            acc.add(hit)
    return acc


def _write_gz(path: Path, text: str) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        handle.write(text)


def test_parse_ngram_line():
    assert parse_ngram_line("56\thyperscale data center johor\t3") == (56, "hyperscale data center johor", 3)
    assert parse_ngram_line("  12\tfoo bar baz qux\t1.0") == (12, "foo bar baz qux", 1)
    assert parse_ngram_line("not-a-row") is None
    assert parse_ngram_line("") is None
    assert parse_ngram_line("x\ty\tz") is None


def test_toc_maps_local_docid(tmp_path: Path):
    path = tmp_path / "20260823154600.toc.json.gz"
    rows = [
        {"ID": 56, "title": "Johor campus", "url": "https://example.com/johor-campus", "lang": "en"},
        {"ID": 99, "title": "Other", "url": "https://example.com/other", "lang": "en"},
    ]
    _write_gz(path, "\n".join(json.dumps(row) for row in rows) + "\n")
    found = load_toc(path, {56})
    assert 56 in found
    assert 99 not in found
    assert found[56]["url"] == "https://example.com/johor-campus"


def test_article_level_aggregation_same_docid():
    topic = _topic()
    matcher = TermMatcher(topic)
    rows = [
        (7, matcher.match_ngram("ai compute infrastructure plans", 2)),
        (7, matcher.match_ngram("johor bahru campus site", 1)),
        (8, matcher.match_ngram("data center construction", 1)),
        (9, matcher.match_ngram("vietnam rice exports", 1)),
    ]
    docs = aggregate_hits(rows)
    assert docs[7].qualifies(topic.required_groups)
    assert "ai compute" in docs[7].tech_terms or "compute infrastructure" in docs[7].tech_terms
    assert "johor" in docs[7].geo_terms or "johor bahru" in docs[7].geo_terms
    assert not docs[8].qualifies(topic.required_groups)
    assert not docs[9].qualifies(topic.required_groups)
    assert 7 in docs and 8 in docs and 9 in docs


def test_entities_alone_do_not_qualify():
    gaming = _accumulate(2, ["microsoft xbox vietnam launch", "oracle opens hanoi office"])
    assert not gaming.qualifies(_topic().required_groups)
    assert not gaming.tech_terms
    assert "vietnam" in gaming.geo_terms or "hanoi" in gaming.geo_terms


def test_weak_nvidia_vietnam_does_not_rank_highly():
    topic = _topic()
    weak = _accumulate(1, ["nvidia dlss ray reconstruction", "vietnam market notes"])
    assert weak.qualifies(topic.required_groups)
    weak_item = score_document(
        topic,
        weak,
        title="Nvidia DLSS 4.5 Ray Reconstruction arrives for gamers",
        url="https://www.example.com/nvidia-dlss-45-ray-reconstruction-review",
        language="en",
    )
    strong = _accumulate(
        2,
        ["johor bahru hyperscale data center", "ai compute infrastructure investment"],
    )
    strong_item = score_document(
        topic,
        strong,
        title="Johor hyperscale data center draws AI compute infrastructure investment",
        url="https://www.channelnewsasia.com/business/johor-hyperscale-data-center-ai-compute-815507",
        language="en",
    )
    assert strong_item.relevance_score > weak_item.relevance_score + 6
    assert strong_item.relevance_score >= 12
    assert weak_item.relevance_score < 12
    assert weak_item.breakdown.penalties < 0


def test_index_and_generic_titles_rejected():
    assert is_likely_article_page("Latest News", "https://example.com/news/") is False
    assert is_likely_article_page("Technology News | Latest Updates", "https://example.com/topics/tech") is False
    assert is_likely_article_page("Odisha News | Odisha Latest News", "https://www.newsnow.co.uk/news/") is False
    assert is_likely_article_page("Hinduism News | Latest News", "https://example.com/category/religion") is False
    assert is_likely_article_page("DIGITIMES Research - Server & HPC", "https://www.digitimes.com/reports/category") is False
    assert is_likely_article_page(
        "Johor hyperscale data center expansion",
        "https://www.channelnewsasia.com/business/johor-hyperscale-data-center-expansion-12345",
    )


def test_url_tracking_params_deduped():
    a = canonicalize_url(
        "https://www.channelnewsasia.com/business/johor-campus?utm_source=twitter&utm_campaign=x&fbclid=abc"
    )
    b = canonicalize_url("https://www.channelnewsasia.com/business/johor-campus?gclid=1")
    assert a == b
    assert "utm_" not in a
    assert "fbclid" not in a
    assert "gclid" not in b


def test_process_snapshot_files_offline(tmp_path: Path):
    stamp = "20260823154600"
    ngram_path = tmp_path / f"{stamp}.ngrams.txt.gz"
    toc_path = tmp_path / f"{stamp}.toc.json.gz"
    ngrams = "\n".join(
        [
            "56\thyperscale data center johor\t4",
            "56\tai compute infrastructure\t2",
            "70\tnvidia gaming graphics\t3",
            "70\tvietnam launch event\t1",
            "80\tdata center singapore\t2",
            "99\tnvidia dlss update\t8",
        ]
    )
    toc = "\n".join(
        [
            json.dumps(
                {
                    "ID": 56,
                    "title": "Johor hyperscale data center expansion",
                    "url": "https://www.channelnewsasia.com/business/johor-hyperscale-data-center-expansion-12345",
                    "lang": "en",
                    "date": "2026-08-23T15:46:00.000Z",
                }
            ),
            json.dumps(
                {
                    "ID": 70,
                    "title": "Nvidia DLSS 4.5 Ray Reconstruction",
                    "url": "https://www.example.com/nvidia-dlss-45-ray-reconstruction",
                    "lang": "en",
                }
            ),
            json.dumps(
                {
                    "ID": 80,
                    "title": "Latest News",
                    "url": "https://www.newsnow.co.uk/news/",
                    "lang": "en",
                }
            ),
            json.dumps(
                {
                    "ID": 99,
                    "title": "Nvidia gaming driver notes",
                    "url": "https://www.example.com/nvidia-driver-notes",
                    "lang": "en",
                }
            ),
        ]
    )
    _write_gz(ngram_path, ngrams + "\n")
    _write_gz(toc_path, toc + "\n")
    topic = _topic()
    ranked, stats = process_snapshot_files(
        stamp,
        ngram_path,
        toc_path,
        TermMatcher(topic),
        topic,
        min_score=8.0,
        known_urls=set(),
    )
    urls = {item.url for item in ranked}
    assert any("johor-hyperscale" in url for url in urls)
    assert not any("newsnow" in url for url in urls)
    assert not any("nvidia-dlss" in url for url in urls)
    assert not any("nvidia-driver" in url for url in urls)
    assert stats.rejected_index_pages >= 1
    candidate = ranked_to_candidate(ranked[0])
    assert candidate.raw["provider"] == "gdelt_ngrams"
    assert candidate.raw["gdelt_doc_id"] == 56
    assert "tech" in candidate.raw["score_breakdown"]


def test_candidate_stamps_newest_first():
    now = datetime(2026, 8, 23, 16, 10, tzinfo=timezone.utc)
    stamps = candidate_stamps(now=now, lag_minutes=5, lookback_hours=1, max_probes=8)
    assert stamps[0] == snapshot_stamp(datetime(2026, 8, 23, 16, 5, tzinfo=timezone.utc))
    assert stamps[0] > stamps[-1]
    assert len(stamps) == 8


def test_topic_config_is_reusable():
    ev = topic_from_query("EV battery investments in Southeast Asia")
    assert "ev battery" in ev.concept_groups["technology"]
    semi = topic_from_query("semiconductor supply chain in Malaysia")
    assert "foundry" in semi.concept_groups["technology"] or "semiconductor" in semi.concept_groups["technology"]
    default = topic_from_query("AI infrastructure in Southeast Asia")
    assert default.required_groups == ("technology", "geography")
    assert "singapore" in default.concept_groups["geography"]
