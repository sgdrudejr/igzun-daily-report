#!/usr/bin/env python3
import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent

ASSETS = {
    "S&P500": "^GSPC",
    "KOSPI": "^KS11",
    "USDKRW": "KRW=X",
    "US10Y": "^TNX",
    "WTI": "CL=F",
    "GOLD": "GC=F",
    "NASDAQ": "^IXIC",
    "Nikkei": "^N225",
    "DAX": "^GDAXI",
    "USDJPY": "JPY=X",
    "EURUSD": "EURUSD=X",
}


def parse_iso_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def build_payload(start: date, end: date) -> dict:
    payload = {"start": start.isoformat(), "end": end.isoformat(), "assets": {}}
    for name, ticker in ASSETS.items():
        df = yf.download(
            ticker,
            start=start.isoformat(),
            end=(end + timedelta(days=1)).isoformat(),
            progress=False,
            auto_adjust=False,
        )
        if df is None or df.empty:
            payload["assets"][name] = {"ticker": ticker, "error": "empty"}
            continue

        normalized_cols = {}
        for column in df.columns:
            key = column[0].lower() if isinstance(column, tuple) else str(column).lower()
            normalized_cols[key] = column

        close_col = normalized_cols.get("close", "Close")
        high_col = normalized_cols.get("high", "High")
        low_col = normalized_cols.get("low", "Low")

        records = []
        for idx, row in df.iterrows():
            ds = idx.strftime("%Y-%m-%d")
            records.append(
                {
                    "date": ds,
                    "close": float(row[close_col]) if pd.notna(row[close_col]) else None,
                    "high": float(row[high_col]) if pd.notna(row[high_col]) else None,
                    "low": float(row[low_col]) if pd.notna(row[low_col]) else None,
                }
            )

        payload["assets"][name] = {"ticker": ticker, "records": records}
    return payload


def main():
    parser = argparse.ArgumentParser(description="Fetch market data used by quant and report pipeline")
    parser.add_argument("--base-dir", default=str(ROOT), help="Project root directory")
    parser.add_argument("--start-date", help="History start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", default=date.today().isoformat(), help="History end date (YYYY-MM-DD)")
    parser.add_argument("--lookback-days", type=int, default=370, help="Default lookback days when start-date is omitted")
    parser.add_argument(
        "--output",
        help="Output JSON path (defaults to data/market_data_latest.json under base-dir)",
    )
    args = parser.parse_args()

    root = Path(args.base_dir)
    end = parse_iso_date(args.end_date)
    start = parse_iso_date(args.start_date) if args.start_date else end - timedelta(days=args.lookback_days)
    output = Path(args.output) if args.output else root / "data" / "market_data_latest.json"
    output.parent.mkdir(parents=True, exist_ok=True)

    payload = build_payload(start, end)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"wrote {output}")


if __name__ == "__main__":
    main()
