#!/usr/bin/env python3
"""
Build GitHub Pages site report for a given date.
Reads:  data/macro_analysis/{date}.json
        data/etf_recommendations/{date}.json
        data/normalized/{date}/documents.jsonl
        data/market_quant_snapshot.json
Writes: site/{date}/result.json
        site/{date}/index.html  (copies from existing template)
        site/date_status.json   (overall calendar index)
"""
import argparse
import json
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

PERIODS = ["1일", "1주", "1개월", "3개월", "6개월"]


# ── helpers ──────────────────────────────────────────────────────────────────

def load_json(path: Path) -> dict | list | None:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return None


def load_jsonl(path: Path) -> list[dict]:
    docs = []
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    docs.append(json.loads(line))
                except Exception:
                    pass
    return docs


def score_to_sentiment(score: float | None) -> dict:
    """Convert 0-100 score to sentiment label."""
    if score is None:
        return {"score": 50, "status": "중립", "desc": "데이터 미확보"}
    s = int(round(score))
    if s >= 65:
        status = "위험선호/강세"
    elif s >= 55:
        status = "완만한 위험선호"
    elif s >= 45:
        status = "중립"
    elif s >= 35:
        status = "완만한 위험회피"
    else:
        status = "위험회피/약세"
    return {"score": s, "status": status, "desc": f"퀀트 총점 {s}/100 — {status}"}


def format_period_return(ret: float | None, label: str) -> str:
    if ret is None:
        return f"{label}: N/A"
    sign = "▲" if ret >= 0 else "▼"
    return f"{label} {sign}{abs(ret):.2f}%"


def etf_tier_icon(tier: str) -> str:
    return {"강력매수": "🟢", "매수": "🔵", "중립": "⚪", "비중축소": "🟡", "회피": "🔴"}.get(tier, "")


# ── period builder ────────────────────────────────────────────────────────────

def build_period(
    period_label: str,
    macro: dict,
    etf: dict,
    docs: list[dict],
    quant_snap: dict,
) -> dict:
    scores = macro.get("scores", {})
    inputs = macro.get("macro_inputs", {})
    regime = macro.get("regime", "Neutral")
    total = scores.get("total")

    # Find matching period return data
    period_ret = next(
        (p for p in macro.get("periods", []) if p.get("label") == period_label), {}
    )
    returns = period_ret.get("returns", {})

    # Sentiment
    sentiment = score_to_sentiment(total)

    # Returns summary text
    ret_lines = [
        format_period_return(returns.get("sp500"), "S&P500"),
        format_period_return(returns.get("kospi"), "KOSPI"),
        format_period_return(returns.get("nasdaq"), "NASDAQ"),
        format_period_return(returns.get("gold"), "Gold"),
        format_period_return(returns.get("wti"), "WTI"),
        format_period_return(returns.get("usdkrw"), "USD/KRW"),
    ]
    ret_text = "  |  ".join(ret_lines)

    # Macro conditions summary
    macro_desc = (
        f"VIX {inputs.get('vix', 'N/A')} | "
        f"US10Y {inputs.get('us10y', 'N/A')}% | "
        f"DXY {inputs.get('dxy', 'N/A'):.1f} | "
        f"Oil ${inputs.get('oil', 'N/A'):.1f} | "
        f"Fed {inputs.get('fedfunds', 'N/A')}% | "
        f"10Y-2Y Spread {inputs.get('t10y2y_spread', 'N/A')}"
    ) if isinstance(inputs.get('dxy'), float) else "매크로 지표 로딩 중"

    # Quant score summary
    quant_text = (
        f"Regime: {regime} | "
        f"Macro {scores.get('macro', '-')} | "
        f"Tech {scores.get('technical', '-')} | "
        f"Quant {scores.get('quant', '-')} | "
        f"FX {scores.get('fx', '-')} | "
        f"Total {scores.get('total', '-')}"
    )

    # Forecast text from collected docs (top summaries)
    sorted_docs = sorted(docs, key=lambda d: d.get("published_date", ""), reverse=True)
    highlights = []
    for d in sorted_docs[:5]:
        t = d.get("title") or d.get("core_subject", "")
        ks = d.get("key_takeaways") or d.get("summary", "")
        if t:
            line = f"• {t}"
            if ks and len(ks) > 10:
                line += f": {ks[:150]}..."
            highlights.append(line)

    forecast_text = "<br><br>".join([
        f"<b>[{period_label} 시장 요약]</b>",
        ret_text,
        f"<b>[매크로 지표]</b> {macro_desc}",
        f"<b>[퀀트 스코어링]</b> {quant_text}",
        "<b>[주요 수집 내용]</b><br>" + "<br>".join(highlights) if highlights else "",
    ])

    # ETF ranking for recommendations
    etf_ranking = []
    for r in etf.get("recommendations", [])[:8]:
        etf_ranking.append({
            "name": r["name"],
            "ticker": r["id"],
            "score": r["score"],
            "tier": r["tier"],
            "momentum": r.get("momentum_3m"),
            "rationale": r["rationale"],
            "icon": etf_tier_icon(r["tier"]),
        })

    # newsList from collected docs
    news_list = []
    by_region = {}
    for d in sorted_docs:
        region = d.get("region", "Global")
        by_region.setdefault(region, []).append(d)

    for region, rdocs in by_region.items():
        tops = rdocs[:3]
        if not tops:
            continue
        summary_parts = []
        sources = []
        for d in tops:
            t = d.get("title") or d.get("core_subject", "")
            if t:
                summary_parts.append(t)
            url = d.get("url") or d.get("source_url", "")
            sources.append({
                "label": d.get("source_id", region),
                "source": d.get("source_id", ""),
                "title": t,
                "published_at": d.get("published_date", ""),
                "url": url,
            })
        news_list.append({
            "title": f"{region} 주요 수집 ({period_label})",
            "tags": [region, period_label, "자동수집"],
            "summary": " / ".join(summary_parts[:3]),
            "impacts": [{"sector": region, "isPositive": (total or 50) >= 50, "desc": f"총점 {total}"}],
            "sources": sources[:3],
        })

    # Insights
    insights = [
        {
            "category": "퀀트",
            "text": quant_text,
            "sources": [{"label": "macro_analysis", "source": "quant_formula_engine", "title": f"{period_label} Regime={regime}", "published_at": macro.get("date", "")}],
        },
        {
            "category": "시장",
            "text": ret_text,
            "sources": [{"label": "yfinance", "source": "market_data", "title": "price data", "published_at": macro.get("date", "")}],
        },
    ]
    if etf.get("top3"):
        top3_text = " | ".join([f"{r['name']} (score={r['score']})" for r in etf["top3"]])
        insights.append({
            "category": "ETF추천",
            "text": f"Top3: {top3_text}",
            "sources": [{"label": "etf_recommender", "source": "etf_recommender", "title": "ETF ranking", "published_at": etf.get("date", "")}],
        })

    return {
        "briefing": {
            "sentiment": sentiment,
            "forecast": {
                "title": f"{period_label} 핵심 인사이트",
                "text": forecast_text,
                "sources": [{"label": d.get("source_id", ""), "source": d.get("source_id", ""), "title": d.get("title", "")[:80], "published_at": d.get("published_date", "")} for d in sorted_docs[:5]],
            },
            "insights": insights,
            "indices": [
                {"name": "S&P 500", "change": format_period_return(returns.get("sp500"), "")},
                {"name": "KOSPI", "change": format_period_return(returns.get("kospi"), "")},
                {"name": "NASDAQ", "change": format_period_return(returns.get("nasdaq"), "")},
                {"name": "Gold", "change": format_period_return(returns.get("gold"), "")},
                {"name": "WTI", "change": format_period_return(returns.get("wti"), "")},
                {"name": "USD/KRW", "change": format_period_return(returns.get("usdkrw"), "")},
            ],
        },
        "newsList": news_list,
        "portfolio": {
            "accountAlert": "자동 파이프라인 — 계좌 스냅샷 별도 연결 필요",
            "accountDetail": f"{period_label} 기간 기준 자동 생성 리포트입니다.",
            "weeklyReview": {"returnRate": "데이터 미연결", "desc": "계좌 스냅샷 연결 시 업데이트"},
            "holdings": [],
            "planDesc": f"Regime={regime} 기반 전략: 아래 ETF 추천 참고",
            "allocations": [],
        },
        "recommendations": {
            "ideas": [],
            "etfRanking": etf_ranking,
        },
    }


# ── main ──────────────────────────────────────────────────────────────────────

def build(root: Path, date_str: str):
    macro = load_json(root / "data/macro_analysis" / f"{date_str}.json") or {}
    etf = load_json(root / "data/etf_recommendations" / f"{date_str}.json") or {}
    docs = load_jsonl(root / "data/normalized" / date_str / "documents.jsonl")
    quant_snap = load_json(root / "data/market_quant_snapshot.json") or {}

    if not macro:
        print(f"[warn] No macro_analysis for {date_str} — run macro_analysis.py first")

    total = (macro.get("scores") or {}).get("total")
    regime = macro.get("regime", "Neutral")

    data_by_period = {}
    for period_label in PERIODS:
        data_by_period[period_label] = build_period(period_label, macro, etf, docs, quant_snap)

    result = {
        "date": f"{date_str} 기준 업데이트",
        "dataStatus": "full" if docs else "sparse",
        "regime": regime,
        "totalScore": total,
        "dataByPeriod": data_by_period,
    }

    # Write result.json
    out_dir = root / "site" / date_str
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))

    # Copy latest index.html template from most recent existing site entry
    template_path = out_dir / "index.html"
    if not template_path.exists():
        # Find most recent index.html in site/
        candidates = sorted(
            [p for p in (root / "site").glob("*/index.html") if p.parent.name != date_str],
            reverse=True,
        )
        if candidates:
            shutil.copy(candidates[0], template_path)
            print(f"  copied template from {candidates[0].parent.name}")

    print(f"wrote {out_dir / 'result.json'}  ({len(docs)} docs, regime={regime}, score={total})")
    return result


def update_date_status(root: Path, date_str: str, status: str, doc_count: int):
    """Upsert one entry in site/date_status.json."""
    status_file = root / "site/date_status.json"
    existing = load_json(status_file) or {}
    existing[date_str] = {"count": doc_count, "status": status}
    # Sort by date descending
    sorted_entries = dict(sorted(existing.items(), reverse=True))
    status_file.write_text(json.dumps(sorted_entries, ensure_ascii=False, indent=2))
    print(f"updated site/date_status.json — {date_str}: {status} ({doc_count} docs)")


def main():
    parser = argparse.ArgumentParser(description="Build site report for a date")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--base-dir", default=str(ROOT))
    args = parser.parse_args()

    root = Path(args.base_dir)
    docs = load_jsonl(root / "data/normalized" / args.date / "documents.jsonl")

    result = build(root, args.date)

    status = result.get("dataStatus", "sparse")
    update_date_status(root, args.date, status, len(docs))


if __name__ == "__main__":
    main()
