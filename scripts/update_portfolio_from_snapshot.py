#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import date

ROOT = Path('/Users/seo/.openclaw/workspace/igzun-daily-report')
INBOX = ROOT / 'data/account_snapshot_inbox'
SITE = ROOT / 'site'


def latest_snapshot():
    snaps = sorted(INBOX.glob('*_snapshot.json'))
    return snaps[-1] if snaps else None


def signal_from_pnl(pct):
    if pct <= -15: return -70
    if pct <= -5: return -30
    if pct < 5: return 10
    if pct < 15: return 40
    return 70


def update_result(path, snap):
    obj = json.loads(path.read_text())
    for period_name, period in obj.get('dataByPeriod', {}).items():
        p = period.setdefault('portfolio', {})
        total_deposit = snap.get('total_deposit', 0)
        cash = snap.get('cash', 0)
        total_equity = snap.get('total_equity', 0)
        p['accountAlert'] = f"총 예수금 {total_deposit:,.0f}원 / 현금 {cash:,.0f}원 / 투자금 {total_equity:,.0f}원"
        p['accountDetail'] = f"증권사: {snap.get('broker','미상')} · 기준일: {snap.get('account_date','')}"
        p['weeklyReview'] = p.get('weeklyReview', {'returnRate': '미연결', 'desc': ''})
        p['holdings'] = []
        allocations = []
        for pos in snap.get('positions', []):
            p['holdings'].append({
                'name': pos.get('name',''),
                'ticker': pos.get('ticker',''),
                'returnRate': f"{pos.get('pnl_pct',0):+.1f}%",
                'score': signal_from_pnl(float(pos.get('pnl_pct',0) or 0)),
                'indicators': [f"수량 {pos.get('quantity',0)}", f"평단 {pos.get('avg_price',0)}", f"현재가 {pos.get('current_price',0)}"],
                'reason': f"평가손익 {pos.get('pnl_amount',0):,.0f} / 비중 {pos.get('allocation',0)}% 기반 자동 생성"
            })
            allocations.append({
                'name': pos.get('name',''),
                'percent': float(pos.get('allocation',0) or 0),
                'color': '#3182F6',
                'desc': f"{pos.get('ticker','')} / 평가금액 {pos.get('market_value',0):,.0f}"
            })
        cash_alloc = max(0.0, round(100.0 - sum(a['percent'] for a in allocations), 2))
        if cash_alloc > 0:
            allocations.append({'name':'현금', 'percent':cash_alloc, 'color':'#E5E8EB', 'desc':f"현금 {cash:,.0f}원"})
        p['allocations'] = allocations
        p['planDesc'] = '실계좌 스냅샷 기준 자동 반영된 포트폴리오 비중입니다.'
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2))


def main():
    snap_path = latest_snapshot()
    if not snap_path:
        print('no snapshot found')
        return
    snap = json.loads(snap_path.read_text())
    ds = snap.get('account_date') or date.today().isoformat()
    result_path = SITE / ds / 'result.json'
    if result_path.exists():
        update_result(result_path, snap)
        print('updated', result_path)
    else:
        print('missing result', result_path)

if __name__ == '__main__':
    main()
