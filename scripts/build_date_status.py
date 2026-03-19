#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path('/Users/seo/.openclaw/workspace/igzun-daily-report')
INV = ROOT / 'data/raw_inventory_2026-02-19_to_2026-03-19.json'
SITE = ROOT / 'site'
OUT = ROOT / 'site/date_status.json'


def main():
    inv = json.loads(INV.read_text()) if INV.exists() else []
    out = {}
    for row in inv:
        ds = row['date']
        count = row['count']
        result_path = SITE / ds / 'result.json'
        status = 'empty'
        if result_path.exists():
            try:
                obj = json.loads(result_path.read_text())
                status = obj.get('dataStatus', 'sparse')
            except Exception:
                status = 'sparse' if count > 0 else 'empty'
        else:
            if count >= 8: status = 'full'
            elif count >= 3: status = 'partial'
            elif count >= 1: status = 'sparse'
        out[ds] = {'count': count, 'status': status}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print('wrote', OUT)

if __name__ == '__main__':
    main()
