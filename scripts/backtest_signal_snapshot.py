#!/usr/bin/env python3
"""
Signal snapshot backtest.

Evaluates a single report date by checking how the generated ETF signals
performed on the next available trading session.

Output: data/backtests/{date}_signal_snapshot.json
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

try:
    import yfinance as yf

    HAS_YF = True
except ImportError:
    HAS_YF = False


POSITIVE_SIGNALS = {"강력매수", "분할매수", "소규모탐색"}
NEGATIVE_SIGNALS = {"비중축소", "회피"}


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_signal_candidates(root: Path, date_str: str) -> list[dict]:
    signal_file = root / "data" / "signals" / f"{date_str}.json"
    payload = load_json(signal_file)
    return payload.get("signals", [])


def fetch_history(ticker: str, start: date, end: date) -> list[dict]:
    if not HAS_YF:
        return []

    try:
        df = yf.download(
            ticker,
            start=start.isoformat(),
            end=(end + timedelta(days=1)).isoformat(),
            progress=False,
            auto_adjust=True,
        )
        if df is None or df.empty:
            return []

        close_col = next((col for col in df.columns if "close" in str(col).lower()), None)
        if close_col is None:
            return []

        rows = []
        for idx, value in df[close_col].dropna().items():
            rows.append({
                "date": idx.strftime("%Y-%m-%d"),
                "close": float(value),
            })
        return rows
    except Exception:
        return []


def load_local_price_history(root: Path, ticker: str, as_of: str) -> list[dict]:
    history_dir = root / "data" / "etf_price_history"
    if not history_dir.exists():
        return []

    candidates = []
    for path in history_dir.glob("*.json"):
        try:
            payload = json.loads(path.read_text())
        except Exception:
            continue
        rows = payload.get("prices", {}).get(ticker, [])
        if rows:
            last_date = rows[-1]["date"]
            candidates.append((last_date, len(rows), rows))

    if not candidates:
        return []

    # Prefer the most up-to-date local history, then longest length.
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return candidates[0][2]


def first_on_or_after(rows: list[dict], threshold: str) -> dict | None:
    for row in rows:
        if row["date"] >= threshold:
            return row
    return None


def next_after(rows: list[dict], threshold: str) -> dict | None:
    for row in rows:
        if row["date"] > threshold:
            return row
    return None


def prev_before(rows: list[dict], threshold: str) -> dict | None:
    previous = None
    for row in rows:
        if row["date"] < threshold:
            previous = row
        else:
            break
    return previous


def verdict_for_signal(signal: str, return_pct: float | None) -> str:
    if return_pct is None:
        return "데이터부족"
    if signal in POSITIVE_SIGNALS:
        if return_pct > 0:
            return "성공"
        if return_pct == 0:
            return "보합"
        return "실패"
    if signal in NEGATIVE_SIGNALS:
        if return_pct < 0:
            return "성공"
        if return_pct == 0:
            return "보합"
        return "실패"
    return "참고"


def run_backtest(root: Path, date_str: str) -> dict:
    signal_file = root / "data" / "signals" / f"{date_str}.json"
    signals_payload = load_json(signal_file)
    candidates = load_signal_candidates(root, date_str)
    as_of = parse_date(date_str)

    focus = [
        item for item in candidates
        if item.get("signal") in POSITIVE_SIGNALS | NEGATIVE_SIGNALS
    ]

    results = []
    weighted_numerator = 0.0
    weighted_denominator = 0.0
    success_count = 0
    evaluated_count = 0

    for item in focus:
        ticker = item.get("ticker")
        if not ticker:
            continue

        history = load_local_price_history(root, ticker, date_str)
        if not history:
            history = fetch_history(ticker, as_of - timedelta(days=7), as_of + timedelta(days=10))
        if not history:
            continue

        report_session = first_on_or_after(history, date_str)
        if report_session is None:
            report_session = history[-1]

        baseline = prev_before(history, report_session["date"])
        exit_row = next_after(history, report_session["date"])
        backtest_mode = "next_session" if exit_row is not None else "report_session"

        if exit_row is not None:
            entry = report_session
        elif baseline is not None:
            entry = baseline
            exit_row = report_session
        else:
            entry = report_session

        return_pct = None
        if exit_row is not None:
            return_pct = ((exit_row["close"] / entry["close"]) - 1.0) * 100.0

        first_amount = (item.get("position_sizing") or {}).get("first_amount") or 0
        weight = float(first_amount) if first_amount else 1.0
        verdict = verdict_for_signal(item.get("signal", ""), return_pct)

        if return_pct is not None:
            weighted_numerator += return_pct * weight
            weighted_denominator += weight
            evaluated_count += 1
            if verdict == "성공":
                success_count += 1

        results.append({
            "id": item.get("id"),
            "ticker": ticker,
            "name": item.get("name"),
            "signal": item.get("signal"),
            "backtest_mode": backtest_mode,
            "entry_date": entry["date"],
            "entry_close": round(entry["close"], 4),
            "exit_date": exit_row["date"] if exit_row else None,
            "exit_close": round(exit_row["close"], 4) if exit_row else None,
            "return_pct": round(return_pct, 2) if return_pct is not None else None,
            "verdict": verdict,
            "first_amount": first_amount,
            "timing_grade": item.get("timing_grade"),
            "reasons": item.get("reasons", [])[:3],
        })

    weighted_return = round(weighted_numerator / weighted_denominator, 2) if weighted_denominator else None
    success_rate = round(success_count / evaluated_count * 100.0, 1) if evaluated_count else None

    return {
        "date": date_str,
        "backtest_type": "signal_snapshot_next_session",
        "source_signal_file": str(signal_file.relative_to(root)),
        "market_signal": signals_payload.get("market_signal", {}),
        "evaluated_count": evaluated_count,
        "success_count": success_count,
        "success_rate_pct": success_rate,
        "weighted_return_pct": weighted_return,
        "results": results,
        "summary": {
            "positive_signals": sum(1 for item in results if item["signal"] in POSITIVE_SIGNALS),
            "negative_signals": sum(1 for item in results if item["signal"] in NEGATIVE_SIGNALS),
            "note": "기본은 다음 거래 세션 비교이며, 다음 세션이 아직 없으면 직전 종가 대비 리포트일 세션 종가로 대체한 1회 백테스트",
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="Report date (YYYY-MM-DD)")
    parser.add_argument("--base-dir", default=str(ROOT))
    args = parser.parse_args()

    root = Path(args.base_dir)
    result = run_backtest(root, args.date)

    out_dir = root / "data" / "backtests"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{args.date}_signal_snapshot.json"
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2))

    print(f"wrote {out_file}")
    print(
        f"[backtest] evaluated={result['evaluated_count']} "
        f"success_rate={result['success_rate_pct']}% "
        f"weighted_return={result['weighted_return_pct']}%"
    )


if __name__ == "__main__":
    main()
