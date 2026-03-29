#!/usr/bin/env python3
import json, sys
from pathlib import Path
from datetime import date, timedelta
import yfinance as yf
import pandas as pd

ROOT = Path(__file__).parent.parent
OUT = ROOT / 'data/market_data_latest.json'

ASSETS = {
    'S&P500': '^GSPC',
    'KOSPI': '^KS11',
    'USDKRW': 'KRW=X',
    'US10Y': '^TNX',
    'WTI': 'CL=F',
    'GOLD': 'GC=F',
    'NASDAQ': '^IXIC'
}


def main():
    end = date.today()
    start = end - timedelta(days=370)
    payload = {'start': start.isoformat(), 'end': end.isoformat(), 'assets': {}}
    for name, ticker in ASSETS.items():
        df = yf.download(ticker, start=start.isoformat(), end=(end + timedelta(days=1)).isoformat(), progress=False, auto_adjust=False)
        if df is None or df.empty:
            payload['assets'][name] = {'ticker': ticker, 'error': 'empty'}
            continue
        normalized_cols = {}
        for c in df.columns:
            key = c[0].lower() if isinstance(c, tuple) else str(c).lower()
            normalized_cols[key] = c
        close_col = normalized_cols.get('close', 'Close')
        high_col = normalized_cols.get('high', 'High')
        low_col = normalized_cols.get('low', 'Low')
        records = []
        for idx, row in df.iterrows():
            ds = idx.strftime('%Y-%m-%d')
            records.append({
                'date': ds,
                'close': float(row[close_col]) if pd.notna(row[close_col]) else None,
                'high': float(row[high_col]) if pd.notna(row[high_col]) else None,
                'low': float(row[low_col]) if pd.notna(row[low_col]) else None,
            })
        payload['assets'][name] = {'ticker': ticker, 'records': records}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print('wrote', OUT)

if __name__ == '__main__':
    main()
