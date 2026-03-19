#!/usr/bin/env python3
from scoring_engine import minmax, clamp

DEFAULT_PARAMS = {
    'REGIME_VIX_LOW_THRESHOLD': 35,
    'REGIME_VIX_HIGH_THRESHOLD': 65,
    'REGIME_GROWTH_HIGH_THRESHOLD': 60,
    'REGIME_GROWTH_LOW_THRESHOLD': 40,
    'REGIME_INFLATION_LOW_THRESHOLD': 40,
    'REGIME_INFLATION_HIGH_THRESHOLD': 60,
    'REGIME_US10Y_HIGH_THRESHOLD': 65,
    'REGIME_DXY_HIGH_THRESHOLD': 65,
}


def classify_market_regime(vix_norm, us10y_norm, dxy_norm, inflation_norm, growth_norm, params=None):
    p = {**DEFAULT_PARAMS, **(params or {})}
    if vix_norm < p['REGIME_VIX_LOW_THRESHOLD'] and growth_norm > p['REGIME_GROWTH_HIGH_THRESHOLD'] and inflation_norm < p['REGIME_INFLATION_LOW_THRESHOLD']:
        return 'Growth'
    if vix_norm > p['REGIME_VIX_HIGH_THRESHOLD'] and growth_norm < p['REGIME_GROWTH_LOW_THRESHOLD'] and inflation_norm > p['REGIME_INFLATION_HIGH_THRESHOLD']:
        return 'Stagflation/Recession'
    if us10y_norm > p['REGIME_US10Y_HIGH_THRESHOLD'] and inflation_norm > p['REGIME_INFLATION_HIGH_THRESHOLD']:
        return 'Inflationary'
    if dxy_norm > p['REGIME_DXY_HIGH_THRESHOLD'] and vix_norm > p['REGIME_VIX_HIGH_THRESHOLD']:
        return 'Risk-Off DollarStrength'
    return 'Neutral'


def weighted_score(parts):
    vals = [v*w for v,w in parts if v is not None]
    ws = [w for v,w in parts if v is not None]
    if not ws:
        return None
    return sum(vals) / sum(ws)


def macro_score(vix_norm=None, us10y_norm=None, dxy_norm=None, oil_norm=None, inflation_norm=None, growth_norm=None):
    return weighted_score([
        ((100-vix_norm) if vix_norm is not None else None, 1.2),
        ((100-us10y_norm) if us10y_norm is not None else None, 1.0),
        ((100-dxy_norm) if dxy_norm is not None else None, 0.8),
        (oil_norm, 0.4),
        ((100-inflation_norm) if inflation_norm is not None else None, 1.0),
        (growth_norm, 1.2),
    ])


def fundamental_score(pe_norm=None, pb_norm=None, dividend_yield_norm=None, roe_norm=None, eps_growth_norm=None):
    return weighted_score([
        ((100-pe_norm) if pe_norm is not None else None, 1.0),
        ((100-pb_norm) if pb_norm is not None else None, 0.8),
        (dividend_yield_norm, 0.8),
        (roe_norm, 1.0),
        (eps_growth_norm, 1.2),
    ])


def technical_score(rsi_value=None, ma_gap_norm=None, rel_strength_norm=None, trend_strength_norm=None, volume_breakout_norm=None):
    rsi_score = None
    if rsi_value is not None:
        if rsi_value < 30: rsi_score = 70
        elif rsi_value > 70: rsi_score = 30
        else: rsi_score = (rsi_value - 30) / 40 * 100
    return weighted_score([
        (rsi_score, 0.8),
        (ma_gap_norm, 1.0),
        (rel_strength_norm, 1.1),
        (trend_strength_norm, 0.9),
        (volume_breakout_norm, 0.7),
    ])


def quant_score(momentum_3m_norm=None, momentum_12m_norm=None, volatility_norm=None, value_factor_norm=None, quality_factor_norm=None):
    return weighted_score([
        (momentum_3m_norm, 1.0),
        (momentum_12m_norm, 1.1),
        ((100-volatility_norm) if volatility_norm is not None else None, 0.8),
        (value_factor_norm, 0.7),
        (quality_factor_norm, 0.9),
    ])


def fx_score(dxy_change_norm=None, usdkrw_change_norm=None, usdjpy_change_norm=None, hedge_cost_norm=None, market_corr_norm=None):
    return weighted_score([
        ((100-dxy_change_norm) if dxy_change_norm is not None else None, 0.8),
        ((100-usdkrw_change_norm) if usdkrw_change_norm is not None else None, 0.7),
        ((100-usdjpy_change_norm) if usdjpy_change_norm is not None else None, 0.7),
        ((100-hedge_cost_norm) if hedge_cost_norm is not None else None, 0.5),
        ((100-market_corr_norm) if market_corr_norm is not None else None, 0.6),
    ])


def total_score(regime, macro=None, fundamental=None, technical=None, quant=None, fx=None):
    weights = {
        'Growth': {'macro':0.20,'fundamental':0.20,'technical':0.25,'quant':0.25,'fx':0.10},
        'Stagflation/Recession': {'macro':0.35,'fundamental':0.15,'technical':0.15,'quant':0.15,'fx':0.20},
        'Inflationary': {'macro':0.30,'fundamental':0.15,'technical':0.20,'quant':0.15,'fx':0.20},
        'Risk-Off DollarStrength': {'macro':0.35,'fundamental':0.10,'technical':0.15,'quant':0.15,'fx':0.25},
        'Neutral': {'macro':0.25,'fundamental':0.20,'technical':0.20,'quant':0.20,'fx':0.15},
    }.get(regime, {'macro':0.25,'fundamental':0.20,'technical':0.20,'quant':0.20,'fx':0.15})
    parts = [('macro', macro), ('fundamental', fundamental), ('technical', technical), ('quant', quant), ('fx', fx)]
    num = 0.0; den = 0.0
    for name, val in parts:
        if val is None: continue
        w = weights[name]
        num += val * w
        den += w
    return None if den == 0 else clamp(num / den)
