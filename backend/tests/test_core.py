from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from app.clients.brightdata import as_record_list, extract_json_payload
from app.clients.llm import (
    AnthropicClient,
    anthropic_api_key,
    anthropic_model_name,
    get_llm_client,
    is_anthropic_key,
)
from app.models.schemas import Article, CausalEdge, Event
from app.services.dedupe import titles_similar
from app.services.evidence import annotate_cross_border, calculate_evidence_score
from app.services.graph_service import build_graph, get_regional_ripple, get_what_next, get_why
from app.services.health import validate_article
from app.sources.adapters import canonicalize_url, normalize_article, normalize_discovery, strip_cna_promos, strip_edge_uploader


def test_cna_prefers_product_page_url():
    record = {
        "title": "Rates hold",
        "article_url": "https://www.channelnewsasia.com/fast/abc",
        "product_page_url": "https://www.channelnewsasia.com/business/rates-hold-123",
        "published_at": "21 Aug 2026 11:33PM",
        "category": "Business",
        "summary": "MAS held rates.",
    }
    candidate = normalize_discovery("cna", record)
    assert candidate is not None
    assert "fast" not in candidate.url
    assert candidate.url.endswith("rates-hold-123")
    assert candidate.published_at is not None


def test_cna_promo_strip_keeps_body():
    body = "MAS held the policy rate.\nCNA Games\nGuess Word\nBanks rallied in afternoon trade.\nShow More"
    cleaned = strip_cna_promos(body)
    assert "MAS held" in cleaned
    assert "Banks rallied" in cleaned
    assert "CNA Games" not in cleaned
    assert "Show More" not in cleaned


def test_edge_uploader_strip():
    body = "Tenaga announced grid upgrades in Johor.\nUploaded by Jane Tan"
    assert "Uploaded by" not in strip_edge_uploader(body)
    assert "Tenaga" in strip_edge_uploader(body)


def test_edge_ignores_related_for_primary_url():
    record = {
        "article_title": "Tenaga plan",
        "article_url": "https://theedgemalaysia.com/node/815507",
        "publish_date": "22 Aug 2026, 09:55 am",
        "categories": ["Corporate", "World"],
        "related_articles": [{"article_url": "https://theedgemalaysia.com/node/1"}],
    }
    candidate = normalize_discovery("edge", record)
    assert candidate is not None
    assert candidate.url.endswith("/node/815507")


def test_vir_minimal_discovery():
    record = {
        "article_title": "Nestlé Vietnam beefs up production capacity for coffee exports",
        "article_url": "https://vir.com.vn/nestle-vietnam-beefs-up-production-capacity-for-coffee-exports-159266.html",
        "input": {"url": "https://vir.com.vn/"},
    }
    candidate = normalize_discovery("vir", record)
    assert candidate is not None
    assert "159266" in candidate.url


def test_canonicalize_tracking_params():
    url = "https://WWW.ChannelNewsAsia.com/business/foo/?utm_source=x&id=1#section"
    canonical = canonicalize_url(url)
    assert canonical.startswith("https://www.channelnewsasia.com/business/foo")
    assert "utm_source" not in canonical
    assert "#section" not in canonical


def test_json_payload_with_logs():
    stdout = "running collector...\nprogress 50%\n[{\"title\": \"A\", \"article_url\": \"https://x.com/a\"}]\n"
    payload = extract_json_payload(stdout)
    assert as_record_list(payload)[0]["title"] == "A"


def test_openai_env_claude_key_routes_to_anthropic():
    assert is_anthropic_key("sk-ant-api03-abc")
    assert not is_anthropic_key("sk-proj-abc")
    settings = SimpleNamespace(
        openai_api_key="sk-ant-api03-abc",
        openai_model="gpt-5-mini",
        anthropic_api_key="",
    )
    assert anthropic_api_key(settings) == "sk-ant-api03-abc"
    assert anthropic_model_name(settings) == "claude-sonnet-4-20250514"
    settings.openai_model = "claude-sonnet-4-20250514"
    assert anthropic_model_name(settings) == "claude-sonnet-4-20250514"

    fake = SimpleNamespace(
        llm_provider="openai",
        openai_api_key="sk-ant-api03-test",
        openai_model="gpt-5-mini",
        anthropic_api_key="",
        gemini_api_key="",
        llm_timeout_s=90.0,
        llm_temperature=0.0,
    )
    with patch("app.clients.llm.get_settings", return_value=fake):
        client = get_llm_client()
    assert isinstance(client, AnthropicClient)
    assert client.api_key == "sk-ant-api03-test"
    assert client.model == "claude-sonnet-4-20250514"


def test_validate_article_length():
    article = Article(
        id="1",
        title="Title",
        url="https://example.com/a",
        source="CNA",
        country="Singapore",
        body="short",
        ingested_at=datetime.utcnow(),
    )
    result = validate_article(article)
    assert result.healthy is False
    assert "body_too_short" in result.failures


def test_title_similarity():
    assert titles_similar(
        "Alibaba plans US$10.2 billion share placement for AI",
        "Alibaba plans US$10.2 billion share placement for AI expansion",
    )
    assert not titles_similar("Vietnam coffee exports rise", "Singapore data centre rents jump")


def test_graph_why_next_ripple():
    events = [
        Event(id="a", title="A", summary="A", countries=["Singapore"], source_article_ids=["1"], event_type="MARKET_MOVE"),
        Event(id="b", title="B", summary="B", countries=["Malaysia"], source_article_ids=["2"], event_type="EXPANSION"),
        Event(id="c", title="C", summary="C", countries=["Indonesia"], source_article_ids=["3"], event_type="INVESTMENT"),
    ]
    articles = {
        "1": Article(id="1", title="t1", url="https://a.com/1", source="CNA", country="Singapore", body="x" * 300, ingested_at=datetime.utcnow()),
        "2": Article(id="2", title="t2", url="https://b.com/2", source="The Edge Malaysia", country="Malaysia", body="x" * 300, ingested_at=datetime.utcnow()),
        "3": Article(id="3", title="t3", url="https://c.com/3", source="VIR", country="Vietnam", body="x" * 300, ingested_at=datetime.utcnow()),
    }
    edges = [
        CausalEdge(id="e1", source_event_id="a", target_event_id="b", relation="CAUSES", confidence=0.9, reason="constraint spillover", supporting_article_ids=["1", "2"], status="observed"),
        CausalEdge(id="e2", source_event_id="b", target_event_id="c", relation="AFFECTS", confidence=0.7, reason="corridor expansion", supporting_article_ids=["2", "3"], status="inferred"),
    ]
    event_map = {event.id: event for event in events}
    edges = [annotate_cross_border(edge, event_map) for edge in edges]
    for edge in edges:
        edge.evidence_score = calculate_evidence_score(edge, articles)
    assert edges[0].cross_border is True
    assert edges[0].evidence_score >= 0.6
    graph = build_graph(events, edges)
    why = get_why(graph, "c")
    assert "a" in why["highlight_node_ids"]
    nxt = get_what_next(graph, "a")
    assert any(item["id"] == "b" for item in nxt["observed"])
    ripple = get_regional_ripple(graph, "a")
    assert ripple["markets_connected"] >= 2
