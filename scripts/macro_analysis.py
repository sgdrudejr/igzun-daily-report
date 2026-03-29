#!/usr/bin/env python3
"""
Multi-period macro analysis.
Reads market_data_latest.json (yfinance) + FRED raw data,
computes regime classification and module scores for 1일/1주/1개월/3개월/6개월.
Output: data/macro_analysis/{date}.json
"""
import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from quant_formula_engine import (
    classify_market_regime, macro_score, technical_score,
    quant_score, fx_score, total_score,
)
from scoring_engine import minmax
from technical_indicators import rsi, ma_gap, momentum, volatility, relative_strength, adx


def load_market_data(root: Path) -> dict | None:
    p = root / "data/market_data_latest.json"
    if not p.exists():
        return None
    return json.loads(p.read_text())


def extract_series(asset: dict) -> tuple[list, list, list]:
    """Return (closes, highs, lows) from asset records."""
    recs = asset.get("records", [])
    closes = [r["close"] for r in recs if r.get("close") is not None]
    highs = [r["high"] for r in recs if r.get("high") is not None]
    lows = [r["low"] for r in recs if r.get("low") is not None]
    return closes, highs, lows


def load_fred_latest(root: Path, date_str: str) -> dict:
    """Read latest scalar values from FRED raw JSON files."""
    raw_dir = root / "data/raw" / date_str / "fred_api"
    values = {}
    if not raw_dir.exists():
        return values
    for f in raw_dir.glob("*.json"):
        doc = json.loads(f.read_text())
        meta = doc.get("metadata", {})
        sid = meta.get("series_id")
        val = meta.get("latest_value")
        if sid and val:
            try:
                values[sid] = float(val)
            except (ValueError, TypeError):
                pass
    return values


def period_return(closes: list, n: int) -> float | None:
    """Return % change over last n trading days."""
    if len(closes) < n + 1:
        return None
    base = closes[-n - 1]
    if not base:
        return None
    return (closes[-1] / base - 1) * 100


def analyze(root: Path, date_str: str) -> dict:
    market = load_market_data(root)
    if not market:
        return {"error": "market_data_latest.json not found — run load_market_data.py first"}

    a = market["assets"]
    sp, sph, spl = extract_series(a.get("S&P500", {}))
    kospi, _, _ = extract_series(a.get("KOSPI", {}))
    usdkrw, _, _ = extract_series(a.get("USDKRW", {}))
    us10y, _, _ = extract_series(a.get("US10Y", {}))
    wti, _, _ = extract_series(a.get("WTI", {}))
    gold, _, _ = extract_series(a.get("GOLD", {}))
    nas, _, _ = extract_series(a.get("NASDAQ", {}))

    fred = load_fred_latest(root, date_str)

    # --- Macro inputs (latest values) ---
    vix = fred.get("VIXCLS", 20.0)
    us10y_val = fred.get("DGS10", us10y[-1] if us10y else 4.0)
    dxy_val = fred.get("DTWEXBGS", 100.0)
    oil_val = fred.get("DCOILWTICO", wti[-1] if wti else 75.0)
    fedfunds = fred.get("FEDFUNDS", 5.3)
    t10y2y = fred.get("T10Y2Y", 0.0)
    hy_spread = fred.get("BAMLH0A0HYM2", 3.0)
    unrate = fred.get("UNRATE", 4.0)
    cpi_level = fred.get("CPIAUCSL", 315.0)

    # --- Normalize inputs (0–100 scale) ---
    vix_norm = minmax(vix, 10, 50)
    us10y_norm = minmax(us10y_val, 2.0, 6.5)
    dxy_norm = minmax(dxy_val, 90, 125)
    oil_norm = minmax(oil_val, 50, 120)
    inflation_norm = minmax(cpi_level, 295, 345)
    usdkrw_norm = minmax(usdkrw[-1] if usdkrw else 1350, 1200, 1550)

    # --- Technical indicators (uses full series for stability) ---
    rsi_sp = rsi(sp, 14)
    mag_sp = ma_gap(sp, 20, 60)
    mom3_sp = momentum(sp, 63)
    mom12_sp = momentum(sp, 252)
    vol20_sp = volatility(sp, 20)
    rel_sp_kospi = relative_strength(sp, kospi, 120) if kospi else None
    adx_sp = adx(sph, spl, sp, 14) if len(sph) == len(sp) and len(sp) > 15 else None

    growth_norm = minmax(mom12_sp if mom12_sp is not None else 0, -20, 30)

    # --- Regime + scores ---
    regime = classify_market_regime(vix_norm, us10y_norm, dxy_norm, inflation_norm, growth_norm)

    mac = macro_score(vix_norm, us10y_norm, dxy_norm, oil_norm, inflation_norm, growth_norm)
    tech = technical_score(
        rsi_sp,
        minmax(mag_sp or 0, -20, 20),
        minmax(rel_sp_kospi or 0, -30, 30),
        minmax(adx_sp or 20, 0, 60),
        50,
    )
    qnt = quant_score(
        minmax(mom3_sp or 0, -20, 20),
        minmax(mom12_sp or 0, -30, 40),
        minmax(vol20_sp or 20, 5, 50),
        50, 50,
    )
    fx = fx_score(
        minmax(dxy_val, 90, 125),
        usdkrw_norm,
        50, 50, 50,
    )
    total = total_score(regime, macro=mac, technical=tech, quant=qnt, fx=fx)

    def r2(v):
        return round(v, 2) if v is not None else None

    # --- Multi-period returns ---
    PERIODS = [(1, "1일"), (5, "1주"), (21, "1개월"), (63, "3개월"), (126, "6개월")]
    period_data = []
    for n, label in PERIODS:
        period_data.append({
            "label": label,
            "days": n,
            "returns": {
                "sp500": r2(period_return(sp, n)),
                "kospi": r2(period_return(kospi, n)),
                "nasdaq": r2(period_return(nas, n)),
                "gold": r2(period_return(gold, n)),
                "wti": r2(period_return(wti, n)),
                "usdkrw": r2(period_return(usdkrw, n)),
                "us10y_yield_chg": r2((us10y[-1] - us10y[-n-1]) if len(us10y) >= n+1 else None),
            },
        })

    return {
        "date": date_str,
        "regime": regime,
        "scores": {
            "macro": r2(mac),
            "technical": r2(tech),
            "quant": r2(qnt),
            "fx": r2(fx),
            "total": r2(total),
        },
        "macro_inputs": {
            "vix": vix,
            "us10y": us10y_val,
            "dxy": dxy_val,
            "oil": oil_val,
            "fedfunds": fedfunds,
            "t10y2y_spread": t10y2y,
            "hy_spread": hy_spread,
            "unrate": unrate,
            "cpi_level": cpi_level,
        },
        "technical_inputs": {
            "rsi_sp500": r2(rsi_sp),
            "ma_gap_sp500": r2(mag_sp),
            "momentum_3m": r2(mom3_sp),
            "momentum_12m": r2(mom12_sp),
            "volatility_20d": r2(vol20_sp),
            "rel_strength_sp500_vs_kospi": r2(rel_sp_kospi),
            "adx_sp500": r2(adx_sp),
        },
        "latest_prices": {
            "sp500": sp[-1] if sp else None,
            "kospi": kospi[-1] if kospi else None,
            "nasdaq": nas[-1] if nas else None,
            "usdkrw": usdkrw[-1] if usdkrw else None,
            "us10y_yield": us10y_val,
            "wti": oil_val,
            "gold": gold[-1] if gold else None,
        },
        "periods": period_data,
    }


def main():
    parser = argparse.ArgumentParser(description="Multi-period macro analysis")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--base-dir", default=str(ROOT))
    args = parser.parse_args()

    root = Path(args.base_dir)
    result = analyze(root, args.date)

    out_dir = root / "data/macro_analysis"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{args.date}.json"
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"wrote {out_file}")

    regime = result.get("regime", "?")
    total = result.get("scores", {}).get("total", "?")
    print(f"Regime: {regime} | Total score: {total}")


if __name__ == "__main__":
    main()
