"""CrewAI Orchestration module supporting Sequential & Hierarchical teams, validation retry, and safety fallbacks."""

import os
import re
import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from crewai import Crew, Task, Process

from src.config_loader import TeamYamlConfig
from src.agents.factory import build_agents_from_team_config
from src.agents.schemas import TeamTradingPlan, TradeDecision
from src.database.supabase_client import SupabaseDBClient

logger = logging.getLogger(__name__)


def setup_execution_file_logging() -> str:
    """Ensure logs directory exists and return daily log file path."""
    os.makedirs("./logs", exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"./logs/raw_execution_{today}.log"


def log_raw_execution(message: str) -> None:
    """Append detailed execution log entry to daily log file."""
    log_path = setup_execution_file_logging()
    timestamp = datetime.now(timezone.utc).isoformat()
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")


def log_error_execution(error_msg: str) -> None:
    """Append error details to ./logs/errors.log and daily log file."""
    os.makedirs("./logs", exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    timestamp = datetime.now(timezone.utc).isoformat()

    error_path = "./logs/errors.log"
    with open(error_path, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {error_msg}\n")

    daily_path = f"./logs/raw_execution_{today}.log"
    with open(daily_path, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] [ERROR] {error_msg}\n")


def extract_and_parse_json_plan(raw_text: str, default_ticker: str) -> TeamTradingPlan:
    """
    Extract and validate TeamTradingPlan Pydantic model from raw LLM output string.
    
    :param raw_text: Output text from CrewAI task
    :param default_ticker: Stock ticker symbol as fallback if symbol missing
    :return: Validated TeamTradingPlan instance
    """
    if not raw_text or not raw_text.strip():
        raise ValueError("Raw output string is empty.")

    cleaned = raw_text.strip()

    # Search for markdown codeblock containing JSON
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        # Search for first '{' and last '}'
        start_idx = cleaned.find("{")
        end_idx = cleaned.rfind("}")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            json_str = cleaned[start_idx:end_idx + 1]
        else:
            json_str = cleaned

    try:
        data = json.loads(json_str)
        if isinstance(data, list):
            data = {"decisions": data}
        
        # Ensure default ticker if symbol missing
        if "decisions" in data and isinstance(data["decisions"], list):
            for dec in data["decisions"]:
                if isinstance(dec, dict) and "symbol" not in dec:
                    dec["symbol"] = default_ticker

        return TeamTradingPlan.model_validate(data)
    except Exception as e:
        raise ValueError(f"JSON validation failed: {e}. Output was: {raw_text[:200]}")


def build_trading_crew(
    team_config: TeamYamlConfig,
    portfolio_id: str,
    ticker: str,
    db_client: Optional[SupabaseDBClient] = None,
    validation_error: Optional[str] = None
) -> Crew:
    """
    Build CrewAI Crew instance (Sequential or Hierarchical) with agent tasks.
    
    :param team_config: TeamYamlConfig instance loaded from YAML
    :param portfolio_id: Portfolio UUID or string identifier
    :param ticker: Stock ticker symbol (e.g. 'AAPL')
    :param db_client: Optional SupabaseDBClient instance
    :param validation_error: Optional error string from previous failed validation attempt
    :return: Configured CrewAI Crew instance
    """
    worker_agents, manager_agent = build_agents_from_team_config(team_config)
    tasks: List[Task] = []

    retry_instruction = ""
    if validation_error:
        retry_instruction = (
            f"\n\nCRITICAL FIX REQUIRED: Previous attempt failed output validation with error:\n"
            f"'{validation_error}'\n"
            f"You MUST fix your output to strictly conform to valid JSON format:\n"
            f'{{"decisions": [{{"symbol": "{ticker}", "action": "BUY"|"SELL"|"HOLD", "quantity": float, "reasoning": "string"}}]}}'
        )

    if team_config.team.architecture == "sequential":
        # Create pipeline tasks for worker agents
        for agent in worker_agents:
            if "Macro" in agent.role or "News" in agent.role:
                task_desc = f"Fetch and analyze market news & sentiment for ticker '{ticker}' using fetch_market_news_and_sentiment tool.{retry_instruction}"
                expected_out = f"News analysis and aggregate sentiment score for {ticker}."
            elif "Technical" in agent.role or "Indicators" in agent.role:
                task_desc = f"Evaluate technical indicators (RSI, SMA, MACD) for ticker '{ticker}' using fetch_technical_indicators tool.{retry_instruction}"
                expected_out = f"Technical indicator assessment and trend signal for {ticker}."
            else:
                task_desc = (
                    f"Synthesize news and technical reports for ticker '{ticker}'. Query portfolio state for '{portfolio_id}' using get_portfolio_state tool. "
                    f"Formulate final trading decision strictly in JSON schema format:\n"
                    f'{{"decisions": [{{"symbol": "{ticker}", "action": "BUY"|"SELL"|"HOLD", "quantity": 0.0, "reasoning": "detailed explanation"}}]}}{retry_instruction}'
                )
                expected_out = f"Strict JSON formatted TeamTradingPlan for {ticker}."

            task = Task(
                description=task_desc,
                expected_output=expected_out,
                agent=agent,
            )
            tasks.append(task)

        return Crew(
            agents=worker_agents,
            tasks=tasks,
            process=Process.sequential,
            verbose=True,
        )

    else:
        # Hierarchical architecture
        task = Task(
            description=(
                f"Coordinate analysis for ticker '{ticker}' and portfolio '{portfolio_id}'. "
                f"Collect news sentiment, technical indicators, and current portfolio state. "
                f"Formulate final trading decision strictly in JSON schema format:\n"
                f'{{"decisions": [{{"symbol": "{ticker}", "action": "BUY"|"SELL"|"HOLD", "quantity": 0.0, "reasoning": "detailed explanation"}}]}}{retry_instruction}'
            ),
            expected_output=f"Strict JSON formatted TeamTradingPlan for {ticker}.",
            agent=worker_agents[-1] if worker_agents else None,
        )

        return Crew(
            agents=worker_agents,
            tasks=[task],
            process=Process.hierarchical,
            manager_agent=manager_agent,
            verbose=True,
        )


def execute_crew_trading_cycle(
    team_config: TeamYamlConfig,
    portfolio_id: str,
    ticker: str,
    db_client: Optional[SupabaseDBClient] = None,
) -> TeamTradingPlan:
    """
    Execute crew trading cycle with 1x retry logic on validation failure and 2nd failure safety fallback.
    
    :param team_config: Loaded TeamYamlConfig instance
    :param portfolio_id: Portfolio UUID or ID string
    :param ticker: Stock ticker symbol
    :param db_client: Optional SupabaseDBClient instance
    :return: Validated TeamTradingPlan instance
    """
    team_name = team_config.team.name
    log_raw_execution(f"--- Starting Trading Cycle: Team='{team_name}', Ticker='{ticker}', Portfolio='{portfolio_id}' ---")

    # --- Attempt 1 ---
    try:
        crew = build_trading_crew(team_config, portfolio_id, ticker, db_client=db_client)
        raw_result = str(crew.kickoff(inputs={"ticker": ticker, "portfolio_id": portfolio_id}))
        log_raw_execution(f"[Attempt 1 Output]: {raw_result}")
        plan = extract_and_parse_json_plan(raw_result, default_ticker=ticker)
        log_raw_execution(f"[Attempt 1 Success]: Validated {len(plan.decisions)} decisions.")
        return plan
    except Exception as e1:
        err_msg_1 = f"Attempt 1 JSON Validation Failed for ticker {ticker}: {e1}"
        log_error_execution(err_msg_1)
        log_raw_execution("[Attempt 1 Failed] Initiating Attempt 2 (First Retry) with validation error re-prompt...")

    # --- Attempt 2 (First Retry with validation error re-prompt) ---
    try:
        retry_crew = build_trading_crew(
            team_config, portfolio_id, ticker, db_client=db_client, validation_error=err_msg_1
        )
        raw_result_2 = str(retry_crew.kickoff(inputs={"ticker": ticker, "portfolio_id": portfolio_id, "validation_error": err_msg_1}))
        log_raw_execution(f"[Attempt 2 Output]: {raw_result_2}")
        plan_2 = extract_and_parse_json_plan(raw_result_2, default_ticker=ticker)
        log_raw_execution(f"[Attempt 2 Success]: Validated {len(plan_2.decisions)} decisions after retry.")
        return plan_2
    except Exception as e2:
        err_msg_2 = f"Attempt 2 JSON Validation Failed for ticker {ticker}: {e2}. Triggering SAFETY FALLBACK."
        log_error_execution(err_msg_2)

    # --- Safety Fallback (Triggered when 2nd attempt fails) ---
    fallback_decision = TradeDecision(
        symbol=ticker,
        action="HOLD",
        quantity=0.0,
        reasoning="SAFETY FALLBACK: Agent output failed JSON validation twice."
    )
    fallback_plan = TeamTradingPlan(decisions=[fallback_decision])
    log_raw_execution(f"[Safety Fallback Triggered]: {fallback_plan}")
    return fallback_plan
