from __future__ import annotations

from typing import Any

from financial_agent.utils.config import Settings
from financial_agent.utils.data import DataLoader
from financial_agent.providers.llm import ExplanationService
from financial_agent.providers.market import MarketIntelligenceService
from financial_agent.utils.observability import ObservabilityService
from financial_agent.providers.portfolio import PortfolioAnalyticsService
from financial_agent.core.engine import EvaluationService, ReasoningEngine
from financial_agent.api.schemas import AnalyzeResponse, ChatRequest, ChatResponse, ConfidenceFactors, Conflict, Counterfactual, Driver, ImpactAttribution, PortfolioDescriptor


class FinancialAdvisorService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.loader = DataLoader(settings.data_dir)
        self.market_intelligence_service = MarketIntelligenceService()
        self.portfolio_analytics_service = PortfolioAnalyticsService()
        self.observability_service = ObservabilityService(settings)
        self.explanation_service = ExplanationService(settings)
        self.reasoning_engine = ReasoningEngine(
            explanation_service=self.explanation_service,
            evaluation_service=EvaluationService(),
            observability_service=self.observability_service,
        )

    def list_portfolios(self) -> list[PortfolioDescriptor]:
        return [PortfolioDescriptor.model_validate(item) for item in self.loader.list_portfolios()]

    def analyze(self, requested_portfolio_id: str) -> AnalyzeResponse:
        trace = self.observability_service.start_trace(
            name="analyze",
            request_input={"portfolio_id": requested_portfolio_id},
        )
        state = self.loader.get_portfolio_state(requested_portfolio_id)
        self.observability_service.record_phase(
            trace,
            "data.load",
            output_data={
                "portfolio_id": state["portfolio_id"],
                "portfolio_name": state["portfolio"]["user_name"],
                "datasets": ["market_data", "news_data", "portfolios", "sector_mapping", "mutual_funds", "historical_data"],
            },
        )

        market_intelligence = self.market_intelligence_service.analyze(
            market_data=state["market"],
            news_data=state["news"],
            sector_mapping=state["sector_map"],
            historical_data=state["historical"],
        )
        self.observability_service.record_phase(
            trace,
            "phase.market_intelligence",
            output_data={
                "market_sentiment": market_intelligence["market_sentiment"],
                "processed_news": len(market_intelligence["processed_news"]),
                "sector_trend_count": len(market_intelligence["sector_trends"]),
            },
        )

        portfolio_analytics = self.portfolio_analytics_service.analyze(
            portfolio=state["portfolio"],
            mutual_funds_data=state["mutual_funds"],
            market_symbol_lookup=state["market_symbol_lookup"],
            mutual_fund_name_lookup=state["mutual_fund_name_lookup"],
            sector_map=state["sector_map"],
            market_data=state["market"],
        )
        self.observability_service.record_phase(
            trace,
            "phase.portfolio_analytics",
            output_data={
                "pnl": portfolio_analytics["pnl"],
                "risk_count": len(portfolio_analytics["risks"]),
                "top_sector": next(iter(portfolio_analytics["allocation"].items()), None),
            },
        )

        reasoning_state = self.reasoning_engine.run(
            {
                "market_intelligence": market_intelligence,
                "portfolio_analytics": portfolio_analytics,
                "portfolio": state["portfolio"],
                "market": state["market"],
                "trace": trace,
            }
        )

        response = AnalyzeResponse(
            summary=reasoning_state["explanation"]["summary"],
            insight=reasoning_state.get("insight"),
            drivers=[
                Driver(
                    factor=signal["factor"],
                    impact=round(signal["impact"], 2),
                    impact_details=ImpactAttribution(**signal["impact_details"]) if signal.get("impact_details") else None,
                )
                for signal in reasoning_state["top_signals"]
            ],
            risks=portfolio_analytics["risks"],
            conflicts=[
                Conflict(signal=conflict["signal"], explanation=conflict["explanation"])
                for conflict in reasoning_state["conflicts"]
            ],
            non_drivers=reasoning_state.get("non_drivers", []),
            counterfactuals=[Counterfactual(**c) for c in reasoning_state.get("counterfactuals", [])],
            confidence=reasoning_state["evaluation"]["confidence"],
            confidence_factors=ConfidenceFactors(**reasoning_state["evaluation"]["confidence_factors"]),
            score=reasoning_state["evaluation"]["score"],
            evaluation_breakdown=reasoning_state["evaluation"]["breakdown"],
            causal_graph=reasoning_state["causal_graph"],
        )
        self.observability_service.finish_trace(trace, response.model_dump())
        return response

    def chat(self, portfolio_id: str, message: str, history: list[dict[str, str]]) -> ChatResponse:
        # Get context by running analysis
        analysis = self.analyze(portfolio_id)
        
        system_prompt = (
            "You are a professional Financial Advisor Chatbot. "
            "You have access to the user's current portfolio analysis. "
            "Answer questions based ONLY on the provided context. If you don't know, say you don't know. "
            "Be polite, professional, and concise. Do not give direct buy/sell advice, but explain the data.\n\n"
            f"--- PORTFOLIO CONTEXT ---\n"
            f"Summary: {analysis.summary}\n"
            f"Key Drivers: {', '.join([d.factor for d in analysis.drivers])}\n"
            f"Detected Risks: {', '.join(analysis.risks)}\n"
            f"Confidence in Data: {analysis.confidence * 100}%\n"
            "--------------------------"
        )
        
        answer = self.explanation_service.chat(system_prompt, message, history)
        return ChatResponse(
            answer=answer, 
            context_used=["Portfolio Analysis", "Market Drivers", "Risk Matrix"]
        )
