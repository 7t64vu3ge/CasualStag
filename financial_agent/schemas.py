from __future__ import annotations

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    portfolio_id: str = Field(..., description="Canonical portfolio ID or alias such as sector_heavy")


class Driver(BaseModel):
    factor: str
    impact: float = Field(..., description="Estimated portfolio impact in percentage points")


class Conflict(BaseModel):
    signal: str
    explanation: str


class AnalyzeResponse(BaseModel):
    summary: str
    drivers: list[Driver]
    risks: list[str]
    conflicts: list[Conflict]
    confidence: float = Field(..., ge=0.0, le=1.0)
    score: float = Field(..., ge=0.0, le=5.0)


class PortfolioDescriptor(BaseModel):
    portfolio_id: str
    aliases: list[str]
    user_name: str
    portfolio_type: str
    description: str

