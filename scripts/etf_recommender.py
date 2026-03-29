#!/usr/bin/env python3
"""
ETF 추천 엔진 — 레짐 기반 점수화 + 모멘텀/변동성 통합.
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


# ── ETF 유니버스 ──────────────────────────────────────────────────────────────
ETF_UNIVERSE = [
    # 미국
    {"id": "SPY",  "name": "S&P 500 ETF",          "ticker": "SPY",     "region": "US",  "type": "equity_broad",   "currency": "USD"},
    {"id": "QQQ",  "name": "나스닥 100 ETF",         "ticker": "QQQ",     "region": "US",  "type": "equity_tech",    "currency": "USD"},
    {"id": "GLD",  "name": "금 ETF",                 "ticker": "GLD",     "region": "US",  "type": "commodity_gold", "currency": "USD"},
    {"id": "TLT",  "name": "미국 장기국채 ETF",       "ticker": "TLT",     "region": "US",  "type": "bond_long",      "currency": "USD"},
    {"id": "IEF",  "name": "미국 중기국채 ETF",       "ticker": "IEF",     "region": "US",  "type": "bond_mid",       "currency": "USD"},
    {"id": "UUP",  "name": "달러 불리시 ETF",         "ticker": "UUP",     "region": "US",  "type": "fx_dollar",      "currency": "USD"},
    {"id": "EEM",  "name": "이머징마켓 ETF",          "ticker": "EEM",     "region": "EM",  "type": "equity_em",      "currency": "USD"},
    {"id": "XLE",  "name": "에너지 섹터 ETF",         "ticker": "XLE",     "region": "US",  "type": "equity_sector",  "currency": "USD"},
    {"id": "XLF",  "name": "금융 섹터 ETF",           "ticker": "XLF",     "region": "US",  "type": "equity_sector",  "currency": "USD"},
    {"id": "EWJ",  "name": "iShares MSCI Japan",    "ticker": "EWJ",     "region": "JP",  "type": "equity_broad",   "currency": "USD"},
    {"id": "EZU",  "name": "iShares MSCI Eurozone", "ticker": "EZU",     "region": "EU",  "type": "equity_broad",   "currency": "USD"},
    # 한국 (KRX)
    {"id": "TIGER200",    "name": "TIGER 200",              "ticker": "069500.KS", "region": "KR", "type": "equity_broad",   "currency": "KRW"},
    {"id": "TIGER_NQ100", "name": "TIGER 미국나스닥100",     "ticker": "133690.KS", "region": "US", "type": "equity_tech",    "currency": "KRW"},
    {"id": "KODEX_SEMI",  "name": "KODEX 반도체",            "ticker": "091160.KS", "region": "KR", "type": "equity_sector",  "currency": "KRW"},
    {"id": "KODEX_GOLD",  "name": "KODEX 골드선물(H)",       "ticker": "132030.KS", "region": "US", "type": "commodity_gold", "currency": "KRW"},
    {"id": "KODEX_USD",   "name": "KODEX 미국달러선물",       "ticker": "261240.KS", "region": "US", "type": "fx_dollar",      "currency": "KRW"},
    {"id": "TIGER200_IT", "name": "TIGER 200 IT",            "ticker": "371460.KS", "region": "KR", "type": "equity_sector",  "currency": "KRW"},
    {"id": "KODEX_US30Y", "name": "KODEX 미국채울트라30년(H)","ticker": "148020.KS", "region": "US", "type": "bond_long",      "currency": "KRW"},
    {"id": "TIGER_JAPAN", "name": "TIGER 일본니케이225",      "ticker": "241180.KS", "region": "JP", "type": "equity_broad",   "currency": "KRW"},
]

# ── 레짐별 방향 바이어스 (type → ±점수) ───────────────────────────────────────
REGIME_BIAS: dict[str, dict[str, int]] = {
    "Growth": {
        "equity_broad": 25, "equity_tech": 30, "equity_em": 20, "equity_sector": 15,
        "commodity_gold": -10, "bond_long": -20, "bond_mid": -15, "fx_dollar": -15,
    },
    "Stagflation/Recession": {
        "equity_broad": -20, "equity_tech": -25, "equity_em": -20, "equity_sector": -5,
        "commodity_gold": 25, "bond_long": 20, "bond_mid": 15, "fx_dollar": 20,
    },
    "Inflationary": {
        "equity_broad": 0, "equity_tech": -10, "equity_em": -5, "equity_sector": 20,
        "commodity_gold": 25, "bond_long": -25, "bond_mid": -10, "fx_dollar": 10,
    },
    "Risk-Off DollarStrength": {
        "equity_broad": -15, "equity_tech": -15, "equity_em": -25, "equity_sector": -5,
        "commodity_gold": 20, "bond_long": 10, "bond_mid": 10, "fx_dollar": 25,
    },
    "Neutral": {
        "equity_broad": 5, "equity_tech": 5, "equity_em": 0, "equity_sector": 5,
        "commodity_gold": 5, "bond_long": 5, "bond_mid": 5, "fx_dollar": 0,
    },
}

TIER_LABELS = {
    (65, 101): "강력매수",
    (55,  65): "매수",
    (45,  55): "중립",
    (35,  45): "비중축소",
    (0,   35): "회피",
}


def get_tier(score: float) -> str:
    for (lo, hi), label in TIER_LABELS.items():
        if lo <= score < hi:
            return label
    return "중립"


def build_rationale(etf: dict, regime: str, bias: int,
                    mom3: float | None, rsi_val: float | None, vol: float | None) -> str:
    parts = []

    # 레짐 기반 방향
    if abs(bias) >= 20:
        dir_kr = "강한 수혜" if bias > 0 else "불리한 환경"
        parts.append(f"{regime} 레짐 — {dir_kr}")
    elif abs(bias) >= 10:
        dir_kr = "수혜" if bias > 0 else "다소 불리"
        parts.append(f"{regime} 레짐 {dir_kr}")
    else:
        parts.append(f"{regime} 레짐 중립")

    # 모멘텀
    if mom3 is not None:
        sign = "▲" if mom3 >= 0 else "▼"
        level = "강한 모멘텀" if abs(mom3) > 15 else "모멘텀 유지" if abs(mom3) > 5 else "모멘텀 약함"
        parts.append(f"3M {sign}{abs(mom3):.1f}% {level}")

    # RSI
    if rsi_val is not None:
        if rsi_val > 70:
            parts.append(f"RSI {rsi_val:.0f} 과매수 주의")
        elif rsi_val < 30:
            parts.append(f"RSI {rsi_val:.0f} 과매도 — 반등 가능성")
        else:
            parts.append(f"RSI {rsi_val:.0f} 정상 구간")

    # 변동성
    if vol is not None:
        if vol > 30:
            parts.append(f"변동성 {vol:.0f}% 高")
        elif vol < 10:
            parts.append(f"변동성 {vol:.0f}% 低")

    return " | ".join(parts)


def fetch_etf_prices(tickers: list[str], lookback_days: int = 270) -> dict[str, list[float]]:
    if not HAS_YF:
        return {}
    end   = date.today()
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
    bias    = REGIME_BIAS.get(regime, REGIME_BIAS["Neutral"]).get(etf["type"], 0)
    mom3    = momentum(prices, 63)  if len(prices) > 63  else None
    mom12   = momentum(prices, 252) if len(prices) > 252 else None
    vol     = volatility(prices, 20) if len(prices) > 20 else None
    rsi_val = rsi(prices, 14)        if len(prices) > 14 else None

    mom_signed  = (minmax(mom3 or 0, -30, 30) - 50)  # -50 ~ +50
    vol_penalty = max(0, (minmax(vol or 20, 5, 60) - 50) * 0.3)
    base        = 50 + bias * 0.5

    score = etf_rank_score(
        base=base,
        momentum=mom_signed * 0.5,
        risk=vol_penalty,
        thematic=bias * 0.3,
    )

    return {
        "id":           etf["id"],
        "name":         etf["name"],
        "ticker":       etf["ticker"],
        "region":       etf["region"],
        "type":         etf["type"],
        "currency":     etf.get("currency", "USD"),
        "score":        score,
        "tier":         get_tier(score),
        "regime_bias":  bias,
        "momentum_3m":  round(mom3,  2) if mom3  is not None else None,
        "momentum_12m": round(mom12, 2) if mom12 is not None else None,
        "volatility_20d": round(vol, 2) if vol   is not None else None,
        "rsi":          round(rsi_val, 1) if rsi_val is not None else None,
        "rationale":    build_rationale(etf, regime, bias, mom3, rsi_val, vol),
    }


def recommend(root: Path, date_str: str) -> dict:
    macro_file = root / "data/macro_analysis" / f"{date_str}.json"
    if macro_file.exists():
        macro   = json.loads(macro_file.read_text())
        regime  = macro.get("regime", "Neutral")
        m_total = (macro.get("scores") or {}).get("total") or 50.0
    else:
        regime, m_total = "Neutral", 50.0

    tickers   = [e["ticker"] for e in ETF_UNIVERSE]
    print(f"ETF 가격 데이터 수집 중 ({len(tickers)}개)…")
    prices_map = fetch_etf_prices(tickers)

    scored = [score_etf(e, regime, m_total, prices_map.get(e["ticker"], [])) for e in ETF_UNIVERSE]
    scored.sort(key=lambda x: x["score"], reverse=True)

    return {
        "date":              date_str,
        "regime":            regime,
        "macro_total_score": m_total,
        "etf_count":         len(scored),
        "recommendations":   scored,
        "top3": [
            {"rank": i + 1, "id": e["id"], "name": e["name"],
             "score": e["score"], "tier": e["tier"], "rationale": e["rationale"]}
            for i, e in enumerate(scored[:3])
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date",     default=date.today().isoformat())
    parser.add_argument("--base-dir", default=str(ROOT))
    args = parser.parse_args()

    root   = Path(args.base_dir)
    result = recommend(root, args.date)

    out_dir = root / "data/etf_recommendations"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{args.date}.json"
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"wrote {out_file}")

    print(f"\nRegime: {result['regime']} | Macro: {result['macro_total_score']}")
    print("Top 3:")
    for r in result["top3"]:
        print(f"  {r['rank']}. [{r['tier']}] {r['name']} ({r['id']}) {r['score']}점 — {r['rationale']}")


if __name__ == "__main__":
    main()
