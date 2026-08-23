from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.static_frontend import mount_frontend


def test_api_root_without_frontend():
    app = FastAPI()
    mount_frontend(app, "")
    with TestClient(app) as client:
        body = client.get("/").json()
        assert body["service"] == "causalens-sea"


def test_frontend_index_is_served(tmp_path):
    (tmp_path / "index.html").write_text("<html>causalens</html>", encoding="utf-8")
    next_dir = tmp_path / "_next" / "static"
    next_dir.mkdir(parents=True)
    (next_dir / "app.css").write_text("body{}", encoding="utf-8")
    app = FastAPI()
    mount_frontend(app, str(tmp_path))
    with TestClient(app) as client:
        home = client.get("/")
        assert home.status_code == 200
        assert "causalens" in home.text
        asset = client.get("/_next/static/app.css")
        assert asset.status_code == 200
        assert "body" in asset.text
