"""Financial Metrics Engine computing Base 100, Sharpe Ratio, Max Drawdown, and Portfolio Summaries."""

import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional

from src.database.supabase_client import SupabaseDBClient

logger = logging.getLogger(__name__)


def compute_base100(series: pd.Series) -> pd.Series:
    """
    Compute Base 100 indexed series relative to first valid element.
    Formula: Base100 = 100 * (value / initial_value)
    
    :param series: Time-series of portfolio or asset values.
    :return: pd.Series of indexed values starting at 100.0.
    """
    if series.empty:
        return pd.Series(dtype=float)

    # Clean out initial NaNs or zeros if any
    valid_series = series.dropna()
    if valid_series.empty:
        return pd.Series(dtype=float)

    initial_val = float(valid_series.iloc[0])
    if initial_val <= 0:
        logger.warning("Initial value is <= 0; returning zero series for Base 100.")
        return pd.Series(0.0, index=series.index)

    return (series / initial_val) * 100.0


def compute_sharpe_ratio(daily_returns: pd.Series, risk_free_rate: float = 0.02) -> float:
    """
    Compute Annualized Sharpe Ratio from daily returns.
    Formula: Sharpe = (mean_daily_return - daily_rf) / std_daily_return * sqrt(252)
    
    :param daily_returns: Time-series of daily return percentages or decimals.
    :param risk_free_rate: Annualized risk-free rate (default 0.02 = 2%).
    :return: Annualized Sharpe Ratio float.
    """
    clean_returns = daily_returns.dropna()
    if len(clean_returns) < 2:
        return 0.0

    mean_return = clean_returns.mean()
    std_return = clean_returns.std(ddof=1)

    if pd.isna(std_return) or std_return <= 1e-9:
        return 0.0

    daily_rf = risk_free_rate / 252.0
    sharpe = ((mean_return - daily_rf) / std_return) * np.sqrt(252)
    return float(sharpe) if not np.isnan(sharpe) else 0.0


def compute_max_drawdown(series: pd.Series) -> float:
    """
    Compute Maximum Drawdown from peak over a time series of values.
    Formula: Max Drawdown = min((value - peak) / peak)
    
    :param series: Time-series of portfolio total values.
    :return: Float representing maximum drawdown (e.g. -0.15 for 15% drawdown, 0.0 if no drawdown).
    """
    clean_series = series.dropna()
    if clean_series.empty or len(clean_series) < 1:
        return 0.0

    peak = clean_series.cummax()
    peak_replaced = peak.replace(0, np.nan)
    drawdown = (clean_series - peak_replaced) / peak_replaced
    drawdown = drawdown.fillna(0.0)

    max_dd = float(drawdown.min())
    return max_dd if not np.isnan(max_dd) else 0.0


def compute_win_rate(transactions: list) -> float:
    """
    Compute Win Rate percentage from non-HOLD transactions.
    
    :param transactions: List of transaction dictionaries.
    :return: Win rate percentage (0.0 to 100.0).
    """
    non_hold_trades = [t for t in transactions if t.get("action") in ("BUY", "SELL")]
    if not non_hold_trades:
        return 0.0

    winning_trades = [t for t in non_hold_trades if float(t.get("executed_price", 0.0)) > 0]
    return float((len(winning_trades) / len(non_hold_trades)) * 100.0)


def compute_portfolio_summary_metrics(portfolio_id: str, db_client: Optional[SupabaseDBClient] = None) -> Dict[str, Any]:
    """
    Fetch snapshot series and transaction data from Supabase and compute overall portfolio summary metrics.
    
    :param portfolio_id: Portfolio UUID or string identifier.
    :param db_client: Optional SupabaseDBClient instance.
    :return: Dictionary containing calculated metrics.
    """
    client = db_client or SupabaseDBClient()
    snapshots = client.get_snapshots(portfolio_id)
    transactions = client.get_transactions(portfolio_id)
    portfolio = client.get_portfolio_by_id(portfolio_id) or {
        "id": str(portfolio_id),
        "initial_cash": 10000.0,
        "current_cash": 10000.0,
        "total_value": 10000.0,
    }

    initial_cash = float(portfolio.get("initial_cash", 10000.0))
    current_cash = float(portfolio.get("current_cash", initial_cash))
    total_value = float(portfolio.get("total_value", initial_cash))

    if snapshots:
        df_snap = pd.DataFrame(snapshots)
        df_snap["snapshot_date"] = pd.to_datetime(df_snap["snapshot_date"])
        df_snap = df_snap.sort_values("snapshot_date")

        val_series = df_snap["total_value"].astype(float)
        base100_series = compute_base100(val_series)
        
        if "daily_return" in df_snap.columns and not df_snap["daily_return"].isna().all():
            returns_series = df_snap["daily_return"].astype(float)
        else:
            returns_series = val_series.pct_change().dropna()

        sharpe = compute_sharpe_ratio(returns_series)
        max_dd = compute_max_drawdown(val_series)
        latest_base100 = float(base100_series.iloc[-1]) if not base100_series.empty else 100.0
    else:
        val_series = pd.Series([total_value])
        latest_base100 = 100.0
        sharpe = 0.0
        max_dd = 0.0

    cum_return_pct = ((total_value - initial_cash) / initial_cash) * 100.0
    win_rate_pct = compute_win_rate(transactions)

    return {
        "portfolio_id": portfolio_id,
        "initial_cash": initial_cash,
        "current_cash": current_cash,
        "total_value": total_value,
        "cumulative_return_pct": round(cum_return_pct, 2),
        "base100": round(latest_base100, 2),
        "sharpe_ratio": round(sharpe, 2),
        "max_drawdown": round(max_dd, 4),
        "win_rate_pct": round(win_rate_pct, 2),
        "total_transactions": len(transactions),
    }
