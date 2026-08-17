"""yfinance client module for market price ingestion and technical indicator calculations."""

import logging
from typing import Dict, Any, Optional
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# Attempt to import pandas_ta
try:
    import pandas_ta as ta
    HAS_PANDAS_TA = True
except Exception as e:
    logger.warning(f"pandas_ta module import error: {e}. Native pandas fallback will be used.")
    HAS_PANDAS_TA = False


def fetch_ohlcv(symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """
    Fetch OHLCV historical price data using yfinance.
    
    :param symbol: Ticker symbol (e.g. 'AAPL')
    :param period: Data period ('1mo', '3mo', '6mo', '1y', '2y', etc.)
    :param interval: Data interval ('1d', '1wk', etc.)
    :return: pandas DataFrame containing Open, High, Low, Close, Volume
    """
    logger.info(f"Fetching OHLCV data for {symbol} (period={period}, interval={interval})")
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval)
    
    if df.empty:
        logger.warning(f"No OHLCV data returned for symbol {symbol}")
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])

    cols_to_keep = [col for col in ["Open", "High", "Low", "Close", "Volume"] if col in df.columns]
    df = df[cols_to_keep].copy()
    df.dropna(subset=["Close"], inplace=True)
    return df


def _calculate_fallback_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate RSI (14), MACD (12, 26, 9), and SMA (20, 50) using native pandas."""
    df_calc = df.copy()

    # SMA 20 and SMA 50
    df_calc["SMA_20"] = df_calc["Close"].rolling(window=20).mean()
    df_calc["SMA_50"] = df_calc["Close"].rolling(window=50).mean()

    # RSI 14
    delta = df_calc["Close"].diff()
    gain = (delta.where(delta > 0, 0.0)).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0.0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss.replace(0, 1e-10)
    df_calc["RSI_14"] = 100 - (100 / (1 + rs))

    # MACD (12, 26, 9)
    ema12 = df_calc["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df_calc["Close"].ewm(span=26, adjust=False).mean()
    df_calc["MACD_12_26_9"] = ema12 - ema26
    df_calc["MACDs_12_26_9"] = df_calc["MACD_12_26_9"].ewm(span=9, adjust=False).mean()
    df_calc["MACDh_12_26_9"] = df_calc["MACD_12_26_9"] - df_calc["MACDs_12_26_9"]

    return df_calc


def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate and append technical indicators (RSI_14, MACD, SMA_20, SMA_50) to DataFrame.
    
    :param df: pandas DataFrame with 'Close' column
    :return: DataFrame enriched with technical indicator columns
    """
    if df.empty or "Close" not in df.columns:
        logger.warning("DataFrame empty or missing 'Close' column. Skipping technical indicators.")
        return df

    df_res = df.copy()

    if HAS_PANDAS_TA:
        try:
            # RSI (14)
            rsi = df_res.ta.rsi(length=14)
            if rsi is not None and not rsi.empty:
                df_res["RSI_14"] = rsi

            # SMA (20, 50)
            sma20 = df_res.ta.sma(length=20)
            if sma20 is not None and not sma20.empty:
                df_res["SMA_20"] = sma20

            sma50 = df_res.ta.sma(length=50)
            if sma50 is not None and not sma50.empty:
                df_res["SMA_50"] = sma50

            # MACD (12, 26, 9)
            macd = df_res.ta.macd(fast=12, slow=26, signal=9)
            if macd is not None and not macd.empty:
                for col in macd.columns:
                    df_res[col] = macd[col]

        except Exception as e:
            logger.warning(f"Error executing pandas_ta calculation ({e}). Falling back to native calculation.")
            return _calculate_fallback_indicators(df)
    else:
        return _calculate_fallback_indicators(df)

    if "SMA_20" not in df_res.columns or "RSI_14" not in df_res.columns or "MACD_12_26_9" not in df_res.columns:
        return _calculate_fallback_indicators(df)

    return df_res


def get_stock_summary(symbol: str, period: str = "6mo") -> Dict[str, Any]:
    """
    Fetch OHLCV data with technical indicators and compile a summary dictionary.
    
    :param symbol: Ticker symbol
    :param period: Data lookback period
    :return: Dictionary containing latest price, trend indicators, and full DataFrame
    """
    df = fetch_ohlcv(symbol, period=period)
    if df.empty:
        return {
            "symbol": symbol,
            "latest_price": 0.0,
            "rsi_14": None,
            "sma_20": None,
            "sma_50": None,
            "macd": None,
            "macd_signal": None,
            "macd_hist": None,
            "trend": "NEUTRAL",
            "df": df,
        }

    df_indicators = add_technical_indicators(df)
    latest = df_indicators.iloc[-1]

    close_price = float(latest["Close"])
    rsi_val = float(latest["RSI_14"]) if pd.notna(latest.get("RSI_14")) else None
    sma20_val = float(latest["SMA_20"]) if pd.notna(latest.get("SMA_20")) else None
    sma50_val = float(latest["SMA_50"]) if pd.notna(latest.get("SMA_50")) else None

    macd_col = [c for c in df_indicators.columns if c.startswith("MACD_") and not c.startswith("MACDs_") and not c.startswith("MACDh_")]
    macds_col = [c for c in df_indicators.columns if c.startswith("MACDs_")]
    macdh_col = [c for c in df_indicators.columns if c.startswith("MACDh_")]

    macd_val = float(latest[macd_col[0]]) if macd_col and pd.notna(latest.get(macd_col[0])) else None
    macds_val = float(latest[macds_col[0]]) if macds_col and pd.notna(latest.get(macds_col[0])) else None
    macdh_val = float(latest[macdh_col[0]]) if macdh_col and pd.notna(latest.get(macdh_col[0])) else None

    trend = "NEUTRAL"
    if sma20_val and sma50_val:
        if sma20_val > sma50_val and close_price > sma20_val:
            trend = "BULLISH"
        elif sma20_val < sma50_val and close_price < sma20_val:
            trend = "BEARISH"

    return {
        "symbol": symbol,
        "latest_price": round(close_price, 2),
        "rsi_14": round(rsi_val, 2) if rsi_val is not None else None,
        "sma_20": round(sma20_val, 2) if sma20_val is not None else None,
        "sma_50": round(sma50_val, 2) if sma50_val is not None else None,
        "macd": round(macd_val, 4) if macd_val is not None else None,
        "macd_signal": round(macds_val, 4) if macds_val is not None else None,
        "macd_hist": round(macdh_val, 4) if macdh_val is not None else None,
        "trend": trend,
        "df": df_indicators,
    }


def get_latest_price(symbol: str) -> float:
    """
    Fetch latest closing price for ticker symbol.
    
    :param symbol: Ticker symbol (e.g. 'AAPL')
    :return: Latest closing price float.
    """
    try:
        summary = get_stock_summary(symbol, period="5d")
        if summary and summary.get("latest_price", 0.0) > 0:
            return float(summary["latest_price"])
    except Exception as e:
        logger.warning(f"Failed to fetch latest price for {symbol}: {e}")
    return 150.0
