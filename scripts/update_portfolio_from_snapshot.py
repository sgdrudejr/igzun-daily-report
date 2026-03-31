#!/usr/bin/env python3
"""Update portfolio data from account snapshot.

Writes to three places so the live report always reflects real account data:
  1. data/portfolio_state.json  — source-of-truth fed into the daily build pipeline
  2. site/horizons/daily/<date>.json — immediate live update of the portfolio section
  3. site/<date>/result.json   — legacy format kept for backward compat
"""
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from shared_state import update_dashboard_status  # noqa: E402

INBOX = ROOT / "data/account_snapshot_inbox"
SITE = ROOT / "site"
PORTFOLIO_STATE = ROOT / "data" / "portfolio_state.json"

REGIME_ALLOC = {
    "Growth": {"주식": 0.65, "채권": 0.15, "원자재": 0.05, "현금": 0.15},
    "Stagflation/Recession": {"주식": 0.15, "채권": 0.25, "원자재": 0.35, "현금": 0.25},
    "Inflationary": {"주식": 0.30, "채권": 0.10, "원자재": 0.40, "현금": 0.20},
    "Risk-Off DollarStrength": {"주식": 0.20, "채권": 0.30, "원자재": 0.20, "현금": 0.30},
    "Neutral": {"주식": 0.45, "채권": 0.20, "원자재": 0.10, "현금": 0.25},
}

ACCOUNT_KEY_MAP = {
    "TOSS": ["토스증권", "toss"],
    "ISA": ["isa", "신한 isa", "신한은행 isa"],
    "PENSION": ["연금저축", "pension", "신한은행 연금"],
}


def latest_snapshot():
    snaps = sorted(INBOX.glob("*_snapshot.json"))
    return snaps[-1] if snaps else None


def money(val):
    try:
        return f"{int(float(val)):,}원"
    except (TypeError, ValueError):
        return "0원"


def detect_account_key(broker: str) -> str | None:
    bl = (broker or "").lower()
    for key, tokens in ACCOUNT_KEY_MAP.items():
        if any(t in bl for t in tokens):
            return key
    return None


def infer_asset_class(ticker: str, name: str) -> str:
    text = f"{ticker} {name}".lower()
    if any(t in text for t in ["bond", "채", "국채", "회사채", "treasury", "tlt", "ief", "shy", "bnd"]):
        return "채권"
    if any(t in text for t in ["gold", "oil", "원자재", "commodity", "energy", "metal", "gld", "uso", "dba"]):
        return "원자재"
    if any(t in text for t in ["cash", "현금", "mmf"]):
        return "현금"
    return "주식"


def calc_portfolio_score(regime: str, positions: list, cash_amount: float) -> dict:
    alloc_target = REGIME_ALLOC.get(regime, REGIME_ALLOC["Neutral"])
    amounts = {"주식": 0.0, "채권": 0.0, "원자재": 0.0, "현금": float(cash_amount)}
    for pos in positions:
        ac = infer_asset_class(pos.get("ticker", ""), pos.get("name", ""))
        amounts[ac] += float(pos.get("market_value", 0) or 0)
    total = sum(amounts.values()) or 1.0

    current_pct = {a: round(amounts[a] / total * 100, 1) for a in ["주식", "채권", "원자재", "현금"]}
    target_pct = {a: round(alloc_target[a] * 100, 1) for a in ["주식", "채권", "원자재", "현금"]}
    gaps = {a: round(abs(current_pct[a] - target_pct[a]), 1) for a in current_pct}

    allocation_fit = round(max(0.0, 100.0 - sum(gaps.values()) / 2.0))

    active_non_cash = sum(1 for a in ["주식", "채권", "원자재"] if current_pct[a] >= 5)
    diversification_score = {0: 25, 1: 45, 2: 72}.get(active_non_cash, 90)
    if current_pct["현금"] >= 70:
        diversification_score = min(diversification_score, 40)

    target_cash = target_pct["현금"]
    cash_pct = current_pct["현금"]
    if cash_pct > target_cash + 40:
        cash_mgmt = 55
    elif cash_pct > target_cash + 20:
        cash_mgmt = 68
    elif cash_pct >= max(target_cash - 10, 0):
        cash_mgmt = 86
    else:
        cash_mgmt = 72

    final_score = round(allocation_fit * 0.55 + diversification_score * 0.25 + cash_mgmt * 0.20)
    grade = next(
        (g for t, g in [(80, "우수"), (65, "양호"), (50, "보통"), (35, "미흡")] if final_score >= t),
        "개선 필요",
    )

    if current_pct["현금"] >= 90:
        summary = "현금 비중이 과도하게 높아 레짐 대비 배분 점수는 낮지만, 대기 자금은 충분합니다."
    elif allocation_fit >= 75:
        summary = "현재 포트폴리오는 현 레짐의 권장 자산배분과 비교적 잘 맞습니다."
    else:
        summary = "현재 포트폴리오는 현 레짐 대비 자산군 편차가 커서 단계적 재배분 여지가 있습니다."

    return {
        "score": final_score,
        "grade": grade,
        "summary": summary,
        "currentPct": current_pct,
        "targetPct": target_pct,
        "gaps": gaps,
        "breakdown": {
            "regimeFit": allocation_fit,
            "diversification": diversification_score,
            "cashManagement": cash_mgmt,
        },
        "reasons": [
            f"레짐 적합도 {allocation_fit}점 — 목표 배분 대비 편차를 반영",
            f"분산도 {diversification_score}점 — 실제 보유 자산군 수와 집중도를 반영",
            f"현금 운용 {cash_mgmt}점 — 목표 현금 비중 대비 과소·과다 여부를 반영",
        ],
    }


def update_portfolio_state(snap: dict, account_key: str | None = None):
    """Update data/portfolio_state.json with real snapshot data."""
    if not PORTFOLIO_STATE.exists():
        print("portfolio_state.json not found, skipping")
        return

    ps = json.loads(PORTFOLIO_STATE.read_text())
    cash = float(snap.get("cash", 0) or 0)
    total_equity = float(snap.get("total_equity", 0) or 0)
    positions = snap.get("positions", [])
    day_str = snap.get("account_date") or date.today().isoformat()

    holdings = [
        {
            "ticker": pos.get("ticker", ""),
            "name": pos.get("name", ""),
            "market_value": float(pos.get("market_value", 0) or 0),
            "quantity": float(pos.get("quantity", 0) or 0),
            "avg_price": float(pos.get("avg_price", 0) or 0),
            "current_price": float(pos.get("current_price", 0) or 0),
            "pnl_pct": float(pos.get("pnl_pct", 0) or 0),
            "pnl_amount": float(pos.get("pnl_amount", 0) or 0),
            "allocation": float(pos.get("allocation", 0) or 0),
        }
        for pos in positions
    ]

    accounts = ps.setdefault("accounts", {})
    if account_key and account_key in accounts:
        accounts[account_key]["cash"] = cash
        accounts[account_key]["holdings"] = holdings
        print(f"updated portfolio_state account: {account_key}")
    else:
        # No account match — update totals without per-account breakdown
        # Store in a generic SNAPSHOT slot so total_cash recalc works
        accounts.setdefault("SNAPSHOT", {"label": "스냅샷 (계좌 미분류)", "cash": 0, "holdings": [], "note": ""})
        accounts["SNAPSHOT"]["cash"] = cash
        accounts["SNAPSHOT"]["holdings"] = holdings
        print("updated portfolio_state SNAPSHOT account (no broker match)")

    # Recalculate totals from all accounts
    total_cash = sum(int(acc.get("cash", 0)) for acc in accounts.values())
    total_invested = sum(
        sum(float(h.get("market_value", 0) or 0) for h in acc.get("holdings", []))
        for acc in accounts.values()
    )
    ps["total_cash"] = total_cash
    ps["total_invested"] = total_invested
    ps["updated"] = day_str

    PORTFOLIO_STATE.write_text(json.dumps(ps, ensure_ascii=False, indent=2))
    print(f"updated portfolio_state total_cash={total_cash:,}")


def update_horizon_view(day_str: str, snap: dict):
    """Directly update the horizon daily JSON's portfolio section with real data."""
    horizon_path = SITE / "horizons" / "daily" / f"{day_str}.json"
    if not horizon_path.exists():
        print(f"no horizon file for {day_str}, skipping")
        return

    obj = json.loads(horizon_path.read_text())
    portfolio = obj.get("portfolio")
    if not portfolio:
        print("no portfolio section in horizon view, skipping")
        return

    total_deposit = float(snap.get("total_deposit", 0) or 0)
    cash = float(snap.get("cash", 0) or 0)
    total_equity = float(snap.get("total_equity", 0) or 0)
    positions = snap.get("positions", [])
    broker = snap.get("broker", "")
    account_date = snap.get("account_date", day_str)
    regime = obj.get("regime", "Neutral")

    # Update account alert with real numbers
    portfolio["accountAlert"] = (
        f"총 예수금 {total_deposit:,.0f}원 / 현금 {cash:,.0f}원 / 투자금 {total_equity:,.0f}원"
        f" · 실계좌 스냅샷 기준 ({account_date})."
    )

    # Update keyStats — replace 총 투자 대기 현금 with real value
    for stat in portfolio.get("keyStats", []):
        lbl = stat.get("label", "")
        if "현금" in lbl or "예수금" in lbl:
            stat["value"] = money(cash)
            stat["sub"] = f"실계좌 스냅샷 기준 ({account_date})"

    # Recalculate portfolio score with real positions
    new_score = calc_portfolio_score(regime, positions, cash)
    portfolio["portfolioScore"] = new_score

    # Update scoreChips
    bd = new_score.get("breakdown", {})
    portfolio["scoreChips"] = [
        {"label": "총점", "value": f"{new_score['score']}점", "tone": "score"},
        {"label": "레짐 적합도", "value": f"{bd.get('regimeFit', 0)}점", "tone": "score"},
        {"label": "분산도", "value": f"{bd.get('diversification', 0)}점", "tone": "score"},
        {"label": "현금 운용", "value": f"{bd.get('cashManagement', 0)}점", "tone": "score"},
    ]

    # Update capitalPlan totalCash with real cash
    capital_plan = portfolio.get("capitalPlan", {})
    if capital_plan:
        capital_plan["totalCash"] = money(cash)
        portfolio["capitalPlan"] = capital_plan

    # Update currentAmount in targetAmounts/todayTargetAmounts
    alloc_target = REGIME_ALLOC.get(regime, REGIME_ALLOC["Neutral"])
    current_amounts = {"주식": 0.0, "채권": 0.0, "원자재": 0.0, "현금": float(cash)}
    for pos in positions:
        ac = infer_asset_class(pos.get("ticker", ""), pos.get("name", ""))
        current_amounts[ac] += float(pos.get("market_value", 0) or 0)
    total_assets = sum(current_amounts.values()) or float(cash)

    for items_key in ["targetAmounts", "todayTargetAmounts"]:
        for item in portfolio.get(items_key, []):
            asset = item.get("name")
            if asset not in current_amounts:
                continue
            current_amt = current_amounts[asset]
            target_amt_str = item.get("targetAmount", "0원")
            # Parse existing target amount to compute gap
            try:
                target_amt = float(target_amt_str.replace(",", "").replace("원", "").strip())
            except (ValueError, AttributeError):
                target_amt = total_assets * alloc_target.get(asset, 0)
            gap = target_amt - current_amt
            item["currentAmount"] = money(current_amt)
            item["gapAmount"] = money(abs(gap))
            item["direction"] = "늘리기" if gap > 0 else ("줄이기" if gap < 0 else "유지")

    portfolio["planDesc"] = "실계좌 스냅샷 기준 자동 반영된 포트폴리오 비중입니다."
    obj["portfolio"] = portfolio
    horizon_path.write_text(json.dumps(obj, ensure_ascii=False, indent=2))
    print(f"updated horizon view {horizon_path}")


# ---------------------------------------------------------------------------
# Legacy: keep result.json (dataByPeriod format) updated for backward compat
# ---------------------------------------------------------------------------

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


def update_result(path: Path, snap: dict):
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

    # Detect account from broker field
    account_key = detect_account_key(snap.get("broker", ""))

    # 1. Update portfolio_state.json (feeds into next daily build)
    update_portfolio_state(snap, account_key)

    # 2. Update horizon daily JSON (immediate live update)
    update_horizon_view(day_str, snap)

    # 3. Update legacy result.json
    result_path = SITE / day_str / "result.json"
    if result_path.exists():
        update_result(result_path, snap)
        update_dashboard_status(result_path, source="main_session")
        print("updated result.json", result_path)
    else:
        print("missing result.json", result_path)


if __name__ == "__main__":
    main()
