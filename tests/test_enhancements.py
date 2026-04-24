from __future__ import annotations

from fastapi.testclient import TestClient
from financial_agent.api.routes import app

client = TestClient(app)

def test_analyze_no_news_scenario() -> None:
    # Portfolio 003 (conservative) typically has less news coverage in mock data
    response = client.post("/analyze", json={"portfolio_id": "conservative"})
    assert response.status_code == 200
    payload = response.json()
    
    # Verify new fields exist
    assert "causal_graph" in payload
    assert "evaluation_breakdown" in payload
    assert "causality" in payload["evaluation_breakdown"]
    assert "relevance" in payload["evaluation_breakdown"]
    assert "specificity" in payload["evaluation_breakdown"]
    
    # Check if fallback message is used when no drivers are found
    if not payload["drivers"]:
        assert "No significant news events directly impacted your portfolio" in payload["summary"]
    else:
        # If there are drivers, check the causal graph entries
        for node in payload["causal_graph"]:
            assert "event" in node
            assert "portfolio_impact" in node
            assert "entity" in node
            assert "confidence_score" in node

def test_causal_graph_structure() -> None:
    response = client.post("/analyze", json={"portfolio_id": "sector_heavy"})
    assert response.status_code == 200
    payload = response.json()
    
    assert len(payload["causal_graph"]) > 0
    first_node = payload["causal_graph"][0]
    assert isinstance(first_node["event"], str)
    assert isinstance(first_node["portfolio_impact"], float)
    assert first_node["entity"] is not None
