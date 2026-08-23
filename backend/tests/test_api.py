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
