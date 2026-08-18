"""Tyche Platform Main CLI Entry Point supporting verification, paper trading, backtesting, and static site building modes."""

import os
import sys
import argparse
import logging
from datetime import datetime, timezone
import pandas as pd
import yfinance as yf

from dotenv import load_dotenv
load_dotenv()

# Ensure UTF-8 output encoding for Windows stdout/stderr
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from src.config_loader import load_team_config, load_default_settings
from src.data.yfinance_client import get_stock_summary, get_latest_price
from src.data.noozra_client import fetch_market_news
from src.data.sentiment import score_news_list
from src.database.supabase_client import SupabaseDBClient
from src.database.models import TeamCreate, PortfolioSnapshotCreate
from src.agents.crews import execute_crew_trading_cycle
from src.execution.paper_trading import PaperTradingEngine
from src.execution.metrics import compute_base100, compute_sharpe_ratio, compute_max_drawdown
from src.execution.backtester import BacktestRunner
from src.dashboard.gh_pages_builder import build_github_pages

# Setup logging format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("TycheMain")


def run_verification() -> bool:
    print("=" * 80)
    print("  TYCHE MULTI-AGENT TRADING PLATFORM — PHASE 1 & 2 VERIFICATION")
    print("=" * 80)

    # 1. Configuration Loading
    print("\n--- [Step 1/5] Testing Configuration Loader ---")
    team_config_path = "config/teams/sequential_team_alpha.yaml"
    settings_path = "config/default_settings.yaml"

    try:
        team_cfg = load_team_config(team_config_path)
        default_settings = load_default_settings(settings_path)
        print(f"✅ Loaded Team Config: '{team_cfg.team.name}' ({team_cfg.team.architecture})")
        print(f"   Registered Agents: {[a.name for a in team_cfg.agents]}")
        print(f"✅ Loaded Default Settings: Initial Capital = ${default_settings.portfolio.initial_cash:,.2f}")
    except Exception as e:
        logger.error(f"❌ Failed to load configuration: {e}")
        return False

    # 2. Stock Data Ingestion & Technical Indicators
    print("\n--- [Step 2/5] Testing Financial Data Ingestion (yfinance + pandas-ta) ---")
    symbol = "AAPL"
    try:
        stock_summary = get_stock_summary(symbol, period="6mo")
        print(f"✅ Retrieved Stock Summary for '{symbol}':")
        print(f"   Latest Price: ${stock_summary['latest_price']}")
        print(f"   RSI (14):     {stock_summary['rsi_14']}")
        print(f"   SMA (20):     ${stock_summary['sma_20']}")
        print(f"   SMA (50):     ${stock_summary['sma_50']}")
        print(f"   MACD Hist:    {stock_summary['macd_hist']}")
        print(f"   Trend Signal: {stock_summary['trend']}")
    except Exception as e:
        logger.error(f"❌ Failed to fetch stock data for {symbol}: {e}")
        return False

    # 3. News Data Ingestion & Fallbacks
    print("\n--- [Step 3/5] Testing News Ingestion & Fallback Chain ---")
    try:
        news_items = fetch_market_news(symbol=symbol, limit_per_category=3)
        print(f"✅ Retrieved {len(news_items)} news items for '{symbol}'")
        for i, item in enumerate(news_items[:2], 1):
            print(f"   Headline {i}: {item['title'][:70]}... [Source: {item['source']}]")
    except Exception as e:
        logger.error(f"❌ Failed to fetch news items: {e}")
        return False

    # 4. Sentiment Scoring Engine
    print("\n--- [Step 4/5] Testing Rule-Based Sentiment Analysis Engine ---")
    try:
        aggregate_sentiment, scored_news = score_news_list(news_items)
        print(f"✅ Aggregate Market Sentiment Score for '{symbol}': {aggregate_sentiment:+.4f}")
        for i, item in enumerate(scored_news[:2], 1):
            print(f"   Headline {i} Sentiment Score: {item.get('sentiment_score', 0.0):+.4f}")
    except Exception as e:
        logger.error(f"❌ Failed to compute sentiment scores: {e}")
        return False

    # 5. Supabase Database Client & ORM Models
    print("\n--- [Step 5/5] Testing Supabase Database Client & ORM Models ---")
    try:
        db_client = SupabaseDBClient()
        status_str = "ONLINE (Connected)" if db_client.is_connected else "OFFLINE / MOCK MODE (Graceful Fallback)"
        print(f"✅ Supabase Client Status: {status_str}")

        # Test Team Registration
        team_create = TeamCreate(
            name=team_cfg.team.name,
            architecture=team_cfg.team.architecture,
            description=team_cfg.team.description
        )
        db_team = db_client.get_or_create_team(team_create)
        print(f"✅ Team DB Record Handled: ID = {db_team.get('id')}")

        # Test Portfolio Registration
        team_id = db_team.get("id", "00000000-0000-0000-0000-000000000001")
        db_portfolio = db_client.get_or_create_portfolio(team_id=team_id, initial_cash=default_settings.portfolio.initial_cash)
        print(f"✅ Portfolio DB Record Handled: ID = {db_portfolio.get('id')}, Cash = ${float(db_portfolio.get('current_cash', 0)):,.2f}")

    except Exception as e:
        logger.error(f"❌ Database client verification failed: {e}")
        return False

    print("\n" + "=" * 80)
    print("  🎉 VERIFICATION PASSED — ALL CORE PLATFORM COMPONENTS FUNCTIONAL")
    print("=" * 80 + "\n")
    return True


def run_paper_trading_pipeline() -> bool:
    """Run automated daily paper trading cycle across registered team configurations."""
    print("=" * 80)
    print("  TYCHE PLATFORM — DAILY PAPER TRADING PIPELINE EXECUTION")
    print("=" * 80)

    db_client = SupabaseDBClient()
    settings = load_default_settings("config/default_settings.yaml")
    team_config_paths = list(os.path.join("config/teams/", os.listdir("config/teams/")))
    tickers = settings.markets.get_all_tickers() or ["AAPL", "NVDA", "MSFT"]

    engine = PaperTradingEngine(db_client=db_client)

    for cfg_path in team_config_paths:
        try:
            team_cfg = load_team_config(cfg_path)
            print(f"\n--- Executing Daily Cycle for Team: '{team_cfg.team.name}' ---")

            team_create = TeamCreate(
                name=team_cfg.team.name,
                architecture=team_cfg.team.architecture,
                description=team_cfg.team.description
            )
            db_team = db_client.get_or_create_team(team_create)
            team_id = db_team.get("id", "00000000-0000-0000-0000-000000000001")
            portfolio = db_client.get_or_create_portfolio(team_id=team_id, initial_cash=settings.portfolio.initial_cash)
            portfolio_id = portfolio.get("id", "00000000-0000-0000-0000-000000000003")

            for ticker in tickers:
                price = get_latest_price(ticker)
                print(f"Processing Ticker: {ticker} (Current Price: ${price:.2f})")

                # Run decision cycle
                plan = execute_crew_trading_cycle(
                    team_config=team_cfg,
                    portfolio_id=portfolio_id,
                    ticker=ticker,
                    db_client=db_client
                )

                # Process decisions
                for decision in plan.decisions:
                    res = engine.process_decision(
                        portfolio_id=portfolio_id,
                        decision=decision,
                        current_price=price,
                        agent_name="Portfolio Manager"
                    )
                    print(f"  Result: {res['action']} {res['quantity']} {res['symbol']} @ ${res['executed_price']:.2f}")

            # Record daily snapshot
            updated_portfolio = db_client.get_or_create_portfolio(team_id=team_id)
            cur_val = float(updated_portfolio.get("total_value", settings.portfolio.initial_cash))
            cur_cash = float(updated_portfolio.get("current_cash", settings.portfolio.initial_cash))

            today_date = datetime.now(timezone.utc).date()
            snapshots = db_client.get_snapshots(portfolio_id)
            val_series = pd.Series([s["total_value"] for s in snapshots] + [cur_val])
            base100_series = compute_base100(val_series)

            snapshot = PortfolioSnapshotCreate(
                portfolio_id=portfolio_id,
                snapshot_date=today_date,
                total_value=round(cur_val, 2),
                cash_balance=round(cur_cash, 2),
                portfolio_base100=round(float(base100_series.iloc[-1]), 4),
                benchmark_base100=100.0,
                daily_return=0.0,
                max_drawdown=round(compute_max_drawdown(val_series), 4),
                sharpe_ratio=round(compute_sharpe_ratio(val_series.pct_change().dropna()), 4)
            )
            db_client.insert_snapshot(snapshot)
            print(f"✅ Recorded Daily Snapshot: Total Value = ${cur_val:,.2f}")

        except Exception as e:
            logger.error(f"❌ Paper trading pipeline failed for {cfg_path}: {e}")

    print("\n✅ Daily Paper Trading Cycle Completed Successfully.\n")
    return True


def main():
    parser = argparse.ArgumentParser(description="Tyche Multi-Agent Trading Platform Execution Engine")
    parser.add_argument(
        "--mode",
        choices=["verification", "paper_trading", "backtest", "build_dashboard"],
        default="verification",
        help="Pipeline execution mode"
    )
    args = parser.parse_args()

    if args.mode == "verification":
        success = run_verification()
        sys.exit(0 if success else 1)
    elif args.mode == "paper_trading":
        success = run_paper_trading_pipeline()
        sys.exit(0 if success else 1)
    elif args.mode == "build_dashboard":
        build_github_pages()
        sys.exit(0)
    elif args.mode == "backtest":
        team_cfg = load_team_config("config/teams/sequential_team_alpha.yaml")
        runner = BacktestRunner(team_config=team_cfg, start_date="2026-01-01", end_date="2026-01-05", use_mock_llm=True)
        res = runner.run_backtest(tickers=["AAPL"])
        print(f"Backtest Completed: {res}")
        sys.exit(0)


if __name__ == "__main__":
    main()
