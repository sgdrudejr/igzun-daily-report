#!/usr/bin/env python3
"""
수동 심화분석용 브리프 생성기.

이 스크립트는 자동 배치와 분리된 반자동 워크플로우를 위해 사용한다.
사용자가 "오늘 거 심화 분석해줘" 같은 요청을 할 때, Codex/Claude가
한 번에 읽기 좋은 Markdown 브리프를 생성한다.

Output:
- data/manual_summary/{date}.md
- data/manual_summary/latest.md
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

from build_research_context import build_research_context


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
    return date.today().isoformat()


def as_float(value, default=None):
    try:
        if value is None or value == "N/A":
            return default
        return float(value)
    except Exception:
        return default


def money(value) -> str:
    number = as_float(value, 0) or 0
    return f"{int(round(number)):,}원"


def short(value, limit=180) -> str:
    text = "" if value is None else str(value).strip().replace("\n", " ")
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def nested(mapping, *keys, default=None):
    value = mapping
    for key in keys:
        if not isinstance(value, dict):
            return default
        value = value.get(key)
        if value is None:
            return default
    return value


def build_brief(root: Path, date_str: str) -> str:
    research_context = load_json(root / "data" / "research_context" / f"{date_str}.json")
    if not research_context:
        research_context = build_research_context(root, date_str)

    result = load_json(root / "site" / date_str / "result.json") or {}
    llm = result.get("llmInsights", {}) or {}
    valuation = result.get("valuation", {}) or {}
    signals = result.get("signals", {}) or {}
    periods = (result.get("dataByPeriod") or {})
    daily_portfolio = ((periods.get("1일") or {}).get("portfolio") or {})
    capital_plan = daily_portfolio.get("capitalPlan") or {}
    market_signal = (signals.get("marketSignal") or {})

    lines = [
        f"# 수동 심화분석 브리프 ({date_str})",
        "",
        "이 문서는 Codex/Claude가 반자동으로 심화 리포트를 작성할 때 읽는 표준 브리프다.",
        "자동 수집/분석 데이터는 이미 생성되어 있고, 여기서는 그것을 사람이 호출한 시점에 더 깊게 해석한다.",
        "",
        "## 현재 스냅샷",
        f"- 레짐: {result.get('regimeKr', result.get('regime', '데이터 없음'))}",
        f"- 총점: {result.get('totalScore', '데이터 없음')}",
        f"- 시장 시그널: {market_signal.get('action', '데이터 없음')}",
        f"- 배치 가능 비중: {market_signal.get('deployablePct', '데이터 없음')}%",
        f"- 총 투자 대기 현금: {capital_plan.get('totalCash', '데이터 없음')}",
        "",
        "## 누적 컨텍스트",
        f"- 최근 7거래일 문서 수: {(((research_context.get('source_windows') or {}).get('recent_7d') or {}).get('document_count', 0))}",
        f"- 최근 30거래일 문서 수: {(((research_context.get('source_windows') or {}).get('recent_30d') or {}).get('document_count', 0))}",
    ]

    for label, key in [("최근 7거래일 상위 주제", "recent_7d"), ("최근 30거래일 상위 주제", "recent_30d")]:
        topics = ((research_context.get("topic_windows") or {}).get(key) or [])[:5]
        if topics:
            lines.append(
                f"- {label}: " + ", ".join(f"{item['topic']} {item['count']}건" for item in topics)
            )

    score_trend = research_context.get("score_trend") or {}
    lines.extend(
        [
            f"- 점수 변화: 1일 {score_trend.get('delta_1d', 'N/A')} / 1주 {score_trend.get('delta_1w', 'N/A')} / 1개월 {score_trend.get('delta_1m', 'N/A')}",
            f"- 레짐 지속일수: {score_trend.get('regime_streak', 0)}거래일",
            "",
            "## 기간별 투자 방향성 요약",
        ]
    )

    for period in ["1일", "1주", "1개월", "3개월", "6개월"]:
        pdata = periods.get(period) or {}
        briefing = pdata.get("briefing") or {}
        portfolio = pdata.get("portfolio") or {}
        rebal = pdata.get("rebalancing") or {}
        lines.extend(
            [
                f"### {period}",
                f"- 브리핑: {short((briefing.get('forecast') or {}).get('text'))}",
                f"- 포트폴리오 해석: {short((portfolio.get('horizonView') or {}).get('desc'))}",
                f"- 실행 가이드: {short(rebal.get('summary'))}",
            ]
        )

    lines.extend(["", "## LLM/딥리서치 참고 블록"])
    if llm:
        if llm.get("marketNarrative"):
            lines.append(f"- 기존 시장 내러티브: {short(llm.get('marketNarrative'), 260)}")
        if llm.get("deepResearchSummary"):
            lines.append(f"- 기존 딥리서치 요약: {short(llm.get('deepResearchSummary'), 260)}")
        if llm.get("timingGuidance"):
            lines.append(f"- 기존 타이밍 가이드: {short(llm.get('timingGuidance'), 220)}")

    source_backed = llm.get("sourceBackedView") or []
    if source_backed:
        lines.append("")
        lines.append("### 누적 근거 관점")
        for item in source_backed[:3]:
            lines.append(f"- 결론: {item.get('claim')}")
            for evidence in (item.get("evidence") or [])[:3]:
                lines.append(f"  - 근거: {evidence}")

    lines.extend(
        [
            "",
            "## 작성 지침",
            "- 단순 뉴스 요약 금지",
            "- 1일 / 1주 / 1개월 / 3개월 / 6개월 해석을 구분",
            "- ISA / 토스증권 / 연금저축 계좌별 액션을 따로 적기",
            "- 매수/대기/축소를 명확히 쓰고, 분할매수 속도까지 적기",
            "- 반드시 누적 데이터 변화와 출처군(FRED, ECOS, OpenDART, 네이버 리서치, 증권사 리포트 등)을 근거로 연결하기",
            "",
            "## 원본 참조 파일",
            f"- 연구 컨텍스트: /Users/seo/igzun-daily-report/data/research_context/{date_str}.json",
            f"- 일간 결과: /Users/seo/igzun-daily-report/site/{date_str}/result.json",
            f"- 일간 LLM 결과: /Users/seo/igzun-daily-report/data/llm_insights/{date_str}.json",
            f"- horizon index: /Users/seo/igzun-daily-report/site/horizon_index.json",
            "",
            "## 권장 출력 형식",
            "1. 시장 총평",
            "2. 단기(1일/1주) 대응",
            "3. 중기(1개월/3개월/6개월) 전략",
            "4. 계좌별 액션 플랜",
            "5. ETF/섹터 아이디어",
            "6. 가장 중요한 리스크와 확인 포인트",
        ]
    )

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="")
    parser.add_argument("--base-dir", default=str(ROOT))
    args = parser.parse_args()

    root = Path(args.base_dir)
    date_str = args.date or latest_available_date(root)
    brief = build_brief(root, date_str)

    out_dir = root / "data" / "manual_summary"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{date_str}.md"
    out_file.write_text(brief)
    (out_dir / "latest.md").write_text(brief)

    print(f"wrote {out_file}")
    print(f"wrote {out_dir / 'latest.md'}")
    print()
    print("\n".join(brief.splitlines()[:40]))


if __name__ == "__main__":
    main()
