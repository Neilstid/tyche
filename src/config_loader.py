"""Configuration loader module using YAML and Pydantic validation."""

import os
import yaml
import logging
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


class AgentYamlConfig(BaseModel):
    """Pydantic model for individual agent configuration in YAML."""
    name: str = Field(..., description="Name of the agent")
    role: str = Field(..., description="Role of the agent")
    goal: str = Field(..., description="Goal objective of the agent")
    backstory: Optional[str] = Field(default="", description="Agent backstory and context")
    llm_model: str = Field(default="openrouter/qwen/qwen3.7-flash", description="LLM model identifier")
    prompt_file: Optional[str] = Field(default="", description="Path to prompt text file")
    tools: Optional[List[str]] = Field(default_factory=list, description="List of tools assigned to agent")


class ManagerYamlConfig(BaseModel):
    """Pydantic model for manager agent configuration in hierarchical teams."""
    name: str = Field(..., description="Manager name")
    role: str = Field(..., description="Manager role")
    goal: str = Field(..., description="Manager goal")
    llm_model: str = Field(default="gpt-4o", description="LLM model identifier for manager")


class TeamYamlMetadata(BaseModel):
    """Pydantic model for team-level configuration metadata."""
    name: str = Field(..., description="Name of the team")
    architecture: Literal["sequential", "hierarchical"] = Field(..., description="Execution architecture")
    description: Optional[str] = Field(default="", description="Team description")


class TeamYamlConfig(BaseModel):
    """Pydantic model for full team configuration file."""
    team: TeamYamlMetadata
    manager: Optional[ManagerYamlConfig] = Field(default=None, description="Manager agent if hierarchical")
    agents: List[AgentYamlConfig] = Field(..., description="List of team agents")


class PlatformConfig(BaseModel):
    name: str = Field(default="Tyche Multi-Agent Trading Platform")
    version: str = Field(default="0.1.0")


class PortfolioSettingsConfig(BaseModel):
    initial_cash: float = Field(default=10000.00, ge=0.0)
    benchmark_symbol: str = Field(default="^GSPC")
    risk_free_rate: float = Field(default=0.02, ge=0.0)
    trading_days_per_year: int = Field(default=252, gt=0)


class StockMarketItem(BaseModel):
    name: str = Field(..., description="Friendly market name (e.g. S&P 500 Index)")
    symbol: str = Field(..., description="Ticker symbol (e.g. ^GSPC)")


class EtfPresetItem(BaseModel):
    name: str = Field(..., description="ETF name (e.g. SPDR S&P 500 ETF Trust)")
    symbol: str = Field(..., description="ETF ticker symbol (e.g. SPY)")
    category: str = Field(default="General", description="Asset class or sector category")


class MarketsSettingsConfig(BaseModel):
    stock_markets: List[StockMarketItem] = Field(default_factory=lambda: [
        StockMarketItem(name="S&P 500 Index", symbol="^GSPC"),
        StockMarketItem(name="Nasdaq Composite", symbol="^IXIC"),
        StockMarketItem(name="Dow Jones Industrial Average", symbol="^DJI"),
        StockMarketItem(name="FTSE 100", symbol="^FTSE"),
    ])
    default_etfs: List[EtfPresetItem] = Field(default_factory=lambda: [
        EtfPresetItem(name="SPDR S&P 500 ETF Trust", symbol="SPY", category="US Large Cap"),
        EtfPresetItem(name="Invesco QQQ Trust", symbol="QQQ", category="US Tech / Growth"),
        EtfPresetItem(name="Vanguard Total Stock Market ETF", symbol="VTI", category="US Total Market"),
        EtfPresetItem(name="iShares Russell 2000 ETF", symbol="IWM", category="US Small Cap"),
        EtfPresetItem(name="SPDR Gold Shares", symbol="GLD", category="Commodities"),
        EtfPresetItem(name="iShares 20+ Year Treasury Bond ETF", symbol="TLT", category="Bonds"),
        EtfPresetItem(name="Technology Select Sector SPDR Fund", symbol="XLK", category="Sector - Tech"),
        EtfPresetItem(name="Financial Select Sector SPDR Fund", symbol="XLF", category="Sector - Financials"),
    ])
    default_tickers: List[str] = Field(default_factory=lambda: ["SPY", "QQQ", "VTI", "IWM", "GLD", "TLT"])



class ExecutionSettingsConfig(BaseModel):
    max_retry_attempts: int = Field(default=2, ge=1)
    fallback_action: str = Field(default="HOLD")
    news_categories: List[str] = Field(default_factory=lambda: ["Politics", "Finance", "Business", "World"])


class DefaultSettingsConfig(BaseModel):
    """Pydantic model for default_settings.yaml."""
    platform: PlatformConfig = Field(default_factory=PlatformConfig)
    portfolio: PortfolioSettingsConfig = Field(default_factory=PortfolioSettingsConfig)
    markets: MarketsSettingsConfig = Field(default_factory=MarketsSettingsConfig)
    execution: ExecutionSettingsConfig = Field(default_factory=ExecutionSettingsConfig)


def load_yaml_file(file_path: str) -> Dict[str, Any]:
    """Read raw YAML file into dictionary."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Configuration file not found: {file_path}")
    
    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def load_team_config(config_path: str) -> TeamYamlConfig:
    """
    Load and validate team YAML configuration file.
    
    :param config_path: Path to team YAML configuration file
    :return: Validated TeamYamlConfig instance
    """
    raw_data = load_yaml_file(config_path)
    try:
        validated_config = TeamYamlConfig.model_validate(raw_data)
        logger.info(f"Loaded and validated team configuration from: {config_path}")
        return validated_config
    except ValidationError as e:
        logger.error(f"Validation error loading team configuration '{config_path}': {e}")
        raise


def load_default_settings(settings_path: str = "config/default_settings.yaml") -> DefaultSettingsConfig:
    """
    Load and validate default platform settings.
    
    :param settings_path: Path to default settings YAML file
    :return: Validated DefaultSettingsConfig instance
    """
    if not os.path.exists(settings_path):
        logger.warning(f"Default settings file not found at '{settings_path}'. Returning defaults.")
        return DefaultSettingsConfig()

    raw_data = load_yaml_file(settings_path)
    try:
        validated_settings = DefaultSettingsConfig.model_validate(raw_data)
        logger.info(f"Loaded default settings from: {settings_path}")
        return validated_settings
    except ValidationError as e:
        logger.error(f"Validation error loading default settings '{settings_path}': {e}")
        raise
