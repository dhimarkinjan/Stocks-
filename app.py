#!/usr/bin/env python3
"""
Indian stocks MA/EMA screener (NSE) using yfinance.

Filters for:
  1) 50-SMA crossing ABOVE 100-SMA on the latest candle
  2) 20-SMA > 50-SMA
  3) 8-EMA > 20-SMA

Usage examples:
  python screen_india_ma.py --symbols RELIANCE.NS TCS.NS INFY.NS
  python screen_india_ma.py --file tickers.txt
  python screen_india_ma.py --recent 3 --symbols RELIANCE.NS TCS.NS

Notes:
- NSE tickers must end with ".NS" (e.g., HDFCBANK.NS).
- Use --recent N to allow signals that happened within the last N trading days.
"""

import argparse
from datetime import datetime, timedelta
import sys
from typing import List, Optional

import pandas as pd

try:
    import yfinance as yf
except ImportError as e:
    raise SystemExit("Please install dependencies:\n  pip install pandas yfinance") from e


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    close = df["Close"]

    df["SMA20"]  = close.rolling(20).mean()
    df["SMA50"]  = close.rolling(50).mean()
    df["SMA100"] = close.rolling(100).mean()
    df["EMA8"]   = close.ewm(span=8, adjust=False).mean()

    # Golden cross on each day
    df["golden_cross"] = (df["SMA50"] > df["SMA100"]) & (df["SMA50"].shift(1) <= df["SMA100"].shift(1))

    # Trend filters on each day
    df["cond_trend"] = (df["SMA20"] > df["SMA50"]) & (df["EMA8"] > df["SMA20"])
    return df


def fetch_history(symbol: str, period: str = "400d") -> pd.DataFrame:
    # 400 trading days covers > 1.5 years; enough for SMA100 warmup.
    df = yf.download(symbol, period=period, interval="1d", auto_adjust=True, progress=False)
    # Ensure clean index
    if not df.empty:
        df = df.copy()
        df.index = pd.to_datetime(df.index)
    return df


def screen_symbol(symbol: str, recent: int = 0) -> Optional[pd.Series]:
    """
    Return the last row that satisfies all conditions, or None if not found.
    recent: allow crossover within last N trading days (0 = only latest bar).
    """
    df = fetch_history(symbol)
    if df.empty or len(df) < 110:
        return None

    df = compute_indicators(df)
    if recent <= 0:
        # Only today’s bar must have golden cross + trend conditions
        last = df.iloc[-1]
        if bool(last["golden_cross"]) and bool(last["cond_trend"]):
            row = last.copy()
            row["symbol"] = symbol
            row["signal_date"] = df.index[-1].date()
            return row
        return None
    else:
        # Look back up to `recent` bars for golden cross; trend must also be true on that same bar
        tail = df.tail(recent + 1)  # include today
        hits = tail[tail["golden_cross"] & tail["cond_trend"]]
        if hits.empty:
            return None
        last_hit = hits.iloc[-1].copy()
        last_hit["symbol"] = symbol
        last_hit["signal_date"] = hits.index[-1].date()
        return last_hit


def load_symbols(args) -> List[str]:
    if args.symbols:
        return [s if s.endswith(".NS") else f"{s}.NS" for s in args.symbols]
    if args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                syms = [line.strip() for line in f if line.strip()]
            return [s if s.endswith(".NS") else f"{s}.NS" for s in syms]
        except Exception as e:
            print(f"Failed to read {args.file}: {e}", file=sys.stderr)
            sys.exit(2)
    # Default: a small, common NSE set (edit/expand as you like)
    return [
        "RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS",
        "ITC.NS","LT.NS","SBIN.NS","BHARTIARTL.NS","AXISBANK.NS",
        "HINDUNILVR.NS","KOTAKBANK.NS","MARUTI.NS","SUNPHARMA.NS","ASIANPAINT.NS",
    ]


def main():
    parser = argparse.ArgumentParser(description="Indian stocks MA/EMA screener (NSE)")
    parser.add_argument("--symbols", nargs="*", help="Space-separated NSE symbols (with or without .NS)")
    parser.add_argument("--file", help="Path to text file with one symbol per line")
    parser.add_argument("--recent", type=int, default=0, help="Allow signals within last N trading days (default 0 = today only)")
    parser.add_argument("--csv", default="india_ma_screen_results.csv", help="Output CSV path")
    args = parser.parse_args()

    symbols = load_symbols(args)
    results = []

    print(f"Scanning {len(symbols)} symbols...")
    for sym in symbols:
        row = screen_symbol(sym, recent=args.recent)
        if row is not None:
            results.append(row)

    if not results:
        print("No matches found with the current filters.")
        sys.exit(0)

    out = pd.DataFrame(results)
    cols = [
        "symbol","signal_date","Close","SMA20","SMA50","SMA100","EMA8",
    ]
    # Keep available columns
    cols = [c for c in cols if c in out.columns]
    out = out[cols].sort_values(["signal_date","symbol"]).reset_index(drop=True)

    out.to_csv(args.csv, index=False)
    print(out.to_string(index=False))
    print(f"\nSaved results to: {args.csv}")


if __name__ == "__main__":
    main()
