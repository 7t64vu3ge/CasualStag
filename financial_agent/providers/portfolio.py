from __future__ import annotations

from collections import defaultdict
from typing import Any

from financial_agent.utils.helpers import normalize_identifier, prettify_token


NON_EQUITY_BUCKETS = {"ARBITRAGE", "CASH", "DEBT", "DIVERSIFIED_EQUITY", "OTHERS", "UNCLASSIFIED_MF"}


class PortfolioAnalyticsService:
    def analyze(
        self,
        portfolio: dict[str, Any],
        mutual_funds_data: dict[str, Any],
        market_symbol_lookup: dict[str, str],
        mutual_fund_name_lookup: dict[str, dict[str, Any]],
        sector_map: dict[str, Any],
        market_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        stock_holdings = portfolio["holdings"]["stocks"]
        mf_holdings = portfolio["holdings"]["mutual_funds"]
        total_current_value = float(portfolio["current_value"])

        sector_values: dict[str, float] = defaultdict(float)
        stock_values: dict[str, float] = defaultdict(float)

        direct_stock_value = 0.0
        mutual_fund_value = 0.0
        day_change_absolute = 0.0

        for holding in stock_holdings:
            current_value = float(holding["current_value"])
            symbol = holding["symbol"]
            sector = holding["sector"]
            direct_stock_value += current_value
            day_change_absolute += float(holding["day_change"])
            sector_values[sector] += current_value
            stock_values[symbol] += current_value

        mutual_fund_catalog = mutual_funds_data["mutual_funds"]
        for holding in mf_holdings:
            current_value = float(holding["current_value"])
            mutual_fund_value += current_value
            day_change_absolute += float(holding["day_change"])

            profile = self._resolve_fund_profile(holding, mutual_fund_catalog, mutual_fund_name_lookup)
            self._apply_fund_sector_exposure(holding, profile, sector_values)
            self._apply_fund_stock_exposure(holding, profile, stock_values, market_symbol_lookup)

        previous_day_value = total_current_value - day_change_absolute
        day_change_percent = 0.0
        if previous_day_value:
            day_change_percent = round((day_change_absolute / previous_day_value) * 100, 2)

        sector_allocation = {
            sector: round((value / total_current_value) * 100, 2)
            for sector, value in sorted(sector_values.items(), key=lambda item: item[1], reverse=True)
        }
        stock_exposure = {
            symbol: round((value / total_current_value) * 100, 2)
            for symbol, value in sorted(stock_values.items(), key=lambda item: item[1], reverse=True)
        }
        asset_type_allocation = {
            "DIRECT_STOCKS": round((direct_stock_value / total_current_value) * 100, 2),
            "MUTUAL_FUNDS": round((mutual_fund_value / total_current_value) * 100, 2),
        }

        risks = self._detect_risks(portfolio, sector_allocation, stock_exposure, sector_map, market_data)
        return {
            "pnl": {
                "total_change": round(day_change_absolute, 2),
                "percentage_change": day_change_percent,
            },
            "allocation": sector_allocation,
            "asset_type_allocation": asset_type_allocation,
            "stock_exposure": stock_exposure,
            "risks": risks,
            "portfolio_name": portfolio["user_name"],
            "portfolio_type": portfolio["portfolio_type"],
            "total_current_value": total_current_value,
        }

    def _resolve_fund_profile(
        self,
        holding: dict[str, Any],
        mutual_fund_catalog: dict[str, Any],
        mutual_fund_name_lookup: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        scheme_code = holding["scheme_code"]
        if scheme_code in mutual_fund_catalog:
            return mutual_fund_catalog[scheme_code]

        normalized_name = normalize_identifier(holding["scheme_name"])
        return mutual_fund_name_lookup.get(normalized_name, {})

    def _apply_fund_sector_exposure(
        self,
        holding: dict[str, Any],
        profile: dict[str, Any],
        sector_values: dict[str, float],
    ) -> None:
        fund_value = float(holding["current_value"])
        sector_allocation = profile.get("sector_allocation")
        if sector_allocation:
            for sector, weight in sector_allocation.items():
                sector_values[sector] += fund_value * float(weight) / 100
            return

        asset_allocation = profile.get("asset_allocation")
        if asset_allocation:
            equity_weight = float(asset_allocation.get("equity", 0.0))
            top_equity_holdings = profile.get("top_equity_holdings", [])
            represented_equity = 0.0
            for item in top_equity_holdings:
                sector = item.get("sector")
                weight = float(item.get("weight", 0.0))
                if not sector or not weight:
                    continue
                represented_equity += weight
                sector_values[sector] += fund_value * weight / 100
            if equity_weight > represented_equity:
                sector_values["DIVERSIFIED_EQUITY"] += fund_value * (equity_weight - represented_equity) / 100

            for bucket in ("debt", "arbitrage", "cash"):
                weight = float(asset_allocation.get(bucket, 0.0))
                if weight:
                    sector_values[bucket.upper()] += fund_value * weight / 100
            return

        portfolio_characteristics = profile.get("portfolio_characteristics", {})
        if "arbitrage_exposure" in portfolio_characteristics:
            sector_values["ARBITRAGE"] += fund_value * float(portfolio_characteristics["arbitrage_exposure"]) / 100
            sector_values["DEBT"] += fund_value * float(portfolio_characteristics.get("debt_exposure", 0.0)) / 100
            sector_values["CASH"] += fund_value * float(portfolio_characteristics.get("cash", 0.0)) / 100
            return

        category = profile.get("category", holding.get("category", ""))
        if category in {"CORPORATE_BOND", "GILT"}:
            sector_values["DEBT"] += fund_value
            return

        sector_values["UNCLASSIFIED_MF"] += fund_value

    def _apply_fund_stock_exposure(
        self,
        holding: dict[str, Any],
        profile: dict[str, Any],
        stock_values: dict[str, float],
        market_symbol_lookup: dict[str, str],
    ) -> None:
        fund_value = float(holding["current_value"])
        holdings = profile.get("top_holdings", []) or profile.get("top_equity_holdings", [])
        for item in holdings:
            stock_reference = item.get("stock")
            if not stock_reference:
                continue
            resolved_symbol = market_symbol_lookup.get(normalize_identifier(stock_reference))
            if not resolved_symbol:
                continue
            weight = float(item.get("weight", 0.0))
            stock_values[resolved_symbol] += fund_value * weight / 100

    def _detect_risks(
        self,
        portfolio: dict[str, Any],
        sector_allocation: dict[str, float],
        stock_exposure: dict[str, float],
        sector_map: dict[str, Any],
        market_data: dict[str, Any] | None = None,
    ) -> list[str]:
        risks: list[str] = []

        for sector, weight in sector_allocation.items():
            if sector in NON_EQUITY_BUCKETS:
                continue
            if weight >= 40.0:
                risks.append(f"High exposure to {prettify_token(sector)} ({weight:.2f}%)")

        rate_sensitive = set(sector_map.get("rate_sensitive_sectors", []))
        rate_sensitive_exposure = round(
            sum(weight for sector, weight in sector_allocation.items() if sector in rate_sensitive),
            2,
        )
        if rate_sensitive_exposure >= 55.0:
            risks.append(f"Portfolio is heavily exposed to rate-sensitive sectors ({rate_sensitive_exposure:.2f}%)")

        if stock_exposure:
            top_stock, top_weight = next(iter(stock_exposure.items()))
            if top_weight >= 20.0:
                risks.append(f"Single-stock concentration is elevated in {top_stock} ({top_weight:.2f}%)")

            # Advanced Market-Driven Risks
            if market_data and "stocks" in market_data:
                for symbol, weight in stock_exposure.items():
                    if weight < 1.0: continue # Only check material holdings
                    
                    stock_data = market_data["stocks"].get(symbol, {})
                    if not stock_data: continue

                    # 1. Volatility Risk
                    if float(stock_data.get("beta", 0.0)) > 1.35:
                        risks.append(f"Holding {symbol} adds high systemic volatility (Beta: {stock_data['beta']})")

                    # 2. Valuation Risk
                    if float(stock_data.get("pe_ratio", 0.0)) > 70.0:
                        risks.append(f"Elevated valuation risk in {symbol} (P/E: {stock_data['pe_ratio']})")

                    # 3. Liquidity/Momentum Divergence
                    vol = float(stock_data.get("volume", 0))
                    avg_vol = float(stock_data.get("avg_volume_20d", 0))
                    change = float(stock_data.get("change_percent", 0))
                    if change < -2.5 and vol > avg_vol * 1.5:
                        risks.append(f"High-volume sell-off detected in {symbol} ({change:+.2f}%)")

        existing_warning = portfolio.get("analytics", {}).get("risk_metrics", {}).get("concentration_warning")
        if existing_warning:
            risks.append(existing_warning)

        deduped: list[str] = []
        seen: set[str] = set()
        for risk in risks:
            if risk not in seen:
                deduped.append(risk)
                seen.add(risk)
        return deduped
