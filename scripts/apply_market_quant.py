#!/usr/bin/env python3
import json, sys
from pathlib import Path
sys.path.insert(0, '/Users/seo/.openclaw/workspace/igzun-daily-report/scripts')
from technical_indicators import sma, ema, rsi, ma_gap, momentum, volatility, relative_strength, adx
from quant_formula_engine import classify_market_regime, macro_score, technical_score, quant_score, total_score
from scoring_engine import minmax

ROOT = Path('/Users/seo/.openclaw/workspace/igzun-daily-report')
MARKET = ROOT / 'data/market_data_latest.json'
OUT = ROOT / 'data/market_quant_snapshot.json'
SITE = ROOT / 'site/2026-03-19/result.json'


def get_series(asset):
    recs = asset.get('records', [])
    closes = [r['close'] for r in recs if r.get('close') is not None]
    highs = [r['high'] for r in recs if r.get('high') is not None]
    lows = [r['low'] for r in recs if r.get('low') is not None]
    return closes, highs, lows


def main():
    obj = json.loads(MARKET.read_text())
    a = obj['assets']
    sp, sph, spl = get_series(a['S&P500'])
    kospi, _, _ = get_series(a['KOSPI'])
    usdkrw, _, _ = get_series(a['USDKRW'])
    us10y, _, _ = get_series(a['US10Y'])
    wti, _, _ = get_series(a['WTI'])
    gold, _, _ = get_series(a['GOLD'])
    nas, _, _ = get_series(a['NASDAQ'])

    rsi_sp = rsi(sp, 14)
    ma_gap_sp = ma_gap(sp, 20, 60)
    mom3_sp = momentum(sp, 63)
    mom12_sp = momentum(sp, 252)
    vol_sp = volatility(sp, 20)
    rel_sp_kospi = relative_strength(sp, kospi, 120) if kospi else None
    adx_sp = adx(sph, spl, sp, 14) if sph and spl else None

    # normalize against pragmatic ranges
    vix_norm = 50
    us10y_norm = minmax(us10y[-1] if us10y else 4.0, 2.0, 6.0)
    dxy_norm = minmax(usdkrw[-1] if usdkrw else 1400, 1200, 1550)
    inflation_norm = minmax(wti[-1] if wti else 85, 60, 120)
    growth_norm = minmax(mom12_sp if mom12_sp is not None else 10, -20, 30)
    regime = classify_market_regime(vix_norm, us10y_norm, dxy_norm, inflation_norm, growth_norm)
    macro = macro_score(vix_norm, us10y_norm, dxy_norm, minmax(wti[-1] if wti else 85, 60, 120), inflation_norm, growth_norm)
    tech = technical_score(rsi_sp, minmax(ma_gap_sp if ma_gap_sp is not None else 0, -20, 20), minmax(rel_sp_kospi if rel_sp_kospi is not None else 0, -30, 30), minmax(adx_sp if adx_sp is not None else 20, 0, 60), 50)
    quant = quant_score(minmax(mom3_sp if mom3_sp is not None else 0, -20, 20), minmax(mom12_sp if mom12_sp is not None else 0, -30, 40), minmax(vol_sp if vol_sp is not None else 20, 5, 50), 50, 50)
    total = total_score(regime, macro=macro, technical=tech, quant=quant, fx=50)

    snapshot = {
        'regime': regime,
        'macro_score': macro,
        'technical_score': tech,
        'quant_score': quant,
        'total_score': total,
        'inputs': {
            'rsi_sp500': rsi_sp,
            'ma_gap_sp500': ma_gap_sp,
            'momentum_3m_sp500': mom3_sp,
            'momentum_12m_sp500': mom12_sp,
            'volatility_sp500': vol_sp,
            'relative_strength_sp500_vs_kospi': rel_sp_kospi,
            'adx_sp500': adx_sp,
            'us10y_last': us10y[-1] if us10y else None,
            'usdkrw_last': usdkrw[-1] if usdkrw else None,
            'wti_last': wti[-1] if wti else None,
        }
    }
    OUT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2))

    # reflect into 3개월/6개월 result if exists
    if SITE.exists():
        r = json.loads(SITE.read_text())
        for period in ['3개월', '6개월']:
            if period in r.get('dataByPeriod', {}):
                brief = r['dataByPeriod'][period].setdefault('briefing', {})
                ins = brief.setdefault('insights', [])
                ins.insert(0, {'category':'Quant', 'text': f"{period} 퀀트 요약: Regime={regime}, Macro={macro:.1f}, Technical={tech:.1f}, Quant={quant:.1f}, Total={total:.1f}", 'sources':[{'label':'market_quant_snapshot.json','source':'yfinance+pandas','title':'market quant snapshot','published_at':'2026-03-19'}]})
                brief['forecast']['text'] += f"<br><br>퀀트 결합: Regime={regime}, Macro={macro:.1f}, Technical={tech:.1f}, Quant={quant:.1f}, Total={total:.1f}"
        SITE.write_text(json.dumps(r, ensure_ascii=False, indent=2))
    print('wrote', OUT)

if __name__ == '__main__':
    main()
