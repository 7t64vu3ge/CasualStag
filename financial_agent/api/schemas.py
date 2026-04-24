from __future__ import annotations

from pydantic import BaseModel, Field


class CausalNode(BaseModel):
    event: str
    sector: str | None = Field(default=None, description="Dominant sector impacted by the event")
    stock: str | None = Field(default=None, description="Dominant stock impacted by the event")
    portfolio_impact: float = Field(..., description="Estimated portfolio impact in percentage points")


class EvaluationBreakdown(BaseModel):
    causality: float = Field(..., ge=1.0, le=5.0)
    relevance: float = Field(..., ge=1.0, le=5.0)
    specificity: float = Field(..., ge=1.0, le=5.0)


class AnalyzeRequest(BaseModel):
    portfolio_id: str = Field(..., description="Canonical portfolio ID or alias such as sector_heavy")


class ImpactAttribution(BaseModel):
    impact_pct: float = Field(..., description="Estimated portfolio impact in percentage points")
    sector_weight: float | None = Field(default=None, description="Portfolio exposure to the dominant sector")
    sector_change: float | None = Field(default=None, description="Observed move in the dominant sector")
    stock_weight: float | None = Field(default=None, description="Portfolio exposure to the dominant stock")
    stock_change: float | None = Field(default=None, description="Observed move in the dominant stock")


class Driver(BaseModel):
    factor: str
    impact: float = Field(..., description="Estimated portfolio impact in percentage points")
    impact_details: ImpactAttribution | None = None


class Conflict(BaseModel):
    signal: str
    explanation: str


class Counterfactual(BaseModel):
    without: str
    portfolio_change_without_factor: float = Field(..., description="Portfolio day change if the top driver is removed")
    impact_removed: float = Field(..., description="Absolute portfolio impact removed from the top driver")
    insight: str


class ConfidenceFactors(BaseModel):
    data_completeness: float = Field(..., ge=0.0, le=1.0)
    impact_coverage: float = Field(..., ge=0.0, le=1.0)
    signal_alignment: float = Field(..., ge=0.0, le=1.0)
    news_strength: float = Field(..., ge=0.0, le=1.0)
    conflict_penalty: float = Field(..., ge=0.0, le=1.0)


class AnalyzeResponse(BaseModel):
    summary: str
    insight: str | None = None
    drivers: list[Driver]
    risks: list[str]
    conflicts: list[Conflict]
    non_drivers: list[str] = Field(default_factory=list)
    counterfactuals: list[Counterfactual] = Field(default_factory=list, description="What-if analysis for the top drivers")
    causal_graph: list[CausalNode] = Field(default_factory=list, description="Explicit causal chain from event to impact")
    confidence: float = Field(..., ge=0.0, le=1.0)
    confidence_factors: ConfidenceFactors
    score: float = Field(..., ge=0.0, le=5.0)
    evaluation_breakdown: EvaluationBreakdown


class ChatRequest(BaseModel):
    portfolio_id: str
    message: str
    history: list[dict[str, str]] = Field(default_factory=list)


class ChatResponse(BaseModel):
    answer: str
    context_used: list[str]


class PortfolioDescriptor(BaseModel):
    portfolio_id: str
    aliases: list[str]
    user_name: str
    portfolio_type: str
    description: str
