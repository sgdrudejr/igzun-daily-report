#!/usr/bin/env python3
"""
ETF Recommendation Engine.
Reads macro_analysis output, downloads ETF price data via yfinance,
scores and ranks ETFs based on regime + momentum + volatility.
Output: data/etf_recommendations/{date}.json
"""
import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from scoring_engine import minmax, etf_rank_score
from technical_indicators import momentum, volatility, rsi

try:
    import yfinance as yf
    HAS_YF = True
except ImportError:
    HAS_YF = False


# ── ETF universe ─────────────────────────────────────────────────────────────

ETF_UNIVERSE = [
    # US 거래 ETF
    {"id": "SPY",  "name": "S&P 500",             "ticker": "SPY",     "region": "US",  "type": "equity_broad"},
    {"id": "QQQ",  "name": "NASDAQ 100",           "ticker": "QQQ",     "region": "US",  "type": "equity_tech"},
    {"id": "GLD",  "name": "Gold",                  "ticker": "GLD",     "region": "US",  "type": "commodity_gold"},
    {"id": "TLT",  "name": "US 20Y Treasury",       "ticker": "TLT",     "region": "US",  "type": "bond_long"},
    {"id": "IEF",  "name": "US 7-10Y Treasury",     "ticker": "IEF",     "region": "US",  "type": "bond_mid"},
    {"id": "UUP",  "name": "Dollar Bullish",         "ticker": "UUP",     "region": "US",  "type": "fx_dollar"},
    {"id": "EEM",  "name": "Emerging Markets",       "ticker": "EEM",     "region": "EM",  "type": "equity_em"},
    {"id": "XLE",  "name": "Energy Select SPDR",     "ticker": "XLE",     "region": "US",  "type": "equity_sector"},
    {"id": "XLF",  "name": "Financial Select SPDR",  "ticker": "XLF",     "region": "US",  "type": "equity_sector"},
    # 한국 ETF (KRX — yfinance ticker format)
    {"id": "TIGER200",    "name": "TIGER 200",             "ticker": "069500.KS", "region": "KR", "type": "equity_broad"},
    {"id": "TIGER_NQ100", "name": "TIGER 미국나스닥100",    "ticker": "133690.KS", "region": "US", "type": "equity_tech"},
    {"id": "KODEX_SEMI",  "name": "KODEX 반도체",           "ticker": "091160.KS", "region": "KR", "type": "equity_sector"},
    {"id": "KODEX_GOLD",  "name": "KODEX 골드선물(H)",      "ticker": "132030.KS", "region": "US", "type": "commodity_gold"},
    {"id": "KODEX_USD",   "name": "KODEX 미국달러선물",      "ticker": "261240.KS", "region": "US", "type": "fx_dollar"},
    {"id": "TIGER200_IT", "name": "TIGER 200 IT",           "ticker": "371460.KS", "region": "KR", "type": "equity_sector"},
    {"id": "KODEX_US30Y", "name": "KODEX 미국채울트라30년(H)","ticker": "148020.KS","region": "US", "type": "bond_long"},
]


# ── Regime-based directional bias per ETF type ───────────────────────────────

REGIME_BIAS: dict[str, dict[str, int]] = {
    # type → bias score (+/- 0~30)
    "Growth": {
        "equity_broad": 25, "equity_tech": 30, "equity_em": 20, "equity_sector": 15,
        "commodity_gold": -10, "bond_long": -20, "bond_mid": -15, "fx_dollar": -15,
    },
    "Stagflation/Recession": {
        "equity_broad": -20, "equity_tech": -25, "equity_em": -20, "equity_sector": -10,
        "commodity_gold": 25, "bond_long": 20, "bond_mid": 15, "fx_dollar": 20,
    },
    "Inflationary": {
        "equity_broad": 0, "equity_tech": -10, "equity_em": -5, "equity_sector": 20,
        "commodity_gold": 25, "bond_long": -25, "bond_mid": -15, "fx_dollar": 10,
    },
    "Risk-Off DollarStrength": {
        "equity_broad": -15, "equity_tech": -15, "equity_em": -25, "equity_sector": -10,
        "commodity_gold": 20, "bond_long": 10, "bond_mid": 10, "fx_dollar": 25,
    },
    "Neutral": {
        "equity_broad": 5, "equity_tech": 5, "equity_em": 0, "equity_sector": 5,
        "commodity_gold": 5, "bond_long": 5, "bond_mid": 5, "fx_dollar": 0,
    },
}

REGIME_RATIONALE: dict[str, dict[str, str]] = {
    "Growth": {
        "equity_broad": "성장 레짐 — 광의 주식 수혜",
        "equity_tech": "성장 레짐 — 기술주 최대 수혜",
        "equity_em": "성장 레짐 — 신흥국 위험선호 확대",
        "commodity_gold": "성장 레짐 — 안전자산 수요 감소",
        "bond_long": "성장 레짐 — 장기채 기대수익 저하",
        "fx_dollar": "성장 레짐 — 달러 약세 환경",
    },
    "Stagflation/Recession": {
        "commodity_gold": "스태그플레이션 — 금 인플레 헤지",
        "bond_long": "경기침체 — 장기채 도피처",
        "fx_dollar": "위험회피 — 달러 강세",
        "equity_broad": "경기침체 — 주식 약세",
        "equity_tech": "스태그플레이션 — 성장주 가장 취약",
    },
    "Inflationary": {
        "commodity_gold": "인플레 레짐 — 금 실질금리 헤지",
        "equity_sector": "인플레 레짐 — 에너지/원자재 섹터 수혜",
        "bond_long": "인플레 레짐 — 장기채 가장 불리",
        "equity_tech": "인플레/고금리 — 밸류에이션 부담",
    },
    "Risk-Off DollarStrength": {
        "fx_dollar": "달러 강세 레짐 — 달러 ETF 직접 수혜",
        "commodity_gold": "위험회피 — 금 안전자산 수요",
        "equity_em": "달러 강세 — 신흥국 자금 이탈 우려",
    },
    "Neutral": {},
}


def fetch_etf_prices(tickers: list[str], lookback_days: int = 270) -> dict[str, list[float]]:
    """Download ETF close prices for momentum/vol calculation."""
    if not HAS_YF:
        return {}
    end = date.today()
    start = end - timedelta(days=lookback_days)
    prices = {}
    for ticker in tickers:
        try:
            df = yf.download(ticker, start=start.isoformat(),
                             end=(end + timedelta(days=1)).isoformat(),
                             progress=False, auto_adjust=True)
            if df is None or df.empty:
                continue
            close_col = [c for c in df.columns if "close" in str(c).lower()]
            if not close_col:
                continue
            closes = df[close_col[0]].dropna().tolist()
            if closes:
                prices[ticker] = [float(v) for v in closes]
        except Exception:
            pass
    return prices


def score_etf(etf: dict, regime: str, macro_total: float, prices: list[float]) -> dict:
    """Compute composite score for one ETF."""
    bias = REGIME_BIAS.get(regime, REGIME_BIAS["Neutral"]).get(etf["type"], 0)

    # Momentum & volatility from price series
    mom3 = momentum(prices, 63) if len(prices) > 63 else None
    mom12 = momentum(prices, 252) if len(prices) > 252 else None
    vol = volatility(prices, 20) if len(prices) > 20 else None
    rsi_val = rsi(prices, 14) if len(prices) > 14 else None

    mom_score = minmax(mom3 or 0, -30, 30) - 50  # -50 ~ +50 → signed
    vol_penalty = minmax(vol or 20, 5, 60) - 50   # higher vol → negative

    base = minmax(macro_total or 50, 0, 100)

    # etf_rank_score: base + momentum thematic - risk
    rank = etf_rank_score(
        base=50 + bias * 0.5,
        momentum=mom_score * 0.5,
        risk=abs(vol_penalty) * 0.3,
        thematic=bias * 0.5,
    )

    # Rationale
    rationale = REGIME_RATIONALE.get(regime, {}).get(etf["type"], f"{regime} 레짐 중립")

    return {
        "id": etf["id"],
        "name": etf["name"],
        "ticker": etf["ticker"],
        "region": etf["region"],
        "type": etf["type"],
        "score": rank,
        "regime_bias": bias,
        "momentum_3m": round(mom3, 2) if mom3 is not None else None,
        "momentum_12m": round(mom12, 2) if mom12 is not None else None,
        "volatility_20d": round(vol, 2) if vol is not None else None,
        "rsi": round(rsi_val, 1) if rsi_val is not None else None,
        "rationale": rationale,
    }


def recommend(root: Path, date_str: str) -> dict:
    # Load macro analysis
    macro_file = root / "data/macro_analysis" / f"{date_str}.json"
    if macro_file.exists():
        macro = json.loads(macro_file.read_text())
        regime = macro.get("regime", "Neutral")
        macro_total = macro.get("scores", {}).get("total") or 50.0
    else:
        regime = "Neutral"
        macro_total = 50.0

    # Fetch ETF price data
    tickers = [e["ticker"] for e in ETF_UNIVERSE]
    print(f"Fetching price data for {len(tickers)} ETFs...")
    prices_map = fetch_etf_prices(tickers)

    # Score each ETF
    scored = []
    for etf in ETF_UNIVERSE:
        prices = prices_map.get(etf["ticker"], [])
        result = score_etf(etf, regime, macro_total, prices)
        scored.append(result)

    # Sort by score descending
    scored.sort(key=lambda x: x["score"], reverse=True)

    # Tier labels
    for i, e in enumerate(scored):
        if e["score"] >= 65:
            e["tier"] = "강력매수"
        elif e["score"] >= 55:
            e["tier"] = "매수"
        elif e["score"] >= 45:
            e["tier"] = "중립"
        elif e["score"] >= 35:
            e["tier"] = "비중축소"
        else:
            e["tier"] = "회피"

    return {
        "date": date_str,
        "regime": regime,
        "macro_total_score": macro_total,
        "etf_count": len(scored),
        "recommendations": scored,
        "top3": [{"rank": i+1, "id": e["id"], "name": e["name"],
                  "score": e["score"], "tier": e["tier"], "rationale": e["rationale"]}
                 for i, e in enumerate(scored[:3])],
    }


def main():
    parser = argparse.ArgumentParser(description="ETF Recommendation Engine")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--base-dir", default=str(ROOT))
    args = parser.parse_args()

    root = Path(args.base_dir)
    result = recommend(root, args.date)

    out_dir = root / "data/etf_recommendations"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{args.date}.json"
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"wrote {out_file}")

    print(f"\nRegime: {result['regime']} | Macro score: {result['macro_total_score']}")
    print("\nTop 3 ETF 추천:")
    for r in result["top3"]:
        print(f"  {r['rank']}. [{r['tier']}] {r['name']} ({r['id']}) score={r['score']}  — {r['rationale']}")


if __name__ == "__main__":
    main()
