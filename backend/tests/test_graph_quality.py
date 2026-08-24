from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from datetime import datetime

from app.models.schemas import Article, CausalEdge, Event
from app.services.event_dedup import dedupe_events
from app.services.graph_quality import assemble_events, build_diagnostics, classify_articles, finalize_edges
from app.services.query_intent import parse_query_intent
from app.services.relations import apply_relation_policy
from app.services.relevance import classify_text


QUERY = "Semiconductor investment in Malaysia"


def _article(title: str, body: str, *, url: str = "https://example.com/a", country: str = "Malaysia") -> Article:
    return Article(
        id="art_" + title[:12],
        title=title,
        url=url,
        source="CNA",
        country=country,
        body=body,
        ingested_at=datetime.utcnow(),
        summary=title,
    )


def _event(event_id: str, title: str, summary: str, **kwargs) -> Event:
    payload = dict(
        id=event_id,
        title=title,
        summary=summary,
        countries=kwargs.get("countries", ["Malaysia"]),
        companies=kwargs.get("companies", []),
        industries=kwargs.get("industries", ["Semiconductors"]),
        source_article_ids=kwargs.get("source_article_ids", ["a1"]),
        event_type=kwargs.get("event_type", "INVESTMENT"),
        confidence=0.8,
    )
    return Event(**payload)


def test_intent_semiconductor_malaysia_is_not_flat_keywords():
    intent = parse_query_intent(QUERY)
    assert intent.subject.lower().startswith("semiconductor")
    assert intent.event_type == "investment"
    assert intent.primary_geographies == ["Malaysia"]
    assert "Singapore" in intent.context_geographies
    assert "Vietnam" in intent.context_geographies
    required = {term.lower() for term in intent.required_terms()}
    assert "semiconductor" in required
    assert "data center" not in required
    assert "data centre" not in required
    assert "ai" in {term.lower() for term in intent.weak_context_terms}
    assert any("kulim" in term for term in intent.primary_geo_terms)
    assert any("penang" in term for term in intent.primary_geo_terms)


def test_infineon_kulim_is_core():
    intent = parse_query_intent(QUERY)
    result = classify_text(
        intent,
        "Infineon invests in new Kulim semiconductor capacity",
        "Infineon will invest in additional semiconductor manufacturing capacity at its Kulim, Malaysia facility.",
    )
    assert result.classification == "CORE"
    assert result.core_eligible
    assert result.subject_relevance >= 0.6
    assert result.geography_relevance >= 0.6


def test_infineon_kulim_without_semiconductor_word_is_core():
    intent = parse_query_intent(QUERY)
    result = classify_text(
        intent,
        "Infineon expands Kulim plant",
        "Infineon will expand its Kulim, Malaysia plant and hire more engineers this year.",
    )
    assert result.classification == "CORE"
    assert result.core_eligible


def test_chipmakers_penang_is_core():
    intent = parse_query_intent(QUERY)
    result = classify_text(
        intent,
        "Malaysia chipmakers expand in Penang",
        "Chipmakers in Penang are adding assembly and test lines this quarter.",
    )
    assert result.classification == "CORE"


def test_phrase_chip_matches_chipmakers_not_intelligence():
    from app.gdelt.topics import normalize_text
    from app.services.query_intent import phrase_in_text

    assert phrase_in_text("chip", normalize_text("Malaysia chipmakers expand"))
    assert phrase_in_text("chip", normalize_text("new chips and wafers"))
    assert not phrase_in_text("intel", normalize_text("market intelligence report"))
    assert phrase_in_text("intel", normalize_text("Intel expands Penang"))


def test_vietnam_semiconductor_is_not_core():
    intent = parse_query_intent(QUERY)
    result = classify_text(
        intent,
        "Vietnam expands semiconductor manufacturing",
        "Vietnam is expanding semiconductor manufacturing capacity in Bac Ninh as electronics FDI grows.",
    )
    assert result.classification != "CORE"
    assert result.classification in {"CONTEXT", "REJECTED"}


def test_microsoft_cloud_malaysia_is_not_core():
    intent = parse_query_intent(QUERY)
    result = classify_text(
        intent,
        "Microsoft launches new cloud region in Malaysia",
        "Microsoft launched a new cloud region in Malaysia to serve enterprise software and office workloads.",
    )
    assert result.classification != "CORE"


def test_nvidia_gaming_gpu_is_rejected():
    intent = parse_query_intent(QUERY)
    result = classify_text(
        intent,
        "Nvidia launches new gaming GPU",
        "Nvidia launched a new GeForce gaming GPU with DLSS 4.5 for consumer graphics cards.",
    )
    assert result.classification == "REJECTED"


def test_ngram_boilerplate_false_positive_rejected_after_body():
    intent = parse_query_intent(QUERY)
    result = classify_text(
        intent,
        "The art of protest is alive and well in Kansas",
        (
            "Gallery owners in Kansas discuss public art. Footer: Related: Malaysia semiconductor "
            "investment, Vietnam data center, Singapore cloud."
        ),
    )
    assert result.classification == "REJECTED"


def test_weak_terms_cannot_replace_required_subject():
    intent = parse_query_intent(QUERY)
    result = classify_text(
        intent,
        "GPU cluster planned for Malaysia",
        "A new GPU cluster in Malaysia will serve AI developers. Nvidia GPUs were mentioned.",
    )
    assert result.classification != "CORE"


def test_generic_queries_still_parse():
    ev = parse_query_intent("EV battery investment in Indonesia")
    assert ev.primary_geographies == ["Indonesia"]
    assert ev.event_type == "investment"
    assert "battery" in " ".join(ev.required_terms()).lower() or "ev" in ev.subject.lower()

    shipping = parse_query_intent("shipping disruption around Singapore")
    assert shipping.primary_geographies == ["Singapore"]
    assert shipping.event_type in {"disruption", "constraint"} or "shipping" in shipping.subject.lower()

    johor = parse_query_intent("data centre electricity constraints in Johor")
    assert johor.primary_geographies == ["Malaysia"]
    assert johor.domain == "data_center"


def test_same_article_causal_language_can_stay_strong():
    source = _event("e1", "AI accelerator demand rises", "Demand for AI accelerators is rising.", source_article_ids=["a1"])
    target = _event(
        "e2",
        "Malaysian packaging investment increases",
        "OSAT houses in Malaysia are expanding capacity.",
        source_article_ids=["a1"],
    )
    article = _article(
        "AI demand drives Malaysian packaging",
        "AI accelerator demand has driven increased investment in Malaysian semiconductor packaging capacity.",
        url="https://example.com/causal",
    )
    article.id = "a1"
    edge = CausalEdge(
        id="edg1",
        source_event_id="e1",
        target_event_id="e2",
        relation="CAUSES",
        confidence=0.91,
        evidence_score=0.88,
        reason="The article states that AI accelerator demand has driven increased investment in Malaysian semiconductor packaging capacity.",
        supporting_article_ids=["a1"],
    )
    out = apply_relation_policy(edge, source, target, {article.id: article})
    assert out.relation in {"CAUSES", "CONTRIBUTES_TO"}
    assert out.evidence


def test_semantic_similarity_defaults_to_related_to():
    source = _event("e1", "Infineon expands Kulim fab", "Infineon is expanding a fab in Kulim.", source_article_ids=["a1"])
    target = _event(
        "e2",
        "Malaysia OSAT utilisation rises",
        "Packaging houses in Penang reported higher utilisation.",
        source_article_ids=["a2"],
        companies=["OSAT"],
    )
    a1 = _article("Infineon expands Kulim fab", "Infineon is expanding semiconductor output in Kulim, Malaysia.")
    a1.id = "a1"
    a2 = _article(
        "Malaysia OSAT utilisation rises",
        "Packaging houses in Penang reported higher utilisation this quarter.",
        url="https://example.com/b",
    )
    a2.id = "a2"
    edge = CausalEdge(
        id="edg2",
        source_event_id="e1",
        target_event_id="e2",
        relation="CAUSES",
        confidence=0.7,
        evidence_score=0.7,
        reason="Both articles discuss semiconductors in Malaysia.",
        supporting_article_ids=["a1", "a2"],
    )
    out = apply_relation_policy(edge, source, target, {a1.id: a1, a2.id: a2})
    assert out.relation == "RELATED_TO"


def test_cross_article_without_linking_evidence_is_related_to():
    source = _event(
        "e1",
        "AI demand increases",
        "Enterprises are buying more AI accelerators.",
        countries=["Singapore"],
        source_article_ids=["a1"],
    )
    target = _event(
        "e2",
        "Infineon invests in Kulim",
        "Infineon announced a semiconductor investment in Kulim.",
        source_article_ids=["a2"],
    )
    a1 = _article("AI demand increases", "Enterprises are buying more AI accelerators worldwide.")
    a1.id = "a1"
    a2 = _article("Infineon invests in Kulim", "Infineon announced a semiconductor investment in Kulim, Malaysia.")
    a2.id = "a2"
    edge = CausalEdge(
        id="edg3",
        source_event_id="e1",
        target_event_id="e2",
        relation="CAUSES",
        confidence=0.9,
        evidence_score=0.9,
        reason="AI demand happened and then investment happened.",
        supporting_article_ids=["a1"],
    )
    out = apply_relation_policy(edge, source, target, {a1.id: a1, a2.id: a2})
    assert out.relation == "RELATED_TO"


def test_core_first_graph_drops_unrelated_context():
    intent = parse_query_intent(QUERY)
    articles = [
        _article(
            "Infineon invests in new Kulim semiconductor capacity",
            "Infineon will invest in additional semiconductor manufacturing capacity at its Kulim, Malaysia facility.",
            url="https://example.com/infineon",
        ),
        _article(
            "Nvidia launches new gaming GPU",
            "Nvidia launched a new GeForce gaming GPU with DLSS for consumers.",
            url="https://example.com/nvidia",
        ),
        _article(
            "Microsoft launches new cloud region in Malaysia",
            "Microsoft launched a new cloud region in Malaysia.",
            url="https://example.com/msft",
        ),
        _article(
            "Alibaba increases cloud investment in Southeast Asia",
            "Alibaba Cloud is spending more on data centres across Southeast Asia.",
            url="https://example.com/alibaba",
            country="Singapore",
        ),
    ]
    for idx, article in enumerate(articles, start=1):
        article.id = f"art{idx}"
    classified = classify_articles(intent, articles)
    labels = {item.article.title: item.result.classification for item in classified}
    assert labels["Infineon invests in new Kulim semiconductor capacity"] == "CORE"
    assert labels["Nvidia launches new gaming GPU"] == "REJECTED"
    assert labels["Microsoft launches new cloud region in Malaysia"] != "CORE"
    assert labels["Alibaba increases cloud investment in Southeast Asia"] != "CORE"

    events = [
        _event("core1", articles[0].title, articles[0].body, source_article_ids=["art1"], companies=["Infineon"]),
        _event("noise1", articles[1].title, articles[1].body, source_article_ids=["art2"], countries=["United States"]),
        _event("noise2", articles[2].title, articles[2].body, source_article_ids=["art3"], companies=["Microsoft"]),
    ]
    core, context = assemble_events(intent, events, articles, classified)
    titles = {event.title for event in core + context}
    assert any("Infineon" in title for title in titles)
    assert not any("Nvidia" in title for title in titles)
    assert not any("Microsoft" in title for title in titles)


def test_core_article_stub_is_not_demoted():
    intent = parse_query_intent(QUERY)
    article = _article(
        "Infineon expands Kulim plant",
        "Infineon will expand its Kulim, Malaysia plant and hire more engineers this year.",
        url="https://example.com/infineon-stub",
    )
    article.id = "art1"
    classified = classify_articles(intent, [article])
    assert classified[0].result.classification == "CORE"
    stubs = [
        _event(
            "e1",
            article.title,
            article.title,
            source_article_ids=["art1"],
            companies=["Infineon"],
        )
    ]
    core, _context = assemble_events(intent, stubs, [article], classified)
    assert any("Infineon" in event.title for event in core)


def test_empty_core_is_a_diagnostic_warning_not_topic_fill():
    intent = parse_query_intent(QUERY)
    articles = [
        _article(
            "Nvidia launches new gaming GPU",
            "Nvidia launched a new GeForce gaming GPU with DLSS for consumers.",
            url="https://example.com/nvidia",
        )
    ]
    articles[0].id = "art1"
    classified = classify_articles(intent, articles)
    events = [
        _event("noise1", articles[0].title, articles[0].body, source_article_ids=["art1"], countries=["United States"])
    ]
    core, context = assemble_events(intent, events, articles, classified)
    diagnostics = build_diagnostics(intent, classified, core + context, [])
    assert diagnostics.core_count == 0
    assert diagnostics.context_count == 0
    assert any("sparse" in warning.lower() or "no core" in warning.lower() for warning in diagnostics.warnings)


def test_html_article_extract_reads_title_and_paragraphs():
    from app.services.web_extract import extract_article_from_html, should_fetch_candidate

    html = """
    <html><head><title>Infineon expands Kulim fab | The Star</title></head>
    <body>
      <nav>Home Business Markets</nav>
      <article>
        <p>Infineon will invest in additional semiconductor manufacturing capacity at its Kulim, Malaysia facility this year.</p>
        <p>The expansion covers advanced packaging lines and is expected to add engineering jobs across Kedah.</p>
      </article>
    </body></html>
    """
    page = extract_article_from_html(html)
    assert "Infineon" in page.title
    assert "Kulim" in page.body
    assert "advanced packaging" in page.body
    assert should_fetch_candidate(
        "https://www.thestar.com.my/business/infineon-kulim-semiconductor-expansion-123456",
        page.title,
        {"provider": "gdelt_ngrams", "is_likely_article": True},
    )
    assert not should_fetch_candidate(
        "https://www.newsnow.co.uk/news/",
        "Latest News",
        {"is_aggregator": True},
    )


def test_event_dedup_merges_kulim_headlines():
    events = [
        _event("a", "Infineon expands Kulim fab", "Infineon expands a fab in Kulim.", companies=["Infineon"], source_article_ids=["1"]),
        _event(
            "b",
            "Infineon increases Malaysia semiconductor capacity",
            "Infineon increases semiconductor capacity in Malaysia.",
            companies=["Infineon"],
            source_article_ids=["2"],
        ),
    ]
    merged = dedupe_events(events)
    assert len(merged) == 1
    assert set(merged[0].source_article_ids) == {"1", "2"}


def test_context_context_edges_are_dropped():
    core = _event("c1", "Infineon expands Kulim fab", "Infineon semiconductor expansion in Kulim.", source_article_ids=["a1"])
    core.relevance_class = "CORE"
    ctx1 = _event("x1", "Vietnam electronics FDI grows", "Vietnam electronics FDI grows.", countries=["Vietnam"], source_article_ids=["a2"])
    ctx1.relevance_class = "CONTEXT"
    ctx2 = _event("x2", "Indonesia data-centre incentives", "Indonesia offers data-centre incentives.", countries=["Indonesia"], source_article_ids=["a3"])
    ctx2.relevance_class = "CONTEXT"
    edges = [
        CausalEdge(
            id="e1",
            source_event_id="x1",
            target_event_id="x2",
            relation="RELATED_TO",
            confidence=0.7,
            reason="both regional",
            supporting_article_ids=["a2", "a3"],
        ),
        CausalEdge(
            id="e2",
            source_event_id="c1",
            target_event_id="x1",
            relation="RELATED_TO",
            confidence=0.6,
            reason="supply chain",
            supporting_article_ids=["a1", "a2"],
        ),
    ]
    out = finalize_edges([core, ctx1, ctx2], edges, [])
    assert {edge.id for edge in out} == {"e2"}
