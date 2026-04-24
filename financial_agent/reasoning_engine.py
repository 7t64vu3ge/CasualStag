from __future__ import annotations

import re
from typing import Any, Callable, TypedDict

from financial_agent.explanation import ExplanationService, label_for_target
from financial_agent.observability import ObservabilityService, TraceRun
from financial_agent.portfolio_analytics import NON_EQUITY_BUCKETS
from financial_agent.utils import clamp, normalize_identifier, prettify_token, short_headline

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
    insight: str
    counterfactuals: list[dict[str, Any]]
    non_drivers: list[str]
    causal_graph: list[dict[str, Any]]


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
                "causality": round(clamp(causality, 1.0, 5.0), 2),
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
        
        relevant_sectors = set(portfolio_allocation.keys())
        relevant_stocks = set(stock_exposure.keys())
        
        relevant_signals: list[dict[str, Any]] = []
        for signal in state["market_intelligence"]["processed_news"]:
            target_type = signal["target_type"]
            if target_type == "market":
                relevant_signals.append(signal)
            elif target_type == "sector" and any(s in relevant_sectors for s in signal["sectors"]):
                relevant_signals.append(signal)
            elif target_type == "stock" and any(s in relevant_stocks for s in signal["stocks"]):
                relevant_signals.append(signal)

        state["relevant_signals"] = relevant_signals
        self.observability_service.record_phase(
            state["trace"],
            "filtered_news",
            input_data={"total_news": len(state["market_intelligence"]["processed_news"])},
            output_data={"relevant_signals_count": len(relevant_signals)},
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
            "linked_signals",
            input_data={"relevant_news": len(state["relevant_signals"])},
            output_data={"linked_signals": linked, "conflicts": conflicts},
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
        
        causal_graph = []
        for signal in top_signals:
            causal_graph.append({
                "event": self._cause_label(signal),
                "entity": signal.get("dominant_stock_label") or signal.get("dominant_sector_label") or "Market",
                "portfolio_impact": round(signal["impact"], 2),
                "confidence_score": round(abs(float(signal["sentiment_score"])), 2)
            })
        state["causal_graph"] = causal_graph

        self.observability_service.record_phase(
            state["trace"],
            "drivers",
            output_data={
                "top_signals": top_signals,
                "causal_graph": causal_graph,
            },
        )
        return state

    def explanation_node(self, state: ReasoningState) -> ReasoningState:
        insight = self._build_dominance_insight(
            pnl=state["portfolio_analytics"]["pnl"],
            top_signals=state["top_signals"],
        )
        counterfactuals = self._build_counterfactual(
            pnl=state["portfolio_analytics"]["pnl"],
            top_signals=state["top_signals"],
        )
        non_drivers = self._build_non_drivers(
            allocation=state["portfolio_analytics"]["allocation"],
            sector_trends=state["market_intelligence"]["sector_trends"],
            top_signals=state["top_signals"],
        )
        drivers = [
            {
                "factor": signal["factor"],
                "impact": round(signal["impact"], 2),
                "impact_details": signal.get("impact_details"),
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
            "insight": insight,
            "counterfactuals": counterfactuals,
            "non_drivers": non_drivers,
        }
        explanation = self.explanation_service.generate_summary(explanation_context)
        state["explanation"] = explanation
        state["insight"] = insight
        state["counterfactuals"] = counterfactuals
        state["non_drivers"] = non_drivers
        self.observability_service.record_generation(
            state["trace"],
            "final_summary",
            input_data={"prompt": explanation["prompt"]},
            output_data={"summary": explanation["summary"], "generator": explanation["generator"]},
            model=explanation["model"],
            usage=explanation.get("usage"),
        )
        return state

    def evaluation_node(self, state: ReasoningState) -> ReasoningState:
        evaluation = self.evaluation_service.evaluate(
            summary=state["explanation"]["summary"],
            top_signals=state["top_signals"],
            pnl=state["portfolio_analytics"]["pnl"],
            conflicts=state["conflicts"],
        )
        confidence_assessment = self._confidence_assessment(
            pnl=state["portfolio_analytics"]["pnl"],
            linked_signals=state["linked_signals"],
            top_signals=state["top_signals"],
            conflicts=state["conflicts"],
        )
        evaluation.update(confidence_assessment)
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
            stock_impacts: list[tuple[str, float, float]] = []
            sectors: list[str] = []
            for stock in matched_stocks:
                stock_change = float(market_stocks[stock]["change_percent"])
                stock_impact = stock_change * stock_exposure[stock] / 100
                impact += stock_impact
                stock_impacts.append((stock, stock_change, stock_impact))
                sector = market_stocks[stock]["sector"]
                if sector not in sectors:
                    sectors.append(sector)
            dominant_stock, dominant_change, _ = max(stock_impacts, key=lambda item: abs(item[2]))
            dominant_sector = market_stocks[dominant_stock]["sector"]
            target_label = self._security_label(dominant_stock, market_stocks)
            factor = self._format_factor_label(signal, target_label=target_label, impact=impact)
            causal_chain = (
                f"{short_headline(signal['headline'])} -> {target_label} "
                f"{self._direction_label(impact)} -> portfolio stock exposure"
            )
            return {
                **signal,
                "matched_sectors": sectors,
                "matched_stocks": matched_stocks,
                "impact": round(impact, 2),
                "factor": factor,
                "causal_chain": causal_chain,
                "driver_target": target_label,
                "impact_details": {
                    "impact_pct": round(impact, 2),
                    "sector_weight": round(allocation.get(dominant_sector, 0.0), 2) if dominant_sector in allocation else None,
                    "sector_change": round(float(sector_trends.get(dominant_sector, 0.0)), 2)
                    if dominant_sector in sector_trends
                    else None,
                    "stock_weight": round(stock_exposure[dominant_stock], 2),
                    "stock_change": round(float(dominant_change), 2),
                },
                "primary_key": f"stock:{matched_stocks[0]}",
                "dominant_stock_label": target_label,
                "dominant_sector_label": prettify_token(dominant_sector),
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

        sector_contributions = {
            sector: sector_trends.get(sector, 0.0) * allocation[sector] / 100 for sector in matched_sectors
        }
        impact = round(sum(sector_trends.get(sector, 0.0) * allocation[sector] / 100 for sector in matched_sectors), 2)
        dominant_sector = max(sector_contributions, key=lambda sector: abs(sector_contributions[sector]))
        target_label = prettify_token(dominant_sector)
        factor = self._format_factor_label(signal, target_label=target_label, impact=impact)
        causal_chain = (
            f"{short_headline(signal['headline'])} -> {target_label} sector move -> portfolio exposure in {target_label}"
        )
        return {
            **signal,
            "matched_sectors": matched_sectors,
            "matched_stocks": [],
            "impact": impact,
            "factor": factor,
            "causal_chain": causal_chain,
            "driver_target": target_label,
            "impact_details": {
                "impact_pct": impact,
                "sector_weight": round(allocation[dominant_sector], 2),
                "sector_change": round(float(sector_trends.get(dominant_sector, 0.0)), 2),
                "stock_weight": None,
                "stock_change": None,
            },
            "primary_key": f"sector:{dominant_sector}",
            "dominant_sector_label": target_label,
            "dominant_stock_label": None,
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

    def _confidence_assessment(
        self,
        *,
        pnl: dict[str, Any],
        linked_signals: list[dict[str, Any]],
        top_signals: list[dict[str, Any]],
        conflicts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        completeness = 1.0 if linked_signals else 0.6
        total_top_impact = sum(abs(signal["impact"]) for signal in top_signals)
        pnl_magnitude = abs(pnl["percentage_change"])
        
        # Optimization: More sensitive coverage calculation
        coverage = 1.0 if pnl_magnitude < 0.1 else clamp(total_top_impact / max(pnl_magnitude, 0.01), 0.0, 1.0)
        
        alignment = 0.8
        if total_top_impact > 0:
            pnl_direction = 1 if pnl["percentage_change"] > 0 else -1 if pnl["percentage_change"] < 0 else 0
            aligned = sum(
                abs(signal["impact"])
                for signal in top_signals
                if pnl_direction == 0 or (signal["impact"] > 0 and pnl_direction > 0) or (signal["impact"] < 0 and pnl_direction < 0)
            )
            alignment = aligned / total_top_impact if total_top_impact else 0.7
            
        # Optimization: Factor in the priority of news
        news_strength = 0.5
        if top_signals:
            average_priority = sum(signal["priority_rank"] for signal in top_signals) / (3 * len(top_signals))
            average_sentiment = sum(min(abs(float(signal["sentiment_score"])), 1.0) for signal in top_signals) / len(top_signals)
            news_strength = clamp((0.6 * average_priority) + (0.4 * average_sentiment), 0.0, 1.0)
            
        # Optimization: Harsher conflict penalty for reasoning integrity
        conflict_penalty = min(len(conflicts) * 0.12, 0.36)
        
        confidence = clamp(
            (0.20 * completeness) + (0.35 * coverage) + (0.25 * alignment) + (0.20 * news_strength) - conflict_penalty,
            0.0,
            1.0,
        )
        return {
            "confidence": round(confidence, 2),
            "confidence_factors": {
                "data_completeness": round(completeness, 2),
                "impact_coverage": round(coverage, 2),
                "signal_alignment": round(alignment, 2),
                "news_strength": round(news_strength, 2),
                "conflict_penalty": round(conflict_penalty, 2),
            },
        }

    def _build_dominance_insight(self, *, pnl: dict[str, Any], top_signals: list[dict[str, Any]]) -> str:
        if not top_signals:
            return "No material driver could be isolated from the available signals."

        primary_driver = top_signals[0]
        target_label = primary_driver.get("driver_target", primary_driver["factor"])
        pnl_magnitude = abs(pnl["percentage_change"])
        if pnl_magnitude < 0.01:
            return f"{target_label} was the largest identified driver, but the portfolio finished close to flat."

        share_of_move = min(abs(primary_driver["impact"]) / max(pnl_magnitude, 0.01), 1.0)
        if share_of_move >= 0.5:
            return f"{target_label} accounted for about {share_of_move * 100:.0f}% of the observed portfolio move."
        return f"No single factor dominated; {target_label} was the largest driver at about {share_of_move * 100:.0f}% of the move."

    def _build_counterfactual(
        self,
        *,
        pnl: dict[str, Any],
        top_signals: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        counterfactuals: list[dict[str, Any]] = []
        for driver in top_signals[:2]:
            target_label = driver.get("driver_target", driver["factor"])
            change_without_factor = round(pnl["percentage_change"] - driver["impact"], 2)
            counterfactuals.append({
                "without": target_label,
                "portfolio_change_without_factor": change_without_factor,
                "impact_removed": round(abs(driver["impact"]), 2),
                "insight": (
                    f"Without {target_label}, the portfolio would have been {self._pnl_phrase(change_without_factor)} "
                    f"instead of {self._pnl_phrase(pnl['percentage_change'])}."
                ),
            })
        return counterfactuals

    def _build_non_drivers(
        self,
        *,
        allocation: dict[str, float],
        sector_trends: dict[str, float],
        top_signals: list[dict[str, Any]],
    ) -> list[str]:
        driver_sectors = {sector for signal in top_signals for sector in signal.get("matched_sectors", [])}
        low_exposure_candidates: list[tuple[float, str]] = []
        muted_move_candidates: list[tuple[float, str]] = []

        for sector, weight in allocation.items():
            if sector in NON_EQUITY_BUCKETS or sector in driver_sectors:
                continue

            sector_change = float(sector_trends.get(sector, 0.0))
            contribution = round(sector_change * weight / 100, 2)
            label = prettify_token(sector)
            if weight < 10.0 and abs(contribution) < 0.15:
                low_exposure_candidates.append(
                    (
                        weight,
                        f"{label} had negligible impact due to low exposure ({weight:.2f}%).",
                    )
                )
                continue

            if abs(sector_change) < 0.75 and abs(contribution) < 0.15:
                contribution_text = "<0.10 pp" if abs(contribution) < 0.1 else f"{abs(contribution):.2f} pp"
                muted_move_candidates.append(
                    (
                        abs(sector_change),
                        f"{label} was not a driver because its move was muted ({sector_change:+.2f}%), contributing only {contribution_text}.",
                    )
                )

        non_drivers: list[str] = []
        if low_exposure_candidates:
            low_exposure_candidates.sort(key=lambda item: item[0], reverse=True)
            non_drivers.append(low_exposure_candidates[0][1])
        if muted_move_candidates:
            muted_move_candidates.sort(key=lambda item: item[0])
            non_drivers.append(muted_move_candidates[0][1])

        if non_drivers:
            return non_drivers[:2]

        if top_signals:
            primary_target = top_signals[0].get("driver_target", "the primary driver")
            return [f"No other allocated sector came close to {primary_target} in portfolio impact."]
        return []

    def _format_factor_label(self, signal: dict[str, Any], *, target_label: str, impact: float) -> str:
        cause_label = self._cause_label(signal)
        movement_label = "Decline" if impact < -0.05 else "Strength" if impact > 0.05 else "Stability"
        return f"{cause_label} -> {target_label} {movement_label}"

    def _cause_label(self, signal: dict[str, Any]) -> str:
        for causal_factor in signal.get("causal_factors", []):
            phrase = self._compress_causal_phrase(causal_factor)
            if phrase:
                return phrase

        normalized_targets = {
            normalize_identifier(signal.get("target", "")).replace("_", ""),
            *[normalize_identifier(sector).replace("_", "") for sector in signal.get("sectors", [])],
        }
        for keyword in signal.get("keywords", []):
            phrase = self._format_event_phrase(keyword)
            if phrase and normalize_identifier(phrase).replace("_", "") not in normalized_targets:
                return phrase

        headline_clause = re.split(r",| but | amid | as ", signal["headline"], maxsplit=1, flags=re.IGNORECASE)[0]
        return short_headline(headline_clause, limit=36)

    def _compress_causal_phrase(self, value: str) -> str:
        cleaned = re.sub(r"[()]", "", value).strip(" .,:;-")
        if not cleaned:
            return ""

        stop_verbs = {
            "add",
            "adds",
            "attract",
            "attracting",
            "benefit",
            "benefits",
            "compress",
            "compresses",
            "create",
            "creating",
            "drive",
            "drives",
            "improve",
            "improves",
            "increase",
            "increases",
            "limit",
            "limiting",
            "make",
            "making",
            "offer",
            "offers",
            "pressure",
            "pressuring",
            "reduce",
            "reducing",
            "reflect",
            "reflected",
            "show",
            "showing",
            "signal",
            "signals",
            "support",
            "supports",
            "validate",
            "validates",
            "weigh",
            "weighing",
        }

        selected: list[str] = []
        for raw_word in cleaned.split():
            word = raw_word.strip(" ,.;:()")
            if not word:
                continue
            normalized = word.lower().strip("-")
            if selected and normalized in stop_verbs:
                break
            selected.append(word)
            if len(selected) == 4:
                break

        phrase = " ".join(selected) if selected else " ".join(cleaned.split()[:4])
        return self._format_event_phrase(phrase)

    def _format_event_phrase(self, value: str) -> str:
        formatted_tokens: list[str] = []
        for raw_token in value.split():
            token = raw_token.strip(" ,.;:()")
            if not token:
                continue
            if "-" in token and token.upper() != token:
                parts = [part if part.isupper() else part.capitalize() for part in token.split("-")]
                formatted_tokens.append("-".join(parts))
                continue
            if token.upper() == token or any(char.isdigit() for char in token) or "/" in token:
                formatted_tokens.append(token)
                continue
            formatted_tokens.append(token.capitalize())
        return " ".join(formatted_tokens)

    def _security_label(self, symbol: str, market_stocks: dict[str, Any]) -> str:
        name = market_stocks.get(symbol, {}).get("name") or label_for_target(symbol)
        for suffix in (" Ltd", " Limited"):
            if name.endswith(suffix):
                return name[: -len(suffix)]
        return name

    def _pnl_phrase(self, percentage_change: float) -> str:
        if abs(percentage_change) < 0.01:
            return "roughly flat"
        direction = "down" if percentage_change < 0 else "up"
        return f"{direction} {abs(percentage_change):.2f}%"

    def _direction_label(self, impact: float) -> str:
        if impact > 0:
            return "strength"
        if impact < 0:
            return "weakness"
        return "flat performance"
