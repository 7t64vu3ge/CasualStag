from __future__ import annotations

from fastapi.testclient import TestClient

from financial_agent.api.routes import app


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
    assert payload["confidence_factors"]["data_completeness"] >= 0.0
    assert payload["drivers"]
    assert payload["drivers"][0]["impact_details"]["impact_pct"] == payload["drivers"][0]["impact"]
    assert payload["risks"]
    assert payload["non_drivers"]
    assert payload["counterfactuals"][0]["impact_removed"] >= 0.0
    assert 1 <= len(payload["summary"].splitlines()) <= 4
    assert "portfolio" in payload["summary"].lower() or "priya" in payload["summary"].lower()
