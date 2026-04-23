from __future__ import annotations

from typing import Any, Callable, TypedDict

from financial_agent.explanation import ExplanationService, label_for_target
from financial_agent.observability import ObservabilityService, TraceRun
from financial_agent.utils import clamp, prettify_token, short_headline

try:
    from langgraph.graph import END, StateGraph
except ImportError:  # pragma: no cover - optional dependency
    END = None
    StateGraph = None


class ReasoningState(TypedDict, total=False):
    market_intelligence: dict[str, Any]
    portfolio_analytics: dict[str, Any]
    portfolio: dict[str, Any]
    market: dict[str, Any]
    trace: TraceRun
    relevant_signals: list[dict[str, Any]]
    linked_signals: list[dict[str, Any]]
    top_signals: list[dict[str, Any]]
    conflicts: list[dict[str, Any]]
    explanation: dict[str, Any]
    evaluation: dict[str, Any]


class EvaluationService:
    def evaluate(self, summary: str, top_signals: list[dict[str, Any]], pnl: dict[str, Any], conflicts: list[dict[str, Any]]) -> dict[str, Any]:
        causality = 2.5
        if top_signals:
            causality += 1.0
        if any(signal.get("causal_chain") for signal in top_signals):
            causality += 0.9
        if "because" in summary.lower() or "through" in summary.lower():
            causality += 0.4

        total_driver_impact = sum(abs(signal["impact"]) for signal in top_signals)
        pnl_magnitude = abs(pnl["percentage_change"])
        if pnl_magnitude < 0.1:
            relevance = 4.0 if top_signals else 3.0
        else:
            relevance = 2.0 + min(total_driver_impact / pnl_magnitude, 1.0) * 2.5

        specificity = 2.4
        if any(char.isdigit() for char in summary):
            specificity += 1.0
        if any(signal.get("headline") for signal in top_signals):
            specificity += 0.8
        if conflicts:
            specificity += 0.5

        score = round(clamp((causality + relevance + specificity) / 3, 1.0, 5.0), 1)
        return {
            "score": score,
            "breakdown": {
                "causality_clarity": round(clamp(causality, 1.0, 5.0), 2),
                "relevance": round(clamp(relevance, 1.0, 5.0), 2),
                "specificity": round(clamp(specificity, 1.0, 5.0), 2),
            },
        }


class ReasoningEngine:
    def __init__(
        self,
        explanation_service: ExplanationService,
        evaluation_service: EvaluationService,
        observability_service: ObservabilityService,
    ) -> None:
        self.explanation_service = explanation_service
        self.evaluation_service = evaluation_service
        self.observability_service = observability_service
        self._compiled_graph = self._build_langgraph() if StateGraph else None

    def run(self, state: ReasoningState) -> ReasoningState:
        if self._compiled_graph:
            return self._compiled_graph.invoke(state)

        for node in (
            self.filter_signals_node,
            self.link_signals_node,
            self.rank_impacts_node,
            self.explanation_node,
            self.evaluation_node,
        ):
            state = node(state)
        return state

    def _build_langgraph(self):  # pragma: no cover - exercised only when dependency exists
        graph = StateGraph(ReasoningState)
        graph.add_node("filter_signals", self.filter_signals_node)
        graph.add_node("link_signals", self.link_signals_node)
        graph.add_node("rank_impacts", self.rank_impacts_node)
        graph.add_node("explanation", self.explanation_node)
        graph.add_node("evaluation", self.evaluation_node)
        graph.set_entry_point("filter_signals")
        graph.add_edge("filter_signals", "link_signals")
        graph.add_edge("link_signals", "rank_impacts")
        graph.add_edge("rank_impacts", "explanation")
        graph.add_edge("explanation", "evaluation")
        graph.add_edge("evaluation", END)
        return graph.compile()

    def filter_signals_node(self, state: ReasoningState) -> ReasoningState:
        portfolio_allocation = state["portfolio_analytics"]["allocation"]
        stock_exposure = state["portfolio_analytics"]["stock_exposure"]
        relevant_signals: list[dict[str, Any]] = []
        for signal in state["market_intelligence"]["processed_news"]:
            if signal["target_type"] == "market":
                relevant_signals.append(signal)
                continue
            if signal["target_type"] == "sector" and any(sector in portfolio_allocation for sector in signal["sectors"]):
                relevant_signals.append(signal)
                continue
            if signal["target_type"] == "stock" and any(stock in stock_exposure for stock in signal["stocks"]):
                relevant_signals.append(signal)

        state["relevant_signals"] = relevant_signals
        self.observability_service.record_phase(
            state["trace"],
            "reasoning.filter_signals",
            input_data={"total_news": len(state["market_intelligence"]["processed_news"])},
            output_data={"relevant_news": len(relevant_signals)},
        )
        return state

    def link_signals_node(self, state: ReasoningState) -> ReasoningState:
        allocation = state["portfolio_analytics"]["allocation"]
        stock_exposure = state["portfolio_analytics"]["stock_exposure"]
        sector_trends = state["market_intelligence"]["sector_trends"]
        market_stocks = state["market"]["stocks"]
        linked: list[dict[str, Any]] = []
        conflicts: list[dict[str, Any]] = []

        for signal in state["relevant_signals"]:
            linked_signal = self._link_signal(signal, allocation, stock_exposure, sector_trends, market_stocks)
            if not linked_signal or abs(linked_signal["impact"]) < 0.01:
                continue
            linked.append(linked_signal)
            conflict = self._detect_conflict(signal, linked_signal)
            if conflict:
                conflicts.append(conflict)

        state["linked_signals"] = linked
        state["conflicts"] = conflicts
        self.observability_service.record_phase(
            state["trace"],
            "reasoning.link_signals",
            input_data={"relevant_news": len(state["relevant_signals"])},
            output_data={"linked_signals": len(linked), "conflicts": len(conflicts)},
        )
        return state

    def rank_impacts_node(self, state: ReasoningState) -> ReasoningState:
        linked = state["linked_signals"]
        ranked = sorted(
            linked,
            key=lambda item: (abs(item["impact"]), item["priority_rank"], abs(item["sentiment_score"])),
            reverse=True,
        )
        top_signals: list[dict[str, Any]] = []
        seen_keys: set[str] = set()
        for signal in ranked:
            primary_key = signal.get("primary_key", signal["factor"])
            if primary_key in seen_keys:
                continue
            top_signals.append(signal)
            seen_keys.add(primary_key)
            if len(top_signals) == 3:
                break

        if len(top_signals) < 3:
            used_headlines = {signal["headline"] for signal in top_signals}
            for signal in ranked:
                if signal["headline"] in used_headlines:
                    continue
                top_signals.append(signal)
                used_headlines.add(signal["headline"])
                if len(top_signals) == 3:
                    break
        state["top_signals"] = top_signals
        self.observability_service.record_phase(
            state["trace"],
            "reasoning.rank_impacts",
            output_data={
                "top_factors": [signal["factor"] for signal in top_signals],
                "top_impacts": [signal["impact"] for signal in top_signals],
            },
        )
        return state

    def explanation_node(self, state: ReasoningState) -> ReasoningState:
        drivers = [
            {
                "factor": signal["factor"],
                "impact": round(signal["impact"], 2),
                "causal_chain": signal["causal_chain"],
                "headline": signal["headline"],
            }
            for signal in state["top_signals"]
        ]
        explanation_context = {
            "portfolio_name": state["portfolio_analytics"]["portfolio_name"],
            "portfolio_type": state["portfolio_analytics"]["portfolio_type"],
            "pnl": state["portfolio_analytics"]["pnl"],
            "market_sentiment": state["market_intelligence"]["market_sentiment"],
            "drivers": drivers,
            "risks": state["portfolio_analytics"]["risks"],
            "conflicts": state["conflicts"],
        }
        explanation = self.explanation_service.generate_summary(explanation_context)
        state["explanation"] = explanation
        self.observability_service.record_phase(
            state["trace"],
            "reasoning.explanation",
            input_data={"prompt": explanation["prompt"]},
            output_data={"summary": explanation["summary"], "generator": explanation["generator"]},
            metadata={"model": explanation["model"]},
        )
        return state

    def evaluation_node(self, state: ReasoningState) -> ReasoningState:
        evaluation = self.evaluation_service.evaluate(
            summary=state["explanation"]["summary"],
            top_signals=state["top_signals"],
            pnl=state["portfolio_analytics"]["pnl"],
            conflicts=state["conflicts"],
        )
        confidence = self._confidence_score(
            pnl=state["portfolio_analytics"]["pnl"],
            linked_signals=state["linked_signals"],
            top_signals=state["top_signals"],
            conflicts=state["conflicts"],
        )
        evaluation["confidence"] = confidence
        state["evaluation"] = evaluation
        self.observability_service.record_phase(
            state["trace"],
            "reasoning.evaluation",
            output_data=evaluation,
        )
        return state

    def _link_signal(
        self,
        signal: dict[str, Any],
        allocation: dict[str, float],
        stock_exposure: dict[str, float],
        sector_trends: dict[str, float],
        market_stocks: dict[str, Any],
    ) -> dict[str, Any] | None:
        if signal["target_type"] == "stock":
            matched_stocks = [stock for stock in signal["stocks"] if stock in stock_exposure]
            if not matched_stocks:
                return None
            impact = 0.0
            sectors: list[str] = []
            for stock in matched_stocks:
                stock_change = float(market_stocks[stock]["change_percent"])
                impact += stock_change * stock_exposure[stock] / 100
                sector = market_stocks[stock]["sector"]
                if sector not in sectors:
                    sectors.append(sector)
            factor = f"{label_for_target(signal['target'])} price action after {short_headline(signal['headline'])}"
            causal_chain = (
                f"{short_headline(signal['headline'])} -> {label_for_target(signal['target'])} "
                f"{self._direction_label(impact)} -> portfolio stock exposure"
            )
            return {
                **signal,
                "matched_sectors": sectors,
                "matched_stocks": matched_stocks,
                "impact": round(impact, 2),
                "factor": factor,
                "causal_chain": causal_chain,
                "primary_key": f"stock:{matched_stocks[0]}",
            }

        matched_sectors = [sector for sector in signal["sectors"] if sector in allocation]
        if signal["target_type"] == "market" and not matched_sectors:
            matched_sectors = [
                sector
                for sector in allocation
                if sector not in {"ARBITRAGE", "CASH", "DEBT", "DIVERSIFIED_EQUITY", "OTHERS", "UNCLASSIFIED_MF"}
            ][:3]
        if not matched_sectors:
            return None

        impact = round(sum(sector_trends.get(sector, 0.0) * allocation[sector] / 100 for sector in matched_sectors), 2)
        dominant_sector = max(matched_sectors, key=lambda sector: abs(sector_trends.get(sector, 0.0) * allocation[sector] / 100))
        factor = f"{prettify_token(dominant_sector)} move after {short_headline(signal['headline'])}"
        causal_chain = (
            f"{short_headline(signal['headline'])} -> {prettify_token(dominant_sector)} sector move "
            f"-> portfolio exposure in {prettify_token(dominant_sector)}"
        )
        return {
            **signal,
            "matched_sectors": matched_sectors,
            "matched_stocks": [],
            "impact": impact,
            "factor": factor,
            "causal_chain": causal_chain,
            "primary_key": f"sector:{dominant_sector}",
        }

    def _detect_conflict(self, signal: dict[str, Any], linked_signal: dict[str, Any]) -> dict[str, Any] | None:
        sentiment_score = float(signal["sentiment_score"])
        impact = float(linked_signal["impact"])
        sentiment_direction = 1 if sentiment_score > 0.15 else -1 if sentiment_score < -0.15 else 0
        impact_direction = 1 if impact > 0.05 else -1 if impact < -0.05 else 0

        if signal.get("conflict_flag"):
            return {
                "signal": signal["headline"],
                "explanation": signal.get("conflict_explanation", "headline sentiment and price action are not aligned"),
            }

        if sentiment_direction and impact_direction and sentiment_direction != impact_direction:
            return {
                "signal": signal["headline"],
                "explanation": (
                    f"the news tone was {signal['sentiment'].lower()} but the linked market move for the portfolio "
                    f"was {self._direction_label(impact)}"
                ),
            }
        return None

    def _confidence_score(
        self,
        *,
        pnl: dict[str, Any],
        linked_signals: list[dict[str, Any]],
        top_signals: list[dict[str, Any]],
        conflicts: list[dict[str, Any]],
    ) -> float:
        completeness = 1.0 if linked_signals else 0.6
        total_linked_impact = sum(abs(signal["impact"]) for signal in linked_signals)
        total_top_impact = sum(abs(signal["impact"]) for signal in top_signals)
        pnl_magnitude = abs(pnl["percentage_change"])
        coverage = 1.0 if pnl_magnitude < 0.1 else min(total_top_impact / max(pnl_magnitude, 0.01), 1.0)
        alignment = 0.8
        if total_linked_impact > 0:
            pnl_direction = 1 if pnl["percentage_change"] > 0 else -1 if pnl["percentage_change"] < 0 else 0
            aligned = sum(
                abs(signal["impact"])
                for signal in top_signals
                if pnl_direction == 0 or (signal["impact"] > 0 and pnl_direction > 0) or (signal["impact"] < 0 and pnl_direction < 0)
            )
            alignment = aligned / total_top_impact if total_top_impact else 0.7
        conflict_penalty = min(len(conflicts) * 0.08, 0.24)
        confidence = clamp((0.35 * completeness) + (0.4 * coverage) + (0.25 * alignment) - conflict_penalty, 0.0, 1.0)
        return round(confidence, 2)

    def _direction_label(self, impact: float) -> str:
        if impact > 0:
            return "strength"
        if impact < 0:
            return "weakness"
        return "flat performance"
