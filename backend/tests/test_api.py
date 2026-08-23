from __future__ import annotations

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
    with TestClient(app) as client:
        status = client.get("/pipeline/status")
        assert status.status_code == 200
        sources = status.json()["sources"]
        assert len(sources) == 3
        assert all("collector_id" in item for item in sources)

        analysis = client.post("/analyze", json={"query": "AI infrastructure in Southeast Asia"})
        assert analysis.status_code == 200
        body = analysis.json()
        assert body["events"]
        assert body["edges"]
        assert body["stats"]["cross_border"] >= 1
        event_id = next(event["id"] for event in body["events"] if "Alibaba" in event["title"])
        why = client.get(f"/events/{event_id}/why", params={"analysis_id": body["analysis_id"]})
        assert why.status_code == 200
        assert why.json()["narrative"]
        ripple = client.get(f"/events/{event_id}/ripple", params={"analysis_id": body["analysis_id"]})
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
