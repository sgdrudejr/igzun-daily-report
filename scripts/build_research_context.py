#!/usr/bin/env python3
"""
누적 데이터 기반 딥리서치 컨텍스트 생성기.

목적:
- 당일 뉴스/리포트 몇 건만 보는 것이 아니라,
  최근 누적 데이터, 과거 판단 변화, 주간/월간/분기 집계,
  계좌 실행 제약을 함께 묶어 LLM에 공급할 상위 컨텍스트를 만든다.

Output:
- data/research_context/{date}.json
"""

from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REGIME_LABELS = {
    "Growth": "성장 국면",
    "Neutral": "중립 횡보 국면",
    "Stagflation/Recession": "스태그플레이션/경기침체 국면",
    "Inflationary": "인플레이션 국면",
    "Risk-Off DollarStrength": "달러 강세/위험회피 국면",
}

SOURCE_NAMES = {
    "fed_speeches_rss": "연준 연설",
    "fed_press_rss": "연준 보도자료",
    "fred_api": "FRED 거시지표",
    "ecos_api": "한국은행 ECOS",
    "opendart": "OpenDART 공시",
    "naver_research": "네이버 금융 리서치",
    "kr_brokerage_kb": "KB증권 리서치",
    "kr_brokerage_mirae": "미래에셋 리서치",
    "kr_brokerage_shinhan": "신한투자증권 리서치",
    "bis_speeches": "BIS 연설",
    "investing_com_rss": "Investing.com 뉴스",
    "sec_edgar": "SEC EDGAR",
}

TOPIC_RULES = [
    ("AI/반도체", ["ai", "반도체", "hbm", "semiconductor", "chip", "nvidia", "엔비디아"]),
    ("금리/연준", ["금리", "연준", "fomc", "fed", "국채", "yield", "파월", "rate"]),
    ("인플레이션/물가", ["인플레이션", "물가", "cpi", "pce", "임금", "inflation"]),
    ("환율/달러", ["환율", "달러", "dxy", "usd", "원/달러", "usd/krw"]),
    ("유가/원자재", ["유가", "원유", "wti", "브렌트", "금", "원자재", "oil", "gold"]),
    ("한국 수출/반도체", ["수출", "한국", "kospi", "삼성전자", "sk하이닉스", "하이닉스"]),
    ("방산/지정학", ["방산", "전쟁", "중동", "우크라", "관세", "미사일", "지정학", "국방"]),
    ("바이오/헬스케어", ["바이오", "헬스케어", "제약", "의료기기", "신약"]),
    ("소비/내수", ["소비", "내수", "유통", "retail", "백화점", "음식료"]),
    ("배당/밸류업", ["배당", "밸류업", "주주환원", "pbr", "퀄리티"]),
]


def load_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    docs = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            docs.append(json.loads(line))
        except Exception:
            continue
    return docs


def load_jsonl_gz(path: Path) -> list[dict]:
    if not path.exists():
        return []
    docs = []
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                docs.append(json.loads(line))
            except Exception:
                continue
    return docs


def parse_date(text: str | None) -> date | None:
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except Exception:
        return None


def as_float(value, default=None):
    try:
        if value is None or value == "N/A":
            return default
        return float(value)
    except Exception:
        return default


def safe_text(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text


def nested(mapping, *keys, default=None):
    value = mapping
    for key in keys:
        if not isinstance(value, dict):
            return default
        value = value.get(key)
        if value is None:
            return default
    return value


def available_dates(root: Path, target_date: date) -> list[str]:
    dates = []
    for path in sorted((root / "data" / "macro_analysis").glob("*.json")):
        parsed = parse_date(path.stem)
        if parsed and parsed <= target_date:
            dates.append(path.stem)
    return dates


def docs_for_date(root: Path, date_str: str) -> list[dict]:
    live = root / "data" / "normalized" / date_str / "documents.jsonl"
    if live.exists():
        return load_jsonl(live)
    archived = root / "data" / "archives" / "normalized" / f"{date_str}.jsonl.gz"
    if archived.exists():
        return load_jsonl_gz(archived)
    return []


def doc_summary_for_date(root: Path, date_str: str) -> dict:
    return load_json(root / "data" / "archive_summaries" / "normalized" / f"{date_str}.json") or {}


def score_direction(delta: float | None) -> str:
    if delta is None:
        return "변화 데이터 없음"
    if delta >= 3:
        return "뚜렷한 개선"
    if delta >= 1:
        return "완만한 개선"
    if delta <= -3:
        return "뚜렷한 악화"
    if delta <= -1:
        return "완만한 둔화"
    return "큰 변화 없음"


def metric_direction(current: float | None, previous: float | None, label: str) -> str:
    if current is None or previous is None:
        return f"{label} 변화 데이터 없음"
    delta = current - previous
    if abs(delta) < 0.5:
        return f"{label} 큰 변화 없음"
    if delta > 0:
        return f"{label} 상승 ({delta:+.1f})"
    return f"{label} 하락 ({delta:+.1f})"


def load_macro(root: Path, date_str: str) -> dict:
    return load_json(root / "data" / "macro_analysis" / f"{date_str}.json") or {}


def load_result(root: Path, date_str: str) -> dict:
    return load_json(root / "site" / date_str / "result.json") or {}


def build_score_trend(root: Path, dates: list[str], current_macro: dict) -> dict:
    history = []
    for ds in dates[-30:]:
        macro = load_macro(root, ds)
        scores = macro.get("scores", {}) or {}
        mi = macro.get("macro_inputs", {}) or {}
        history.append(
            {
                "date": ds,
                "score": as_float(scores.get("total")),
                "regime": macro.get("regime", "Neutral"),
                "vix": as_float(mi.get("vix")),
                "usd_krw": as_float(mi.get("usd_krw")),
            }
        )

    current_score = as_float((current_macro.get("scores") or {}).get("total"))
    prev_1d = history[-2]["score"] if len(history) >= 2 else None
    prev_1w = history[-6]["score"] if len(history) >= 6 else None
    prev_1m = history[-21]["score"] if len(history) >= 21 else None

    current_regime = current_macro.get("regime", "Neutral")
    streak = 0
    for item in reversed(history):
        if item.get("regime") == current_regime:
            streak += 1
        else:
            break

    regime_counter = Counter(item.get("regime", "Neutral") for item in history[-10:])
    current_vix = as_float(((current_macro.get("macro_inputs") or {}).get("vix")))
    prev_vix = history[-6]["vix"] if len(history) >= 6 else None
    current_usdkrw = as_float(((current_macro.get("macro_inputs") or {}).get("usd_krw")))
    prev_usdkrw = history[-6]["usd_krw"] if len(history) >= 6 else None

    return {
        "history": history[-10:],
        "current_score": current_score,
        "delta_1d": None if current_score is None or prev_1d is None else round(current_score - prev_1d, 2),
        "delta_1w": None if current_score is None or prev_1w is None else round(current_score - prev_1w, 2),
        "delta_1m": None if current_score is None or prev_1m is None else round(current_score - prev_1m, 2),
        "direction_1w": score_direction(None if current_score is None or prev_1w is None else current_score - prev_1w),
        "regime_streak": streak,
        "recent_regime_counts": {
            REGIME_LABELS.get(regime, regime): count for regime, count in regime_counter.items()
        },
        "vix_trend": metric_direction(current_vix, prev_vix, "VIX"),
        "usdkrw_trend": metric_direction(current_usdkrw, prev_usdkrw, "원/달러"),
    }


def aggregate_docs(root: Path, date_window: list[str], max_sample_docs: int = 160) -> dict:
    source_counter: Counter[str] = Counter()
    region_counter: Counter[str] = Counter()
    sector_counter: Counter[str] = Counter()
    type_counter: Counter[str] = Counter()
    total_docs = 0
    sampled_docs: list[dict] = []

    for ds in date_window:
        docs = docs_for_date(root, ds)
        if docs:
            total_docs += len(docs)
            for doc in docs:
                source_counter[doc.get("source_id") or "unknown"] += 1
                region_counter[doc.get("region") or "unknown"] += 1
                sector_counter[doc.get("sector") or "unknown"] += 1
                type_counter[doc.get("document_type") or "unknown"] += 1
            remaining = max_sample_docs - len(sampled_docs)
            if remaining > 0:
                sampled_docs.extend(docs[:remaining])
            continue

        summary = doc_summary_for_date(root, ds)
        total_docs += int(summary.get("doc_count") or 0)
        for key, count in (summary.get("sources") or {}).items():
            source_counter[key] += int(count)
        for key, count in (summary.get("regions") or {}).items():
            region_counter[key] += int(count)
        for key, count in (summary.get("types") or {}).items():
            type_counter[key] += int(count)

    return {
        "document_count": total_docs,
        "sources": [
            {
                "source_id": source_id,
                "label": SOURCE_NAMES.get(source_id, source_id),
                "count": count,
            }
            for source_id, count in source_counter.most_common(6)
        ],
        "regions": [{"label": label, "count": count} for label, count in region_counter.most_common(4)],
        "sectors": [{"label": label, "count": count} for label, count in sector_counter.most_common(6) if label and label != "unknown"],
        "types": [{"label": label, "count": count} for label, count in type_counter.most_common(4)],
        "sampled_docs": sampled_docs,
    }


def extract_topics(docs: list[dict]) -> list[dict]:
    counter: Counter[str] = Counter()
    examples: dict[str, list[str]] = {}

    for doc in docs:
        blob = " ".join(
            [
                safe_text(doc.get("title")),
                safe_text(doc.get("summary")),
                safe_text(doc.get("content"))[:400],
            ]
        ).lower()
        if not blob:
            continue

        seen = set()
        for label, keywords in TOPIC_RULES:
            if any(keyword.lower() in blob for keyword in keywords):
                counter[label] += 1
                if label not in examples:
                    examples[label] = []
                title = safe_text(doc.get("title"))
                if title and title not in examples[label] and len(examples[label]) < 2:
                    examples[label].append(title)
                seen.add(label)
        if not seen:
            counter["기타/시장일반"] += 1

    ranked = [(label, count) for label, count in counter.most_common() if label != "기타/시장일반"]
    if not ranked and counter:
        ranked = counter.most_common(6)

    items = []
    for label, count in ranked[:6]:
        items.append(
            {
                "topic": label,
                "count": count,
                "examples": examples.get(label, []),
            }
        )
    return items


def select_horizon_snapshot(root: Path, folder_name: str, target_date: date) -> dict:
    folder = root / "site" / "horizons" / folder_name
    if not folder.exists():
        return {}

    exact = []
    fallback = []
    for path in folder.glob("*.json"):
        obj = load_json(path) or {}
        from_date = parse_date(obj.get("fromDate"))
        to_date = parse_date(obj.get("toDate"))
        if from_date and to_date and from_date <= target_date <= to_date:
            exact.append((to_date, obj))
        elif to_date and to_date <= target_date:
            fallback.append((to_date, obj))

    chosen = None
    if exact:
        chosen = sorted(exact, key=lambda item: item[0])[-1][1]
    elif fallback:
        chosen = sorted(fallback, key=lambda item: item[0])[-1][1]
    else:
        return {}

    llm = chosen.get("llmInsights", {}) or {}
    briefing = chosen.get("briefing", {}) or {}
    rebalancing = chosen.get("rebalancing", {}) or {}
    forecast = (briefing.get("forecast") or {}).get("text", "")
    return {
        "bucket_label": chosen.get("bucketLabel", ""),
        "update_count": chosen.get("updateCount", 0),
        "avg_score": as_float(chosen.get("avgScore")),
        "regime": chosen.get("regime", ""),
        "regime_kr": chosen.get("regimeKr", ""),
        "summary": llm.get("marketNarrative") or forecast or rebalancing.get("summary", ""),
        "key_signals": llm.get("keySignals") or [],
        "timing_guidance": llm.get("timingGuidance") or rebalancing.get("summary", ""),
    }


def build_recent_memos(root: Path, dates: list[str]) -> list[dict]:
    memos = []
    for ds in dates[-5:]:
        result = load_result(root, ds)
        if not result:
            continue
        llm = result.get("llmInsights", {}) or {}
        daily = ((result.get("dataByPeriod") or {}).get("1일") or {})
        briefing = daily.get("briefing", {}) or {}
        forecast = (briefing.get("forecast") or {}).get("text", "")
        narrative = llm.get("marketNarrative") or forecast
        if narrative:
            memos.append({"date": ds, "summary": narrative[:220]})
    return memos[-4:]


def build_portfolio_context(portfolio: dict, signals: dict) -> dict:
    plans = (signals.get("account_plans") or {}) if signals else {}
    items = []
    for account_id, account in ((portfolio.get("accounts") or {}).items()):
        plan = plans.get(account_id, {}) or {}
        picks = []
        for pick in (plan.get("top_picks") or [])[:3]:
            picks.append(
                {
                    "ticker": pick.get("ticker") or pick.get("id"),
                    "name": pick.get("name"),
                    "signal": pick.get("signal"),
                }
            )
        items.append(
            {
                "account_id": account_id,
                "label": account.get("label", account_id),
                "cash": account.get("cash", 0),
                "deploy_amount": plan.get("deploy_amount", 0),
                "top_picks": picks,
            }
        )
    return {"total_cash": portfolio.get("total_cash", 0), "accounts": items}


def _top_doc_samples(docs: list[dict], limit: int = 8) -> list[dict]:
    items = []
    for doc in docs[:limit]:
        items.append(
            {
                "source_id": doc.get("source_id"),
                "title": safe_text(doc.get("title")),
                "published_date": doc.get("published_date"),
                "region": doc.get("region"),
                "document_type": doc.get("document_type"),
                "summary": safe_text(doc.get("summary"))[:220],
            }
        )
    return items


def build_agent_packets(
    date_str: str,
    macro: dict,
    signals: dict,
    valuation: dict,
    docs_7: dict,
    docs_30: dict,
    score_trend: dict,
    horizons: dict,
    portfolio_context: dict,
    current_snapshot: dict,
) -> dict:
    mi = macro.get("macro_inputs", {}) or {}
    top_buys = (signals.get("top_buys") or [])[:4]
    avoid_list = (signals.get("avoid_list") or [])[:3]
    risk_flags = []
    if as_float(mi.get("vix"), 0) and as_float(mi.get("vix"), 0) > 25:
        risk_flags.append(f"VIX {as_float(mi.get('vix')):.1f}로 변동성 경계 상태")
    if as_float(mi.get("usd_krw"), 0) and as_float(mi.get("usd_krw"), 0) > 1450:
        risk_flags.append(f"원/달러 {as_float(mi.get('usd_krw')):.0f}원으로 원화 자산 부담 확대")
    if ((valuation.get("summary") or {}).get("avg_score") or 50) < 40:
        risk_flags.append("시장 전반 밸류에이션 점수가 낮아 가격 메리트가 크지 않음")
    if (signals.get("market_signal") or {}).get("action") == "관망 유지":
        risk_flags.append("시장 전체는 관망 기조라 공격적 배치보다 선별 접근이 우선")

    macro_drivers = []
    if as_float(mi.get("vix")) is not None:
        macro_drivers.append(f"VIX {as_float(mi.get('vix')):.1f}")
    if as_float(mi.get("us10y")) is not None:
        macro_drivers.append(f"미국 10년물 {as_float(mi.get('us10y')):.2f}%")
    if as_float(mi.get("usd_krw")) is not None:
        macro_drivers.append(f"원/달러 {as_float(mi.get('usd_krw')):.0f}원")
    if as_float(mi.get("oil")) is not None:
        macro_drivers.append(f"WTI ${as_float(mi.get('oil')):.1f}")

    recent_7_topics = extract_topics(docs_7.get("sampled_docs") or [])
    recent_30_topics = extract_topics(docs_30.get("sampled_docs") or [])

    return {
        "macro_strategist": {
            "role": "거시경제 전략가",
            "date": date_str,
            "current_regime": current_snapshot.get("regime_kr"),
            "market_signal": current_snapshot.get("market_signal"),
            "macro_drivers": macro_drivers,
            "score_trend": {
                "delta_1d": score_trend.get("delta_1d"),
                "delta_1w": score_trend.get("delta_1w"),
                "delta_1m": score_trend.get("delta_1m"),
                "regime_streak": score_trend.get("regime_streak"),
                "direction_1w": score_trend.get("direction_1w"),
            },
            "horizon_bias": [
                {
                    "period": label,
                    "regime": item.get("regime_kr"),
                    "avg_score": item.get("avg_score"),
                    "summary": safe_text(item.get("summary"))[:200],
                }
                for label, item in [
                    ("1주", horizons.get("weekly") or {}),
                    ("1개월", horizons.get("monthly") or {}),
                    ("3개월", horizons.get("quarterly") or {}),
                    ("6개월", horizons.get("semiannual") or {}),
                ]
                if item
            ],
            "primary_question": "지금은 공격적으로 비중을 늘릴 시점인가, 아니면 과매도 자산만 선별적으로 모을 시점인가?",
        },
        "quant_analyst": {
            "role": "퀀트 애널리스트",
            "market_signal": signals.get("market_signal") or {},
            "valuation_summary": valuation.get("summary") or {},
            "valuation_table": {
                "sp500": valuation.get("sp500") or {},
                "kospi": valuation.get("kospi") or {},
                "nasdaq": valuation.get("nasdaq") or {},
                "gold": valuation.get("gold") or {},
            },
            "top_candidates": [
                {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "signal": item.get("signal"),
                    "timing_grade": item.get("timing_grade"),
                    "rsi": item.get("rsi"),
                    "first_amount": nested(item, "position_sizing", "first_amount", default=0),
                    "schedule": nested(item, "position_sizing", "schedule", default=""),
                }
                for item in top_buys
            ],
            "avoid_candidates": [
                {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "signal": item.get("signal"),
                    "reason": " / ".join((item.get("reasons") or [])[:2]),
                }
                for item in avoid_list
            ],
            "quant_question": "정성적 뉴스 흐름이 실제 가격과 기술적 시그널에서 확인되는가?",
        },
        "fundamental_researcher": {
            "role": "펀더멘털 리서처",
            "recent_7d_coverage": {
                "document_count": docs_7.get("document_count", 0),
                "top_sources": docs_7.get("sources") or [],
                "top_topics": recent_7_topics[:5],
                "sample_docs": _top_doc_samples(docs_7.get("sampled_docs") or [], limit=6),
            },
            "recent_30d_coverage": {
                "document_count": docs_30.get("document_count", 0),
                "top_sources": docs_30.get("sources") or [],
                "top_topics": recent_30_topics[:6],
                "sample_docs": _top_doc_samples(docs_30.get("sampled_docs") or [], limit=8),
            },
            "research_question": "최근 누적 문서에서 반복되는 섹터/정책/실적 논리가 현재 포트폴리오 행동과 연결되는가?",
        },
        "skeptic_risk_manager": {
            "role": "리스크 및 검증자",
            "risk_flags": risk_flags,
            "contradictions_to_check": [
                "리서치 문구는 낙관적이지만 시장 점수와 배치 가능 비중이 낮은지",
                "과매도 기술 신호가 있어도 밸류에이션이 너무 비싼 자산은 아닌지",
                "한국 자산 매수 논리가 환율 상승과 충돌하지 않는지",
            ],
            "required_rechecks": [
                "주간 점수 변화가 음수일 때는 추격매수 문구를 금지",
                "시장 전체 신호가 관망이면 계좌별 액션도 소액 분할로 제한",
                "상위 시그널과 source-backed 주장 간 불일치 여부 점검",
            ],
        },
        "portfolio_operator": {
            "role": "포트폴리오 실행 담당",
            "total_cash": portfolio_context.get("total_cash", 0),
            "accounts": portfolio_context.get("accounts") or [],
            "execution_question": "계좌별 제약을 고려했을 때 오늘 어떤 순서와 속도로 배치해야 하는가?",
        },
        "synthesis_editor": {
            "role": "수석 에디터",
            "required_sections": [
                "executive_summary",
                "core_theses",
                "counter_signals",
                "what_changed",
                "scenario_matrix",
                "account_actions",
                "evidence_ledger",
                "next_checkpoints",
            ],
            "editor_goal": "브리핑이 아니라 가설-반박-실행-점검 구조의 투자 메모를 만든다.",
        },
    }


def build_research_context(root: Path, date_str: str) -> dict:
    target_date = date.fromisoformat(date_str)
    dates = available_dates(root, target_date)

    macro = load_macro(root, date_str)
    signals = load_json(root / "data" / "signals" / f"{date_str}.json") or {}
    valuation = load_json(root / "data" / "valuation" / f"{date_str}.json") or {}
    portfolio = load_json(root / "data" / "portfolio_state.json") or {}

    recent_7 = dates[-7:]
    recent_30 = dates[-30:]
    docs_7 = aggregate_docs(root, recent_7, max_sample_docs=140)
    docs_30 = aggregate_docs(root, recent_30, max_sample_docs=220)

    horizons = {
        "weekly": select_horizon_snapshot(root, "weekly", target_date),
        "monthly": select_horizon_snapshot(root, "monthly", target_date),
        "quarterly": select_horizon_snapshot(root, "quarterly", target_date),
        "semiannual": select_horizon_snapshot(root, "semiannual", target_date),
    }

    current_snapshot = {
        "date": date_str,
        "regime": macro.get("regime", "Neutral"),
        "regime_kr": REGIME_LABELS.get(macro.get("regime", "Neutral"), macro.get("regime", "Neutral")),
        "total_score": as_float((macro.get("scores") or {}).get("total")),
        "market_signal": ((signals.get("market_signal") or {}).get("action")) or "관망",
        "deployable_pct": ((signals.get("market_signal") or {}).get("deployable_pct")) or 0,
        "market_valuation": ((valuation.get("summary") or {}).get("market_valuation")) or "데이터 부족",
        "total_cash": portfolio.get("total_cash", 0),
    }

    score_trend = build_score_trend(root, dates, macro)
    portfolio_context = build_portfolio_context(portfolio, signals)
    packets = build_agent_packets(
        date_str=date_str,
        macro=macro,
        signals=signals,
        valuation=valuation,
        docs_7=docs_7,
        docs_30=docs_30,
        score_trend=score_trend,
        horizons=horizons,
        portfolio_context=portfolio_context,
        current_snapshot=current_snapshot,
    )

    return {
        "date": date_str,
        "current_snapshot": current_snapshot,
        "score_trend": score_trend,
        "horizon_snapshots": horizons,
        "source_windows": {
            "recent_7d": {
                "document_count": docs_7["document_count"],
                "sources": docs_7["sources"],
                "regions": docs_7["regions"],
                "sectors": docs_7["sectors"],
                "types": docs_7["types"],
            },
            "recent_30d": {
                "document_count": docs_30["document_count"],
                "sources": docs_30["sources"],
                "regions": docs_30["regions"],
                "sectors": docs_30["sectors"],
                "types": docs_30["types"],
            },
        },
        "topic_windows": {
            "recent_7d": extract_topics(docs_7["sampled_docs"]),
            "recent_30d": extract_topics(docs_30["sampled_docs"]),
        },
        "recent_memos": build_recent_memos(root, dates),
        "portfolio_context": portfolio_context,
        "agent_packets": packets,
        "packet_refs": {
            "research_packets": f"data/research_packets/{date_str}.json",
        },
        "index_refs": {
            "hierarchical_index": f"data/research_index/hierarchical/{date_str}.json",
            "graph_index": f"data/research_graph/{date_str}.json",
        },
    }


def _fmt_score(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.1f}점"


def _fmt_delta(value: float | None) -> str:
    if value is None:
        return "N/A"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.1f}p"


def format_research_context(context: dict) -> str:
    snapshot = context.get("current_snapshot", {}) or {}
    trend = context.get("score_trend", {}) or {}
    horizons = context.get("horizon_snapshots", {}) or {}
    source_windows = context.get("source_windows", {}) or {}
    topic_windows = context.get("topic_windows", {}) or {}
    portfolio_context = context.get("portfolio_context", {}) or {}

    lines = [
        "=== 누적 딥리서치 컨텍스트 ===",
        "[추세 변화]",
        (
            f"- 현재 레짐 {snapshot.get('regime_kr', 'N/A')} / 총점 {_fmt_score(snapshot.get('total_score'))} "
            f"/ 시장신호 {snapshot.get('market_signal', 'N/A')} / 배치 가능 {snapshot.get('deployable_pct', 0)}% "
            f"/ 시장 밸류에이션 {snapshot.get('market_valuation', 'N/A')}"
        ),
        (
            f"- 점수 변화: 1거래일 {_fmt_delta(trend.get('delta_1d'))}, "
            f"1주 {_fmt_delta(trend.get('delta_1w'))}, 1개월 {_fmt_delta(trend.get('delta_1m'))} "
            f"→ {trend.get('direction_1w', '데이터 없음')}"
        ),
        (
            f"- 최근 레짐 지속일수 {trend.get('regime_streak', 0)}거래일 | "
            f"VIX: {trend.get('vix_trend', '데이터 없음')} | "
            f"원/달러: {trend.get('usdkrw_trend', '데이터 없음')}"
        ),
        (
            "- 최근 10거래일 레짐 분포: "
            + ", ".join(f"{label} {count}회" for label, count in (trend.get("recent_regime_counts") or {}).items())
        ),
        "",
        "[누적 기간 관점]",
    ]

    horizon_labels = {
        "weekly": "1주",
        "monthly": "1개월",
        "quarterly": "3개월",
        "semiannual": "6개월",
    }
    for key, label in horizon_labels.items():
        item = horizons.get(key) or {}
        if not item:
            continue
        lines.append(
            f"- {label}: {item.get('bucket_label', '')} | 평균점수 {_fmt_score(item.get('avg_score'))} | "
            f"레짐 {item.get('regime_kr', 'N/A')} | {safe_text(item.get('summary'))[:180]}"
        )

    recent_7 = source_windows.get("recent_7d", {}) or {}
    recent_30 = source_windows.get("recent_30d", {}) or {}
    topics_7 = topic_windows.get("recent_7d", []) or []
    topics_30 = topic_windows.get("recent_30d", []) or []

    lines.extend(
        [
            "",
            "[누적 데이터 커버리지]",
            (
                f"- 최근 7거래일 문서 {recent_7.get('document_count', 0)}건 | 상위 출처: "
                + ", ".join(
                    f"{item['label']} {item['count']}건" for item in (recent_7.get("sources") or [])[:4]
                )
            ),
            (
                f"- 최근 30거래일 문서 {recent_30.get('document_count', 0)}건 | 상위 출처: "
                + ", ".join(
                    f"{item['label']} {item['count']}건" for item in (recent_30.get("sources") or [])[:4]
                )
            ),
            (
                "- 최근 7거래일 반복 주제: "
                + ", ".join(f"{item['topic']} {item['count']}건" for item in topics_7[:5])
            ),
            (
                "- 최근 30거래일 누적 주제: "
                + ", ".join(f"{item['topic']} {item['count']}건" for item in topics_30[:5])
            ),
        ]
    )

    memos = context.get("recent_memos") or []
    if memos:
        lines.append("")
        lines.append("[직전 판단 메모]")
        for memo in memos:
            lines.append(f"- {memo['date']}: {memo['summary']}")

    lines.extend(["", "[계좌 실행 컨텍스트]", f"- 총 투자 가능 현금 {portfolio_context.get('total_cash', 0):,}원"])
    for item in portfolio_context.get("accounts", []):
        top_picks = ", ".join(
            f"{pick.get('name')}({pick.get('signal')})" for pick in (item.get("top_picks") or [])[:2]
        )
        if not top_picks:
            top_picks = "우선 대기/관찰"
        lines.append(
            f"- {item.get('label')}: 현금 {item.get('cash', 0):,}원 | 추천 집행 {item.get('deploy_amount', 0):,}원 | "
            f"우선 후보 {top_picks}"
        )

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--base-dir", default=str(ROOT))
    args = parser.parse_args()

    root = Path(args.base_dir)
    context = build_research_context(root, args.date)

    out_dir = root / "data" / "research_context"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{args.date}.json"
    out_file.write_text(json.dumps(context, ensure_ascii=False, indent=2))

    packet_dir = root / "data" / "research_packets"
    packet_dir.mkdir(parents=True, exist_ok=True)
    packet_file = packet_dir / f"{args.date}.json"
    packet_file.write_text(json.dumps(context.get("agent_packets") or {}, ensure_ascii=False, indent=2))

    print(f"wrote {out_file}")
    print(f"wrote {packet_file}")
    print()
    print(format_research_context(context))


if __name__ == "__main__":
    main()
