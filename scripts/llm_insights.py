#!/usr/bin/env python3
"""
LLM 인사이트 엔진 — Claude API를 이용한 투자 인사이트 생성.

수집된 뉴스/리서치/경제 데이터 + 매크로 분석 + 밸류에이션 + 시그널을
종합해 한국어 투자 인사이트를 생성합니다.

Output: data/llm_insights/{date}.json
"""
import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

# Load .env file
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


MAX_DOC_CHARS = 800  # 문서당 최대 문자수
MAX_DOCS = 15        # 최대 문서 수


def _load_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _load_jsonl(path: Path) -> list[dict]:
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


def _format_docs(docs: list[dict], max_docs: int = MAX_DOCS) -> str:
    """수집된 문서들을 프롬프트용 텍스트로 변환."""
    if not docs:
        return "(수집된 문서 없음)"

    # Priority: FED speeches, BIS, research reports > news
    priority_sources = {"fed_speeches_rss", "fed_press_rss", "bis_speeches",
                         "naver_research", "kr_brokerage_kb", "kr_brokerage_mirae"}
    priority = [d for d in docs if d.get("source_id") in priority_sources]
    others = [d for d in docs if d.get("source_id") not in priority_sources]
    ordered = (priority + others)[:max_docs]

    lines = []
    for i, doc in enumerate(ordered, 1):
        source = doc.get("source_id", "unknown")
        title = (doc.get("title") or "제목없음")[:80]
        date_str = doc.get("published_date", "")
        summary = (doc.get("summary") or doc.get("content") or "")[:MAX_DOC_CHARS]
        region = doc.get("region", "")
        lines.append(f"[{i}] [{source}] {date_str} | {region}\n제목: {title}\n내용: {summary}\n")

    return "\n".join(lines)


def _format_macro(macro: dict) -> str:
    """매크로 데이터를 텍스트로 변환."""
    if not macro:
        return "(매크로 데이터 없음)"

    mi = macro.get("macro_inputs", {}) or {}
    ti = macro.get("technical_inputs", {}) or {}
    lp = macro.get("latest_prices", {}) or {}
    scores = macro.get("scores", {}) or {}
    periods = macro.get("periods", []) or []

    def fmt(v, d=2): return f"{v:.{d}f}" if v is not None else "N/A"

    lines = [
        f"=== 매크로 현황 ({macro.get('date', 'N/A')}) ===",
        f"레짐: {macro.get('regime', 'N/A')} | 종합점수: {fmt(scores.get('total'))}",
        f"",
        f"[미국 거시지표]",
        f"  VIX: {fmt(mi.get('vix'), 1)} | 연준금리: {fmt(mi.get('fedfunds'))}% | 미 10년물: {fmt(mi.get('us10y'))}%",
        f"  달러지수(DXY): {fmt(mi.get('dxy'), 1)} | WTI: ${fmt(mi.get('oil'), 1)} | CPI레벨: {fmt(mi.get('cpi_level'), 1)}",
        f"  수익률커브(10Y-2Y): {fmt(mi.get('t10y2y_spread'))}% | HY스프레드: {fmt(mi.get('hy_spread'))}%",
        f"",
        f"[한국 거시지표]",
        f"  BOK 기준금리: {fmt(mi.get('bok_rate'))}% | USD/KRW: {fmt(mi.get('usd_krw'), 0)}원",
        f"",
        f"[현재 시장 가격]",
        f"  S&P500: {fmt(lp.get('sp500'), 0)} | KOSPI: {fmt(lp.get('kospi'), 0)} | 나스닥: {fmt(lp.get('nasdaq'), 0)}",
        f"  금: ${fmt(lp.get('gold'), 0)} | 니케이: {fmt(lp.get('nikkei'), 0)} | DAX: {fmt(lp.get('dax'), 0)}",
        f"",
        f"[기술적 지표]",
        f"  S&P500 RSI(14): {fmt(ti.get('rsi_sp500'), 1)} | 20/60일 이격도: {fmt(ti.get('ma_gap_sp500'))}%",
        f"  모멘텀 3M: {fmt(ti.get('momentum_3m'))}% | 12M: {fmt(ti.get('momentum_12m'))}% | 변동성: {fmt(ti.get('volatility_20d'))}%",
        f"  ADX: {fmt(ti.get('adx_sp500'))} | 니케이 3M 모멘텀: {fmt(ti.get('momentum_3m_nikkei'))}%",
    ]

    if periods:
        lines.append("")
        lines.append("[구간별 수익률]")
        for p in periods[:3]:
            r = p.get("returns", {})
            def r2(k): return f"{r.get(k):+.1f}%" if r.get(k) is not None else "N/A"
            lines.append(f"  {p['label']}: SP500={r2('sp500')} KOSPI={r2('kospi')} 나스닥={r2('nasdaq')} 금={r2('gold')} WTI={r2('wti')}")

    return "\n".join(lines)


def _format_signals(signals: dict) -> str:
    """신호 데이터 텍스트 변환."""
    if not signals:
        return "(신호 데이터 없음)"

    ms = signals.get("market_signal", {}) or {}
    top_buys = signals.get("top_buys", []) or []
    avoid = signals.get("avoid_list", []) or []
    summary = signals.get("summary", {}) or {}

    lines = [
        f"=== 매수/매도 신호 요약 ===",
        f"시장 신호: {ms.get('action')} (배포가능 {ms.get('deployable_pct')}%)",
        f"신호 분포: 강력매수 {summary.get('강력매수',0)}개 | 분할매수 {summary.get('분할매수',0)}개 | 관망 {summary.get('관망',0)}개 | 회피 {summary.get('회피',0)}개",
        f"",
        f"[상위 매수 추천]",
    ]
    for s in top_buys[:5]:
        lines.append(f"  {s['signal']} | {s['name']}({s['id']}) | 타이밍:{s.get('timing_grade','?')} | RSI:{s.get('rsi','N/A')}")
        reasons = s.get("reasons", [])
        if reasons:
            lines.append(f"    근거: {' | '.join(reasons[:2])}")

    if avoid:
        lines.append("")
        lines.append(f"[회피 ETF]")
        for s in avoid[:3]:
            lines.append(f"  {s['name']}({s['id']}) — {' | '.join(s.get('reasons', [])[:2])}")

    return "\n".join(lines)


def _format_valuation(valuation: dict) -> str:
    """밸류에이션 데이터 텍스트 변환."""
    if not valuation:
        return "(밸류에이션 데이터 없음)"

    sp = valuation.get("sp500", {}) or {}
    kospi = valuation.get("kospi", {}) or {}
    nas = valuation.get("nasdaq", {}) or {}
    gold = valuation.get("gold", {}) or {}
    summary = valuation.get("summary", {}) or {}

    def fmt(v, d=1):
        return f"{v:.{d}f}" if v is not None else "N/A"

    lines = [
        f"=== 밸류에이션 ===",
        f"시장 전반: {summary.get('market_valuation', 'N/A')}",
        f"",
        f"S&P500: {sp.get('valuation_grade','N/A')} | ERP {fmt(sp.get('erp_pct'))}% | PE {sp.get('estimated_pe','N/A')}x | 52W위치 {fmt(sp.get('range_52w_pct'))}%",
        f"KOSPI: {kospi.get('valuation_grade','N/A')} | PBR {kospi.get('estimated_pbr','N/A')}x | 52W위치 {fmt(kospi.get('range_52w_pct'))}%",
        f"나스닥: {nas.get('valuation_grade','N/A')} | ERP {fmt(nas.get('erp_pct'))}% | 52W위치 {fmt(nas.get('range_52w_pct'))}%",
        f"금: {gold.get('assessment', 'N/A')} | 52W위치 {fmt(gold.get('range_52w_pct'))}%",
    ]
    return "\n".join(lines)


def _format_portfolio(portfolio: dict, signals: dict) -> str:
    accounts = portfolio.get("accounts", {}) or {}
    total_cash = portfolio.get("total_cash", 0)
    plans = (signals.get("account_plans") or {}) if signals else {}

    lines = [
        "=== 현재 투자 가능 자금 ===",
        f"총 현금: {total_cash:,}원",
    ]
    for account_id, account in accounts.items():
        plan = plans.get(account_id, {}) or {}
        lines.append(
            f"- {account.get('label', account_id)}: 현금 {account.get('cash', 0):,}원"
            + (f" | 추천 집행 {plan.get('deploy_amount', 0):,}원" if plan else "")
        )
    return "\n".join(lines)


SYSTEM_PROMPT = """당신은 한국의 전문 투자 리서치 애널리스트입니다.

역할과 목적:
- 분석 대상: ISA(국내ETF), 토스증권(해외ETF), 연금저축 계좌에 투자하는 개인 투자자
- 투자 스타일: 3~6개월 중기 투자, 펀더멘탈 중심 + 기술적 보조
- 리스크 성향: 중간 (중위험·중수익 추구)
- 현재 상태: 전액 현금, 새로 투자 포지션 구축 중

분석 원칙:
1. 단순 뉴스 요약이 아닌 **투자 액션 관점**에서 분석하라
2. 모든 인사이트는 **지금 사야하는가, 사지 말아야 하는가, 기다려야 하는가**에 대한 답을 담아라
3. 레짐·밸류에이션·기술적 신호를 종합해 근거 있는 견해를 제시하라
4. 숫자와 구체적 근거를 반드시 포함하라
5. 한국어로 자연스럽게 작성하라 (전문 용어는 영어 병기 허용)"""


def _call_claude_api(prompt: str, api_key: str) -> str:
    """Claude API 호출."""
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
        thinking={"type": "adaptive"},
        output_config={"effort": "medium"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    # Extract text from response (skip thinking blocks)
    texts = []
    for block in response.content:
        if hasattr(block, "text"):
            texts.append(block.text)
    return "\n".join(texts)


def _parse_llm_response(text: str) -> dict:
    """LLM 응답을 구조화된 dict로 파싱."""
    # Try JSON parse first
    try:
        # Find JSON block
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except Exception:
        pass

    # Fallback: return raw text as narrative
    return {
        "market_narrative": text,
        "key_signals": [],
        "regime_assessment": "",
        "sector_calls": [],
        "risk_factors": [],
        "portfolio_comment": "",
        "timing_guidance": "",
    }


def build_prompt(macro: dict, docs: list[dict], signals: dict, valuation: dict, portfolio: dict, date_str: str) -> str:
    doc_text = _format_docs(docs)
    macro_text = _format_macro(macro)
    signals_text = _format_signals(signals)
    val_text = _format_valuation(valuation)
    portfolio_text = _format_portfolio(portfolio, signals)
    total_cash = portfolio.get("total_cash", 0)

    prompt = f"""오늘({date_str}) 기준 투자 분석을 수행해주세요.

{macro_text}

{val_text}

{signals_text}

{portfolio_text}

=== 수집된 뉴스/리서치 ({len(docs)}건) ===
{doc_text}

---

위 데이터를 종합해 다음 형식의 JSON으로 투자 분석을 작성해주세요.
(JSON만 출력하고, 마크다운 코드블록 없이 순수 JSON만 반환하세요)

{{
  "market_narrative": "현재 시장 상황을 3~5줄로 서술 (레짐, 핵심 드라이버, 방향성)",

  "regime_assessment": "레짐 판단 및 투자 함의 (2~3줄)",

  "key_signals": [
    "지금 당장 가장 중요한 투자 시그널 1 (숫자 포함)",
    "지금 당장 가장 중요한 투자 시그널 2",
    "지금 당장 가장 중요한 투자 시그널 3",
    "지금 당장 가장 중요한 투자 시그널 4",
    "지금 당장 가장 중요한 투자 시그널 5"
  ],

  "sector_calls": [
    {{"sector": "섹터/자산군명", "view": "매수가능/관망/비중축소", "rationale": "근거 한 줄"}},
    {{"sector": "섹터/자산군명", "view": "매수가능/관망/비중축소", "rationale": "근거 한 줄"}},
    {{"sector": "섹터/자산군명", "view": "매수가능/관망/비중축소", "rationale": "근거 한 줄"}},
    {{"sector": "섹터/자산군명", "view": "매수가능/관망/비중축소", "rationale": "근거 한 줄"}},
    {{"sector": "섹터/자산군명", "view": "매수가능/관망/비중축소", "rationale": "근거 한 줄"}}
  ],

  "risk_factors": [
    "가장 큰 리스크 요인 1 (구체적 수치 포함)",
    "가장 큰 리스크 요인 2",
    "가장 큰 리스크 요인 3"
  ],

  "timing_guidance": "지금 당장 투자를 시작해야 하는지, 기다려야 하는지, 분할 진입을 어떻게 해야 하는지 구체적으로 (3~4줄). 총 현금 약 {total_cash:,}원 기준.",

  "portfolio_comment": "ISA/토스/연금저축 3개 계좌 각각에 대한 이번 주 액션 플랜 (2~3줄씩)",

  "news_highlights": [
    "수집된 뉴스/리서치에서 가장 중요한 인사이트 1",
    "수집된 뉴스/리서치에서 가장 중요한 인사이트 2",
    "수집된 뉴스/리서치에서 가장 중요한 인사이트 3"
  ]
}}"""
    return prompt


def generate_fallback_insights(macro: dict, signals: dict, valuation: dict, portfolio: dict, docs: list[dict], date_str: str) -> dict:
    """API 키 없을 때 규칙 기반 인사이트 생성."""
    regime = macro.get("regime", "Neutral")
    total_score = (macro.get("scores") or {}).get("total") or 50
    mi = macro.get("macro_inputs", {}) or {}
    ms = (signals or {}).get("market_signal", {}) or {}
    vs = (valuation or {}).get("summary", {}) or {}
    sp_val = (valuation or {}).get("sp500", {}) or {}
    kospi_val = (valuation or {}).get("kospi", {}) or {}
    account_plans = (signals or {}).get("account_plans", {}) or {}
    total_cash = portfolio.get("total_cash", 0)

    vix = mi.get("vix") or 20
    us10y = mi.get("us10y") or 4.2
    usdkrw = mi.get("usd_krw") or 1350
    deploy = ms.get("deployable_pct", 30)

    regime_ko = {
        "Growth": "성장 국면",
        "Neutral": "중립 횡보 국면",
        "Stagflation/Recession": "스태그플레이션/경기침체 국면",
        "Inflationary": "인플레이션 국면",
        "Risk-Off DollarStrength": "달러 강세/위험회피 국면",
    }.get(regime, regime)

    # Market narrative
    narrative_parts = [f"현재 시장은 {regime_ko}에 위치하며 종합 점수 {total_score:.1f}점을 기록 중입니다."]
    if vix > 25:
        narrative_parts.append(f"VIX {vix:.1f}로 공포 지수가 높아 단기 변동성이 확대된 상황입니다.")
    elif vix < 15:
        narrative_parts.append(f"VIX {vix:.1f}로 시장이 안정적인 상태입니다.")
    if us10y > 4.5:
        narrative_parts.append(f"미 10년물 금리 {us10y:.2f}%는 주식 밸류에이션에 부담으로 작용 중입니다.")
    if usdkrw > 1400:
        narrative_parts.append(f"달러/원 {usdkrw:.0f}원은 원화 약세 기조로 국내 자산의 상대 수익률을 압박합니다.")

    # Key signals
    key_signals = []
    if vix > 30:
        key_signals.append(f"VIX {vix:.1f} — 공포 구간, 분할 매수 진입의 역발상 기회 가능")
    elif vix > 25:
        key_signals.append(f"VIX {vix:.1f} — 변동성 확대 구간, 추격매수보다 눌림목 분할 접근이 유리")
    erp = sp_val.get("erp_pct")
    if erp is not None:
        if erp > 2:
            key_signals.append(f"S&P500 주식위험프리미엄(ERP) {erp:.1f}% — 주식이 채권보다 매력적")
        elif erp < 0:
            key_signals.append(f"S&P500 ERP {erp:.1f}% — 채권 대비 주식 매력도 낮음, 선별 진입")
        else:
            key_signals.append(f"S&P500 ERP {erp:.1f}% — 주식 매력도는 중립 수준, 과속 진입은 부담")
    kospi_grade = kospi_val.get("valuation_grade")
    if kospi_grade in ("저평가",):
        key_signals.append(f"KOSPI 밸류에이션 {kospi_grade} — 국내 ETF 중장기 매수 논리 유효")
    elif kospi_grade in ("고평가", "다소 고평가"):
        key_signals.append(f"KOSPI 밸류에이션 {kospi_grade} — 국내 ETF는 비중을 천천히 올리는 편이 적절")
    range_52w = sp_val.get("range_52w_pct")
    if range_52w is not None and range_52w < 20:
        key_signals.append(f"S&P500 52주 레인지 {range_52w:.0f}% 위치 — 역사적 저점 근처")
    top_buys = (signals or {}).get("top_buys", [])
    if top_buys:
        best = top_buys[0]
        key_signals.append(f"{best['name']}({best['id']}) 타이밍 {best.get('timing_grade','?')} — 분할 매수 시작 고려")
    if usdkrw > 1450:
        key_signals.append(f"USD/KRW {usdkrw:.0f}원 — 원화 약세가 이어져 국내 위험자산 비중 확대 속도 조절 필요")
    if deploy <= 15:
        key_signals.append(f"시장 배치 가능 비중 {deploy}% — 지금은 전액 진입보다 1%~2% 단위의 탐색 매수가 적합")
    fallback_candidates = [
        f"레짐 {regime_ko} — 현금 비중을 남기고 확인 매수를 이어갈 구간",
        f"미 10년물 {us10y:.2f}% — 금리 부담이 남아 있어 고PER 자산은 추격보다 분할 접근이 유리",
        f"총점 {total_score:.1f}점 — 공격적 몰빵보다 핵심 ETF 위주의 선별 매수가 적절",
    ]
    for item in fallback_candidates:
        if len(key_signals) >= 5:
            break
        if item not in key_signals:
            key_signals.append(item)

    # Sector calls
    sector_calls = _regime_sector_calls(regime, mi)

    # Risk factors
    risks = []
    if vix > 25:
        risks.append(f"단기 변동성 리스크 — VIX {vix:.1f}로 급등락 가능성")
    if us10y > 4.5:
        risks.append(f"금리 리스크 — 미 10Y {us10y:.2f}%로 고금리 지속 시 주식 밸류에이션 압박")
    if usdkrw > 1430:
        risks.append(f"환율 리스크 — USD/KRW {usdkrw:.0f}원, 달러 강세 지속 시 원화 자산 압박")
    if regime in ("Stagflation/Recession",):
        risks.append("경기침체 리스크 — 실적 하향 조정 가능성, 디펜시브 자산 선호")
    if not risks:
        risks.append("정책 불확실성 — 연준 금리 경로와 지정학적 변수 주시 필요")

    # Timing guidance
    deploy_amount = int(total_cash * deploy / 100) if total_cash else 0
    timing_guidance = (
        f"현재 시장 신호 '{ms.get('action', '신중한 탐색')}'에 따라 전체 현금의 {deploy}%({deploy_amount:,.0f}원 수준)까지 "
        f"배치할 수 있는 환경입니다. "
        f"분할 진입 원칙을 준수하고 RSI 35~40 이하 구간을 활용한 역발상 매수를 권장합니다. "
        f"VIX 25 이상 고공포 구간에서의 소규모 탐색 진입이 중장기 수익률을 높이는 전략입니다."
    )

    # Portfolio comment
    portfolio_parts = []
    for account_id in ["ISA", "TOSS", "PENSION"]:
        account = (portfolio.get("accounts") or {}).get(account_id, {}) or {}
        plan = account_plans.get(account_id, {}) or {}
        picks = plan.get("top_picks") or []
        if picks:
            pick_summary = ", ".join(f"{p.get('name')}({p.get('signal')})" for p in picks[:2])
            portfolio_parts.append(
                f"{account.get('label', account_id)}: 현금 {account.get('cash', 0):,}원 중 {plan.get('deploy_amount', 0):,}원 범위에서 {pick_summary} 순으로 분할 집행"
            )
        else:
            portfolio_parts.append(
                f"{account.get('label', account_id)}: 당장은 신규 진입보다 현금 대기와 다음 신호 확인이 우선"
            )
    portfolio_comment = " ".join(portfolio_parts)
    highlights = []
    for doc in docs[:3]:
        title = (doc.get("title") or "").strip()
        source = doc.get("source_id") or "source"
        if title:
            highlights.append(f"[{source}] {title}")
    if not highlights:
        highlights = ["LLM API 미사용 상태라 규칙 기반 내러티브로 대체했습니다."]

    return {
        "date": date_str,
        "generated_by": "fallback_rule_based",
        "market_narrative": " ".join(narrative_parts),
        "regime_assessment": f"{regime_ko}으로 분류된 현재 환경은 {vs.get('market_valuation', '선별적 접근 권장')}.",
        "key_signals": key_signals[:5],
        "sector_calls": sector_calls,
        "risk_factors": risks[:3],
        "timing_guidance": timing_guidance,
        "portfolio_comment": portfolio_comment,
        "news_highlights": highlights,
    }


def _regime_sector_calls(regime: str, mi: dict) -> list[dict]:
    calls_map = {
        "Growth": [
            {"sector": "미국 대형 기술주 (QQQ)", "view": "매수가능", "rationale": "성장 레짐에서 기술주 모멘텀 강화"},
            {"sector": "S&P500 광범위 지수 (SPY)", "view": "매수가능", "rationale": "경기 확장 국면, 지수 투자 유효"},
            {"sector": "미국 금융 섹터 (XLF)", "view": "관망", "rationale": "금리 방향에 따른 수혜 여부 확인 필요"},
            {"sector": "미국 장기국채 (TLT)", "view": "비중축소", "rationale": "성장 레짐에서 채권 수요 감소"},
            {"sector": "금 (GLD)", "view": "비중축소", "rationale": "위험선호 환경에서 금 헤지 수요 감소"},
        ],
        "Stagflation/Recession": [
            {"sector": "금 (GLD/KODEX_GOLD)", "view": "매수가능", "rationale": "스태그플레이션 최적 헤지 자산"},
            {"sector": "미국 중기국채 (IEF)", "view": "매수가능", "rationale": "경기침체 대비 방어적 채권 비중 확대"},
            {"sector": "달러 ETF (UUP/KODEX_USD)", "view": "매수가능", "rationale": "경기침체 시 달러 강세 경향"},
            {"sector": "미국 기술주 (QQQ)", "view": "비중축소", "rationale": "경기침체 우려에 밸류에이션 프리미엄 축소"},
            {"sector": "이머징마켓 (EEM)", "view": "비중축소", "rationale": "글로벌 침체 국면에서 EM 먼저 타격"},
        ],
        "Inflationary": [
            {"sector": "에너지 섹터 (XLE)", "view": "매수가능", "rationale": "인플레이션 국면 원자재·에너지 강세"},
            {"sector": "금 (GLD/KODEX_GOLD)", "view": "매수가능", "rationale": "실물 인플레이션 헤지 최적 자산"},
            {"sector": "미국 장기국채 (TLT)", "view": "비중축소", "rationale": "인플레이션 지속 시 장기채 손실 위험"},
            {"sector": "나스닥 기술주 (QQQ)", "view": "관망", "rationale": "금리 상승 환경에서 고PER 기술주 부담"},
            {"sector": "이머징마켓 (EEM)", "view": "관망", "rationale": "달러 강세와 원자재 가격 혼조 영향 주시"},
        ],
        "Risk-Off DollarStrength": [
            {"sector": "달러 ETF (UUP/KODEX_USD)", "view": "매수가능", "rationale": "달러 강세 트렌드 직접 추적"},
            {"sector": "금 (GLD/KODEX_GOLD)", "view": "매수가능", "rationale": "위험회피 헤지 + 달러 보완 자산"},
            {"sector": "미국 단/중기국채 (IEF)", "view": "관망", "rationale": "안전자산 수요 있으나 금리 수준 부담"},
            {"sector": "이머징마켓 (EEM)", "view": "비중축소", "rationale": "달러 강세에 EM 자본 유출 압력"},
            {"sector": "KOSPI/한국 ETF", "view": "비중축소", "rationale": "원화 약세 + 수출 환경 불확실"},
        ],
        "Neutral": [
            {"sector": "S&P500 (SPY)", "view": "소규모탐색", "rationale": "중립 레짐, 밸류에이션 확인 후 분할 진입"},
            {"sector": "금 (GLD)", "view": "관망", "rationale": "방어 헤지로 5~8% 비중 검토 가능"},
            {"sector": "미국 중기국채 (IEF)", "view": "관망", "rationale": "금리 방향 확인 전 중립"},
            {"sector": "KOSPI (TIGER200)", "view": "소규모탐색", "rationale": "저밸류 국내 지수 소규모 탐색"},
            {"sector": "나스닥 (QQQ)", "view": "관망", "rationale": "기술주 실적 가이던스 확인 필요"},
        ],
    }
    return calls_map.get(regime, calls_map["Neutral"])


def run_llm_insights(root: Path, date_str: str) -> dict:
    macro_file = root / "data" / "macro_analysis" / f"{date_str}.json"
    signals_file = root / "data" / "signals" / f"{date_str}.json"
    val_file = root / "data" / "valuation" / f"{date_str}.json"
    docs_file = root / "data" / "normalized" / date_str / "documents.jsonl"
    portfolio_file = root / "data" / "portfolio_state.json"

    macro = _load_json(macro_file) or {}
    signals = _load_json(signals_file) or {}
    valuation = _load_json(val_file) or {}
    docs = _load_jsonl(docs_file)
    portfolio = _load_json(portfolio_file) or {}

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()

    if not api_key or not HAS_ANTHROPIC:
        reason = "anthropic 미설치" if not HAS_ANTHROPIC else "ANTHROPIC_API_KEY 미설정"
        print(f"  LLM API 없음 ({reason}) — 규칙 기반 인사이트 생성")
        result = generate_fallback_insights(macro, signals, valuation, portfolio, docs, date_str)
        result["api_used"] = False
        result["fallback_reason"] = reason
    else:
        print(f"  Claude API 호출 중... (문서 {len(docs)}건 기반)")
        try:
            prompt = build_prompt(macro, docs, signals, valuation, portfolio, date_str)
            raw_response = _call_claude_api(prompt, api_key)
            parsed = _parse_llm_response(raw_response)
            parsed["date"] = date_str
            parsed["api_used"] = True
            parsed["generated_by"] = "claude-opus-4-6"
            parsed["doc_count"] = len(docs)
            result = parsed
        except Exception as e:
            print(f"  Claude API 오류: {e} — 규칙 기반으로 대체")
            result = generate_fallback_insights(macro, signals, valuation, portfolio, docs, date_str)
            result["api_used"] = False
            result["api_error"] = str(e)

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--base-dir", default=str(ROOT))
    args = parser.parse_args()

    root = Path(args.base_dir)
    result = run_llm_insights(root, args.date)

    out_dir = root / "data" / "llm_insights"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{args.date}.json"
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"wrote {out_file}")

    print(f"\n[시장 내러티브]")
    print(result.get("market_narrative", ""))
    print(f"\n[타이밍 가이던스]")
    print(result.get("timing_guidance", ""))
    print(f"\n[핵심 신호 5가지]")
    for sig in result.get("key_signals", []):
        print(f"  • {sig}")


if __name__ == "__main__":
    main()
