from __future__ import annotations

from collections import defaultdict
from typing import Any


IMPACT_PRIORITY = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}


class MarketIntelligenceService:
    def analyze(
        self,
        market_data: dict[str, Any],
        news_data: dict[str, Any],
        sector_mapping: dict[str, Any],
        historical_data: dict[str, Any],
    ) -> dict[str, Any]:
        sector_trends = self._derive_sector_trends(market_data, sector_mapping)
        processed_news = self._process_news(news_data)
        return {
            "market_sentiment": self._derive_market_sentiment(market_data, historical_data),
            "sector_trends": sector_trends,
            "processed_news": processed_news,
        }

    def _derive_market_sentiment(
        self,
        market_data: dict[str, Any],
        historical_data: dict[str, Any],
    ) -> str:
        nifty_change = market_data["indices"]["NIFTY50"]["change_percent"]
        sensex_change = market_data["indices"]["SENSEX"]["change_percent"]
        breadth = historical_data.get("market_breadth", {}).get("nifty50", {}).get("advance_decline_ratio", 1.0)
        fear_signal = historical_data.get("market_breadth", {}).get("sentiment_indicator", "")

        score = (nifty_change + sensex_change) / 2
        if breadth < 0.7:
            score -= 0.15
        if fear_signal == "FEAR":
            score -= 0.15

        if score <= -0.5:
            return "Bearish"
        if score >= 0.5:
            return "Bullish"
        return "Neutral"

    def _derive_sector_trends(
        self,
        market_data: dict[str, Any],
        sector_mapping: dict[str, Any],
    ) -> dict[str, float]:
        sector_changes: dict[str, list[float]] = defaultdict(list)
        for stock in market_data["stocks"].values():
            sector_changes[stock["sector"]].append(stock["change_percent"])

        trends: dict[str, float] = {}
        for sector in sector_mapping["sectors"]:
            changes = sector_changes.get(sector, [])
            if changes:
                trends[sector] = round(sum(changes) / len(changes), 2)
                continue
            fallback = market_data.get("sector_performance", {}).get(sector, {}).get("change_percent")
            if fallback is not None:
                trends[sector] = round(float(fallback), 2)
        return trends

    def _process_news(self, news_data: dict[str, Any]) -> list[dict[str, Any]]:
        processed: list[dict[str, Any]] = []
        for article in news_data["news"]:
            scope = article["scope"]
            processed.append(
                {
                    "id": article["id"],
                    "headline": article["headline"],
                    "summary": article["summary"],
                    "published_at": article["published_at"],
                    "source": article["source"],
                    "sentiment": article["sentiment"].title(),
                    "sentiment_score": article["sentiment_score"],
                    "scope": self._normalize_scope(scope),
                    "impact_level": article["impact_level"],
                    "target_type": self._target_type(scope),
                    "target": self._target_value(article),
                    "sectors": article.get("entities", {}).get("sectors", []),
                    "stocks": article.get("entities", {}).get("stocks", []),
                    "indices": article.get("entities", {}).get("indices", []),
                    "keywords": article.get("entities", {}).get("keywords", []),
                    "causal_factors": article.get("causal_factors", []),
                    "conflict_flag": article.get("conflict_flag", False),
                    "conflict_explanation": article.get("conflict_explanation"),
                    "priority_rank": IMPACT_PRIORITY.get(article["impact_level"], 1),
                }
            )
        processed.sort(key=lambda item: (item["priority_rank"], abs(item["sentiment_score"])), reverse=True)
        return processed

    def _normalize_scope(self, scope: str) -> str:
        mapping = {
            "MARKET_WIDE": "Market",
            "SECTOR_SPECIFIC": "Sector",
            "STOCK_SPECIFIC": "Stock",
        }
        return mapping.get(scope, scope.title())

    def _target_type(self, scope: str) -> str:
        mapping = {
            "MARKET_WIDE": "market",
            "SECTOR_SPECIFIC": "sector",
            "STOCK_SPECIFIC": "stock",
        }
        return mapping.get(scope, "market")

    def _target_value(self, article: dict[str, Any]) -> str:
        entities = article.get("entities", {})
        if article["scope"] == "STOCK_SPECIFIC" and entities.get("stocks"):
            return entities["stocks"][0]
        if article["scope"] == "SECTOR_SPECIFIC" and entities.get("sectors"):
            return entities["sectors"][0]
        return "MARKET"

