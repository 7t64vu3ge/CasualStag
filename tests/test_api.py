from __future__ import annotations

from fastapi.testclient import TestClient

from financial_agent.main import app


client = TestClient(app)


def test_healthcheck() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_portfolios() -> None:
    response = client.get("/portfolios")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 3
    assert any(item["portfolio_id"] == "PORTFOLIO_002" for item in payload)


def test_analyze_sector_heavy_portfolio() -> None:
    response = client.post("/analyze", json={"portfolio_id": "sector_heavy"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["score"] >= 1.0
    assert 0.0 <= payload["confidence"] <= 1.0
    assert payload["drivers"]
    assert payload["risks"]
    assert "portfolio" in payload["summary"].lower() or "priya" in payload["summary"].lower()

