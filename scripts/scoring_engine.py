#!/usr/bin/env python3
import math

def clamp(v, lo=0, hi=100):
    return max(lo, min(hi, v))


def minmax(value, lo, hi, invert=False):
    if hi <= lo:
        return 50.0
    x = (value - lo) / (hi - lo) * 100.0
    if invert:
        x = 100.0 - x
    return clamp(x)


def sentiment_from_indices(indices):
    mapping = {i.get('name',''): i for i in indices or []}
    sp = mapping.get('S&P 500') or mapping.get('S&P 500 (일간 기준 대체)') or {}
    nas = mapping.get('나스닥') or {}
    oil = mapping.get('WTI 원유') or {}
    gold = mapping.get('금(Gold)') or mapping.get('금') or {}
    score = 50.0
    for item, weight in [(sp, 12), (nas, 10), (oil, -6), (gold, 4)]:
        ch = str(item.get('change',''))
        sign = -1 if '▼' in ch or '-' in ch else (1 if '▲' in ch or '+' in ch else 0)
        pct = 0.0
        import re
        m = re.search(r'([0-9]+(?:\.[0-9]+)?)%', ch)
        if m: pct = float(m.group(1))
        score += sign * min(pct, 3.0) / 3.0 * weight
    if score < 40: status='경계'
    elif score < 55: status='중립'
    elif score < 70: status='완만한 위험선호'
    else: status='탐욕'
    return int(round(clamp(score))), status


def score_holding(name, indicators, macro_bias=0):
    score = 0
    txt = ' '.join(indicators or []) + ' ' + (name or '')
    pos_keys = ['상회', '우상향', '성장', '인프라', '전력', '모멘텀', '강세']
    neg_keys = ['역배열', '둔화', '하락', '약세', '부담', '위험', '저항']
    for k in pos_keys:
        if k in txt: score += 15
    for k in neg_keys:
        if k in txt: score -= 15
    score += macro_bias
    return max(-100, min(100, score))


def etf_rank_score(base, momentum=0, risk=0, thematic=0):
    return int(round(clamp(base + momentum + thematic - risk)))
