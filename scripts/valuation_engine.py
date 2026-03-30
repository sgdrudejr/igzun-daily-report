#!/usr/bin/env python3
"""
밸류에이션 엔진 — S&P500 ERP, 52주 레인지, 이격도, KOSPI PBR 추정.
Output: data/valuation/{date}.json
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _sma(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def _extract_closes(market: dict, asset_name: str, as_of: str) -> list[float]:
    asset = (market.get("assets") or {}).get(asset_name, {})
    records = asset.get("records", [])
    closes = []
    for r in records:
        if r.get("date", "") <= as_of and r.get("close") is not None:
            closes.append(float(r["close"]))
    return closes


def _load_fred(root: Path, date_str: str) -> dict:
    """Load FRED values from raw snapshot."""
    raw_root = root / "data" / "raw"
    if not raw_root.exists():
        return {}
    candidates = sorted(
        [d for d in raw_root.iterdir() if d.is_dir() and d.name <= date_str],
        key=lambda p: p.name, reverse=True,
    )
    values = {}
    for dated_dir in candidates:
        source_dir = dated_dir / "fred_api"
        if not source_dir.exists():
            continue
        for json_file in source_dir.glob("*.json"):
            try:
                doc = json.loads(json_file.read_text())
                meta = doc.get("metadata", {})
                sid = meta.get("series_id")
                val = meta.get("latest_value")
                if sid and val is not None and sid not in values:
                    try:
                        values[sid] = float(val)
                    except (TypeError, ValueError):
                        pass
            except Exception:
                pass
        if values:
            break
    return values


def _range_pct(closes: list[float], period: int = 252) -> float | None:
    """현재 가격이 지난 N일 레인지에서 몇 % 위치인지 (0=저점, 100=고점)."""
    if len(closes) < 10:
        return None
    window = closes[-min(period, len(closes)):]
    lo, hi = min(window), max(window)
    if hi == lo:
        return 50.0
    return (closes[-1] - lo) / (hi - lo) * 100


def _vs_ma200_pct(closes: list[float]) -> float | None:
    """현재가 대비 200일선 이격도 (%)."""
    if len(closes) < 200:
        return None
    ma200 = sum(closes[-200:]) / 200
    if ma200 == 0:
        return None
    return (closes[-1] / ma200 - 1) * 100


def assess_sp500(closes: list[float], us10y: float, fred: dict) -> dict:
    """
    S&P500 밸류에이션 평가.
    ERP = Earnings Yield - US 10Y yield
    Earnings Yield ≈ 1 / Forward PE (추정)
    """
    range_52w = _range_pct(closes, 252)
    vs_ma200 = _vs_ma200_pct(closes)

    # Estimated forward P/E from FRED or default
    # FRED: SP500_PE ratio can come from MULTPL data; use default if not available
    shiller_cape = fred.get("CAPE") or fred.get("SCHILLER_PE") or None
    # Fallback: estimate current-year PE from market price trends
    # As of 2025-2026, S&P500 P/E is roughly 21-25x — use 22 as base
    estimated_pe = 22.0
    if closes:
        # Rough heuristic: if price is in top 20% of 52w range, assume slightly higher PE
        if range_52w is not None:
            if range_52w > 80:
                estimated_pe = 25.0
            elif range_52w < 20:
                estimated_pe = 19.0

    earnings_yield = (1 / estimated_pe) * 100  # as %

    # Equity Risk Premium
    erp = earnings_yield - us10y
    erp_assessment = ""
    if erp > 3.0:
        erp_assessment = "매력적 (ERP 높음 — 주식이 채권 대비 유리)"
    elif erp > 1.5:
        erp_assessment = "보통 (적정 수준)"
    elif erp > 0:
        erp_assessment = "낮음 (주식 매력도 제한적)"
    else:
        erp_assessment = "음수 (채권이 주식보다 유리한 환경)"

    # Valuation grade
    grade_score = 50
    if range_52w is not None:
        if range_52w < 20:
            grade_score += 20  # 52주 저점 근처 = 저평가 가능성
        elif range_52w > 80:
            grade_score -= 20  # 52주 고점 근처 = 고평가 가능성
    if erp > 2.0:
        grade_score += 15
    elif erp < 0:
        grade_score -= 20
    if vs_ma200 is not None:
        if vs_ma200 < -15:
            grade_score += 15  # 200일선 아래 많이 빠짐 = 저평가
        elif vs_ma200 > 25:
            grade_score -= 15  # 200일선 위 많이 올라감 = 고평가

    grade_score = max(0, min(100, grade_score))
    if grade_score >= 70:
        valuation_grade = "저평가"
    elif grade_score >= 50:
        valuation_grade = "적정"
    elif grade_score >= 35:
        valuation_grade = "다소 고평가"
    else:
        valuation_grade = "고평가"

    price = round(closes[-1], 2) if closes else None

    return {
        "price": price,
        "range_52w_pct": round(range_52w, 1) if range_52w is not None else None,
        "vs_ma200_pct": round(vs_ma200, 2) if vs_ma200 is not None else None,
        "estimated_pe": estimated_pe,
        "earnings_yield_pct": round(earnings_yield, 2),
        "us10y_yield_pct": round(us10y, 2),
        "erp_pct": round(erp, 2),
        "erp_assessment": erp_assessment,
        "shiller_cape": shiller_cape,
        "valuation_grade": valuation_grade,
        "valuation_score": grade_score,
    }


def assess_kospi(closes: list[float]) -> dict:
    """
    KOSPI 밸류에이션 평가.
    Historical KOSPI PBR: 0.8~1.3x, median ~0.95
    """
    range_52w = _range_pct(closes, 252)
    vs_ma200 = _vs_ma200_pct(closes)

    # KOSPI historical levels (approximate)
    # KOSPI 2400 ≈ PBR 0.85, 2800 ≈ PBR 1.0, 3200+ ≈ PBR 1.2
    price = closes[-1] if closes else None
    estimated_pbr = None
    pbr_assessment = ""

    if price:
        if price < 2000:
            estimated_pbr = 0.70
            pbr_assessment = "극단 저평가 (PBR 0.7x 이하)"
        elif price < 2400:
            estimated_pbr = 0.82
            pbr_assessment = "역사적 저점 수준 저평가"
        elif price < 2700:
            estimated_pbr = 0.92
            pbr_assessment = "저평가 구간 (PBR <1x)"
        elif price < 3000:
            estimated_pbr = 1.02
            pbr_assessment = "적정 수준 (PBR ~1x)"
        elif price < 3300:
            estimated_pbr = 1.15
            pbr_assessment = "다소 고평가"
        else:
            estimated_pbr = 1.30
            pbr_assessment = "고평가 구간"

    grade_score = 50
    if range_52w is not None:
        if range_52w < 20:
            grade_score += 20
        elif range_52w > 80:
            grade_score -= 15
    if estimated_pbr is not None:
        if estimated_pbr < 0.85:
            grade_score += 20
        elif estimated_pbr > 1.15:
            grade_score -= 15
    if vs_ma200 is not None:
        if vs_ma200 < -15:
            grade_score += 10
        elif vs_ma200 > 20:
            grade_score -= 10

    grade_score = max(0, min(100, grade_score))
    if grade_score >= 70:
        valuation_grade = "저평가"
    elif grade_score >= 50:
        valuation_grade = "적정"
    elif grade_score >= 35:
        valuation_grade = "다소 고평가"
    else:
        valuation_grade = "고평가"

    return {
        "price": round(price, 2) if price else None,
        "range_52w_pct": round(range_52w, 1) if range_52w is not None else None,
        "vs_ma200_pct": round(vs_ma200, 2) if vs_ma200 is not None else None,
        "estimated_pbr": estimated_pbr,
        "pbr_assessment": pbr_assessment,
        "valuation_grade": valuation_grade,
        "valuation_score": grade_score,
    }


def assess_nasdaq(closes: list[float], us10y: float) -> dict:
    """나스닥 밸류에이션."""
    range_52w = _range_pct(closes, 252)
    vs_ma200 = _vs_ma200_pct(closes)
    # Tech PE typically higher: 28-35x
    estimated_pe = 30.0
    if range_52w is not None:
        if range_52w > 80:
            estimated_pe = 33.0
        elif range_52w < 20:
            estimated_pe = 26.0
    earnings_yield = (1 / estimated_pe) * 100
    erp = earnings_yield - us10y

    grade_score = 50
    if range_52w is not None:
        grade_score += (20 - range_52w * 0.4)
    if erp > 0:
        grade_score += 10
    elif erp < -1:
        grade_score -= 20
    if vs_ma200 is not None and vs_ma200 < -15:
        grade_score += 15

    grade_score = max(0, min(100, int(grade_score)))
    if grade_score >= 70:
        valuation_grade = "저평가"
    elif grade_score >= 50:
        valuation_grade = "적정"
    elif grade_score >= 35:
        valuation_grade = "다소 고평가"
    else:
        valuation_grade = "고평가"

    return {
        "price": round(closes[-1], 2) if closes else None,
        "range_52w_pct": round(range_52w, 1) if range_52w is not None else None,
        "vs_ma200_pct": round(vs_ma200, 2) if vs_ma200 is not None else None,
        "estimated_pe": estimated_pe,
        "earnings_yield_pct": round(earnings_yield, 2),
        "erp_pct": round(erp, 2),
        "valuation_grade": valuation_grade,
        "valuation_score": grade_score,
    }


def assess_gold(closes: list[float]) -> dict:
    """금 밸류에이션 (실질 레인지 기반)."""
    range_52w = _range_pct(closes, 252)
    vs_ma200 = _vs_ma200_pct(closes)
    price = closes[-1] if closes else None

    # Gold valuation is relative — near 52w high vs low
    grade_score = 50
    if range_52w is not None:
        if range_52w < 20:
            grade_score = 75  # 52w 저점 근처 = 매력적
        elif range_52w > 80:
            grade_score = 30  # 52w 고점 근처 = 조심
    if vs_ma200 is not None:
        if vs_ma200 < -10:
            grade_score += 10
        elif vs_ma200 > 15:
            grade_score -= 10
    grade_score = max(0, min(100, grade_score))

    assessment = "중립"
    if range_52w is not None:
        if range_52w < 20:
            assessment = "52주 저점 근처 — 헤지 진입 적합"
        elif range_52w > 80:
            assessment = "52주 고점 — 신규 진입 자제, 일부 이익 실현 고려"

    return {
        "price": round(price, 2) if price else None,
        "range_52w_pct": round(range_52w, 1) if range_52w is not None else None,
        "vs_ma200_pct": round(vs_ma200, 2) if vs_ma200 is not None else None,
        "assessment": assessment,
        "valuation_score": grade_score,
    }


def run_valuation(root: Path, date_str: str) -> dict:
    market_file = root / "data" / "market_data_latest.json"
    market = _load_json(market_file)
    if not market:
        return {"error": "market_data_latest.json 없음", "date": date_str}

    fred = _load_fred(root, date_str)
    us10y = fred.get("DGS10") or 4.2

    sp_closes = _extract_closes(market, "S&P500", date_str)
    kospi_closes = _extract_closes(market, "KOSPI", date_str)
    nas_closes = _extract_closes(market, "NASDAQ", date_str)
    gold_closes = _extract_closes(market, "GOLD", date_str)

    sp_val = assess_sp500(sp_closes, us10y, fred) if sp_closes else {"error": "no data"}
    kospi_val = assess_kospi(kospi_closes) if kospi_closes else {"error": "no data"}
    nas_val = assess_nasdaq(nas_closes, us10y) if nas_closes else {"error": "no data"}
    gold_val = assess_gold(gold_closes) if gold_closes else {"error": "no data"}

    # Overall valuation summary
    scores = [
        v.get("valuation_score") for v in [sp_val, kospi_val, nas_val]
        if isinstance(v, dict) and v.get("valuation_score") is not None
    ]
    avg_score = int(sum(scores) / len(scores)) if scores else 50

    if avg_score >= 65:
        market_valuation = "전반적 저평가 — 장기 매수 기회 가능"
    elif avg_score >= 50:
        market_valuation = "적정 수준 — 선별적 접근 권장"
    elif avg_score >= 35:
        market_valuation = "다소 고평가 — 진입 속도 조절 권장"
    else:
        market_valuation = "고평가 — 안전자산 비중 유지"

    return {
        "date": date_str,
        "us10y_used": us10y,
        "sp500": sp_val,
        "kospi": kospi_val,
        "nasdaq": nas_val,
        "gold": gold_val,
        "summary": {
            "avg_score": avg_score,
            "market_valuation": market_valuation,
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--base-dir", default=str(ROOT))
    args = parser.parse_args()

    root = Path(args.base_dir)
    result = run_valuation(root, args.date)

    out_dir = root / "data" / "valuation"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{args.date}.json"
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"wrote {out_file}")

    sp = result.get("sp500", {})
    print(f"S&P500: {sp.get('valuation_grade')} | ERP {sp.get('erp_pct')}% | 52W {sp.get('range_52w_pct')}%")
    kospi = result.get("kospi", {})
    print(f"KOSPI: {kospi.get('valuation_grade')} | PBR {kospi.get('estimated_pbr')} | 52W {kospi.get('range_52w_pct')}%")
    print(f"요약: {result['summary']['market_valuation']}")


if __name__ == "__main__":
    main()
