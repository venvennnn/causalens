from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app


def test_health():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert "cna" in body["sources"]


def test_pipeline_status_and_analyze_fallback():
    with (
        patch("app.services.analysis.GDELTClient") as mock_gdelt,
        patch("app.services.analysis.fetch_configured_articles", new_callable=AsyncMock) as mock_fetch,
    ):
        mock_gdelt.return_value.search_gdelt = AsyncMock(return_value=[])
        mock_fetch.return_value = []
        with TestClient(app) as client:
            status = client.get("/pipeline/status")
            assert status.status_code == 200
            body = status.json()
            sources = body["sources"]
            assert len(sources) == 3
            assert all("collector_id" in item for item in sources)
            assert body["gdelt"]["discovery_status"] == "ngrams"

            analysis = client.post("/analyze", json={"query": "AI infrastructure in Southeast Asia"})
            assert analysis.status_code == 200
            payload = analysis.json()
            assert payload["events"]
            assert payload["edges"]
            assert payload["stats"]["cross_border"] >= 1
            event_id = next(event["id"] for event in payload["events"] if "Alibaba" in event["title"])
            why = client.get(f"/events/{event_id}/why", params={"analysis_id": payload["analysis_id"]})
            assert why.status_code == 200
            assert why.json()["narrative"]
            ripple = client.get(f"/events/{event_id}/ripple", params={"analysis_id": payload["analysis_id"]})
            assert ripple.status_code == 200
            assert ripple.json()["markets_connected"] >= 1


def test_healing_event_is_recorded():
    with TestClient(app) as client:
        response = client.post(
            "/pipeline/healing-event",
            json={
                "source": "cna",
                "collector_id": "c_mt5xrjlvou8e3hv9h",
                "message": "Article body extraction recovered after scraper healing.",
            },
        )
        assert response.status_code == 200
        events = client.get("/pipeline/events").json()["events"]
        assert any(item["kind"] == "collector_repaired" for item in events)


def test_debug_gdelt_discovery_skips_brightdata():
    from app.gdelt.pipeline import DiscoveryResult
    from app.gdelt.scoring import RankedCandidate, ScoreBreakdown

    ranked = RankedCandidate(
        snapshot_timestamp="20260823154600",
        gdelt_doc_id=56,
        title="Johor hyperscale data center expansion",
        url="https://www.channelnewsasia.com/business/johor-hyperscale-123",
        domain="www.channelnewsasia.com",
        published_at="2026-08-23T15:46:00.000Z",
        language="en",
        image_url=None,
        relevance_score=18.5,
        breakdown=ScoreBreakdown(tech=6, geography=4, entities=2, title=5, source=1, penalties=0),
        matched_tech_terms=["data center"],
        matched_geo_terms=["johor"],
        matched_entities=[],
        matched_ngrams=["hyperscale data center johor"],
        is_aggregator=False,
        is_likely_article=True,
        country="Malaysia",
    )
    fake = DiscoveryResult(
        ranked=[ranked],
        snapshots=["20260823154600"],
        topic="ai_infrastructure_sea",
        stats=[],
    )
    with patch("app.api.routes.discover_ngrams", new_callable=AsyncMock) as mock_discover:
        mock_discover.return_value = fake
        with TestClient(app) as client:
            response = client.get("/debug/gdelt-discovery")
            assert response.status_code == 200
            body = response.json()
            assert body["brightdata"] is False
            assert body["candidates"][0]["title"].startswith("Johor")
            mock_discover.assert_awaited()


def test_debug_graph_quality_classifies_without_gdelt():
    with TestClient(app) as client:
        response = client.get(
            "/debug/graph-quality",
            params={"query": "Semiconductor investment in Malaysia"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["live_pipeline"] is False
        assert body["intent"]["primary_geographies"] == ["Malaysia"]
        assert body["diagnostics"]["candidate_count"] >= 1
        assert "CORE:" in body["text"]


def test_fetch_reuses_stored_configured_url_without_scraping():
    import asyncio
    from datetime import datetime

    from app.models.db import get_session_factory
    from app.models.schemas import Article, ArticleCandidate
    from app.services.analysis import persist_article
    from app.services.ingest import fetch_configured_articles
    from app.sources.adapters import article_id_for, canonicalize_url

    class BoomClient:
        async def run_collector(self, *args, **kwargs):
            raise AssertionError("Bright Data should not be called for URLs already in store")

    url = "https://www.channelnewsasia.com/business/infineon-kulim-semiconductor-capacity-999001"
    article = Article(
        id=article_id_for(url),
        title="Infineon invests in new Kulim semiconductor capacity",
        url=url,
        source="CNA",
        country="Malaysia",
        body=(
            "Infineon will invest in additional semiconductor manufacturing capacity "
            "at its Kulim, Malaysia facility. " * 12
        ),
        ingested_at=datetime.utcnow(),
    )
    candidate = ArticleCandidate(
        id="g1",
        title=article.title,
        url=url,
        source="CNA",
        country="Malaysia",
        raw={"provider": "gdelt_ngrams", "relevance_score": 9.5},
    )
    with TestClient(app):
        db = get_session_factory()()
        try:
            persist_article(db, article)
            db.commit()
            result = asyncio.run(fetch_configured_articles([candidate], db, client=BoomClient()))
            assert len(result) == 1
            assert canonicalize_url(result[0].url) == canonicalize_url(url)
        finally:
            db.close()


def test_analyze_extracts_off_domain_gdelt_candidates():
    from datetime import datetime

    from app.models.schemas import Article, ArticleCandidate
    from app.sources.adapters import article_id_for

    url = "https://www.thestar.com.my/business/infineon-kulim-semiconductor-expansion-123456"
    article = Article(
        id=article_id_for(url),
        title="Infineon invests in new Kulim semiconductor capacity",
        url=url,
        source="thestar.com.my",
        country="Malaysia",
        body=(
            "Infineon will invest in additional semiconductor manufacturing capacity "
            "at its Kulim, Malaysia facility this year. The expansion covers advanced "
            "packaging and wafer-related operations for automotive and industrial chips."
        ),
        ingested_at=datetime.utcnow(),
    )
    candidate = ArticleCandidate(
        id="g-off",
        title=article.title,
        url=url,
        source="thestar.com.my",
        country="Malaysia",
        raw={"provider": "gdelt_ngrams", "relevance_score": 16.0, "is_likely_article": True},
    )
    with (
        patch("app.services.analysis.GDELTClient") as mock_gdelt,
        patch("app.services.analysis.fetch_configured_articles", new_callable=AsyncMock) as mock_bd,
        patch("app.services.analysis.fetch_open_web_articles", new_callable=AsyncMock) as mock_web,
    ):
        mock_gdelt.return_value.search_gdelt = AsyncMock(return_value=[candidate])
        mock_bd.return_value = []
        mock_web.return_value = [article]
        with TestClient(app) as client:
            response = client.post("/analyze", json={"query": "Semiconductor investment in Malaysia"})
            assert response.status_code == 200
            payload = response.json()
            reasons = " ".join(payload.get("degraded_reasons") or [])
            assert "none on CNA" not in reasons
            assert "could not recover usable bodies" not in reasons
            mock_web.assert_awaited()
            titles = " ".join(event["title"] for event in payload["events"])
            assert "Infineon" in titles or payload["diagnostics"]["core_count"] >= 1
