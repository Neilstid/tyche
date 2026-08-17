"""Trade decision and trading plan Pydantic schemas for Agent output validation."""

from typing import Literal, List
from pydantic import BaseModel, Field


class TradeDecision(BaseModel):
    """Pydantic model representing an individual stock trade decision."""
    symbol: str = Field(description="Stock ticker symbol, e.g. AAPL, NVDA, MSFT")
    action: Literal["BUY", "SELL", "HOLD"] = Field(description="Trading decision action")
    quantity: float = Field(default=0.0, ge=0.0, description="Quantity of shares to buy or sell")
    reasoning: str = Field(description="Detailed financial and technical justification for the decision")


class TeamTradingPlan(BaseModel):
    """Pydantic model wrapping list of decisions output by CrewAI team."""
    decisions: List[TradeDecision]
