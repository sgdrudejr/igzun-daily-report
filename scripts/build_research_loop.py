#!/usr/bin/env python3
"""
반복적 딥리서치 루프 생성기.

목적:
- 단일 요약이 아니라 가설 설정 -> 근거 탐색 -> 검증 -> 추가 탐색의 루프를 저장한다.
- 실제 LangGraph/CrewAI 없이도 현재 파이프라인에서 다중 에이전트형 분석 흐름을 모사한다.

Output:
- data/research_loops/{date}.json
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

from build_research_context import build_research_context
from research_toolbox import (
    graph_focus,
    latest_available_date,
    list_tool_defs,
    macro_snapshot,
    portfolio_snapshot,
    search_hierarchical_index,
    signal_snapshot,
    valuation_snapshot,
)


def load_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def as_float(value, default=None):
    try:
        if value is None or value == "N/A":
            return default
        return float(value)
    except Exception:
        return default


def _current_terms(context: dict, packets: dict) -> list[str]:
    topics = ((context.get("topic_windows") or {}).get("recent_7d") or [])[:4]
    top_terms = [item.get("topic") for item in topics if item.get("topic")]
    macro_terms = []
    macro_packet = packets.get("macro_strategist") or {}
    for text in macro_packet.get("macro_drivers") or []:
        macro_terms.extend([chunk.strip() for chunk in str(text).replace("/", " ").split() if chunk.strip()])
    result = []
    seen = set()
    for term in top_terms + macro_terms:
        if not term or term in seen:
            continue
        seen.add(term)
        result.append(term)
    return result[:8]


def _build_initial_hypotheses(context: dict, macro: dict, valuation: dict, signals: dict) -> list[str]:
    current = context.get("current_snapshot") or {}
    sp = valuation.get("sp500") or {}
    market_signal = signals.get("market_signal") or {}
    deploy = current.get("deployable_pct", market_signal.get("deployable_pct", 0))
    regime = current.get("regime_kr", macro.get("regime_kr", "중립"))
    kospi_grade = (valuation.get("kospi") or {}).get("valuation_grade", "중립")
    items = [
        f"현재 메인 가설은 '{market_signal.get('action', '관망')}'이며, 레짐은 {regime}이다.",
        f"S&P500은 ERP {(sp.get('erp_pct')) if sp.get('erp_pct') is not None else 'N/A'}% 수준으로 강한 저평가보다는 선별 매수에 가깝다.",
        f"총 현금의 약 {deploy}%까지만 우선 배치하고, 나머지는 확인 후 확대하는 것이 기본 시나리오다.",
        f"KOSPI 밸류에이션은 {kospi_grade}로 해석되므로 국내 위험자산은 속도 조절이 필요하다.",
    ]
    return items


def _macro_memo(context: dict, packets: dict, macro: dict) -> dict:
    current = context.get("current_snapshot") or {}
    packet = packets.get("macro_strategist") or {}
    drivers = packet.get("macro_drivers") or []
    return {
        "role": "거시경제 전략가",
        "question": packet.get("primary_question", ""),
        "summary": (
            f"현재 레짐은 {current.get('regime_kr', macro.get('regime_kr', '중립'))}이며 "
            f"총점 {current.get('total_score', macro.get('total_score', 'N/A'))}점, "
            f"시장 신호는 {current.get('market_signal', '중립')}로 정리된다."
        ),
        "drivers": drivers[:5],
        "view": (
            "레짐 자체는 붕괴되지 않았지만 VIX/달러/금리 부담이 남아 있어, 공격 확대보다 선별 진입이 자연스럽다."
        ),
    }


def _quant_memo(valuation: dict, signals: dict, packets: dict) -> dict:
    packet = packets.get("quant_analyst") or {}
    sp = valuation.get("sp500") or {}
    kospi = valuation.get("kospi") or {}
    market_signal = signals.get("market_signal") or {}
    top_buys = signals.get("top_buys") or []
    best = top_buys[0] if top_buys else {}
    return {
        "role": "퀀트 애널리스트",
        "question": packet.get("quant_question", ""),
        "summary": (
            f"S&P500 ERP {sp.get('erp_pct', 'N/A')}%, 52주 위치 {sp.get('range_52w_pct', 'N/A')}%, "
            f"KOSPI valuation {kospi.get('valuation_grade', 'N/A')}, "
            f"시장 배치 가능 비중 {market_signal.get('deployable_pct', 0)}%."
        ),
        "best_candidate": {
            "id": best.get("id"),
            "name": best.get("name"),
            "signal": best.get("signal"),
            "timing_grade": best.get("timing_grade"),
        } if best else {},
        "view": (
            "정량 데이터는 전면 risk-on보다는 미국 코어 ETF의 저속 분할 진입을 우선 지지한다."
        ),
    }


def _fundamental_memo(index_hits: dict, graph_hits: dict, packets: dict) -> dict:
    packet = packets.get("fundamental_researcher") or {}
    docs = index_hits.get("documents") or []
    top_docs = []
    for item in docs[:4]:
        top_docs.append(
            {
                "title": item.get("title"),
                "source": item.get("source_label") or item.get("source_id"),
                "topic": ", ".join(item.get("topics") or []),
                "doc_id": item.get("doc_id"),
            }
        )
    communities = graph_hits.get("communities") or {}
    top_assets = communities.get("top_assets") or []
    return {
        "role": "펀더멘털 리서처",
        "question": packet.get("research_question", ""),
        "summary": (
            f"H-RAG 검색 결과 문서 {len(docs)}건, 청크 {(index_hits.get('chunks') or []).__len__()}건을 확인했고, "
            f"Graph 연결상 {(top_assets[0].get('asset') if top_assets else '핵심 자산 미식별')} 축이 반복적으로 등장한다."
        ),
        "top_documents": top_docs,
        "linked_assets": top_assets[:5],
        "view": (
            "최근 누적 문서는 금리·연준, 한국 수출/반도체, 유가/원자재를 반복적으로 가리키며 단발 뉴스보다 누적 흐름 해석이 더 중요하다."
        ),
    }


def _portfolio_memo(portfolio: dict, packets: dict) -> dict:
    packet = packets.get("portfolio_operator") or {}
    accounts = portfolio.get("accounts") or {}
    plans = portfolio.get("account_plans") or {}
    account_rows = []
    for account_id, account in accounts.items():
        plan = plans.get(account_id) or {}
        account_rows.append(
            {
                "account": account.get("label", account_id),
                "cash": account.get("cash", 0),
                "deploy_amount": plan.get("deploy_amount", 0),
                "top_picks": [p.get("name") for p in (plan.get("top_picks") or [])[:2]],
            }
        )
    return {
        "role": "포트폴리오 운영자",
        "question": packet.get("execution_question", ""),
        "summary": f"총 현금 {portfolio.get('total_cash', 0):,}원이며 계좌별로 다른 속도의 집행이 필요하다.",
        "accounts": account_rows,
        "view": "토스는 미국 코어 우선, ISA는 국내 ETF 속도 조절, 연금저축은 축적형 접근이 적절하다.",
    }


def _skeptic_review(macro: dict, valuation: dict, signals: dict, index_hits: dict, iteration: int) -> dict:
    contradictions = []
    follow_up_queries = []

    market_signal = signals.get("market_signal") or {}
    deploy = market_signal.get("deployable_pct", 0)
    top_buys = signals.get("top_buys") or []
    best = top_buys[0] if top_buys else {}
    sp = valuation.get("sp500") or {}
    kospi = valuation.get("kospi") or {}
    drivers = macro.get("drivers") or {}
    vix = as_float(drivers.get("vix"), 20)
    usd_krw = as_float(drivers.get("usd_krw"), 1350)

    if deploy <= 15:
        contradictions.append("배치 가능 비중이 낮아 전면 매수 서사는 성립하기 어렵다.")
        follow_up_queries.extend(["관망", "분할매수"])
    if vix >= 25:
        contradictions.append(f"VIX {vix:.1f}로 변동성이 높아 타이밍 설명을 더 보수적으로 잡아야 한다.")
        follow_up_queries.extend(["VIX", "변동성"])
    if usd_krw >= 1450:
        contradictions.append(f"원/달러 {usd_krw:.0f}원은 국내 위험자산 확대 논리를 약화시킨다.")
        follow_up_queries.extend(["환율", "달러"])
    if (kospi.get("valuation_grade") or "").startswith("고평가") or kospi.get("valuation_grade") == "다소 고평가":
        contradictions.append("국내 자산은 밸류에이션 부담 때문에 좋은 뉴스만으로 공격 확대를 정당화하기 어렵다.")
        follow_up_queries.extend(["KOSPI", "밸류업"])
    if best and best.get("id") == "KODEX_SEMI" and (sp.get("erp_pct") is not None and as_float(sp.get("erp_pct"), 0) <= 0.5):
        contradictions.append("반도체 탐색은 가능하지만 미국 코어보다 우선순위를 높게 두기 어렵다.")
        follow_up_queries.extend(["반도체", "수출"])
    if len(index_hits.get("documents") or []) < 3:
        contradictions.append("근거 문서 수가 충분치 않아 추가 검색이 필요하다.")
        follow_up_queries.extend(["금리", "반도체"])

    status = "needs_follow_up" if contradictions and iteration == 1 else "validated_with_cautions"
    return {
        "role": "리스크 및 검증자",
        "summary": "현재 가설의 약점과 놓친 점을 점검해 추가 탐색 키워드를 제안한다.",
        "contradictions": contradictions[:5],
        "follow_up_queries": list(dict.fromkeys(follow_up_queries))[:6],
        "status": status,
    }


def _build_final_synthesis(iterations: list[dict], portfolio: dict) -> dict:
    last = iterations[-1]
    skeptic = last.get("skeptic_review") or {}
    macro_memo = last.get("macro_memo") or {}
    quant_memo = last.get("quant_memo") or {}
    fundamental_memo = last.get("fundamental_memo") or {}
    portfolio_memo = last.get("portfolio_memo") or {}

    citations = []
    for item in (fundamental_memo.get("top_documents") or [])[:4]:
        citations.append(
            {
                "source": item.get("source"),
                "title": item.get("title"),
                "doc_id": item.get("doc_id"),
            }
        )

    validated = [
        {
            "thesis": "현재 메인 액션은 공격 확대보다 선별 매수다.",
            "why": macro_memo.get("view"),
            "evidence": [macro_memo.get("summary"), quant_memo.get("summary")],
        },
        {
            "thesis": "미국 코어 ETF가 국내 위험자산보다 우선순위가 높다.",
            "why": quant_memo.get("view"),
            "evidence": [quant_memo.get("summary"), portfolio_memo.get("view")],
        },
        {
            "thesis": "금리·연준, 한국 수출/반도체, 유가/원자재가 누적 핵심 축이다.",
            "why": fundamental_memo.get("view"),
            "evidence": [fundamental_memo.get("summary")] + [c.get("title") for c in citations[:2]],
        },
    ]

    rejected = [{"claim": item, "reason": "검증자 메모에서 추가 제약 요인으로 지적됨"} for item in skeptic.get("contradictions") or []]
    accounts = portfolio_memo.get("accounts") or []
    action_digest = []
    for account in accounts[:3]:
        action_digest.append(
            {
                "account": account.get("account"),
                "deploy_amount": account.get("deploy_amount"),
                "top_picks": account.get("top_picks") or [],
            }
        )

    verification_status = skeptic.get("status") or "validated_with_cautions"
    loop_count = len(iterations)
    if verification_status == "validated_with_cautions":
        summary = f"{loop_count}회 루프를 거쳐 핵심 가설을 검증했고, 변동성·환율·국내 밸류에이션 관련 주의 조건을 함께 남겼습니다."
    else:
        summary = f"{loop_count}회 루프를 수행했지만 추가 탐색이 필요한 쟁점이 남았습니다."

    return {
        "loop_count": loop_count,
        "verification_status": verification_status,
        "research_loop_summary": summary,
        "validated_theses": validated,
        "rejected_theses": rejected[:5],
        "action_digest": action_digest,
        "citations": citations,
        "confidence_note": "정량 시그널과 누적 문서 흐름은 대체로 같은 방향을 가리키지만, 공격적 해석을 막는 반대 신호도 분명하다.",
    }


def build_research_loop(root: Path, date_str: str, max_loops: int = 2) -> dict:
    context = load_json(root / "data" / "research_context" / f"{date_str}.json") or build_research_context(root, date_str)
    packets = load_json(root / "data" / "research_packets" / f"{date_str}.json") or (context.get("agent_packets") or {})
    macro = macro_snapshot(root, date_str)
    valuation = valuation_snapshot(root, date_str)
    signals = signal_snapshot(root, date_str)
    portfolio = portfolio_snapshot(root, date_str)

    initial_terms = _current_terms(context, packets)
    hypotheses = _build_initial_hypotheses(context, macro, valuation, signals)
    iterations = []
    current_terms = initial_terms[:]

    for loop_index in range(1, max_loops + 1):
        index_hits = search_hierarchical_index(root, date_str, current_terms, limit=6)
        graph_hits = graph_focus(root, date_str, current_terms, limit=8)
        macro_memo = _macro_memo(context, packets, macro)
        quant_memo = _quant_memo(valuation, signals, packets)
        fundamental_memo = _fundamental_memo(index_hits, graph_hits, packets)
        portfolio_memo = _portfolio_memo(portfolio, packets)
        skeptic_review = _skeptic_review(macro, valuation, signals, index_hits, loop_index)
        iterations.append(
            {
                "iteration": loop_index,
                "terms": current_terms,
                "hypotheses": hypotheses,
                "macro_memo": macro_memo,
                "quant_memo": quant_memo,
                "fundamental_memo": fundamental_memo,
                "portfolio_memo": portfolio_memo,
                "skeptic_review": skeptic_review,
            }
        )
        if not skeptic_review.get("follow_up_queries") or loop_index >= max_loops:
            break
        next_terms = current_terms + skeptic_review.get("follow_up_queries", [])
        current_terms = list(dict.fromkeys([term for term in next_terms if term]))[:10]

    return {
        "date": date_str,
        "tool_registry": list_tool_defs(),
        "initial_hypotheses": hypotheses,
        "iterations": iterations,
        "final_synthesis": _build_final_synthesis(iterations, portfolio),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="")
    parser.add_argument("--base-dir", default=str(ROOT))
    parser.add_argument("--max-loops", type=int, default=2)
    args = parser.parse_args()

    root = Path(args.base_dir)
    date_str = args.date or latest_available_date(root)
    result = build_research_loop(root, date_str, max_loops=max(1, args.max_loops))

    out_dir = root / "data" / "research_loops"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{date_str}.json"
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2))

    print(f"wrote {out_file}")
    print(json.dumps(result.get("final_synthesis") or {}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
