#!/usr/bin/env python3
"""
매수/매도/보류 신호 엔진.

RSI + MACD + 볼린저밴드 + 이평선 + 엘리엇파동 + 캔들 + 레짐 + 밸류에이션 →
종목/ETF별 명시적 진입 신호, 포지션 사이징, 분할 매수 스케줄 생성.

Output: data/signals/{date}.json
"""
import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from technical_timing import timing_score as compute_timing  # noqa: E402
from technical_indicators import rsi, volatility  # noqa: E402

try:
    import yfinance as yf
    HAS_YF = True
except ImportError:
    HAS_YF = False


# ── Signal labels ──────────────────────────────────────────────────────────────

SIGNAL_LABELS = {
    "강력매수":   {"emoji": "🟢🟢", "action": "즉시 분할 진입 시작 (3~5%씩)", "urgency": "높음"},
    "분할매수":   {"emoji": "🟢",   "action": "분할 매수 (1~2%씩, 3회 이상)", "urgency": "중간"},
    "소규모탐색": {"emoji": "🔵",   "action": "탐색 진입 (1%씩, 확인 후 추가)", "urgency": "낮음"},
    "관망":       {"emoji": "⚪",   "action": "진입 보류 — 신호 확인 대기", "urgency": "없음"},
    "비중축소":   {"emoji": "🟡",   "action": "기존 보유 비중 줄이기", "urgency": "중간"},
    "회피":       {"emoji": "🔴",   "action": "진입 금지 — 리스크 과도", "urgency": "높음"},
}

ACCOUNT_TYPE_MAP = {
    "ISA":     "국내 ETF 중심 (세제혜택)",
    "TOSS":    "해외 ETF 가능 (미국/글로벌)",
    "PENSION": "장기 해외지수 (연금저축)",
}

ETF_ACCOUNT_FIT = {
    "TIGER200":       ["ISA"],
    "TIGER_NQ100":    ["ISA", "PENSION"],
    "KODEX_SEMI":     ["ISA"],
    "KODEX_GOLD":     ["ISA"],
    "KODEX_USD":      ["ISA"],
    "TIGER200_IT":    ["ISA"],
    "KODEX_US30Y":    ["ISA", "PENSION"],
    "TIGER_JAPAN":    ["ISA", "PENSION"],
    "SPY":            ["TOSS"],
    "QQQ":            ["TOSS", "PENSION"],
    "GLD":            ["TOSS"],
    "TLT":            ["TOSS"],
    "IEF":            ["TOSS"],
    "UUP":            ["TOSS"],
    "EEM":            ["TOSS"],
    "XLE":            ["TOSS"],
    "XLF":            ["TOSS"],
    "EWJ":            ["TOSS", "PENSION"],
    "EZU":            ["TOSS", "PENSION"],
}


def _load_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _slice_closes(history: list[dict], as_of: str) -> list[float]:
    return [float(r["close"]) for r in history if r.get("date", "") <= as_of and r.get("close") is not None]


def _slice_ohlc(history: list[dict], as_of: str):
    """Returns (opens, highs, lows, closes) lists."""
    o, h, l, c = [], [], [], []
    for r in history:
        if r.get("date", "") > as_of:
            continue
        if r.get("close") is None:
            continue
        c.append(float(r["close"]))
        o.append(float(r.get("open") or r["close"]))
        h.append(float(r.get("high") or r["close"]))
        l.append(float(r.get("low") or r["close"]))
    return o, h, l, c


def _fetch_etf_history(ticker: str, end_date: date, days: int = 300) -> list[dict]:
    if not HAS_YF:
        return []
    start = end_date - timedelta(days=days)
    try:
        df = yf.download(
            ticker,
            start=start.isoformat(),
            end=(end_date + timedelta(days=1)).isoformat(),
            progress=False,
            auto_adjust=True,
        )
        if df is None or df.empty:
            return []
        rows = []
        for idx, row in df.iterrows():
            def _col(name):
                for c in df.columns:
                    if name.lower() in str(c).lower():
                        return c
                return None
            close_col = _col("close")
            high_col = _col("high")
            low_col = _col("low")
            open_col = _col("open")
            import pandas as pd
            c = float(row[close_col]) if close_col and pd.notna(row[close_col]) else None
            if c:
                rows.append({
                    "date": idx.strftime("%Y-%m-%d"),
                    "close": c,
                    "high": float(row[high_col]) if high_col and pd.notna(row[high_col]) else c,
                    "low": float(row[low_col]) if low_col and pd.notna(row[low_col]) else c,
                    "open": float(row[open_col]) if open_col and pd.notna(row[open_col]) else c,
                })
        return rows
    except Exception:
        return []


def _load_price_cache(root: Path) -> dict[str, list[dict]]:
    """Load ETF price history from cached file."""
    # Try to find most recent etf recommendations with price history
    rec_dir = root / "data" / "etf_recommendations"
    if not rec_dir.exists():
        return {}
    # Also check for dedicated price cache
    cache_file = root / "data" / "etf_price_cache.json"
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text())
            return data.get("prices", {})
        except Exception:
            pass
    return {}


def determine_signal(
    timing: dict,
    etf_score: float,
    regime: str,
    valuation_score: Optional[float] = None,
    rsi_val: Optional[float] = None,
) -> tuple[str, list[str]]:
    """
    모든 신호를 종합해 진입 액션 결정.

    Returns: (signal_key, reasons_list)
    """
    ts = timing.get("score", 0)
    reasons = []

    # Regime adjustment
    regime_boost = {
        "Growth": 10,
        "Neutral": 0,
        "Inflationary": -5,
        "Risk-Off DollarStrength": -15,
        "Stagflation/Recession": -25,
    }.get(regime, 0)

    combined = ts + regime_boost
    if etf_score >= 65:
        combined += 15
    elif etf_score >= 55:
        combined += 5
    elif etf_score < 35:
        combined -= 20

    if valuation_score is not None:
        if valuation_score >= 65:
            combined += 10
            reasons.append(f"밸류에이션 매력적 (점수 {valuation_score:.0f})")
        elif valuation_score < 35:
            combined -= 10
            reasons.append(f"밸류에이션 부담 (점수 {valuation_score:.0f})")

    # RSI override
    if rsi_val is not None:
        if rsi_val > 80:
            combined -= 25
            reasons.append(f"RSI {rsi_val:.0f} 극단 과매수 — 진입 금지")
        elif rsi_val < 25:
            combined += 15
            reasons.append(f"RSI {rsi_val:.0f} 극단 과매도 — 반등 가능성")

    # Map to signal
    if combined >= 65:
        signal = "강력매수"
        reasons.append("기술적·레짐·밸류에이션 복합 신호 모두 우호적")
    elif combined >= 40:
        signal = "분할매수"
    elif combined >= 20:
        signal = "소규모탐색"
    elif combined >= -15:
        signal = "관망"
    elif combined >= -40:
        signal = "비중축소"
    else:
        signal = "회피"

    reasons.extend(timing.get("evidence", [])[:4])
    return signal, reasons


def position_sizing(
    signal: str,
    total_cash: int,
    regime: str,
    etf_type: str,
) -> dict:
    """
    포지션 사이징 가이드라인.
    Returns: max_allocation_pct, first_tranche_pct, tranches, schedule
    """
    # Base max allocation by asset type and signal
    base_max = {
        "equity_broad": 20,
        "equity_tech": 15,
        "equity_em": 12,
        "equity_sector": 10,
        "bond_long": 15,
        "bond_mid": 12,
        "commodity_gold": 10,
        "fx_dollar": 8,
    }.get(etf_type, 12)

    # Scale by signal
    signal_multiplier = {
        "강력매수": 1.0,
        "분할매수": 0.75,
        "소규모탐색": 0.4,
        "관망": 0,
        "비중축소": 0,
        "회피": 0,
    }.get(signal, 0.5)

    # Regime scaling
    regime_scale = {
        "Growth": 1.0,
        "Neutral": 0.85,
        "Inflationary": 0.7,
        "Risk-Off DollarStrength": 0.6,
        "Stagflation/Recession": 0.5,
    }.get(regime, 0.8)

    effective_max = base_max * signal_multiplier * regime_scale

    if effective_max <= 0:
        return {
            "max_allocation_pct": 0,
            "first_tranche_pct": 0,
            "tranches": [],
            "first_amount": 0,
            "schedule": "진입 보류",
            "micro_step_pct": 0,
            "micro_step_amount": 0,
            "micro_plan": "관망 또는 기존 보유분 관리가 우선",
        }

    # Tranches
    if signal == "강력매수":
        tranches_pct = [0.35, 0.35, 0.30]
        schedule = "오늘 1차 진입 → 2~3일 내 눌림목 2차 → 추세 확인 후 3차"
    elif signal == "분할매수":
        tranches_pct = [0.25, 0.35, 0.25, 0.15]
        schedule = "이번 주 1차 → 다음 주 확인 2차 → 2주 내 3~4차 완성"
    elif signal == "소규모탐색":
        tranches_pct = [1.0]
        schedule = "소량 탐색 진입 (1%) → RSI 35 이하 혹은 추가 확인 신호 시 증량"
    else:
        tranches_pct = []
        schedule = "진입 보류"

    first_tranche_pct = effective_max * (tranches_pct[0] if tranches_pct else 0)
    first_amount = int(total_cash * first_tranche_pct / 100)
    if signal == "강력매수":
        micro_step_pct = 2.0
    elif signal in ("분할매수", "소규모탐색"):
        micro_step_pct = 1.0
    else:
        micro_step_pct = 0
    micro_step_amount = int(total_cash * micro_step_pct / 100)
    if signal == "강력매수":
        micro_plan = f"지금은 1회에 총 현금의 2%({micro_step_amount:,}원)씩 2~3번 나눠 진입하는 방식이 적합"
    elif signal == "분할매수":
        micro_plan = f"1회에 총 현금의 1%({micro_step_amount:,}원)씩 천천히 시작하고, 눌림목마다 증액"
    elif signal == "소규모탐색":
        micro_plan = f"탐색 단계이므로 1회에 총 현금의 1%({micro_step_amount:,}원) 이내만 진입"
    else:
        micro_plan = "추가 진입보다 보유분 점검 또는 대기가 적합"

    return {
        "max_allocation_pct": round(effective_max, 1),
        "first_tranche_pct": round(first_tranche_pct, 1),
        "tranches": [round(effective_max * t, 1) for t in tranches_pct],
        "first_amount": first_amount,
        "schedule": schedule,
        "micro_step_pct": micro_step_pct,
        "micro_step_amount": micro_step_amount,
        "micro_plan": micro_plan,
    }


def entry_exit_conditions(
    etf: dict,
    timing: dict,
    macro: dict,
) -> dict:
    """진입/청산 조건 생성."""
    mi = macro.get("macro_inputs", {}) or {}
    ti = macro.get("technical_inputs", {}) or {}
    bb_info = timing.get("details", {}).get("bollinger", {}) or {}
    ma_info = timing.get("details", {}).get("ma_alignment", {}) or {}
    rsi_val = timing.get("details", {}).get("rsi")
    macd_info = timing.get("details", {}).get("macd", {}) or {}
    candle_info = timing.get("details", {}).get("candle", {}) or {}
    elliott_info = timing.get("details", {}).get("elliott_wave", {}) or {}

    # Entry conditions
    entry_conditions = []

    # RSI-based entry
    if rsi_val is not None:
        if rsi_val > 55:
            entry_conditions.append(f"RSI {rsi_val:.0f}이 45 이하로 내려올 때까지 대기")
        else:
            entry_conditions.append(f"현재 RSI {rsi_val:.0f} — 진입 가능 구간")

    # MA-based entry
    ma200 = ma_info.get("ma200")
    price_vs_200 = ma_info.get("price_vs_ma200_pct")
    if price_vs_200 is not None:
        if price_vs_200 > 10:
            entry_conditions.append(f"200일선 대비 +{price_vs_200:.1f}% 이격 — 200일선 터치 시 분할 매수 강화")
        else:
            entry_conditions.append(f"200일선 근접(이격 {price_vs_200:+.1f}%) — 현 수준에서 분할 진입 가능")

    # Bollinger-based entry
    pb = bb_info.get("percent_b")
    if pb is not None:
        if pb < 0.3:
            entry_conditions.append(f"볼린저 하단(%B={pb:.2f}) — 반등 확인 후 추가 매수")
        elif pb > 0.7:
            entry_conditions.append(f"볼린저 상단 근접(%B={pb:.2f}) — 눌림목 대기")

    # MACD entry
    if macd_info.get("crossover") == "bullish":
        entry_conditions.append("MACD 골든크로스 — 즉시 진입 신호")
    elif macd_info.get("trend") == "하락추세":
        entry_conditions.append("MACD 하락추세 중 — MACD 전환 확인 후 진입")

    candle_pattern = candle_info.get("pattern")
    candle_sentiment = candle_info.get("sentiment")
    if candle_pattern and candle_pattern != "없음":
        if candle_sentiment in {"강한매수", "매수", "약한매수"}:
            entry_conditions.append(f"캔들 {candle_pattern} 확인 — 오늘 1차 진입 허용")
        elif candle_sentiment in {"강한매도", "매도"}:
            entry_conditions.append(f"캔들 {candle_pattern} 출현 — 양봉 확인 전까지 대기")

    if elliott_info.get("entry_timing") == "매우좋음":
        entry_conditions.append(f"엘리엇 {elliott_info.get('wave_phase')} — 조정 마무리 가능성, 1% 단위 분할매수 적합")
    elif elliott_info.get("entry_timing") == "좋음":
        entry_conditions.append(f"엘리엇 {elliott_info.get('wave_phase')} — 단계적 진입 가능")
    elif elliott_info.get("entry_timing") in {"위험", "매우위험"}:
        entry_conditions.append(f"엘리엇 {elliott_info.get('wave_phase')} — 추격매수보다 조정 대기")

    # VIX-based
    vix = mi.get("vix")
    if vix:
        if vix > 30:
            entry_conditions.append(f"VIX {vix:.1f} 고공포 — VIX 25 이하 안정 확인 후 비중 확대")
        elif vix > 20:
            entry_conditions.append(f"VIX {vix:.1f} 경계 — 분할 진입으로 리스크 관리")
        else:
            entry_conditions.append(f"VIX {vix:.1f} 안정 — 진입 환경 양호")

    # Exit conditions
    exit_conditions = []
    exit_conditions.append("RSI 75 이상 과매수 구간 진입 시 일부 익절")
    exit_conditions.append("200일선 대비 +20% 이상 이격 시 이익 실현")
    if ma_info.get("death_cross"):
        exit_conditions.append("데드크로스(MA50<MA200) 발생 시 전량 청산")
    else:
        exit_conditions.append("데드크로스 발생 시 비중 50% 이하로 축소")
    exit_conditions.append("볼린저밴드 상단 이탈(%B>1.0) 후 반락 시 축소")
    exit_conditions.append("레짐이 Stagflation/Recession으로 전환 시 즉시 검토")

    # Add ETF-specific exit
    if "bond" in etf.get("type", ""):
        exit_conditions.append("금리 재상승(10년물 5% 돌파) 시 채권 비중 즉시 축소")
    elif "equity" in etf.get("type", ""):
        exit_conditions.append("VIX 40 이상 급등 시 방어적 자산으로 교체")

    return {
        "entry_conditions": entry_conditions[:5],
        "exit_conditions": exit_conditions[:5],
    }


def generate_signal_for_etf(
    etf: dict,
    price_history: list[dict],
    regime: str,
    etf_score: float,
    date_str: str,
    macro: dict,
    total_cash: int,
    valuation_data: dict,
) -> dict:
    """단일 ETF에 대한 종합 신호 생성."""
    closes = _slice_closes(price_history, date_str)
    o, h, l, c = _slice_ohlc(price_history, date_str)

    rsi_val = rsi(closes, 14) if len(closes) > 14 else None
    vol_val = volatility(closes, 20) if len(closes) > 20 else None

    # Technical timing score
    timing = compute_timing(closes, opens=o or None, highs=h or None, lows=l or None, rsi_val=rsi_val)

    # Valuation score for this ETF
    val_score = None
    etf_type = etf.get("type", "")
    if "sp500" in etf.get("id", "").lower() or etf.get("ticker") in {"SPY"}:
        val_score = valuation_data.get("sp500", {}).get("valuation_score")
    elif etf.get("ticker") in {"QQQ", "TIGER_NQ100"}:
        val_score = valuation_data.get("nasdaq", {}).get("valuation_score")
    elif etf.get("region") == "KR" or etf.get("ticker", "").endswith(".KS"):
        val_score = valuation_data.get("kospi", {}).get("valuation_score")
    elif "gold" in etf_type or etf.get("ticker") in {"GLD", "KODEX_GOLD"}:
        val_score = valuation_data.get("gold", {}).get("valuation_score")

    signal, reasons = determine_signal(
        timing, etf_score, regime, val_score, rsi_val
    )
    sizing = position_sizing(signal, total_cash, regime, etf_type)
    conditions = entry_exit_conditions(etf, timing, macro)

    # Account fit
    accounts = ETF_ACCOUNT_FIT.get(etf.get("id", ""), ["TOSS"])

    # Current price
    current_price = closes[-1] if closes else None

    return {
        "id": etf.get("id"),
        "name": etf.get("name"),
        "ticker": etf.get("ticker"),
        "region": etf.get("region"),
        "type": etf_type,
        "currency": etf.get("currency", "USD"),
        "current_price": round(current_price, 2) if current_price else None,
        "signal": signal,
        "signal_info": SIGNAL_LABELS.get(signal, {}),
        "timing_score": timing.get("score"),
        "timing_grade": timing.get("grade"),
        "timing_signal": timing.get("signal"),
        "etf_quant_score": etf_score,
        "valuation_score": val_score,
        "rsi": round(rsi_val, 1) if rsi_val is not None else None,
        "volatility_20d": round(vol_val, 1) if vol_val is not None else None,
        "position_sizing": sizing,
        "entry_conditions": conditions["entry_conditions"],
        "exit_conditions": conditions["exit_conditions"],
        "reasons": reasons[:6],
        "account_fit": accounts,
        "timing_details": {
            k: v for k, v in timing.get("details", {}).items()
            if k in ("macd", "bollinger", "ma_alignment", "elliott_wave", "candle", "rsi")
        },
    }


def run_signals(root: Path, date_str: str) -> dict:
    macro_file = root / "data" / "macro_analysis" / f"{date_str}.json"
    etf_file = root / "data" / "etf_recommendations" / f"{date_str}.json"
    val_file = root / "data" / "valuation" / f"{date_str}.json"
    portfolio_file = root / "data" / "portfolio_state.json"

    macro = _load_json(macro_file) or {}
    etf_recs = _load_json(etf_file) or {}
    valuation = _load_json(val_file) or {}
    portfolio = _load_json(portfolio_file) or {}

    regime = macro.get("regime", "Neutral")
    total_cash = portfolio.get("total_cash", 18_000_000)

    # Build ETF score map
    score_map = {}
    name_map = {}
    etf_meta = {}
    for item in etf_recs.get("recommendations", []):
        etf_id = item["id"]
        score_map[etf_id] = item.get("score", 50)
        name_map[etf_id] = item.get("name", etf_id)
        etf_meta[etf_id] = item

    # Load price history cache
    price_cache = _load_price_cache(root)

    # ETF universe (must match etf_recommender.py)
    ETF_UNIVERSE = [
        {"id": "SPY", "name": "S&P 500 ETF", "ticker": "SPY", "region": "US", "type": "equity_broad", "currency": "USD"},
        {"id": "QQQ", "name": "나스닥 100 ETF", "ticker": "QQQ", "region": "US", "type": "equity_tech", "currency": "USD"},
        {"id": "GLD", "name": "금 ETF", "ticker": "GLD", "region": "US", "type": "commodity_gold", "currency": "USD"},
        {"id": "TLT", "name": "미국 장기국채 ETF", "ticker": "TLT", "region": "US", "type": "bond_long", "currency": "USD"},
        {"id": "IEF", "name": "미국 중기국채 ETF", "ticker": "IEF", "region": "US", "type": "bond_mid", "currency": "USD"},
        {"id": "UUP", "name": "달러 불리시 ETF", "ticker": "UUP", "region": "US", "type": "fx_dollar", "currency": "USD"},
        {"id": "EEM", "name": "이머징마켓 ETF", "ticker": "EEM", "region": "EM", "type": "equity_em", "currency": "USD"},
        {"id": "XLE", "name": "에너지 섹터 ETF", "ticker": "XLE", "region": "US", "type": "equity_sector", "currency": "USD"},
        {"id": "XLF", "name": "금융 섹터 ETF", "ticker": "XLF", "region": "US", "type": "equity_sector", "currency": "USD"},
        {"id": "EWJ", "name": "iShares MSCI Japan", "ticker": "EWJ", "region": "JP", "type": "equity_broad", "currency": "USD"},
        {"id": "EZU", "name": "iShares MSCI Eurozone", "ticker": "EZU", "region": "EU", "type": "equity_broad", "currency": "USD"},
        {"id": "TIGER200", "name": "TIGER 200", "ticker": "069500.KS", "region": "KR", "type": "equity_broad", "currency": "KRW"},
        {"id": "TIGER_NQ100", "name": "TIGER 미국나스닥100", "ticker": "133690.KS", "region": "US", "type": "equity_tech", "currency": "KRW"},
        {"id": "KODEX_SEMI", "name": "KODEX 반도체", "ticker": "091160.KS", "region": "KR", "type": "equity_sector", "currency": "KRW"},
        {"id": "KODEX_GOLD", "name": "KODEX 골드선물(H)", "ticker": "132030.KS", "region": "US", "type": "commodity_gold", "currency": "KRW"},
        {"id": "KODEX_USD", "name": "KODEX 미국달러선물", "ticker": "261240.KS", "region": "US", "type": "fx_dollar", "currency": "KRW"},
        {"id": "TIGER200_IT", "name": "TIGER 200 IT", "ticker": "371460.KS", "region": "KR", "type": "equity_sector", "currency": "KRW"},
        {"id": "KODEX_US30Y", "name": "KODEX 미국채울트라30년(H)", "ticker": "148020.KS", "region": "US", "type": "bond_long", "currency": "KRW"},
        {"id": "TIGER_JAPAN", "name": "TIGER 일본니케이225", "ticker": "241180.KS", "region": "JP", "type": "equity_broad", "currency": "KRW"},
    ]

    signals = []
    end_dt = _parse_date(date_str)

    for etf in ETF_UNIVERSE:
        etf_id = etf["id"]
        ticker = etf["ticker"]
        etf_score = score_map.get(etf_id, 50)

        # Try to get price history
        history = price_cache.get(ticker, [])
        if not history and HAS_YF:
            history = _fetch_etf_history(ticker, end_dt, days=300)

        sig = generate_signal_for_etf(
            etf=etf,
            price_history=history,
            regime=regime,
            etf_score=etf_score,
            date_str=date_str,
            macro=macro,
            total_cash=total_cash,
            valuation_data=valuation,
        )
        signals.append(sig)

    # Sort: 강력매수 first, 회피 last
    order = ["강력매수", "분할매수", "소규모탐색", "관망", "비중축소", "회피"]
    signals.sort(key=lambda x: (order.index(x["signal"]) if x["signal"] in order else 99, -(x.get("etf_quant_score") or 0)))

    # Account-based action plan
    account_plans = _build_account_plans(signals, portfolio, regime)

    # Market overview signals
    market_signal = _overall_market_signal(macro, valuation, regime)

    return {
        "date": date_str,
        "regime": regime,
        "total_cash": total_cash,
        "market_signal": market_signal,
        "signals": signals,
        "account_plans": account_plans,
        "top_buys": [s for s in signals if s["signal"] in ("강력매수", "분할매수")][:5],
        "avoid_list": [s for s in signals if s["signal"] == "회피"],
        "summary": {
            "강력매수": sum(1 for s in signals if s["signal"] == "강력매수"),
            "분할매수": sum(1 for s in signals if s["signal"] == "분할매수"),
            "소규모탐색": sum(1 for s in signals if s["signal"] == "소규모탐색"),
            "관망": sum(1 for s in signals if s["signal"] == "관망"),
            "비중축소": sum(1 for s in signals if s["signal"] == "비중축소"),
            "회피": sum(1 for s in signals if s["signal"] == "회피"),
        },
    }


def _overall_market_signal(macro: dict, valuation: dict, regime: str) -> dict:
    """전체 시장 진입 타이밍 신호."""
    total_score = (macro.get("scores") or {}).get("total") or 50
    avg_val = valuation.get("summary", {}).get("avg_score") or 50

    market_score = (total_score + avg_val) / 2

    if market_score >= 65:
        market_action = "공격적 매수 가능"
        deploy_pct = 70
        note = "레짐·밸류에이션 모두 우호적 — 목표 비중의 70%까지 배치 가능"
    elif market_score >= 55:
        market_action = "분할 매수 권장"
        deploy_pct = 50
        note = "긍정 신호 우세 — 월별 분할로 50%까지 배치"
    elif market_score >= 45:
        market_action = "신중한 탐색"
        deploy_pct = 30
        note = "혼조 구간 — 핵심 ETF만 소규모 탐색, 현금 비중 유지"
    elif market_score >= 35:
        market_action = "관망 유지"
        deploy_pct = 15
        note = "리스크 높음 — 대기 현금 확보, 과매도 포착 후 진입"
    else:
        market_action = "방어 모드"
        deploy_pct = 5
        note = "레짐 비우호적 — 안전자산 또는 현금 중심 유지"

    return {
        "market_score": round(market_score, 1),
        "macro_total": total_score,
        "valuation_avg": avg_val,
        "action": market_action,
        "deployable_pct": deploy_pct,
        "note": note,
        "regime": regime,
    }


def _build_account_plans(signals: list[dict], portfolio: dict, regime: str) -> dict:
    accounts = portfolio.get("accounts", {})
    plans = {}

    for acc_key, acc_data in accounts.items():
        cash = acc_data.get("cash", 0)
        label = acc_data.get("label", acc_key)

        # Filter ETFs suitable for this account
        suitable = [s for s in signals if acc_key in s.get("account_fit", []) and s["signal"] in ("강력매수", "분할매수", "소규모탐색")]
        top = suitable[:3]

        # Recommended deployment
        if regime in ("Stagflation/Recession", "Risk-Off DollarStrength"):
            deploy_ratio = 0.2
        elif regime == "Neutral":
            deploy_ratio = 0.35
        elif regime == "Growth":
            deploy_ratio = 0.55
        else:
            deploy_ratio = 0.3

        deploy_amount = int(cash * deploy_ratio)

        plans[acc_key] = {
            "label": label,
            "cash": cash,
            "deploy_ratio": deploy_ratio,
            "deploy_amount": deploy_amount,
            "top_picks": [
                {
                    "id": s["id"],
                    "name": s["name"],
                    "signal": s["signal"],
                    "timing_grade": s.get("timing_grade"),
                    "first_amount": s.get("position_sizing", {}).get("first_amount", 0),
                    "schedule": s.get("position_sizing", {}).get("schedule", ""),
                }
                for s in top
            ],
        }

    return plans


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--base-dir", default=str(ROOT))
    args = parser.parse_args()

    root = Path(args.base_dir)
    result = run_signals(root, args.date)

    out_dir = root / "data" / "signals"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{args.date}.json"
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"wrote {out_file}")

    ms = result["market_signal"]
    print(f"\n[시장 신호] {ms['action']} — {ms['note']}")
    print(f"투자 가능 비중: {ms['deployable_pct']}%")
    print(f"\n[ETF 신호 요약]")
    for k, v in result["summary"].items():
        if v > 0:
            print(f"  {k}: {v}개")
    print(f"\n[상위 매수 추천]")
    for s in result["top_buys"][:3]:
        print(f"  {s['signal']} {s['name']}({s['id']}) | 타이밍:{s['timing_grade']} | RSI:{s.get('rsi')}")


if __name__ == "__main__":
    main()
