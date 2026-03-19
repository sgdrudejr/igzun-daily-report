#!/usr/bin/env python3
import math


def sma(values, period):
    if len(values) < period or period <= 0:
        return None
    return sum(values[-period:]) / period


def ema(values, period):
    if len(values) < period or period <= 0:
        return None
    k = 2 / (period + 1)
    ema_val = sum(values[:period]) / period
    for v in values[period:]:
        ema_val = v * k + ema_val * (1 - k)
    return ema_val


def momentum(values, period):
    if len(values) <= period:
        return None
    prev = values[-period-1]
    if prev == 0:
        return None
    return (values[-1] / prev - 1.0) * 100.0


def volatility(values, period=20):
    if len(values) <= period:
        return None
    rets = []
    for i in range(-period, 0):
        prev = values[i-1]
        cur = values[i]
        if prev == 0:
            continue
        rets.append((cur / prev) - 1.0)
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    var = sum((x-mean)**2 for x in rets) / (len(rets)-1)
    return (var ** 0.5) * (252 ** 0.5) * 100.0


def rsi(values, period=14):
    if len(values) <= period:
        return None
    gains = []
    losses = []
    for i in range(-period, 0):
        diff = values[i] - values[i-1]
        gains.append(max(diff, 0))
        losses.append(abs(min(diff, 0)))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def ma_gap(values, short_period=20, long_period=60):
    s = sma(values, short_period)
    l = sma(values, long_period)
    if s is None or l in (None, 0):
        return None
    return (s - l) / l * 100.0


def relative_strength(asset_values, bench_values, period=120):
    if len(asset_values) <= period or len(bench_values) <= period:
        return None
    a0 = asset_values[-period-1]
    b0 = bench_values[-period-1]
    if a0 == 0 or b0 == 0:
        return None
    ar = asset_values[-1] / a0 - 1.0
    br = bench_values[-1] / b0 - 1.0
    return (ar - br) * 100.0


def true_range(high, low, close_prev, close_cur):
    return max(high-low, abs(high-close_prev), abs(low-close_prev), abs(close_cur-close_prev))


def adx(highs, lows, closes, period=14):
    n = len(closes)
    if n <= period + 1 or len(highs) != n or len(lows) != n:
        return None
    trs, pdm, ndm = [], [], []
    for i in range(1, n):
        up = highs[i] - highs[i-1]
        down = lows[i-1] - lows[i]
        pdm.append(up if up > down and up > 0 else 0.0)
        ndm.append(down if down > up and down > 0 else 0.0)
        trs.append(true_range(highs[i], lows[i], closes[i-1], closes[i]))
    if len(trs) < period:
        return None
    atr = sum(trs[:period]) / period
    pdi = (sum(pdm[:period]) / period) / atr * 100 if atr else 0
    ndi = (sum(ndm[:period]) / period) / atr * 100 if atr else 0
    denom = pdi + ndi
    dxs = [abs(pdi-ndi)/denom*100 if denom else 0]
    for i in range(period, len(trs)):
        atr = (atr * (period - 1) + trs[i]) / period
        spdm = (sum(pdm[i-period+1:i+1]) / period)
        sndm = (sum(ndm[i-period+1:i+1]) / period)
        pdi = spdm / atr * 100 if atr else 0
        ndi = sndm / atr * 100 if atr else 0
        denom = pdi + ndi
        dxs.append(abs(pdi-ndi)/denom*100 if denom else 0)
    if len(dxs) < period:
        return sum(dxs)/len(dxs) if dxs else None
    return sum(dxs[-period:]) / period
