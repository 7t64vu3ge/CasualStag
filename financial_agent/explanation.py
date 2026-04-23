from __future__ import annotations

import os
from typing import Any

from openai import OpenAI

from financial_agent.utils import prettify_token, short_headline


class ExplanationService:
    def __init__(self, mode: str = "template") -> None:
        self.mode = mode
        self.openai_model = os.getenv("OPENAI_MODEL")
        self._client: OpenAI | None = None
        if self.mode == "openai" and os.getenv("OPENAI_API_KEY"):
            self._client = OpenAI()

    def generate_summary(self, context: dict[str, Any]) -> dict[str, Any]:
        prompt = self._build_prompt(context)
        if self._client and self.openai_model:
            try:
                response = self._client.responses.create(
                    model=self.openai_model,
                    input=[
                        {
                            "role": "system",
                            "content": (
                                "You are a financial advisor agent. Explain portfolio movement using only the supplied "
                                "facts. Be concise, causal, and specific. Do not fabricate numbers."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.2,
                )
                summary = getattr(response, "output_text", "").strip()
                if summary:
                    return {
                        "summary": summary,
                        "prompt": prompt,
                        "generator": "openai",
                        "model": self.openai_model,
                    }
            except Exception:
                pass

        return {
            "summary": self._build_template_summary(context),
            "prompt": prompt,
            "generator": "template",
            "model": None,
        }

    def _build_prompt(self, context: dict[str, Any]) -> str:
        drivers = context["drivers"]
        risks = context["risks"]
        conflicts = context["conflicts"]

        driver_lines = []
        for driver in drivers:
            driver_lines.append(
                f"- Factor: {driver['factor']}; impact: {driver['impact']:.2f} pp; chain: {driver['causal_chain']}"
            )

        risk_lines = [f"- {risk}" for risk in risks] or ["- None"]
        conflict_lines = [f"- {conflict['signal']}: {conflict['explanation']}" for conflict in conflicts] or ["- None"]

        pnl = context["pnl"]
        return "\n".join(
            [
                f"Portfolio: {context['portfolio_name']} ({context['portfolio_type']})",
                f"Day change: {pnl['percentage_change']:.2f}% ({pnl['total_change']:.2f} INR)",
                f"Market sentiment: {context['market_sentiment']}",
                "Top drivers:",
                *driver_lines,
                "Risks:",
                *risk_lines,
                "Conflicts:",
                *conflict_lines,
                "Write one short paragraph that explains what moved the portfolio, why it mattered, and any ambiguity.",
            ]
        )

    def _build_template_summary(self, context: dict[str, Any]) -> str:
        pnl = context["pnl"]
        direction = "declined" if pnl["percentage_change"] < 0 else "rose"
        magnitude = abs(pnl["percentage_change"])

        drivers = context["drivers"]
        primary_driver = drivers[0] if drivers else None
        secondary_driver = drivers[1] if len(drivers) > 1 else None
        conflicts = context["conflicts"]

        opening = (
            f"{context['portfolio_name']}'s portfolio {direction} {magnitude:.2f}% for the day in a "
            f"{context['market_sentiment'].lower()} market."
        )

        if not primary_driver:
            return opening

        primary_sentence = (
            f" The largest driver was {primary_driver['factor'].lower()}, which contributed roughly "
            f"{abs(primary_driver['impact']):.2f} percentage points through "
            f"{primary_driver['causal_chain'].lower()}."
        )

        secondary_sentence = ""
        if secondary_driver and abs(secondary_driver["impact"]) >= 0.15:
            secondary_sentence = (
                f" A secondary influence was {secondary_driver['factor'].lower()}, adding "
                f"{abs(secondary_driver['impact']):.2f} percentage points of impact."
            )

        risk_sentence = ""
        if context["risks"]:
            risk_sentence = f" The main portfolio risk remains {context['risks'][0].lower()}."

        conflict_sentence = ""
        if conflicts:
            first_conflict = conflicts[0]
            conflict_sentence = (
                f" One conflicting signal was {short_headline(first_conflict['signal'])}, where "
                f"{first_conflict['explanation'].lower()}."
            )

        return f"{opening}{primary_sentence}{secondary_sentence}{risk_sentence}{conflict_sentence}".strip()


def label_for_target(target: str) -> str:
    if target == "MARKET":
        return "market"
    if target.upper() == target and "_" not in target and " " not in target:
        return target
    return prettify_token(target)
