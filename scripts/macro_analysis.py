#!/usr/bin/env python3
"""
Multi-period macro analysis — 미국/한국/일본/유럽 지역별 + ECOS 통합.
Output: data/macro_analysis/{date}.json
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from quant_formula_engine import (  # noqa: E402
    classify_market_regime,
    fx_score,
    macro_score,
    quant_score,
    technical_score,
    total_score,
)
from scoring_engine import minmax  # noqa: E402
from technical_indicators import adx, ma_gap, momentum, relative_strength, rsi, volatility  # noqa: E402


def load_market_data(path: Path) -> dict | None:
    return json.loads(path.read_text()) if path.exists() else None


def slice_asset(asset: dict, as_of_date: str) -> dict:
    recs = asset.get("records", [])
    filtered = [rec for rec in recs if (rec.get("date") or "") <= as_of_date]
    return {**asset, "records": filtered}


def extract_series(asset: dict) -> tuple[list, list, list]:
    recs = asset.get("records", [])
    closes = [r["close"] for r in recs if r.get("close") is not None]
    highs = [r["high"] for r in recs if r.get("high") is not None]
    lows = [r["low"] for r in recs if r.get("low") is not None]
    return closes, highs, lows


def _candidate_source_dirs(root: Path, source_id: str, as_of_date: str) -> list[Path]:
    raw_root = root / "data" / "raw"
    if not raw_root.exists():
        return []
    candidates = []
    for dated_dir in raw_root.iterdir():
        if not dated_dir.is_dir():
            continue
        if dated_dir.name > as_of_date:
            continue
        source_dir = dated_dir / source_id
        if source_dir.exists():
            candidates.append(source_dir)
    return sorted(candidates, key=lambda path: path.parent.name, reverse=True)


def load_source_snapshot(root: Path, as_of_date: str, source_id: str) -> list[dict]:
    for source_dir in _candidate_source_dirs(root, source_id, as_of_date):
        docs = []
        for json_file in sorted(source_dir.glob("*.json")):
            try:
                docs.append(json.loads(json_file.read_text()))
            except Exception:
                continue
        if docs:
            return docs
    return []


def load_fred_latest(root: Path, date_str: str) -> dict:
    values = {}
    for doc in load_source_snapshot(root, date_str, "fred_api"):
        meta = doc.get("metadata", {})
        sid = meta.get("series_id")
        val = meta.get("latest_value")
        if sid and val not in (None, ""):
            try:
                values[sid] = float(val)
            except (TypeError, ValueError):
                continue
    return values


def load_ecos_latest(root: Path, date_str: str) -> dict:
    values = {}
    for doc in load_source_snapshot(root, date_str, "ecos_api"):
        meta = doc.get("metadata", {})
        tag = meta.get("tag")
        val = meta.get("value")
        if tag and val is not None:
            try:
                values[tag] = float(val)
            except (TypeError, ValueError):
                continue
    return values


def period_return(closes: list, n: int) -> float | None:
    if len(closes) < n + 1 or not closes[-n - 1]:
        return None
    return (closes[-1] / closes[-n - 1] - 1) * 100


def analyze(root: Path, date_str: str, market_data_file: Path) -> dict:
    market = load_market_data(market_data_file)
    if not market:
        return {"error": f"{market_data_file.name} 없음 — load_market_data.py 먼저 실행 필요"}

    assets = {name: slice_asset(asset, date_str) for name, asset in (market.get("assets") or {}).items()}
    sp, sph, spl = extract_series(assets.get("S&P500", {}))
    kospi, _, _ = extract_series(assets.get("KOSPI", {}))
    usdkrw, _, _ = extract_series(assets.get("USDKRW", {}))
    us10y, _, _ = extract_series(assets.get("US10Y", {}))
    wti, _, _ = extract_series(assets.get("WTI", {}))
    gold, _, _ = extract_series(assets.get("GOLD", {}))
    nas, _, _ = extract_series(assets.get("NASDAQ", {}))
    nikkei, _, _ = extract_series(assets.get("Nikkei", {}))
    dax, _, _ = extract_series(assets.get("DAX", {}))
    usdjpy, _, _ = extract_series(assets.get("USDJPY", {}))
    spy_etf, _, _ = extract_series(assets.get("SPY", {}))
    qqq_etf, _, _ = extract_series(assets.get("QQQ", {}))
    gld_etf, _, _ = extract_series(assets.get("GLD", {}))
    tlt_etf, _, _ = extract_series(assets.get("TLT", {}))

    fred = load_fred_latest(root, date_str)
    ecos = load_ecos_latest(root, date_str)

    vix = fred.get("VIXCLS") or 20.0
    us10y_val = fred.get("DGS10") or (us10y[-1] if us10y else 4.0)
    dxy_val = fred.get("DTWEXBGS") or 100.0
    oil_val = fred.get("DCOILWTICO") or (wti[-1] if wti else 75.0)
    fedfunds = fred.get("FEDFUNDS") or 5.3
    t10y2y = fred.get("T10Y2Y") or 0.0
    hy_spread = fred.get("BAMLH0A0HYM2") or 3.0
    unrate = fred.get("UNRATE") or 4.0
    cpi_level = fred.get("CPIAUCSL") or 315.0

    bok_rate = ecos.get("bok_base_rate") or 2.5
    usd_krw = ecos.get("usd_krw") or (usdkrw[-1] if usdkrw else 1350.0)
    cpi_kr = ecos.get("cpi_kr") or 118.0

    vix_norm = minmax(vix, 10, 50)
    us10y_norm = minmax(us10y_val, 2.0, 6.5)
    dxy_norm = minmax(dxy_val, 90, 125)
    oil_norm = minmax(oil_val, 50, 120)
    inflation_norm = minmax(cpi_level, 295, 345)
    usdkrw_norm = minmax(usd_krw, 1200, 1550)

    rsi_sp = rsi(sp, 14)
    mag_sp = ma_gap(sp, 20, 60)
    mom3_sp = momentum(sp, 63)
    mom12_sp = momentum(sp, 252)
    vol20_sp = volatility(sp, 20)
    rel_sp_kospi = relative_strength(sp, kospi, 120) if kospi else None
    adx_sp = adx(sph, spl, sp, 14) if len(sph) == len(sp) and len(sp) > 15 else None
    mom3_nk = momentum(nikkei, 63) if len(nikkei) > 63 else None
    mom3_dax = momentum(dax, 63) if len(dax) > 63 else None

    growth_norm = minmax(mom12_sp or 0, -20, 30)

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
        50,
        50,
    )
    fx = fx_score(minmax(dxy_val, 90, 125), usdkrw_norm, 50, 50, 50)
    total = total_score(regime, macro=mac, technical=tech, quant=qnt, fx=fx)

    def r2(value):
        return round(value, 2) if value is not None else None

    periods = []
    for n, label in [(1, "1일"), (5, "1주"), (21, "1개월"), (63, "3개월"), (126, "6개월")]:
        periods.append(
            {
                "label": label,
                "days": n,
                "returns": {
                    "sp500": r2(period_return(sp, n)),
                    "kospi": r2(period_return(kospi, n)),
                    "nasdaq": r2(period_return(nas, n)),
                    "gold": r2(period_return(gold, n)),
                    "wti": r2(period_return(wti, n)),
                    "usdkrw": r2(period_return(usdkrw, n)),
                    "nikkei": r2(period_return(nikkei, n)),
                    "dax": r2(period_return(dax, n)),
                    "usdjpy": r2(period_return(usdjpy, n)),
                    "spy": r2(period_return(spy_etf, n)),
                    "qqq": r2(period_return(qqq_etf, n)),
                    "gld": r2(period_return(gld_etf, n)),
                    "tlt": r2(period_return(tlt_etf, n)),
                    "us10y_yield_chg": r2((us10y[-1] - us10y[-n - 1]) if len(us10y) >= n + 1 else None),
                },
            }
        )

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
            "bok_rate": bok_rate,
            "usd_krw": usd_krw,
            "cpi_kr": cpi_kr,
        },
        "technical_inputs": {
            "rsi_sp500": r2(rsi_sp),
            "ma_gap_sp500": r2(mag_sp),
            "momentum_3m": r2(mom3_sp),
            "momentum_12m": r2(mom12_sp),
            "volatility_20d": r2(vol20_sp),
            "rel_strength_sp500_vs_kospi": r2(rel_sp_kospi),
            "adx_sp500": r2(adx_sp),
            "momentum_3m_nikkei": r2(mom3_nk),
            "momentum_3m_dax": r2(mom3_dax),
        },
        "latest_prices": {
            "sp500": r2(sp[-1]) if sp else None,
            "kospi": r2(kospi[-1]) if kospi else None,
            "nasdaq": r2(nas[-1]) if nas else None,
            "usdkrw": r2(usd_krw),
            "us10y": r2(us10y_val),
            "wti": r2(oil_val),
            "gold": r2(gold[-1]) if gold else None,
            "nikkei": r2(nikkei[-1]) if nikkei else None,
            "dax": r2(dax[-1]) if dax else None,
            "usdjpy": r2(usdjpy[-1]) if usdjpy else None,
            "spy": r2(spy_etf[-1]) if spy_etf else None,
            "qqq": r2(qqq_etf[-1]) if qqq_etf else None,
            "gld": r2(gld_etf[-1]) if gld_etf else None,
            "tlt": r2(tlt_etf[-1]) if tlt_etf else None,
            "bok_rate": bok_rate,
        },
        "periods": periods,
        "context": {
            "market_data_file": str(market_data_file),
            "fred_snapshot_date": next((path.parent.name for path in _candidate_source_dirs(root, "fred_api", date_str)), None),
            "ecos_snapshot_date": next((path.parent.name for path in _candidate_source_dirs(root, "ecos_api", date_str)), None),
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--base-dir", default=str(ROOT))
    parser.add_argument("--market-data-file", help="Optional market data JSON path")
    args = parser.parse_args()

    root = Path(args.base_dir)
    market_data_file = Path(args.market_data_file) if args.market_data_file else root / "data" / "market_data_latest.json"
    result = analyze(root, args.date, market_data_file)

    out_dir = root / "data/macro_analysis"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{args.date}.json"
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"wrote {out_file}")
    print(f"Regime: {result.get('regime')} | Total: {result.get('scores', {}).get('total')}")


if __name__ == "__main__":
    main()
