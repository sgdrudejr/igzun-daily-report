#!/usr/bin/env python3
"""
기술적 타이밍 지표 모듈 — MACD, 볼린저밴드, 이평선 정배열/역배열,
캔들 패턴, 엘리엇파동 단계, 종합 진입 타이밍 점수.
"""
import math
from typing import Optional

# ── helpers ──────────────────────────────────────────────────────────────────

def _ema(values: list[float], period: int) -> Optional[float]:
    if len(values) < period or period <= 0:
        return None
    k = 2.0 / (period + 1)
    val = sum(values[:period]) / period
    for v in values[period:]:
        val = v * k + val * (1 - k)
    return val


def _ema_series(values: list[float], period: int) -> list[Optional[float]]:
    """Return EMA at each bar (None for bars before we have enough data)."""
    if len(values) < period:
        return [None] * len(values)
    k = 2.0 / (period + 1)
    out = [None] * (period - 1)
    val = sum(values[:period]) / period
    out.append(val)
    for v in values[period:]:
        val = v * k + val * (1 - k)
        out.append(val)
    return out


def _sma(values: list[float], period: int) -> Optional[float]:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def _sma_at(values: list[float], period: int) -> Optional[float]:
    """Most recent SMA."""
    return _sma(values, period)


# ── MACD ─────────────────────────────────────────────────────────────────────

def macd(
    closes: list[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> dict:
    """
    MACD 지표.
    Returns:
      macd_line, signal_line, histogram
      crossover: "bullish" | "bearish" | None
      trend: "상승추세" | "하락추세" | "중립"
      divergence: "bullish_div" | "bearish_div" | None  (simplified)
    """
    if len(closes) < slow + signal:
        return {
            "macd_line": None, "signal_line": None, "histogram": None,
            "crossover": None, "trend": "데이터부족", "divergence": None,
        }

    ema_fast_series = _ema_series(closes, fast)
    ema_slow_series = _ema_series(closes, slow)

    macd_series = []
    for ef, es in zip(ema_fast_series, ema_slow_series):
        if ef is not None and es is not None:
            macd_series.append(ef - es)
        else:
            macd_series.append(None)

    macd_valid = [v for v in macd_series if v is not None]
    if len(macd_valid) < signal:
        return {
            "macd_line": None, "signal_line": None, "histogram": None,
            "crossover": None, "trend": "데이터부족", "divergence": None,
        }

    sig_series = _ema_series(macd_valid, signal)
    macd_line = macd_valid[-1]
    signal_line = sig_series[-1]
    histogram = macd_line - signal_line if signal_line is not None else None

    # Crossover detection (last 2 bars)
    crossover = None
    if len(macd_valid) >= 2 and len(sig_series) >= 2:
        prev_macd = macd_valid[-2]
        prev_sig = sig_series[-2]
        if prev_sig is not None and signal_line is not None:
            if prev_macd < prev_sig and macd_line > signal_line:
                crossover = "bullish"
            elif prev_macd > prev_sig and macd_line < signal_line:
                crossover = "bearish"

    if macd_line > 0 and histogram is not None and histogram > 0:
        trend = "상승추세"
    elif macd_line < 0 and histogram is not None and histogram < 0:
        trend = "하락추세"
    else:
        trend = "중립"

    # Simplified divergence: price new low but MACD higher low (bullish div)
    divergence = None
    if len(closes) >= 20 and len(macd_valid) >= 20:
        price_low_recent = min(closes[-10:])
        price_low_prev = min(closes[-20:-10])
        macd_low_recent = min(v for v in macd_valid[-10:] if v is not None)
        macd_low_prev = min(v for v in macd_valid[-20:-10] if v is not None)
        if price_low_recent < price_low_prev and macd_low_recent > macd_low_prev:
            divergence = "bullish_div"
        elif price_low_recent > price_low_prev and macd_low_recent < macd_low_prev:
            divergence = "bearish_div"

    return {
        "macd_line": round(macd_line, 4),
        "signal_line": round(signal_line, 4) if signal_line else None,
        "histogram": round(histogram, 4) if histogram else None,
        "crossover": crossover,
        "trend": trend,
        "divergence": divergence,
    }


# ── 볼린저밴드 ────────────────────────────────────────────────────────────────

def bollinger_bands(
    closes: list[float],
    period: int = 20,
    num_std: float = 2.0,
) -> dict:
    """
    볼린저밴드.
    Returns:
      upper, middle, lower: 현재값
      percent_b: 0~1 (0.2 이하 과매도, 0.8 이상 과매수)
      bandwidth: (upper-lower)/middle * 100
      squeeze: bandwidth < 5% (변동성 수축 → 폭발 예고)
      position: "과매도" | "하단" | "중간" | "상단" | "과매수"
    """
    if len(closes) < period:
        return {
            "upper": None, "middle": None, "lower": None,
            "percent_b": None, "bandwidth": None,
            "squeeze": None, "position": "데이터부족",
        }

    window = closes[-period:]
    middle = sum(window) / period
    std = math.sqrt(sum((v - middle) ** 2 for v in window) / period)
    upper = middle + num_std * std
    lower = middle - num_std * std

    price = closes[-1]
    band_range = upper - lower
    percent_b = (price - lower) / band_range if band_range > 0 else 0.5
    bandwidth = (band_range / middle) * 100 if middle > 0 else 0

    squeeze = bandwidth < 5.0

    if percent_b < 0:
        position = "과매도"
    elif percent_b < 0.2:
        position = "하단"
    elif percent_b < 0.8:
        position = "중간"
    elif percent_b < 1.0:
        position = "상단"
    else:
        position = "과매수"

    return {
        "upper": round(upper, 4),
        "middle": round(middle, 4),
        "lower": round(lower, 4),
        "percent_b": round(percent_b, 3),
        "bandwidth": round(bandwidth, 2),
        "squeeze": squeeze,
        "position": position,
    }


# ── 이평선 정배열/역배열 ───────────────────────────────────────────────────────

def ma_alignment(closes: list[float]) -> dict:
    """
    이평선 정배열 분석 (20/50/120/200일).
    Returns:
      ma20, ma50, ma120, ma200
      alignment: "완전정배열" | "정배열" | "혼조" | "역배열" | "완전역배열"
      golden_cross: True/False (MA50이 최근 MA200을 상향 돌파했는지)
      death_cross: True/False
      price_vs_ma200_pct: 현재가 MA200 대비 ±%
      score: -100 ~ +100 (정배열도)
    """
    ma20 = _sma(closes, 20)
    ma50 = _sma(closes, 50)
    ma120 = _sma(closes, 120)
    ma200 = _sma(closes, 200)
    price = closes[-1] if closes else None

    # Golden/Death Cross detection (50 vs 200, last 5 bars)
    golden_cross = False
    death_cross = False
    if len(closes) >= 205:
        ma50_prev = _sma(closes[:-5], 50)
        ma200_prev = _sma(closes[:-5], 200)
        if ma50 and ma200 and ma50_prev and ma200_prev:
            if ma50_prev < ma200_prev and ma50 > ma200:
                golden_cross = True
            elif ma50_prev > ma200_prev and ma50 < ma200:
                death_cross = True

    # Alignment scoring
    score = 0
    available_mas = [(v, n) for v, n in [(ma20, 20), (ma50, 50), (ma120, 120), (ma200, 200)] if v is not None]

    # Price vs each MA
    if price:
        for ma_val, period in available_mas:
            diff_pct = (price - ma_val) / ma_val * 100
            weight = {20: 1, 50: 2, 120: 2.5, 200: 3}.get(period, 1)
            score += (1 if diff_pct > 0 else -1) * weight

    score = max(-10, min(10, score))
    score_normalized = int(score / 10 * 100)

    # Alignment label
    sorted_mas = [(v, n) for v, n in sorted(available_mas, key=lambda x: x[0], reverse=True)]
    periods = [n for v, n in sorted_mas]

    if periods[:4] == [20, 50, 120, 200]:
        alignment = "완전정배열"
    elif periods[:2] == [20, 50] and (len(periods) < 3 or periods[0] < periods[-1]):
        alignment = "정배열"
    elif periods[:4] == [200, 120, 50, 20]:
        alignment = "완전역배열"
    elif len(periods) >= 2 and periods[-1] == 20:
        alignment = "역배열"
    else:
        alignment = "혼조"

    price_vs_ma200 = None
    if price and ma200:
        price_vs_ma200 = round((price - ma200) / ma200 * 100, 2)

    return {
        "ma20": round(ma20, 2) if ma20 else None,
        "ma50": round(ma50, 2) if ma50 else None,
        "ma120": round(ma120, 2) if ma120 else None,
        "ma200": round(ma200, 2) if ma200 else None,
        "alignment": alignment,
        "golden_cross": golden_cross,
        "death_cross": death_cross,
        "price_vs_ma200_pct": price_vs_ma200,
        "score": score_normalized,
    }


# ── 캔들 패턴 ─────────────────────────────────────────────────────────────────

def candlestick_pattern(
    opens: list[float],
    highs: list[float],
    lows: list[float],
    closes: list[float],
    lookback: int = 3,
) -> dict:
    """
    최근 캔들 패턴 감지.
    Detects: Doji, Hammer, Shooting Star, Bullish Engulfing, Bearish Engulfing,
             Morning Star, Evening Star, Marubozu
    Returns:
      pattern: 패턴명 (없으면 "없음")
      sentiment: "강한매수" | "매수" | "중립" | "매도" | "강한매도"
      description: 설명
    """
    n = min(len(opens), len(highs), len(lows), len(closes), lookback + 2)
    if n < 2:
        return {"pattern": "데이터부족", "sentiment": "중립", "description": "캔들 데이터 부족"}

    # Use the last few candles
    o = opens[-n:]
    h = highs[-n:]
    l = lows[-n:]
    c = closes[-n:]

    patterns = []

    # Most recent candle
    body = abs(c[-1] - o[-1])
    full_range = h[-1] - l[-1]
    upper_shadow = h[-1] - max(c[-1], o[-1])
    lower_shadow = min(c[-1], o[-1]) - l[-1]
    bullish_candle = c[-1] > o[-1]
    bearish_candle = c[-1] < o[-1]

    # Doji: body < 10% of range
    if full_range > 0 and body / full_range < 0.1:
        patterns.append(("도지", "중립", "매수·매도 균형, 추세 전환 가능성"))

    # Hammer (바닥에서): 아래꼬리가 몸통의 2배 이상, 위꼬리는 짧음
    if body > 0 and lower_shadow >= 2 * body and upper_shadow < body * 0.5:
        if bullish_candle:
            patterns.append(("망치형", "매수", "하락 후 강한 반등 매수세, 저가 지지 신호"))
        else:
            patterns.append(("역망치형", "약한매수", "하락 후 반등 시도, 다음 날 확인 필요"))

    # Shooting Star: 위꼬리가 몸통의 2배 이상
    if body > 0 and upper_shadow >= 2 * body and lower_shadow < body * 0.5:
        patterns.append(("유성형", "매도", "상승 고점에서의 매도 압력, 하락 전환 신호"))

    # Marubozu: 위아래 꼬리 없는 큰 몸통
    if full_range > 0 and body / full_range > 0.9:
        if bullish_candle:
            patterns.append(("강세마루보주", "강한매수", "강한 상승 세력, 추세 지속"))
        else:
            patterns.append(("약세마루보주", "강한매도", "강한 하락 세력, 추세 지속"))

    # Two-candle patterns
    if n >= 2:
        prev_body = abs(c[-2] - o[-2])
        prev_bullish = c[-2] > o[-2]

        # Bullish Engulfing
        if (not prev_bullish) and bullish_candle and c[-1] > o[-2] and o[-1] < c[-2]:
            patterns.append(("강세장악형", "강한매수", "이전 하락봉을 완전히 감싸는 상승봉, 강한 매수 신호"))

        # Bearish Engulfing
        if prev_bullish and (not bullish_candle) and o[-1] > c[-2] and c[-1] < o[-2]:
            patterns.append(("약세장악형", "강한매도", "이전 상승봉을 완전히 감싸는 하락봉, 강한 매도 신호"))

        # Tweezer Top/Bottom
        if abs(h[-1] - h[-2]) / max(h[-1], h[-2], 1) < 0.002:
            if prev_bullish and (not bullish_candle):
                patterns.append(("집게형 고점", "매도", "동일한 고점 두 번 — 저항 확인"))
        if abs(l[-1] - l[-2]) / max(l[-1], l[-2], 1) < 0.002:
            if (not prev_bullish) and bullish_candle:
                patterns.append(("집게형 저점", "매수", "동일한 저점 두 번 — 지지 확인"))

    # Three-candle patterns
    if n >= 3:
        # Morning Star
        mid_body = abs(c[-2] - o[-2])
        if c[-3] < o[-3] and mid_body < abs(c[-3]-o[-3])*0.3 and c[-1] > o[-1]:
            patterns.append(("샛별형", "강한매수", "하락 후 작은 캔들 + 강한 반등 — 바닥 전환"))
        # Evening Star
        if c[-3] > o[-3] and mid_body < abs(c[-3]-o[-3])*0.3 and c[-1] < o[-1]:
            patterns.append(("저녁별형", "강한매도", "상승 후 작은 캔들 + 강한 하락 — 고점 전환"))

    if not patterns:
        return {"pattern": "없음", "sentiment": "중립", "description": "특이 패턴 없음"}

    # Return the most significant pattern
    sentiment_order = ["강한매수", "강한매도", "매수", "매도", "약한매수", "중립"]
    patterns.sort(key=lambda x: sentiment_order.index(x[1]) if x[1] in sentiment_order else 99)

    best = patterns[0]
    return {
        "pattern": best[0],
        "sentiment": best[1],
        "description": best[2],
        "all_patterns": [{"pattern": p[0], "sentiment": p[1], "description": p[2]} for p in patterns],
    }


# ── 엘리엇 파동 단계 (단순화) ─────────────────────────────────────────────────

def elliott_wave_phase(closes: list[float], period: int = 60) -> dict:
    """
    엘리엇 파동 단계 추정 (단순화된 모멘텀 기반).

    3개 구간으로 나눠 모멘텀 패턴을 분석:
    - 5파 상승추세: 각 구간 수익률이 양수 + 가속
    - 3파(ABC) 조정: 하락 후 반등 또는 횡보
    - 조정 완료 후 재개: 저점 높아지는 구조

    Returns:
      wave_phase: "1파(시작)" | "3파(가속)" | "5파(과열)" | "A파(조정시작)" |
                  "B파(반등)" | "C파(최종조정)" | "조정완료(재개가능)"
      confidence: "높음" | "중간" | "낮음"
      interpretation: 설명
      entry_timing: "매우좋음" | "좋음" | "보통" | "위험" | "매우위험"
    """
    if len(closes) < period:
        return {
            "wave_phase": "분석불가",
            "confidence": "낮음",
            "interpretation": "데이터 부족",
            "entry_timing": "보통",
        }

    # Split into 3 equal segments
    seg_size = period // 3
    seg1 = closes[-period:-period+seg_size]
    seg2 = closes[-period+seg_size:-period+2*seg_size]
    seg3 = closes[-seg_size:]

    def seg_return(seg):
        if len(seg) < 2 or seg[0] == 0:
            return 0
        return (seg[-1] - seg[0]) / seg[0] * 100

    r1 = seg_return(seg1)
    r2 = seg_return(seg2)
    r3 = seg_return(seg3)
    total = seg_return(closes[-period:])

    # Recent 10% of period: acceleration check
    recent_period = max(5, period // 10)
    recent_return = seg_return(closes[-recent_period:])

    # Higher lows check (for accumulation)
    lows_check = []
    step = period // 5
    for i in range(5):
        segment = closes[-(i+1)*step:-(i)*step if i > 0 else None]
        if segment:
            lows_check.append(min(segment))
    higher_lows = all(lows_check[i] >= lows_check[i+1] for i in range(len(lows_check)-1)) if len(lows_check) >= 3 else False
    lower_lows = all(lows_check[i] <= lows_check[i+1] for i in range(len(lows_check)-1)) if len(lows_check) >= 3 else False

    # Classify wave
    if total > 15 and r3 > 5 and recent_return > 2:
        wave_phase = "5파(과열)"
        confidence = "중간"
        interpretation = "강한 상승 5파 구간 — 이미 많이 오른 상태, 진입 위험 높음"
        entry_timing = "위험"
    elif total > 5 and r2 > r1 and r2 > 0:
        wave_phase = "3파(가속)"
        confidence = "중간"
        interpretation = "추세 가속 구간(3파) — 모멘텀 강하고 추가 상승 여력 있음"
        entry_timing = "좋음"
    elif total < -15 and r3 < -3 and not higher_lows:
        wave_phase = "C파(최종조정)"
        confidence = "중간"
        interpretation = "C파 조정 진행 중 — 하락 마무리 가능성, 바닥 확인 후 매수 고려"
        entry_timing = "좋음"
    elif total < -5 and r3 < 0 and r2 > 0:
        wave_phase = "B파(반등)"
        confidence = "낮음"
        interpretation = "B파 반등 구간 — 일시적 반등, 추가 하락(C파) 가능성 있음"
        entry_timing = "위험"
    elif higher_lows and total < 5 and total > -5:
        wave_phase = "조정완료(재개가능)"
        confidence = "낮음"
        interpretation = "저점이 높아지는 구조 — 조정 마무리 후 상승 재개 가능성"
        entry_timing = "매우좋음"
    elif r1 < 0 and r3 > 0 and total > -5:
        wave_phase = "1파(시작)"
        confidence = "낮음"
        interpretation = "초기 상승(1파) 가능성 — 아직 추세 미확인, 소규모 탐색 진입 적합"
        entry_timing = "좋음"
    elif total < -5 and r1 < 0:
        wave_phase = "A파(조정시작)"
        confidence = "낮음"
        interpretation = "A파 조정 시작 가능성 — 성급한 진입 자제, 추가 하락 대비 필요"
        entry_timing = "위험"
    else:
        wave_phase = "횡보(판단보류)"
        confidence = "낮음"
        interpretation = "뚜렷한 파동 구조 없음 — 방향성 확인 후 진입 검토"
        entry_timing = "보통"

    return {
        "wave_phase": wave_phase,
        "confidence": confidence,
        "interpretation": interpretation,
        "entry_timing": entry_timing,
        "segment_returns": {
            "seg1_pct": round(r1, 2),
            "seg2_pct": round(r2, 2),
            "seg3_pct": round(r3, 2),
            "total_pct": round(total, 2),
        },
    }


# ── 종합 기술적 타이밍 점수 ────────────────────────────────────────────────────

def timing_score(
    closes: list[float],
    opens: list[float] | None = None,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    rsi_val: float | None = None,
) -> dict:
    """
    종합 기술적 진입 타이밍 점수.
    Returns:
      score: -100 ~ +100 (양수일수록 매수 적합)
      grade: "A" | "B" | "C" | "D" | "F"
      signal: "강력매수" | "매수신호" | "중립관망" | "매도신호" | "강력매도"
      evidence: list of str (근거들)
      details: dict (각 지표별 점수)
    """
    score = 0
    evidence = []
    details = {}

    # ① MACD
    if len(closes) >= 40:
        mac = macd(closes)
        details["macd"] = mac
        if mac["crossover"] == "bullish":
            score += 25
            evidence.append("MACD 골든크로스 발생 — 단기 상승 전환 신호")
        elif mac["crossover"] == "bearish":
            score -= 25
            evidence.append("MACD 데드크로스 발생 — 단기 하락 전환 신호")
        elif mac["trend"] == "상승추세":
            score += 10
            evidence.append(f"MACD 상승추세 유지 (히스토그램 {mac['histogram']:+.3f})" if mac['histogram'] else "MACD 상승추세 유지")
        elif mac["trend"] == "하락추세":
            score -= 10
            evidence.append("MACD 하락추세 지속")
        if mac["divergence"] == "bullish_div":
            score += 15
            evidence.append("MACD 강세 다이버전스 — 가격 신저점에서 MACD 반등, 바닥 신호")
        elif mac["divergence"] == "bearish_div":
            score -= 10
            evidence.append("MACD 약세 다이버전스 — 고점 괴리 주의")

    # ② 볼린저밴드
    if len(closes) >= 20:
        bb = bollinger_bands(closes)
        details["bollinger"] = bb
        pb = bb.get("percent_b")
        if pb is not None:
            if pb < 0:
                score += 30
                evidence.append(f"볼린저밴드 하단 이탈(%B={pb:.2f}) — 극단 과매도, 반등 가능성")
            elif pb < 0.2:
                score += 20
                evidence.append(f"볼린저밴드 하단 근접(%B={pb:.2f}) — 과매도 구간")
            elif pb > 1.0:
                score -= 30
                evidence.append(f"볼린저밴드 상단 이탈(%B={pb:.2f}) — 극단 과매수")
            elif pb > 0.8:
                score -= 15
                evidence.append(f"볼린저밴드 상단 근접(%B={pb:.2f}) — 과매수 주의")
        if bb.get("squeeze"):
            score += 5
            evidence.append(f"볼린저 스퀴즈(밴드폭={bb.get('bandwidth'):.1f}%) — 변동성 수축, 대형 움직임 예고")

    # ③ 이평선 정배열
    if len(closes) >= 20:
        ma = ma_alignment(closes)
        details["ma_alignment"] = ma
        al = ma.get("alignment", "혼조")
        if al == "완전정배열":
            score += 20
            evidence.append("20/50/120/200 이평선 완전 정배열 — 강한 상승 추세")
        elif al == "정배열":
            score += 10
            evidence.append("이평선 정배열 — 상승 추세 유지")
        elif al == "완전역배열":
            score -= 20
            evidence.append("이평선 완전 역배열 — 강한 하락 추세")
        elif al == "역배열":
            score -= 10
            evidence.append("이평선 역배열 — 하락 추세")
        if ma.get("golden_cross"):
            score += 20
            evidence.append("골든크로스 발생(MA50>MA200) — 중장기 상승 전환 신호")
        elif ma.get("death_cross"):
            score -= 20
            evidence.append("데드크로스 발생(MA50<MA200) — 중장기 하락 전환 신호")
        p200 = ma.get("price_vs_ma200_pct")
        if p200 is not None:
            if p200 < -10:
                score += 10
                evidence.append(f"200일선 -{abs(p200):.1f}% 이격 — 저평가 구간, 매수 기회")
            elif p200 > 20:
                score -= 10
                evidence.append(f"200일선 +{p200:.1f}% 이격 — 과열 주의")

    # ④ RSI
    if rsi_val is not None:
        details["rsi"] = rsi_val
        if rsi_val < 25:
            score += 30
            evidence.append(f"RSI {rsi_val:.0f} 극단 과매도 — 강한 반등 가능성")
        elif rsi_val < 35:
            score += 20
            evidence.append(f"RSI {rsi_val:.0f} 과매도 구간 — 분할매수 적합")
        elif rsi_val < 45:
            score += 8
            evidence.append(f"RSI {rsi_val:.0f} 약세 영역 — 저점 매수 탐색 가능")
        elif rsi_val < 55:
            evidence.append(f"RSI {rsi_val:.0f} 중립 구간")
        elif rsi_val < 65:
            score -= 5
            evidence.append(f"RSI {rsi_val:.0f} 강세 구간 — 과열 접근 주의")
        elif rsi_val < 75:
            score -= 15
            evidence.append(f"RSI {rsi_val:.0f} 과매수 — 신규 매수 자제")
        else:
            score -= 30
            evidence.append(f"RSI {rsi_val:.0f} 극단 과매수 — 진입 위험")

    # ⑤ 캔들 패턴
    if opens and highs and lows and len(closes) >= 3:
        candle = candlestick_pattern(opens, highs, lows, closes)
        details["candle"] = candle
        sentiment_score = {
            "강한매수": 20, "매수": 12, "약한매수": 5,
            "중립": 0,
            "매도": -12, "강한매도": -20,
        }
        cs = sentiment_score.get(candle.get("sentiment", "중립"), 0)
        if cs != 0:
            score += cs
            pname = candle.get("pattern", "")
            desc = candle.get("description", "")
            evidence.append(f"캔들 패턴: {pname} — {desc}")

    # ⑥ 엘리엇 파동
    if len(closes) >= 60:
        ew = elliott_wave_phase(closes)
        details["elliott_wave"] = ew
        ew_score = {
            "매우좋음": 15, "좋음": 8, "보통": 0, "위험": -10, "매우위험": -20
        }.get(ew.get("entry_timing", "보통"), 0)
        score += ew_score
        evidence.append(f"엘리엇 파동: {ew['wave_phase']} — {ew['interpretation']}")

    # Clamp
    score = max(-100, min(100, score))

    # Grade
    if score >= 60:
        grade, signal = "A", "강력매수"
    elif score >= 35:
        grade, signal = "B", "매수신호"
    elif score >= -10:
        grade, signal = "C", "중립관망"
    elif score >= -35:
        grade, signal = "D", "매도신호"
    else:
        grade, signal = "F", "강력매도"

    return {
        "score": score,
        "grade": grade,
        "signal": signal,
        "evidence": evidence,
        "details": details,
    }
