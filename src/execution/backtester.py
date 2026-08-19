"""Historical Backtesting Engine iterating day-by-day and logging snapshots."""

import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
import pandas as pd
import yfinance as yf

from src.config_loader import TeamYamlConfig
from src.agents.crews import execute_crew_trading_cycle
from src.agents.schemas import TeamTradingPlan, TradeDecision
from src.execution.paper_trading import PaperTradingEngine
from src.execution.metrics import compute_base100, compute_sharpe_ratio, compute_max_drawdown
from src.database.models import TeamCreate, PortfolioSnapshotCreate
from src.database.supabase_client import SupabaseDBClient
from src.data.yfinance_client import get_latest_price

logger = logging.getLogger(__name__)


class BacktestRunner:
    """Historical simulation runner executing multi-agent paper trading strategies."""

    def __init__(
        self,
        team_config: TeamYamlConfig,
        start_date: str,
        end_date: str,
        initial_cash: float = 10000.0,
        benchmark_symbol: str = "^GSPC",
        db_client: Optional[SupabaseDBClient] = None,
        use_mock_llm: bool = False
    ) -> None:
        self.team_config = team_config
        self.start_date = start_date
        self.end_date = end_date
        self.initial_cash = initial_cash
        self.benchmark_symbol = benchmark_symbol
        self.db_client = db_client or SupabaseDBClient()
        self.use_mock_llm = use_mock_llm
        self.paper_engine = PaperTradingEngine(db_client=self.db_client)

    def _get_trading_days(self) -> List[date]:
        """Generate list of business days (Mon-Fri) between start_date and end_date."""
        start_dt = pd.to_datetime(self.start_date).date()
        end_dt = pd.to_datetime(self.end_date).date()
        
        bday_range = pd.bdate_range(start=start_dt, end=end_dt)
        return [d.date() for d in bday_range]

    def _fetch_benchmark_prices(self, trading_days: List[date]) -> Dict[date, float]:
        """Fetch historical benchmark close prices mapping dates to prices."""
        benchmark_prices: Dict[date, float] = {}
        try:
            df = yf.download(
                self.benchmark_symbol,
                start=self.start_date,
                end=(pd.to_datetime(self.end_date) + timedelta(days=1)).strftime("%Y-%m-%d"),
                progress=False
            )
            if not df.empty:
                # Handle MultiIndex columns if present in newer yfinance
                close_col = df["Close"]
                if isinstance(close_col, pd.DataFrame):
                    close_col = close_col.iloc[:, 0]

                for idx, price in close_col.items():
                    d = idx.date() if hasattr(idx, "date") else pd.to_datetime(idx).date()
                    benchmark_prices[d] = float(price)
        except Exception as e:
            logger.warning(f"Failed to fetch benchmark prices for '{self.benchmark_symbol}': {e}")

        # Fill missing dates with benchmark fallback values or previous price
        last_price = 5000.0
        result: Dict[date, float] = {}
        for day in trading_days:
            if day in benchmark_prices and not pd.isna(benchmark_prices[day]):
                last_price = benchmark_prices[day]
            result[day] = last_price
        return result

    def run_backtest(self, tickers: List[str]) -> Dict[str, Any]:
        """
        Run chronological day-by-day historical backtest.
        
        :param tickers: List of stock tickers to evaluate (e.g. ['AAPL', 'NVDA']).
        :return: Summary metrics dictionary for the backtest.
        """
        logger.info(f"--- Starting Backtest: Team='{self.team_config.team.name}', Period={self.start_date} to {self.end_date} ---")

        # 1. Register Team & Get/Create Portfolio
        team_create = TeamCreate(
            name=self.team_config.team.name,
            architecture=self.team_config.team.architecture,
            model=self.team_config.team.model,
            description=self.team_config.team.description
        )
        db_team = self.db_client.get_or_create_team(team_create)
        team_id = db_team.get("id", "00000000-0000-0000-0000-000000000001")

        portfolio = self.db_client.get_or_create_portfolio(
            team_id=team_id,
            initial_cash=self.initial_cash,
            benchmark=self.benchmark_symbol
        )
        portfolio_id = portfolio.get("id", "00000000-0000-0000-0000-000000000003")

        # 2. Get Trading Days & Benchmark Prices
        trading_days = self._get_trading_days()
        if not trading_days:
            logger.warning("No valid trading days found in specified range.")
            return {"error": "No trading days"}

        bench_prices = self._fetch_benchmark_prices(trading_days)
        bench_initial_price = bench_prices.get(trading_days[0], 5000.0)

        daily_portfolio_values: List[float] = []
        daily_returns: List[float] = []

        # 3. Iterate Chronologically Day-by-Day
        for day in trading_days:
            day_str = day.strftime("%Y-%m-%d")
            logger.info(f"Executing Backtest Day: {day_str}")

            for ticker in tickers:
                # Fetch price for the day
                current_price = get_latest_price(ticker)
                if current_price <= 0:
                    current_price = 150.0  # Fallback price

                if self.use_mock_llm:
                    # Deterministic simulated decision for test mode
                    plan = TeamTradingPlan(decisions=[
                        TradeDecision(
                            symbol=ticker,
                            action="BUY",
                            quantity=1.0,
                            reasoning=f"Simulated backtest decision on {day_str}"
                        )
                    ])
                else:
                    # Run full CrewAI decision loop
                    plan = execute_crew_trading_cycle(
                        team_config=self.team_config,
                        portfolio_id=portfolio_id,
                        ticker=ticker,
                        db_client=self.db_client
                    )

                # Process decision through PaperTradingEngine
                for decision in plan.decisions:
                    self.paper_engine.process_decision(
                        portfolio_id=portfolio_id,
                        decision=decision,
                        current_price=current_price,
                        agent_name="Backtest Engine"
                    )

            # Get current portfolio value
            current_portfolio = self.db_client.get_or_create_portfolio(team_id)
            current_val = float(current_portfolio.get("total_value", self.initial_cash))
            current_cash = float(current_portfolio.get("current_cash", self.initial_cash))
            daily_portfolio_values.append(current_val)

            # Compute Base 100 values
            val_series = pd.Series(daily_portfolio_values)
            port_base100_series = compute_base100(val_series)
            latest_port_base100 = float(port_base100_series.iloc[-1])

            bench_cur_price = bench_prices.get(day, bench_initial_price)
            bench_base100 = (bench_cur_price / bench_initial_price) * 100.0 if bench_initial_price > 0 else 100.0

            # Returns & Risk metrics to date
            if len(daily_portfolio_values) > 1:
                ret = (daily_portfolio_values[-1] - daily_portfolio_values[-2]) / daily_portfolio_values[-2]
            else:
                ret = 0.0
            daily_returns.append(ret)

            returns_series = pd.Series(daily_returns)
            sharpe = compute_sharpe_ratio(returns_series)
            max_dd = compute_max_drawdown(val_series)

            # 4. Insert Daily Snapshot
            snapshot = PortfolioSnapshotCreate(
                portfolio_id=portfolio_id,
                snapshot_date=day,
                total_value=round(current_val, 2),
                cash_balance=round(current_cash, 2),
                portfolio_base100=round(latest_port_base100, 4),
                benchmark_base100=round(bench_base100, 4),
                daily_return=round(ret, 6),
                max_drawdown=round(max_dd, 4),
                sharpe_ratio=round(sharpe, 4)
            )
            self.db_client.insert_snapshot(snapshot)

        final_portfolio = self.db_client.get_or_create_portfolio(team_id)
        final_val = float(final_portfolio.get("total_value", self.initial_cash))
        cum_return = ((final_val - self.initial_cash) / self.initial_cash) * 100.0

        return {
            "team_name": self.team_config.team.name,
            "portfolio_id": portfolio_id,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "initial_cash": self.initial_cash,
            "final_value": final_val,
            "cumulative_return_pct": round(cum_return, 2),
            "sharpe_ratio": round(sharpe, 2),
            "max_drawdown": round(max_dd, 4),
            "total_trading_days": len(trading_days)
        }
