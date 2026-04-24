from __future__ import annotations

import json
from functools import cached_property
from pathlib import Path
from typing import Any

from financial_agent.utils.helpers import normalize_identifier


class DataLoader:
    """Loads and normalizes the mock assignment datasets."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)

    def _load_json(self, filename: str) -> dict[str, Any]:
        with (self.data_dir / filename).open("r", encoding="utf-8") as handle:
            return json.load(handle)

    @cached_property
    def market_data(self) -> dict[str, Any]:
        return self._load_json("market_data.json")

    @cached_property
    def news_data(self) -> dict[str, Any]:
        return self._load_json("news_data.json")

    @cached_property
    def portfolios_data(self) -> dict[str, Any]:
        return self._load_json("portfolios.json")

    @cached_property
    def sector_mapping(self) -> dict[str, Any]:
        return self._load_json("sector_mapping.json")

    @cached_property
    def mutual_funds(self) -> dict[str, Any]:
        return self._load_json("mutual_funds.json")

    @cached_property
    def historical_data(self) -> dict[str, Any]:
        return self._load_json("historical_data.json")

    @cached_property
    def portfolio_aliases(self) -> dict[str, str]:
        portfolios = self.portfolios_data["portfolios"]
        aliases: dict[str, str] = {
            "diversified": "PORTFOLIO_001",
            "sector_heavy": "PORTFOLIO_002",
            "sector_concentrated": "PORTFOLIO_002",
            "banking_heavy": "PORTFOLIO_002",
            "conservative": "PORTFOLIO_003",
            "mf_heavy": "PORTFOLIO_003",
            "mutual_fund_heavy": "PORTFOLIO_003",
        }
        for portfolio_id, portfolio in portfolios.items():
            candidates = {
                portfolio_id,
                portfolio_id.lower(),
                portfolio["portfolio_type"],
                portfolio["user_name"],
                portfolio["description"],
            }
            for candidate in candidates:
                aliases[normalize_identifier(candidate)] = portfolio_id
        return aliases

    @cached_property
    def market_symbol_lookup(self) -> dict[str, str]:
        lookup: dict[str, str] = {}
        for symbol, stock in self.market_data["stocks"].items():
            lookup[normalize_identifier(symbol)] = symbol
            lookup[normalize_identifier(stock["name"])] = symbol
        return lookup

    @cached_property
    def mutual_fund_name_lookup(self) -> dict[str, dict[str, Any]]:
        lookup: dict[str, dict[str, Any]] = {}
        for fund in self.mutual_funds["mutual_funds"].values():
            lookup[normalize_identifier(fund["scheme_name"])] = fund
        return lookup

    def resolve_portfolio_id(self, requested_id: str) -> str:
        portfolios = self.portfolios_data["portfolios"]
        if requested_id in portfolios:
            return requested_id

        normalized = normalize_identifier(requested_id)
        if normalized in portfolios:
            return normalized
        if normalized in self.portfolio_aliases:
            return self.portfolio_aliases[normalized]
        raise KeyError(f"Unknown portfolio id: {requested_id}")

    def list_portfolios(self) -> list[dict[str, Any]]:
        portfolios = self.portfolios_data["portfolios"]
        reverse_aliases: dict[str, set[str]] = {key: set() for key in portfolios}
        for alias, portfolio_id in self.portfolio_aliases.items():
            reverse_aliases.setdefault(portfolio_id, set()).add(alias)

        descriptors: list[dict[str, Any]] = []
        for portfolio_id, portfolio in portfolios.items():
            descriptors.append(
                {
                    "portfolio_id": portfolio_id,
                    "aliases": sorted(reverse_aliases.get(portfolio_id, set())),
                    "user_name": portfolio["user_name"],
                    "portfolio_type": portfolio["portfolio_type"],
                    "description": portfolio["description"],
                }
            )
        return descriptors

    def get_portfolio_state(self, requested_id: str) -> dict[str, Any]:
        portfolio_id = self.resolve_portfolio_id(requested_id)
        portfolios = self.portfolios_data["portfolios"]
        return {
            "portfolio_id": portfolio_id,
            "portfolio": portfolios[portfolio_id],
            "market": self.market_data,
            "news": self.news_data,
            "sector_map": self.sector_mapping,
            "mutual_funds": self.mutual_funds,
            "historical": self.historical_data,
            "market_symbol_lookup": self.market_symbol_lookup,
            "mutual_fund_name_lookup": self.mutual_fund_name_lookup,
        }

