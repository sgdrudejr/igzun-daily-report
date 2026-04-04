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
    ann_vol = annualized_volatility(equity_curve)
    freq = execution_frequency(trades, total_days)
    total_cost, cost_bps = apply_transaction_costs(trades)

    return {
        "symbol": symbol,
        "initial_capital": round(initial_capital, 2),
        "final_equity": round(final_equity, 2),
        "total_return_pct": round((final_equity / initial_capital - 1) * 100, 2),
        "cagr_pct": round(cagr(initial_capital, final_equity, total_days), 2),
        "mdd_pct": round(max_drawdown(equity_curve), 2),
        "annualized_vol_pct": round(ann_vol, 2),
        "sharpe_approx": round((cagr(initial_capital, final_equity, total_days) / ann_vol), 2) if ann_vol > 0 else None,
        "win_rate_pct": round(win_rate, 2),
        "wins": wins,
        "total_trades": total_trades,
        "benchmark_return_pct": round(benchmark_return, 2),
        "execution_frequency": freq,
        "transaction_cost_est": {
            "cost_bps_oneway": cost_bps,
            "total_cost_usd": total_cost,
            "cost_adjusted_return_pct": round((final_equity - total_cost) / initial_capital * 100 - 100, 2),
        },
        "trades": [trade.as_dict() for trade in trades],
        "equity_curve": equity_curve,
    }


def annualized_volatility(equity_curve: list[dict]) -> float:
    """연간화 변동성 (일별 수익률 표준편차 × √252)."""
    if len(equity_curve) < 2:
        return 0.0
    equities = [p["equity"] for p in equity_curve]
    daily_returns = [(equities[i] / equities[i - 1]) - 1 for i in range(1, len(equities))]
    if not daily_returns:
        return 0.0
    n = len(daily_returns)
    mean = sum(daily_returns) / n
    variance = sum((r - mean) ** 2 for r in daily_returns) / max(n - 1, 1)
    return math.sqrt(variance) * math.sqrt(252) * 100


def execution_frequency(trades: list[Trade], total_days: int) -> dict:
    """거래 빈도 지표."""
    if not trades or total_days <= 0:
        return {"trades_per_year": 0.0, "avg_hold_days": 0.0, "max_exposure_pct": 0.0}
    trades_per_year = len(trades) / (total_days / 365.25)
    avg_hold_days = sum(t.hold_days for t in trades) / len(trades)
    # max_exposure: 포지션 보유 일수 / 전체 일수
    total_hold_days = sum(t.hold_days for t in trades)
    max_exposure_pct = min(total_hold_days / total_days * 100, 100.0)
    return {
        "trades_per_year": round(trades_per_year, 2),
        "avg_hold_days": round(avg_hold_days, 1),
        "max_exposure_pct": round(max_exposure_pct, 1),
    }


def apply_transaction_costs(trades: list[Trade], cost_bps: float = 10.0) -> tuple[float, float]:
    """
    왕복 거래비용 적용 후 총 PnL 감소분과 비용 조정 수익률 변화.
    cost_bps: 편도 거래비용 (basis points). 기본 10bp = 0.10%
    """
    cost_rate = cost_bps / 10000.0
    total_cost = 0.0
    for t in trades:
        cost = (t.entry_price + t.exit_price) * t.shares * cost_rate
        total_cost += cost
    return round(total_cost, 2), round(cost_bps, 1)


def walk_forward_backtest(
    symbol: str,
    df: pd.DataFrame,
    initial_capital: float,
    train_months: int = 18,
    test_months: int = 6,
) -> dict:
    """
    워크-포워드(Walk-Forward) 백테스트.
    - 훈련 기간(train_months)으로 신호 체계 적용 후 테스트 기간(test_months)에서 성과 평가.
    - 최소 LOOKBACK_BARS + 30일 데이터가 필요한 구간만 평가.
    - 각 폴드의 결과를 반환 (실제로 임계값 학습은 없지만 시간분할 성과 검증 역할).
    """
    train_bars = train_months * 21  # 대략 거래일 계산
    test_bars = test_months * 21

    folds = []
    total_bars = len(df)
    start = LOOKBACK_BARS + train_bars

    fold_idx = 0
    while start + test_bars <= total_bars:
        train_start = max(0, start - train_bars)
        train_end = start
        test_end = min(start + test_bars, total_bars)

        # 테스트 구간만 백테스트 (훈련 구간 기록은 lookback 전제)
        test_df = df.iloc[train_start:test_end].copy()
        if len(test_df) <= LOOKBACK_BARS + 2:
            start += test_bars
            continue

        fold_result = backtest_symbol(symbol, test_df, initial_capital)
        fold_result["fold"] = fold_idx
        fold_result["train_start"] = df.index[train_start].strftime("%Y-%m-%d")
        fold_result["train_end"] = df.index[train_end - 1].strftime("%Y-%m-%d")
        fold_result["test_start"] = df.index[train_end].strftime("%Y-%m-%d") if train_end < total_bars else None
        fold_result["test_end"] = df.index[test_end - 1].strftime("%Y-%m-%d")

        folds.append(fold_result)
        fold_idx += 1
        start += test_bars

    if not folds:
        return {"symbol": symbol, "folds": [], "note": "데이터 부족으로 워크-포워드 불가"}

    avg_return = sum(f["total_return_pct"] for f in folds) / len(folds)
    avg_mdd = sum(f["mdd_pct"] for f in folds) / len(folds)
    avg_win_rate = sum(f["win_rate_pct"] for f in folds) / len(folds)
    profitable_folds = sum(1 for f in folds if f["total_return_pct"] > 0)

    return {
        "symbol": symbol,
        "fold_count": len(folds),
        "train_months": train_months,
        "test_months": test_months,
        "avg_return_pct": round(avg_return, 2),
        "avg_mdd_pct": round(avg_mdd, 2),
        "avg_win_rate_pct": round(avg_win_rate, 2),
        "profitable_folds": profitable_folds,
        "profitable_folds_pct": round(profitable_folds / len(folds) * 100, 1),
        "folds": [
            {
                "fold": f["fold"],
                "train_start": f.get("train_start"),
                "test_start": f.get("test_start"),
                "test_end": f.get("test_end"),
                "return_pct": f["total_return_pct"],
                "mdd_pct": f["mdd_pct"],
                "win_rate_pct": f["win_rate_pct"],
                "total_trades": f["total_trades"],
            }
            for f in folds
        ],
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
    portfolio = results["portfolio"]
    lines = [
        "# BACKTEST_REPORT",
        "",
        "## 개요",
        f"- 대상: {', '.join(results.get('config', {}).get('symbols', ['SPY', 'QQQ']))}",
        f"- 기간: 최근 {results.get('config', {}).get('years', 5)}년 일봉",
        "- 규칙: A/B 등급이면 다음 날 시가 매수, D/F 등급이면 다음 날 시가 매도",
        f"- 초기 자본금: ${results.get('config', {}).get('initial_capital', 10000):,.0f}",
        "- 체결 방식: 편도 10bp 수수료 추정 포함",
        "",
        "## 포트폴리오 결과",
        f"| 지표 | 값 |",
        f"|------|-----|",
        f"| 최종 자산 | ${portfolio['final_equity']:,.2f} |",
        f"| 총수익률 | {portfolio['total_return_pct']:.2f}% |",
        f"| CAGR | {portfolio['cagr_pct']:.2f}% |",
        f"| MDD | {portfolio['mdd_pct']:.2f}% |",
        f"| 연간 변동성 | {portfolio.get('annualized_vol_pct', 0):.2f}% |",
        f"| 샤프비율 (근사) | {portfolio.get('sharpe_approx') or 'N/A'} |",
        f"| 승률 | {portfolio['win_rate_pct']:.2f}% ({portfolio['wins']}/{portfolio['total_trades']}) |",
        "",
        "## 종목별 결과",
    ]

    for symbol, result in results["per_symbol"].items():
        freq = result.get("execution_frequency", {})
        cost = result.get("transaction_cost_est", {})
        lines.extend([
            f"### {symbol}",
            f"| 지표 | 값 |",
            f"|------|-----|",
            f"| 최종 자산 | ${result['final_equity']:,.2f} |",
            f"| 총수익률 | {result['total_return_pct']:.2f}% |",
            f"| CAGR | {result['cagr_pct']:.2f}% |",
            f"| MDD | {result['mdd_pct']:.2f}% |",
            f"| 연간 변동성 | {result.get('annualized_vol_pct', 0):.2f}% |",
            f"| 샤프비율 (근사) | {result.get('sharpe_approx') or 'N/A'} |",
            f"| 승률 | {result['win_rate_pct']:.2f}% ({result['wins']}/{result['total_trades']}) |",
            f"| Buy & Hold | {result['benchmark_return_pct']:.2f}% |",
            f"| 연간 거래 횟수 | {freq.get('trades_per_year', 0):.1f}회 |",
            f"| 평균 보유 기간 | {freq.get('avg_hold_days', 0):.1f}일 |",
            f"| 최대 노출도 | {freq.get('max_exposure_pct', 0):.1f}% |",
            f"| 거래비용 추정 | ${cost.get('total_cost_usd', 0):,.2f} (편도 {cost.get('cost_bps_oneway', 10):.0f}bp) |",
            f"| 비용 조정 수익률 | {cost.get('cost_adjusted_return_pct', 0):.2f}% |",
            "",
        ])

    # Walk-forward 결과
    if results.get("walk_forward"):
        lines.extend(["## 워크-포워드(Walk-Forward) 검증", ""])
        for symbol, wf in results["walk_forward"].items():
            lines.extend([
                f"### {symbol} — {wf.get('fold_count', 0)}개 폴드 ({wf.get('train_months', 18)}M 훈련 / {wf.get('test_months', 6)}M 테스트)",
                f"- 평균 수익률: {wf.get('avg_return_pct', 0):.2f}%",
                f"- 평균 MDD: {wf.get('avg_mdd_pct', 0):.2f}%",
                f"- 평균 승률: {wf.get('avg_win_rate_pct', 0):.2f}%",
                f"- 수익 폴드 비율: {wf.get('profitable_folds_pct', 0):.1f}% ({wf.get('profitable_folds', 0)}/{wf.get('fold_count', 0)})",
                "",
                "| 폴드 | 테스트 시작 | 테스트 종료 | 수익률 | MDD | 승률 | 거래수 |",
                "|------|-----------|-----------|--------|-----|------|------|",
            ])
            for f in wf.get("folds", []):
                lines.append(
                    f"| {f['fold']} | {f.get('test_start','?')} | {f.get('test_end','?')} "
                    f"| {f['return_pct']:.1f}% | {f['mdd_pct']:.1f}% | {f['win_rate_pct']:.1f}% | {f['total_trades']} |"
                )
            lines.append("")

    lines.extend([
        "## 해석",
        "- 이 백테스트는 현재 기술적 등급 체계(timing_score)가 과거 데이터에서 어느 정도 방어력과 수익성을 가졌는지 검증합니다.",
        "- 워크-포워드 검증: 과적합(overfitting) 여부 확인 — 수익 폴드 비율이 60% 이상이면 전략의 범용성 신호.",
        "- 거래비용 추정: 편도 10bp(증권사 수수료 + 슬리피지)로 실제 수익률 하한을 추정합니다.",
        "- 레짐, 밸류에이션, 계좌 제약, 분할매수 스케줄까지 완전 반영한 풀 시뮬레이션은 추가 단계가 필요합니다.",
        "",
        f"_generated_at: {datetime.now(timezone.utc).isoformat()}_",
    ])

    (root / "BACKTEST_REPORT.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-dir", default=str(ROOT))
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--symbols", default="SPY,QQQ")
    parser.add_argument("--initial-capital", type=float, default=10000)
    parser.add_argument("--walk-forward", action="store_true", help="워크-포워드 검증 실행")
    parser.add_argument("--train-months", type=int, default=18, help="워크-포워드 훈련 기간 (개월)")
    parser.add_argument("--test-months", type=int, default=6, help="워크-포워드 테스트 기간 (개월)")
    args = parser.parse_args()

    root = Path(args.base_dir)
    symbols = [item.strip().upper() for item in args.symbols.split(",") if item.strip()]
    per_symbol_capital = args.initial_capital / max(len(symbols), 1)

    histories: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        print(f"{symbol} 데이터 다운로드 중…")
        histories[symbol] = download_history(symbol, args.years)
        if histories[symbol].empty:
            raise RuntimeError(f"{symbol} 데이터 다운로드 실패")

    per_symbol = {}
    for symbol in symbols:
        print(f"{symbol} 백테스트 실행 중…")
        per_symbol[symbol] = backtest_symbol(symbol, histories[symbol], per_symbol_capital)

    portfolio = build_portfolio_summary(per_symbol, args.initial_capital)
    # portfolio에도 확장 메트릭 추가
    portfolio["annualized_vol_pct"] = annualized_volatility(portfolio.get("equity_curve", []))
    ann_vol = portfolio["annualized_vol_pct"]
    portfolio["sharpe_approx"] = round(portfolio["cagr_pct"] / ann_vol, 2) if ann_vol > 0 else None

    # 워크-포워드 (--walk-forward 플래그 또는 5년 이상 데이터)
    walk_forward_results = {}
    if args.walk_forward or args.years >= 3:
        for symbol in symbols:
            print(f"{symbol} 워크-포워드 검증 중…")
            walk_forward_results[symbol] = walk_forward_backtest(
                symbol=symbol,
                df=histories[symbol],
                initial_capital=per_symbol_capital,
                train_months=args.train_months,
                test_months=args.test_months,
            )

    results = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "strategy": {
            "entry_rule": "timing_score grade A/B -> next open buy",
            "exit_rule": "timing_score grade D/F -> next open sell",
            "execution": "next_open",
            "lookback_bars": LOOKBACK_BARS,
            "transaction_cost_bps_oneway": 10,
        },
        "config": {
            "symbols": symbols,
            "years": args.years,
            "initial_capital": args.initial_capital,
            "per_symbol_capital": round(per_symbol_capital, 2),
        },
        "per_symbol": per_symbol,
        "portfolio": portfolio,
        "walk_forward": walk_forward_results,
    }

    out_dir = root / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "backtest_results.json"
    out_file.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    write_report(root, results)

    print(f"\nwrote {out_file}")
    print(f"wrote {root / 'BACKTEST_REPORT.md'}")
    print()

    pf = results["portfolio"]
    print(f"[포트폴리오] 수익률: {pf['total_return_pct']:.2f}% | CAGR: {pf['cagr_pct']:.2f}% | MDD: {pf['mdd_pct']:.2f}% | 변동성: {pf.get('annualized_vol_pct', 0):.2f}%")
    if walk_forward_results:
        for sym, wf in walk_forward_results.items():
            print(f"[{sym} 워크-포워드] 폴드: {wf.get('fold_count', 0)} | 수익 비율: {wf.get('profitable_folds_pct', 0):.1f}% | 평균 수익률: {wf.get('avg_return_pct', 0):.2f}%")


if __name__ == "__main__":
    main()
