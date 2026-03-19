#!/usr/bin/env python3
import json, re, sys
from pathlib import Path
from datetime import date

ROOT = Path('/Users/seo/.openclaw/workspace/igzun-daily-report')
INBOX = ROOT / 'data/account_snapshot_inbox'
OUT = INBOX / f"{date.today().isoformat()}_snapshot.json"
LATEST = ROOT / 'data/account_snapshot_latest.json'


def parse_money(s):
    s = s.replace(',', '').replace('원','').strip()
    m = re.search(r'-?\d+(?:\.\d+)?', s)
    return float(m.group(0)) if m else 0.0


def parse_text(txt):
    lines = [l.strip() for l in txt.splitlines() if l.strip()]
    result = {
        'account_date': date.today().isoformat(),
        'broker': 'admin_bot_ocr',
        'currency': 'KRW',
        'total_deposit': 0,
        'cash': 0,
        'total_equity': 0,
        'positions': []
    }
    for line in lines:
        if '총 예수금' in line:
            result['total_deposit'] = parse_money(line)
        elif '예수금' in line and result['cash'] == 0:
            result['cash'] = parse_money(line)
        elif '평가금액' in line or '총자산' in line or '총 평가금액' in line:
            result['total_equity'] = max(result['total_equity'], parse_money(line))
    # very simple holding parser: TICKER NAME qty avg current alloc
    for line in lines:
        m = re.search(r'([A-Z]{1,5})\s+([^\d]+?)\s+(\d+(?:\.\d+)?)\s+([\d,]+(?:\.\d+)?)\s+([\d,]+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)%', line)
        if m:
            ticker, name, qty, avgp, curp, alloc = m.groups()
            qty = float(qty); avgp = parse_money(avgp); curp = parse_money(curp); alloc = float(alloc)
            mv = qty * curp
            pnl = (curp - avgp) * qty
            pnl_pct = ((curp/avgp)-1)*100 if avgp else 0
            result['positions'].append({
                'ticker': ticker,
                'name': name.strip(),
                'quantity': qty,
                'avg_price': avgp,
                'current_price': curp,
                'market_value': mv,
                'pnl_amount': pnl,
                'pnl_pct': pnl_pct,
                'allocation': alloc,
                'currency': 'KRW'
            })
    return result


def main():
    if len(sys.argv) < 2:
        print('usage: parse_account_snapshot_text.py <ocr-text-file>')
        sys.exit(1)
    src = Path(sys.argv[1])
    txt = src.read_text(errors='ignore')
    result = parse_text(txt)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print('wrote', OUT)

if __name__ == '__main__':
    main()
n()
'updated latest', LATEST)

if __name__ == '__main__':
    main()
