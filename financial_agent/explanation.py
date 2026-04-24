from __future__ import annotations

import os
from typing import Any

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional dependency
    OpenAI = None  # type: ignore[assignment]

from financial_agent.config import Settings
from financial_agent.utils import prettify_token, short_headline


class ExplanationService:
    def __init__(self, settings: Settings) -> None:
        self.mode = settings.explanation_mode
        self._client: Any | None = None
        self._model = settings.groq_model

        if self.mode == "groq" and OpenAI and settings.groq_api_key:
            self._client = OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=settings.groq_api_key,
            )

    def generate_summary(self, context: dict[str, Any]) -> dict[str, Any]:
        prompt = self._build_prompt(context)
        if self._client:
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a financial advisor agent. Explain portfolio movement using only the supplied "
                                "facts. Return exactly four lines labeled Overall movement, Primary driver, "
                                "Secondary driver, and Key risk. Be concise, causal, specific, and do not fabricate numbers."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.2,
                )
                summary = response.choices[0].message.content or ""
                if summary:
                    usage = None
                    if hasattr(response, "usage") and response.usage:
                        usage = {
                            "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
                            "completion_tokens": getattr(response.usage, "completion_tokens", 0),
                            "total_tokens": getattr(response.usage, "total_tokens", 0),
                        }
                    return {
                        "summary": summary.strip(),
                        "prompt": prompt,
                        "generator": "groq",
                        "model": self._model,
                        "usage": usage,
                    }
            except Exception:
                pass

        return {
            "summary": self._build_template_summary(context),
            "prompt": prompt,
            "generator": "template",
            "model": None,
        }

    def chat(self, system_prompt: str, user_message: str, history: list[dict[str, str]] | None = None) -> str:
        if not self._client:
            return "AI Chat is disabled (mode is 'template'). Please enable 'groq' mode in .env to use the chatbot."
        
        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=0.7,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            return f"Chat Error: {str(e)}"

    def _build_prompt(self, context: dict[str, Any]) -> str:
        drivers = context["drivers"]
        risks = context["risks"]
        conflicts = context["conflicts"]
        non_drivers = context.get("non_drivers", [])
        insight = context.get("insight")
        counterfactuals = context.get("counterfactuals", [])
        counterfactual = counterfactuals[0] if counterfactuals else None

        driver_lines = []
        for driver in drivers:
            impact_details = driver.get("impact_details") or {}
            detail_bits = [f"impact: {driver['impact']:.2f} pp"]
            if impact_details.get("sector_weight") is not None:
                detail_bits.append(f"sector weight: {impact_details['sector_weight']:.2f}%")
            if impact_details.get("sector_change") is not None:
                detail_bits.append(f"sector change: {impact_details['sector_change']:.2f}%")
            if impact_details.get("stock_weight") is not None:
                detail_bits.append(f"stock weight: {impact_details['stock_weight']:.2f}%")
            if impact_details.get("stock_change") is not None:
                detail_bits.append(f"stock change: {impact_details['stock_change']:.2f}%")
            driver_lines.append(
                f"- Factor: {driver['factor']}; {'; '.join(detail_bits)}; chain: {driver['causal_chain']}"
            )

        risk_lines = [f"- {risk}" for risk in risks] or ["- None"]
        conflict_lines = [f"- {conflict['signal']}: {conflict['explanation']}" for conflict in conflicts] or ["- None"]
        non_driver_lines = [f"- {item}" for item in non_drivers] or ["- None"]

        pnl = context["pnl"]
        return "\n".join(
            [
                "### CONTEXT ###",
                f"Portfolio: {context['portfolio_name']} ({context['portfolio_type']})",
                f"Day Change: {pnl['percentage_change']:.2f}% ({pnl['total_change']:.2f} INR)",
                f"Market Sentiment: {context['market_sentiment']}",
                f"Dominance Insight: {insight or 'No single factor dominated.'}",
                f"Counterfactual Analysis: {counterfactual['insight'] if counterfactual else 'N/A'}",
                "",
                "### TOP DRIVERS ###",
                *driver_lines,
                "",
                "### NON-DRIVERS & CONTEXTUAL NOISE ###",
                *non_driver_lines,
                "",
                "### RISKS & CONFLICTS ###",
                f"Identified Risks: {', '.join(risks) if risks else 'None'}",
                *conflict_lines,
                "",
                "### OUTPUT INSTRUCTIONS ###",
                "Return exactly four lines and no bullets:",
                "Overall movement: summarize the day move and market backdrop with numbers.",
                "Primary driver: detail the top driver, its impact, and why it dominated (use the dominance insight).",
                "Secondary driver: mention the second driver or explain why other sectors were muted using non-driver facts.",
                "Key risk: state the main portfolio risk and address any conflicts/ambiguities mentioned above.",
                "Constraints: max 4 lines, no repetition, use only supplied facts, be professional and causal.",
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
        non_drivers = context.get("non_drivers", [])
        insight = context.get("insight")
        counterfactuals = context.get("counterfactuals", [])
        counterfactual = counterfactuals[0] if counterfactuals else None

        overall_line = (
            f"Overall movement: {context['portfolio_name']}'s portfolio {direction} {magnitude:.2f}% "
            f"({pnl['total_change']:+.2f} INR) in a {context['market_sentiment'].lower()} market."
        )

        if not primary_driver:
            primary_line = "Primary driver: No significant news events directly impacted your portfolio. Movement appears market-driven."
        else:
            primary_line = (
                f"Primary driver: {primary_driver['factor']} drove {primary_driver['impact']:+.2f} pp."
            )
            if insight:
                primary_line += f" {insight}"
            if counterfactual:
                primary_line += (
                    f" Without it, the portfolio would have been "
                    f"{self._movement_phrase(counterfactual['portfolio_change_without_factor'])}."
                )

        if secondary_driver and abs(secondary_driver["impact"]) >= 0.15:
            secondary_line = (
                f"Secondary driver: {secondary_driver['factor']} added {secondary_driver['impact']:+.2f} pp."
            )
        elif non_drivers:
            secondary_line = f"Secondary driver: No other factor was comparable; {non_drivers[0]}"
        else:
            secondary_line = "Secondary driver: No other factor materially changed the portfolio."

        risk_text = context["risks"][0] if context["risks"] else "No concentrated portfolio risk was flagged"
        key_risk_line = f"Key risk: {risk_text}."
        if conflicts:
            first_conflict = conflicts[0]
            key_risk_line += (
                f" Ambiguity remains around {short_headline(first_conflict['signal'])}: "
                f"{first_conflict['explanation']}."
            )

        return "\n".join([overall_line, primary_line, secondary_line, key_risk_line]).strip()

    def _movement_phrase(self, percentage_change: float) -> str:
        if abs(percentage_change) < 0.01:
            return "roughly flat"
        direction = "down" if percentage_change < 0 else "up"
        return f"{direction} {abs(percentage_change):.2f}%"


def label_for_target(target: str) -> str:
    if target == "MARKET":
        return "market"
    if target.upper() == target and "_" not in target and " " not in target:
        return target
    return prettify_token(target)
