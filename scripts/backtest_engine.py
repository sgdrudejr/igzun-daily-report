#!/usr/bin/env python3
"""
기술적 매수/매도 신호 백테스트 엔진.

- 대상: SPY, QQQ
- 기간: 최근 5년 일봉
- 규칙:
  - 종가 기준 timing_score 계산
  - 등급 A/B면 다음 거래일 시가에 전량 매수
  - 등급 D/F면 다음 거래일 시가에 전량 매도
  - 초기 자본금 10,000달러를 두 종목에 동일 비중으로 배분
  - 분할매수/레짐 로직까지 완전 재현하는 것이 아니라,
    현재 technical_timing.py의 등급 체계가 독립적으로 유효한지 검증하는 1차 백테스트

Outputs
- data/backtest_results.json
- BACKTEST_REPORT.md
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from technical_indicators import rsi  # noqa: E402
from technical_timing import timing_score  # noqa: E402

try:
    import pandas as pd
    import yfinance as yf
except ImportError as exc:  # pragma: no cover
    raise SystemExit(f"필수 패키지 누락: {exc}")


TRADEABLE_GRADES = {"A", "B"}
EXIT_GRADES = {"D", "F"}
LOOKBACK_BARS = 220


@dataclass
class Trade:
    symbol: str
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    shares: float
    pnl: float
    return_pct: float
    hold_days: int
    entry_grade: str
    exit_grade: str

    def as_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "entry_date": self.entry_date,
            "exit_date": self.exit_date,
            "entry_price": round(self.entry_price, 4),
            "exit_price": round(self.exit_price, 4),
            "shares": round(self.shares, 6),
            "pnl": round(self.pnl, 2),
            "return_pct": round(self.return_pct, 2),
            "hold_days": self.hold_days,
            "entry_grade": self.entry_grade,
            "exit_grade": self.exit_grade,
        }


def _normalize_download(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    target_fields = {"Open", "High", "Low", "Close", "Adj Close", "Volume"}
    if isinstance(df.columns, pd.MultiIndex):
        new_cols = []
        for col in df.columns:
            parts = [str(part) for part in col]
            field = next((part for part in parts if part in target_fields), parts[0])
            new_cols.append(field)
        df = df.copy()
        df.columns = new_cols

    if "Close" not in df.columns and "Adj Close" in df.columns:
        df = df.rename(columns={"Adj Close": "Close"})

    keep = [col for col in ["Open", "High", "Low", "Close", "Volume"] if col in df.columns]
    df = df[keep].dropna(subset=["Open", "High", "Low", "Close"]).copy()
    df.index = pd.to_datetime(df.index)
    return df.sort_index()


def download_history(symbol: str, years: int) -> pd.DataFrame:
    df = yf.download(
        symbol,
        period=f"{years}y",
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    return _normalize_download(df)


def max_drawdown(equity_curve: list[dict]) -> float:
    peak = None
    worst = 0.0
    for point in equity_curve:
        equity = point["equity"]
        peak = equity if peak is None else max(peak, equity)
        if peak and peak > 0:
            drawdown = equity / peak - 1.0
            worst = min(worst, drawdown)
    return worst * 100


def cagr(initial_capital: float, final_equity: float, days: int) -> float:
    if initial_capital <= 0 or final_equity <= 0 or days <= 0:
        return 0.0
    years = days / 365.25
    if years <= 0:
        return 0.0
    return ((final_equity / initial_capital) ** (1 / years) - 1) * 100


def trade_stats(trades: list[Trade]) -> tuple[float, int, int]:
    if not trades:
        return 0.0, 0, 0
    wins = sum(1 for t in trades if t.pnl > 0)
    return wins / len(trades) * 100, wins, len(trades)


def compute_signal(df_slice: pd.DataFrame) -> dict:
    closes = [float(v) for v in df_slice["Close"].tolist()]
    opens = [float(v) for v in df_slice["Open"].tolist()]
    highs = [float(v) for v in df_slice["High"].tolist()]
    lows = [float(v) for v in df_slice["Low"].tolist()]
    rsi_val = rsi(closes, 14)
    return timing_score(
        closes=closes,
        opens=opens,
        highs=highs,
        lows=lows,
        rsi_val=rsi_val,
    )


def backtest_symbol(symbol: str, df: pd.DataFrame, initial_capital: float) -> dict:
    if df.empty or len(df) <= LOOKBACK_BARS + 2:
        return {
            "symbol": symbol,
            "initial_capital": round(initial_capital, 2),
            "final_equity": round(initial_capital, 2),
            "total_return_pct": 0.0,
            "cagr_pct": 0.0,
            "mdd_pct": 0.0,
            "win_rate_pct": 0.0,
            "wins": 0,
            "total_trades": 0,
            "benchmark_return_pct": 0.0,
            "trades": [],
            "equity_curve": [],
            "note": "백테스트에 필요한 충분한 데이터가 없습니다.",
        }

    cash = float(initial_capital)
    shares = 0.0
    pending_action = None
    pending_grade = None
    entry_price = None
    entry_date = None
    entry_grade = None
    trades: list[Trade] = []
    equity_curve: list[dict] = []

    for i, (ts, row) in enumerate(df.iterrows()):
        day = ts.strftime("%Y-%m-%d")
        open_price = float(row["Open"])
        close_price = float(row["Close"])

        if pending_action == "buy" and shares == 0 and cash > 0:
            shares = cash / open_price
            cash = 0.0
            entry_price = open_price
            entry_date = day
            entry_grade = pending_grade
        elif pending_action == "sell" and shares > 0:
            proceeds = shares * open_price
            pnl = proceeds - (entry_price * shares if entry_price else 0.0)
            return_pct = ((open_price / entry_price) - 1) * 100 if entry_price else 0.0
            trades.append(
                Trade(
                    symbol=symbol,
                    entry_date=entry_date or day,
                    exit_date=day,
                    entry_price=entry_price or open_price,
                    exit_price=open_price,
                    shares=shares,
                    pnl=pnl,
                    return_pct=return_pct,
                    hold_days=max((ts - pd.Timestamp(entry_date)).days, 1) if entry_date else 0,
                    entry_grade=entry_grade or "-",
                    exit_grade=pending_grade or "-",
                )
            )
            cash = proceeds
            shares = 0.0
            entry_price = None
            entry_date = None
            entry_grade = None

        pending_action = None
        pending_grade = None

        equity = cash + shares * close_price
        equity_curve.append({"date": day, "equity": round(equity, 4)})

        if i < LOOKBACK_BARS or i >= len(df) - 1:
            continue

        signal = compute_signal(df.iloc[: i + 1])
        grade = signal.get("grade")

        if shares == 0 and grade in TRADEABLE_GRADES:
            pending_action = "buy"
            pending_grade = grade
        elif shares > 0 and grade in EXIT_GRADES:
            pending_action = "sell"
            pending_grade = grade

    if shares > 0 and entry_price is not None:
        last_day = df.index[-1].strftime("%Y-%m-%d")
        last_close = float(df["Close"].iloc[-1])
        proceeds = shares * last_close
        pnl = proceeds - (entry_price * shares)
        return_pct = ((last_close / entry_price) - 1) * 100
        trades.append(
            Trade(
                symbol=symbol,
                entry_date=entry_date or last_day,
                exit_date=last_day,
                entry_price=entry_price,
                exit_price=last_close,
                shares=shares,
                pnl=pnl,
                return_pct=return_pct,
                hold_days=max((df.index[-1] - pd.Timestamp(entry_date)).days, 1) if entry_date else 0,
                entry_grade=entry_grade or "-",
                exit_grade="EOD",
            )
        )
        cash = proceeds
        shares = 0.0
        equity_curve[-1]["equity"] = round(cash, 4)

    final_equity = float(equity_curve[-1]["equity"]) if equity_curve else initial_capital
    benchmark_return = (float(df["Close"].iloc[-1]) / float(df["Close"].iloc[LOOKBACK_BARS]) - 1) * 100
    win_rate, wins, total_trades = trade_stats(trades)
    total_days = max((df.index[-1] - df.index[LOOKBACK_BARS]).days, 1)

    return {
        "symbol": symbol,
        "initial_capital": round(initial_capital, 2),
        "final_equity": round(final_equity, 2),
        "total_return_pct": round((final_equity / initial_capital - 1) * 100, 2),
        "cagr_pct": round(cagr(initial_capital, final_equity, total_days), 2),
        "mdd_pct": round(max_drawdown(equity_curve), 2),
        "win_rate_pct": round(win_rate, 2),
        "wins": wins,
        "total_trades": total_trades,
        "benchmark_return_pct": round(benchmark_return, 2),
        "trades": [trade.as_dict() for trade in trades],
        "equity_curve": equity_curve,
    }


def build_portfolio_summary(per_symbol: dict[str, dict], initial_capital: float) -> dict:
    dates = sorted(
        {point["date"] for result in per_symbol.values() for point in result.get("equity_curve", [])}
    )
    equity_map: dict[str, float] = {}
    combined_curve = []
    for day in dates:
        total = 0.0
        for symbol, result in per_symbol.items():
            for point in result.get("equity_curve", []):
                if point["date"] == day:
                    equity_map[symbol] = point["equity"]
            total += equity_map.get(symbol, result.get("initial_capital", 0.0))
        combined_curve.append({"date": day, "equity": round(total, 4)})

    final_equity = combined_curve[-1]["equity"] if combined_curve else initial_capital
    all_trades = [
        trade
        for result in per_symbol.values()
        for trade in result.get("trades", [])
    ]
    win_rate = 0.0
    wins = 0
    if all_trades:
        wins = sum(1 for trade in all_trades if trade["pnl"] > 0)
        win_rate = wins / len(all_trades) * 100

    if combined_curve:
        start_dt = pd.Timestamp(combined_curve[0]["date"])
        end_dt = pd.Timestamp(combined_curve[-1]["date"])
        total_days = max((end_dt - start_dt).days, 1)
    else:
        total_days = 1

    return {
        "initial_capital": round(initial_capital, 2),
        "final_equity": round(final_equity, 2),
        "total_return_pct": round((final_equity / initial_capital - 1) * 100, 2),
        "cagr_pct": round(cagr(initial_capital, final_equity, total_days), 2),
        "mdd_pct": round(max_drawdown(combined_curve), 2),
        "win_rate_pct": round(win_rate, 2),
        "wins": wins,
        "total_trades": len(all_trades),
        "equity_curve": combined_curve,
    }


def write_report(root: Path, results: dict) -> None:
    lines = [
        "# BACKTEST_REPORT",
        "",
        "## 개요",
        "- 대상: SPY, QQQ",
        "- 기간: 최근 5년 일봉",
        "- 규칙: A/B 등급이면 다음 날 시가 매수, D/F 등급이면 다음 날 시가 매도",
        "- 초기 자본금: $10,000 (SPY/QQQ 동일 비중 분배)",
        "- 체결 방식: 수수료/슬리피지 미반영, 소수점 단위 매수 허용",
        "",
        "## 포트폴리오 결과",
        f"- 최종 자산: ${results['portfolio']['final_equity']:,.2f}",
        f"- 총수익률: {results['portfolio']['total_return_pct']:.2f}%",
        f"- CAGR: {results['portfolio']['cagr_pct']:.2f}%",
        f"- MDD: {results['portfolio']['mdd_pct']:.2f}%",
        f"- 승률: {results['portfolio']['win_rate_pct']:.2f}% ({results['portfolio']['wins']}/{results['portfolio']['total_trades']})",
        "",
        "## 종목별 결과",
    ]

    for symbol, result in results["per_symbol"].items():
        lines.extend(
            [
                f"### {symbol}",
                f"- 최종 자산: ${result['final_equity']:,.2f}",
                f"- 총수익률: {result['total_return_pct']:.2f}%",
                f"- CAGR: {result['cagr_pct']:.2f}%",
                f"- MDD: {result['mdd_pct']:.2f}%",
                f"- 승률: {result['win_rate_pct']:.2f}% ({result['wins']}/{result['total_trades']})",
                f"- Buy & Hold 비교: {result['benchmark_return_pct']:.2f}%",
                "",
            ]
        )

    lines.extend(
        [
            "## 해석",
            "- 이 백테스트는 현재 기술적 등급 체계가 과거 5년의 추세/과매도 구간에서 어느 정도 방어력과 수익성을 가졌는지 보는 1차 검증입니다.",
            "- 레짐, 밸류에이션, 계좌 제약, 분할매수 스케줄까지 완전 반영한 정식 포트폴리오 백테스트는 추가 단계가 필요합니다.",
            "- 다음 개선 후보는 수수료/슬리피지 반영, 다중 포지션 허용, 분할 진입 규칙 반영입니다.",
            "",
            f"_generated_at: {datetime.now(timezone.utc).isoformat()}_",
        ]
    )

    (root / "BACKTEST_REPORT.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-dir", default=str(ROOT))
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--symbols", default="SPY,QQQ")
    parser.add_argument("--initial-capital", type=float, default=10000)
    args = parser.parse_args()

    root = Path(args.base_dir)
    symbols = [item.strip().upper() for item in args.symbols.split(",") if item.strip()]
    per_symbol_capital = args.initial_capital / max(len(symbols), 1)

    histories: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        histories[symbol] = download_history(symbol, args.years)
        if histories[symbol].empty:
            raise RuntimeError(f"{symbol} 데이터 다운로드 실패")

    per_symbol = {}
    for symbol in symbols:
        per_symbol[symbol] = backtest_symbol(symbol, histories[symbol], per_symbol_capital)

    results = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "strategy": {
            "entry_rule": "timing_score grade A/B -> next open buy",
            "exit_rule": "timing_score grade D/F -> next open sell",
            "execution": "next_open",
            "lookback_bars": LOOKBACK_BARS,
        },
        "config": {
            "symbols": symbols,
            "years": args.years,
            "initial_capital": args.initial_capital,
            "per_symbol_capital": round(per_symbol_capital, 2),
        },
        "per_symbol": per_symbol,
        "portfolio": build_portfolio_summary(per_symbol, args.initial_capital),
    }

    out_dir = root / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "backtest_results.json"
    out_file.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    write_report(root, results)

    print(f"wrote {out_file}")
    print(f"wrote {root / 'BACKTEST_REPORT.md'}")
    print()
    print(json.dumps(results["portfolio"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
