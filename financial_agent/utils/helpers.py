from __future__ import annotations

import re


def normalize_identifier(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
    return re.sub(r"_+", "_", normalized).strip("_")


def prettify_token(value: str) -> str:
    return value.replace("_", " ").title()


def short_headline(value: str, limit: int = 72) -> str:
    headline = value.strip()
    if len(headline) <= limit:
        return headline
    truncated = headline[: limit - 3].rstrip(" ,.;:-")
    return f"{truncated}..."


def format_inr(value: float) -> str:
    return f"INR {value:,.0f}"


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))

