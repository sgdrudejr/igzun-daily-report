#!/usr/bin/env python3
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from shared_state import update_dashboard_status  # noqa: E402

INBOX = ROOT / "data/account_snapshot_inbox"
SITE = ROOT / "site"


def latest_snapshot():
    snaps = sorted(INBOX.glob("*_snapshot.json"))
    return snaps[-1] if snaps else None


def signal_from_pnl(pct):
    if pct <= -15:
        return -70
    if pct <= -5:
        return -30
    if pct < 5:
        return 10
    if pct < 15:
        return 40
    return 70


def update_result(path, snap):
    obj = json.loads(path.read_text())
    for period in obj.get("dataByPeriod", {}).values():
        portfolio = period.setdefault("portfolio", {})
        total_deposit = float(snap.get("total_deposit", 0) or 0)
        cash = float(snap.get("cash", 0) or 0)
        total_equity = float(snap.get("total_equity", 0) or 0)
        portfolio["accountAlert"] = f"총 예수금 {total_deposit:,.0f}원 / 현금 {cash:,.0f}원 / 투자금 {total_equity:,.0f}원"
        portfolio["accountDetail"] = f"증권사: {snap.get('broker', '미상')} · 기준일: {snap.get('account_date', '')}"
        portfolio["weeklyReview"] = portfolio.get("weeklyReview", {"returnRate": "미연결", "desc": ""})
        portfolio["holdings"] = []
        allocations = []
        for pos in snap.get("positions", []):
            pnl_pct = float(pos.get("pnl_pct", 0) or 0)
            portfolio["holdings"].append(
                {
                    "name": pos.get("name", ""),
                    "ticker": pos.get("ticker", ""),
                    "returnRate": f"{pnl_pct:+.1f}%",
                    "score": signal_from_pnl(pnl_pct),
                    "indicators": [
                        f"수량 {pos.get('quantity', 0)}",
                        f"평단 {pos.get('avg_price', 0)}",
                        f"현재가 {pos.get('current_price', 0)}",
                    ],
                    "reason": f"평가손익 {float(pos.get('pnl_amount', 0) or 0):,.0f} / 비중 {float(pos.get('allocation', 0) or 0):.1f}% 기반 자동 생성",
                }
            )
            allocations.append(
                {
                    "name": pos.get("name", ""),
                    "percent": float(pos.get("allocation", 0) or 0),
                    "color": "#3182F6",
                    "desc": f"{pos.get('ticker', '')} / 평가금액 {float(pos.get('market_value', 0) or 0):,.0f}",
                }
            )
        cash_alloc = max(0.0, round(100.0 - sum(item["percent"] for item in allocations), 2))
        if cash_alloc > 0:
            allocations.append({"name": "현금", "percent": cash_alloc, "color": "#E5E8EB", "desc": f"현금 {cash:,.0f}원"})
        portfolio["allocations"] = allocations
        portfolio["planDesc"] = "실계좌 스냅샷 기준 자동 반영된 포트폴리오 비중입니다."
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2))


def main():
    snap_path = latest_snapshot()
    if not snap_path:
        print("no snapshot found")
        return
    snap = json.loads(snap_path.read_text())
    day_str = snap.get("account_date") or date.today().isoformat()
    result_path = SITE / day_str / "result.json"
    if result_path.exists():
        update_result(result_path, snap)
        update_dashboard_status(result_path, source="main_session")
        print("updated", result_path)
    else:
        print("missing result", result_path)


if __name__ == "__main__":
    main()
