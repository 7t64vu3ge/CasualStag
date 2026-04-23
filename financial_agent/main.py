from __future__ import annotations

from functools import lru_cache

from fastapi import FastAPI, HTTPException

from financial_agent.config import get_settings
from financial_agent.service import FinancialAdvisorService
from financial_agent.schemas import AnalyzeRequest, AnalyzeResponse, PortfolioDescriptor


@lru_cache(maxsize=1)
def get_service() -> FinancialAdvisorService:
    return FinancialAdvisorService(get_settings())


app = FastAPI(
    title="Financial Agent",
    version="1.0.0",
    description="Client-server autonomous financial advisor agent built around deterministic analytics and graph-shaped reasoning.",
)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/portfolios", response_model=list[PortfolioDescriptor])
def list_portfolios() -> list[PortfolioDescriptor]:
    return get_service().list_portfolios()


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze_portfolio(payload: AnalyzeRequest) -> AnalyzeResponse:
    try:
        return get_service().analyze(payload.portfolio_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

