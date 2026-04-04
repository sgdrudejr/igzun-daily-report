#!/usr/bin/env python3
"""
ETF 추천 엔진 — 레짐 기반 점수화 + 모멘텀/변동성 통합.
Output: data/etf_recommendations/{date}.json
"""
import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from scoring_engine import etf_rank_score, minmax  # noqa: E402
from technical_indicators import momentum, rsi, volatility  # noqa: E402

try:
    import yfinance as yf

    HAS_YF = True
except ImportError:
    HAS_YF = False


def _load_securities_master(root: Path) -> dict:
    """config/securities.json을 로드. 없으면 빈 dict 반환."""
    p = root / "config" / "securities.json"
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


# ── Securities master 로드 (모듈 레벨) ────────────────────────────────────────
# ETF_UNIVERSE / REGIME_BIAS는 config/securities.json에서 자동 생성됩니다.
# 직접 수정하지 마세요 — config/securities.json을 편집하세요.
_SM = _load_securities_master(ROOT)

ETF_UNIVERSE: list[dict] = [
    {
        "id": s["id"],
        "name": s["name"],
        "ticker": s["ticker"],
        "region": s["region"],
        "type": s["asset_class"],
        "currency": s.get("currency", "USD"),
        "allowed_accounts": s.get("allowed_accounts", []),
        "theme_tags": s.get("theme_tags", []),
    }
    for s in _SM.get("securities", [])
]

REGIME_BIAS: dict[str, dict[str, int]] = _SM.get("regime_bias", {
    "Neutral": {
        "equity_broad": 5, "equity_tech": 5, "equity_em": 0, "equity_sector": 5,
        "commodity_gold": 5, "bond_long": 5, "bond_mid": 5, "fx_dollar": 0,
    }
})

TIER_LABELS = {
    (65, 101): "강력매수",
    (55, 65): "매수",
    (45, 55): "중립",
    (35, 45): "비중축소",
    (0, 35): "회피",
}


def parse_iso_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def get_tier(score: float) -> str:
    for (lower, upper), label in TIER_LABELS.items():
        if lower <= score < upper:
            return label
    return "중립"


def build_rationale(etf: dict, regime: str, bias: int, mom3: float | None, rsi_val: float | None, vol: float | None) -> str:
    parts = []
    if abs(bias) >= 20:
        direction = "강한 수혜" if bias > 0 else "불리한 환경"
        parts.append(f"{regime} 레짐 — {direction}")
    elif abs(bias) >= 10:
        direction = "수혜" if bias > 0 else "다소 불리"
        parts.append(f"{regime} 레짐 {direction}")
    else:
        parts.append(f"{regime} 레짐 중립")

    if mom3 is not None:
        sign = "▲" if mom3 >= 0 else "▼"
        level = "강한 모멘텀" if abs(mom3) > 15 else "모멘텀 유지" if abs(mom3) > 5 else "모멘텀 약함"
        parts.append(f"3M {sign}{abs(mom3):.1f}% {level}")

    if rsi_val is not None:
        if rsi_val > 70:
            parts.append(f"RSI {rsi_val:.0f} 과매수 주의")
        elif rsi_val < 30:
            parts.append(f"RSI {rsi_val:.0f} 과매도 — 반등 가능성")
        else:
            parts.append(f"RSI {rsi_val:.0f} 정상 구간")

    if vol is not None:
        if vol > 30:
            parts.append(f"변동성 {vol:.0f}% 高")
        elif vol < 10:
            parts.append(f"변동성 {vol:.0f}% 低")

    return " | ".join(parts)


def fetch_etf_prices(tickers: list[str], start: date, end: date) -> dict[str, list[dict]]:
    if not HAS_YF:
        return {}

    prices = {}
    for ticker in tickers:
        try:
            df = yf.download(
                ticker,
                start=start.isoformat(),
                end=(end + timedelta(days=1)).isoformat(),
                progress=False,
                auto_adjust=True,
            )
            if df is None or df.empty:
                continue
            close_col = next((col for col in df.columns if "close" in str(col).lower()), None)
            if close_col is None:
                continue
            rows = []
            for idx, value in df[close_col].dropna().items():
                rows.append({"date": idx.strftime("%Y-%m-%d"), "close": float(value)})
            if rows:
                prices[ticker] = rows
        except Exception:
            continue
    return prices


def load_price_history(path: Path) -> dict[str, list[dict]]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text())
    except Exception:
        return {}
    return payload.get("prices", {})


def write_price_history(path: Path, start: date, end: date, prices: dict[str, list[dict]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"start": start.isoformat(), "end": end.isoformat(), "prices": prices}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))


def slice_closes(history_rows: list[dict], as_of_date: str) -> list[float]:
    closes = []
    for row in history_rows:
        if (row.get("date") or "") <= as_of_date and row.get("close") is not None:
            closes.append(float(row["close"]))
    return closes


def score_etf(etf: dict, regime: str, prices: list[float]) -> dict:
    bias = REGIME_BIAS.get(regime, REGIME_BIAS["Neutral"]).get(etf["type"], 0)
    mom3 = momentum(prices, 63) if len(prices) > 63 else None
    mom12 = momentum(prices, 252) if len(prices) > 252 else None
    vol = volatility(prices, 20) if len(prices) > 20 else None
    rsi_val = rsi(prices, 14) if len(prices) > 14 else None

    mom_signed = minmax(mom3 or 0, -30, 30) - 50
    vol_penalty = max(0, (minmax(vol or 20, 5, 60) - 50) * 0.3)
    base = 50 + bias * 0.5

    score = etf_rank_score(
        base=base,
        momentum=mom_signed * 0.5,
        risk=vol_penalty,
        thematic=bias * 0.3,
    )

    return {
        "id": etf["id"],
        "name": etf["name"],
        "ticker": etf["ticker"],
        "region": etf["region"],
        "type": etf["type"],
        "currency": etf.get("currency", "USD"),
        "score": score,
        "tier": get_tier(score),
        "regime_bias": bias,
        "momentum_3m": round(mom3, 2) if mom3 is not None else None,
        "momentum_12m": round(mom12, 2) if mom12 is not None else None,
        "volatility_20d": round(vol, 2) if vol is not None else None,
        "rsi": round(rsi_val, 1) if rsi_val is not None else None,
        "rationale": build_rationale(etf, regime, bias, mom3, rsi_val, vol),
    }


def recommend(
    root: Path,
    date_str: str,
    price_history_file: Path | None = None,
    history_start_date: str | None = None,
    history_end_date: str | None = None,
    write_history_file: Path | None = None,
) -> dict:
    macro_file = root / "data/macro_analysis" / f"{date_str}.json"
    if macro_file.exists():
        macro = json.loads(macro_file.read_text())
        regime = macro.get("regime", "Neutral")
        macro_total = (macro.get("scores") or {}).get("total") or 50.0
    else:
        regime, macro_total = "Neutral", 50.0

    history_rows = {}
    if price_history_file and price_history_file.exists():
        history_rows = load_price_history(price_history_file)
    else:
        end = parse_iso_date(history_end_date or date_str)
        start = parse_iso_date(history_start_date) if history_start_date else end - timedelta(days=270)
        universe = ETF_UNIVERSE or []
        print(f"ETF 가격 데이터 수집 중 ({len(universe)}개)…")
        history_rows = fetch_etf_prices([etf["ticker"] for etf in universe], start, end)
        if write_history_file:
            write_price_history(write_history_file, start, end, history_rows)

    universe = ETF_UNIVERSE or []
    scored = []
    for etf in universe:
        closes = slice_closes(history_rows.get(etf["ticker"], []), date_str)
        scored.append(score_etf(etf, regime, closes))
    scored.sort(key=lambda item: item["score"], reverse=True)

    return {
        "date": date_str,
        "regime": regime,
        "macro_total_score": macro_total,
        "etf_count": len(scored),
        "recommendations": scored,
        "top3": [
            {
                "rank": idx + 1,
                "id": item["id"],
                "name": item["name"],
                "score": item["score"],
                "tier": item["tier"],
                "rationale": item["rationale"],
            }
            for idx, item in enumerate(scored[:3])
        ],
        "context": {
            "price_history_file": str(price_history_file) if price_history_file and price_history_file.exists() else None,
            "history_end_date": history_end_date or date_str,
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--base-dir", default=str(ROOT))
    parser.add_argument("--price-history-file", help="Use an existing ETF price history JSON")
    parser.add_argument("--write-price-history", help="Write fetched ETF price history JSON")
    parser.add_argument("--history-start-date", help="History start date when fetching fresh data")
    parser.add_argument("--history-end-date", help="History end date when fetching fresh data")
    args = parser.parse_args()

    root = Path(args.base_dir)
    price_history_file = Path(args.price_history_file) if args.price_history_file else None
    write_history_file = Path(args.write_price_history) if args.write_price_history else None

    result = recommend(
        root=root,
        date_str=args.date,
        price_history_file=price_history_file,
        history_start_date=args.history_start_date,
        history_end_date=args.history_end_date,
        write_history_file=write_history_file,
    )

    out_dir = root / "data/etf_recommendations"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{args.date}.json"
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"wrote {out_file}")
    print(f"\nRegime: {result['regime']} | Macro: {result['macro_total_score']}")
    print("Top 3:")
    for item in result["top3"]:
        print(f"  {item['rank']}. [{item['tier']}] {item['name']} ({item['id']}) {item['score']}점 — {item['rationale']}")


if __name__ == "__main__":
    main()
