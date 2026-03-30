#!/usr/bin/env python3
"""
딥리서치용 로컬 도구 레지스트리.

목적:
- 기존 정량/정성 산출물을 "도구"처럼 호출할 수 있도록 공통 인터페이스를 제공한다.
- 실제 MCP 서버나 외부 프레임워크 없이도 에이전트형 연구 루프가 같은 방식으로 동작하게 한다.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


TOOL_DEFS = [
    {
        "name": "macro_snapshot",
        "category": "quant",
        "description": "macro_analysis 결과에서 현재 레짐, 점수, 거시 드라이버를 반환",
    },
    {
        "name": "valuation_snapshot",
        "category": "quant",
        "description": "valuation_engine 결과에서 미국/한국 밸류에이션과 ERP 상태를 반환",
    },
    {
        "name": "signal_snapshot",
        "category": "quant",
        "description": "signal_engine 결과에서 시장 시그널, 상위 매수 후보, 회피 후보를 반환",
    },
    {
        "name": "portfolio_snapshot",
        "category": "portfolio",
        "description": "portfolio_state 와 계좌별 집행 계획을 묶어 반환",
    },
    {
        "name": "search_hierarchical_index",
        "category": "rag",
        "description": "H-RAG lite 인덱스에서 주제/키워드와 관련된 문서 및 청크를 검색",
    },
    {
        "name": "graph_focus",
        "category": "rag",
        "description": "GraphRAG lite 에서 topic/source/asset 연결성을 요약",
    },
]


def load_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def latest_available_date(root: Path) -> str:
    candidates = sorted((root / "site").glob("20*-*-*/result.json"))
    if candidates:
        return candidates[-1].parent.name
    raise FileNotFoundError("사용 가능한 site result.json 이 없습니다.")


def macro_snapshot(root: Path, date_str: str) -> dict:
    macro = load_json(root / "data" / "macro_analysis" / f"{date_str}.json") or {}
    scores = macro.get("scores") or {}
    mi = macro.get("macro_inputs") or {}
    return {
        "date": date_str,
        "regime": macro.get("regime"),
        "regime_kr": macro.get("regime_kr"),
        "total_score": scores.get("total"),
        "macro_score": scores.get("macro"),
        "technical_score": scores.get("technical"),
        "quant_score": scores.get("quant"),
        "fx_score": scores.get("fx"),
        "drivers": {
            "vix": mi.get("vix"),
            "us10y": mi.get("us10y"),
            "dxy": mi.get("dxy"),
            "usd_krw": mi.get("usd_krw"),
            "oil": mi.get("oil"),
            "fedfunds": mi.get("fedfunds"),
        },
    }


def valuation_snapshot(root: Path, date_str: str) -> dict:
    valuation = load_json(root / "data" / "valuation" / f"{date_str}.json") or {}
    return {
        "date": date_str,
        "summary": valuation.get("summary") or {},
        "sp500": valuation.get("sp500") or {},
        "kospi": valuation.get("kospi") or {},
        "nasdaq": valuation.get("nasdaq") or {},
        "gold": valuation.get("gold") or {},
    }


def signal_snapshot(root: Path, date_str: str) -> dict:
    signals = load_json(root / "data" / "signals" / f"{date_str}.json") or {}
    return {
        "date": date_str,
        "market_signal": signals.get("market_signal") or {},
        "summary": signals.get("summary") or {},
        "top_buys": signals.get("top_buys") or [],
        "avoid_list": signals.get("avoid_list") or [],
        "account_plans": signals.get("account_plans") or {},
    }


def portfolio_snapshot(root: Path, date_str: str) -> dict:
    portfolio = load_json(root / "data" / "portfolio_state.json") or {}
    signals = signal_snapshot(root, date_str)
    return {
        "date": date_str,
        "total_cash": portfolio.get("total_cash"),
        "accounts": portfolio.get("accounts") or {},
        "investment_profile": portfolio.get("investment_profile") or {},
        "account_plans": signals.get("account_plans") or {},
    }


def _score_text(blob: str, terms: list[str]) -> int:
    lowered = blob.lower()
    return sum(2 if term.lower() in lowered else 0 for term in terms)


def search_hierarchical_index(root: Path, date_str: str, terms: list[str], limit: int = 6) -> dict:
    index = load_json(root / "data" / "research_index" / "hierarchical" / f"{date_str}.json") or {}
    documents = index.get("documents") or []
    sections = index.get("sections") or []
    chunks = index.get("chunks") or []

    doc_hits = []
    for doc in documents:
        blob = " ".join(
            [
                str(doc.get("title") or ""),
                str(doc.get("coarse_summary") or ""),
                " ".join(doc.get("topics") or []),
                str(doc.get("source_label") or ""),
                str(doc.get("region") or ""),
            ]
        )
        score = _score_text(blob, terms)
        if score:
            item = dict(doc)
            item["_score"] = score
            doc_hits.append(item)

    section_hits = []
    for section in sections:
        blob = " ".join(
            [
                str(section.get("summary") or ""),
                str(section.get("title") or ""),
                " ".join(section.get("topics") or []),
            ]
        )
        score = _score_text(blob, terms)
        if score:
            item = dict(section)
            item["_score"] = score
            section_hits.append(item)

    chunk_hits = []
    for chunk in chunks:
        blob = " ".join(
            [
                str(chunk.get("text") or ""),
                str(chunk.get("title") or ""),
                " ".join(chunk.get("topics") or []),
            ]
        )
        score = _score_text(blob, terms)
        if score:
            item = dict(chunk)
            item["_score"] = score
            chunk_hits.append(item)

    doc_hits.sort(key=lambda x: (x.get("_score", 0), x.get("date", "")), reverse=True)
    section_hits.sort(key=lambda x: (x.get("_score", 0), x.get("date", "")), reverse=True)
    chunk_hits.sort(key=lambda x: (x.get("_score", 0), x.get("date", "")), reverse=True)

    return {
        "terms": terms,
        "documents": doc_hits[:limit],
        "sections": section_hits[:limit],
        "chunks": chunk_hits[: limit * 2],
    }


def graph_focus(root: Path, date_str: str, terms: list[str], limit: int = 8) -> dict:
    graph = load_json(root / "data" / "research_graph" / f"{date_str}.json") or {}
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []

    matched_nodes = []
    for node in nodes:
        label = str(node.get("label") or "")
        if any(term.lower() in label.lower() for term in terms):
            matched_nodes.append(node)

    node_ids = {node.get("id") for node in matched_nodes}
    linked = []
    for edge in edges:
        if edge.get("source") in node_ids or edge.get("target") in node_ids:
            linked.append(edge)

    linked = linked[:limit]
    return {
        "terms": terms,
        "matched_nodes": matched_nodes[:limit],
        "linked_edges": linked,
        "communities": graph.get("communities") or {},
        "summary": graph.get("summary") or {},
    }


def list_tool_defs() -> list[dict]:
    return list(TOOL_DEFS)

