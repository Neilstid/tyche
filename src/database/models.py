"""Pydantic database schemas representing tables in Supabase PostgreSQL."""

from datetime import datetime, date
from typing import Optional, List, Any, Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, ConfigDict


class TeamBase(BaseModel):
    name: str = Field(..., description="Unique name of the agent team")
    architecture: Literal["sequential", "hierarchical"] = Field(..., description="Team architecture pattern")
    description: Optional[str] = Field(default="", description="Detailed summary of team strategy")


class TeamCreate(TeamBase):
    pass


class TeamModel(TeamBase):
    id: UUID = Field(default_factory=uuid4)
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AgentBase(BaseModel):
    team_id: UUID = Field(..., description="Foreign key to owning team")
    name: str = Field(..., description="Agent name")
    role: str = Field(..., description="Agent role description")
    llm_model: str = Field(..., description="LLM model identifier")
    prompt_file: Optional[str] = Field(default="", description="Path to prompt file")
    tools_list: Optional[List[str]] = Field(default_factory=list, description="List of agent tools")


class AgentCreate(AgentBase):
    pass


class AgentModel(AgentBase):
    id: UUID = Field(default_factory=uuid4)
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PortfolioBase(BaseModel):
    team_id: UUID = Field(..., description="Foreign key to owning team")
    initial_cash: float = Field(default=10000.00, ge=0.0)
    current_cash: float = Field(default=10000.00, ge=0.0)
    total_value: float = Field(default=10000.00, ge=0.0)
    benchmark_symbol: Optional[str] = Field(default="^GSPC")


class PortfolioCreate(PortfolioBase):
    pass


class PortfolioUpdate(BaseModel):
    current_cash: Optional[float] = Field(default=None, ge=0.0)
    total_value: Optional[float] = Field(default=None, ge=0.0)
    updated_at: Optional[datetime] = None


class PortfolioModel(PortfolioBase):
    id: UUID = Field(default_factory=uuid4)
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PositionBase(BaseModel):
    portfolio_id: UUID = Field(..., description="Foreign key to portfolio")
    symbol: str = Field(..., description="Ticker symbol")
    quantity: float = Field(default=0.0, ge=0.0)
    avg_buy_price: float = Field(..., ge=0.0)
    current_price: float = Field(..., ge=0.0)
    market_value: float = Field(..., ge=0.0)


class PositionCreate(PositionBase):
    pass


class PositionModel(PositionBase):
    id: UUID = Field(default_factory=uuid4)
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class TransactionBase(BaseModel):
    portfolio_id: UUID = Field(..., description="Foreign key to portfolio")
    agent_name: str = Field(..., description="Name of executing agent")
    symbol: str = Field(..., description="Ticker symbol")
    action: Literal["BUY", "SELL", "HOLD"] = Field(..., description="Trade action")
    quantity: float = Field(default=0.0, ge=0.0)
    executed_price: Optional[float] = Field(default=None, ge=0.0)
    total_amount: Optional[float] = Field(default=None, ge=0.0)
    reasoning: Optional[str] = Field(default="")
    raw_log_path: Optional[str] = Field(default="")


class TransactionCreate(TransactionBase):
    pass


class TransactionModel(TransactionBase):
    id: UUID = Field(default_factory=uuid4)
    executed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PortfolioSnapshotBase(BaseModel):
    portfolio_id: UUID = Field(..., description="Foreign key to portfolio")
    snapshot_date: date = Field(..., description="Snapshot date")
    total_value: float = Field(..., ge=0.0)
    cash_balance: float = Field(..., ge=0.0)
    portfolio_base100: float = Field(default=100.00)
    benchmark_base100: float = Field(default=100.00)
    daily_return: Optional[float] = Field(default=0.0)
    max_drawdown: Optional[float] = Field(default=0.0)
    sharpe_ratio: Optional[float] = Field(default=0.0)


class PortfolioSnapshotCreate(PortfolioSnapshotBase):
    pass


class PortfolioSnapshotModel(PortfolioSnapshotBase):
    id: UUID = Field(default_factory=uuid4)
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
