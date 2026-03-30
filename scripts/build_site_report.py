#!/usr/bin/env python3
"""
시장 레짐/포트폴리오/ETF 아이디어 중심의 한국어 사이트 리포트 생성기.

Reads:
  - data/macro_analysis/{date}.json
  - data/etf_recommendations/{date}.json
  - data/normalized/{date}/documents.jsonl
  - data/portfolio_state.json

Writes:
  - site/{date}/result.json
  - site/{date}/index.html
  - site/date_status.json
"""

import argparse
import json
import shutil
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORTFOLIO_STATE_FILE = ROOT / "data" / "portfolio_state.json"

PERIODS = ["1일", "1주", "1개월", "3개월", "6개월"]
PERIOD_DAYS = {"1일": 1, "1주": 5, "1개월": 21, "3개월": 63, "6개월": 126}

REGIME_LABELS = {
    "Growth": "성장 국면",
    "Neutral": "중립 횡보 국면",
    "Stagflation/Recession": "스태그플레이션/경기침체 국면",
    "Inflationary": "인플레이션 국면",
    "Risk-Off DollarStrength": "달러 강세/위험회피 국면",
}

REGIME_ALLOC = {
    "Growth": {"주식": 0.65, "채권": 0.15, "원자재": 0.05, "현금": 0.15},
    "Stagflation/Recession": {"주식": 0.15, "채권": 0.25, "원자재": 0.35, "현금": 0.25},
    "Inflationary": {"주식": 0.30, "채권": 0.10, "원자재": 0.40, "현금": 0.20},
    "Risk-Off DollarStrength": {"주식": 0.20, "채권": 0.30, "원자재": 0.20, "현금": 0.30},
    "Neutral": {"주식": 0.45, "채권": 0.20, "원자재": 0.10, "현금": 0.25},
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
    "bis_speeches": "BIS 연설",
    "investing_com_rss": "Investing.com 뉴스",
    "sec_edgar": "SEC EDGAR",
}

ETF_NAME_OVERRIDES = {
    "XLE": "미국 에너지 섹터 ETF",
    "GLD": "금 ETF",
    "TLT": "미국 장기국채 ETF",
    "IEF": "미국 중기국채 ETF",
    "UUP": "달러 강세 ETF",
    "EZU": "유로존 ETF",
    "EWJ": "일본 ETF",
    "SPY": "S&P500 ETF",
    "QQQ": "나스닥100 ETF",
    "EEM": "이머징 ETF",
}

ACCOUNT_STRATEGY = {
    "ISA": {
        "note": "세제혜택 계좌로 국내 ETF 중심 배치",
        "ideas": ["TIGER 200", "KODEX 반도체", "KODEX 단기채권"],
    },
    "TOSS": {
        "note": "해외 ETF 접근성이 좋아 미국 자산 배치에 적합",
        "ideas": ["SPY", "GLD", "IEF"],
    },
    "PENSION": {
        "note": "연금저축은 장기 분산형 ETF 중심이 적합",
        "ideas": ["TIGER 미국나스닥100", "TIGER 200", "KODEX 미국채울트라30년(H)"],
    },
}

PERIOD_EXECUTION = {
    "1일": {
        "deploy_ratio": 0.18,
        "action_label": "탐색 매수",
        "question": "오늘 시점에서 바로 손을 대야 하는가",
        "portfolio_focus": "가격 위치와 변동성, 과매도 여부를 먼저 본다.",
        "guide": "당일 관점에서는 1차 진입만 허용하고 현금 비중을 크게 유지한다.",
    },
    "1주": {
        "deploy_ratio": 0.32,
        "action_label": "확인형 추가 매수",
        "question": "이번 주 흐름이 이어질 가능성이 있는가",
        "portfolio_focus": "정책 반응, 환율, 수급 흐름이 한 방향으로 모이는지 본다.",
        "guide": "주간 관점에서는 코어 ETF를 조금 더 늘리되 추세 확인 전 과열 테마 비중 확대는 자제한다.",
    },
    "1개월": {
        "deploy_ratio": 0.55,
        "action_label": "기본 비중 구축",
        "question": "월간 레짐을 기준으로 어떤 자산군을 중심에 둘 것인가",
        "portfolio_focus": "거시 레짐과 섹터 회전, 밸류에이션 부담을 함께 본다.",
        "guide": "월간 관점에서는 코어 자산군을 세우고 위성 테마는 보조로 붙인다.",
    },
    "3개월": {
        "deploy_ratio": 0.78,
        "action_label": "전략 비중 형성",
        "question": "3개월 후를 보며 어떤 포트폴리오를 만들어 둘 것인가",
        "portfolio_focus": "실적 가시성, 금리 방향, 달러 흐름을 기준으로 자산배분을 완성한다.",
        "guide": "3개월 관점에서는 목표 비중에 근접하게 배치하되 과열 섹터는 상한을 둔다.",
    },
    "6개월": {
        "deploy_ratio": 1.00,
        "action_label": "목표 비중 유지·리밸런싱",
        "question": "6개월 보유를 전제로 어떤 비중을 유지해야 하는가",
        "portfolio_focus": "중기 레짐 지속 여부와 과열 자산의 비중 조절이 핵심이다.",
        "guide": "6개월 관점에서는 단기 진입보다 목표 비중 유지와 월별 리밸런싱 규칙이 더 중요하다.",
    },
}

EXECUTION_RHYTHM = {
    "1일": {
        "label": "3거래일 분할매수",
        "tranches": [0.40, 0.30, 0.30],
        "cadence": "오늘 1차, 1~2거래일 내 눌림목에서 2차, 종가 기준 안정 확인 후 3차",
        "add_rule": "전일 대비 약세 또는 RSI 45 이하 재진입 구간에서 2차를 검토",
        "pause_rule": "장중 급등 추격, RSI 70 이상 과열, VIX 재급등 시 추가 진입 보류",
        "review_rule": "3거래일 안에 방향이 안 나오면 비중 확대를 멈추고 재평가",
    },
    "1주": {
        "label": "주간 3회 분할매수",
        "tranches": [0.45, 0.30, 0.25],
        "cadence": "주초 1차, 중반 데이터 확인 후 2차, 주말 전 추세 확인 후 3차",
        "add_rule": "환율 안정과 지수 저점 확인이 같이 나오면 추가",
        "pause_rule": "주초 급반등 뒤 거래량 둔화, 환율 재상승 시 추가 매수 보류",
        "review_rule": "주 후반까지 정책/수급 방향이 엇갈리면 다음 주로 이월",
    },
    "1개월": {
        "label": "4주 분할 구축",
        "tranches": [0.30, 0.25, 0.25, 0.20],
        "cadence": "매주 한 번씩 4회에 걸쳐 기본 비중을 완성",
        "add_rule": "주간 지표와 섹터 회전이 같은 방향일 때 추가",
        "pause_rule": "과열 섹터 단기 급등, 밸류에이션 부담 확대 시 속도 조절",
        "review_rule": "월말에 목표 비중 대비 초과·미달을 재점검",
    },
    "3개월": {
        "label": "6~8주 단계 구축",
        "tranches": [0.30, 0.25, 0.20, 0.15, 0.10],
        "cadence": "월간 이벤트와 실적 시즌을 보며 5단계로 구축",
        "add_rule": "금리와 달러 압력이 완화되고 실적 가시성이 살아날 때 추가",
        "pause_rule": "실적 가이던스 훼손, 장기금리 재상승 시 상위 테마도 비중 상한 유지",
        "review_rule": "월 1회 리밸런싱하며 과열 자산은 목표 비중을 넘기지 않음",
    },
    "6개월": {
        "label": "월별 리밸런싱 구축",
        "tranches": [0.22, 0.20, 0.20, 0.20, 0.18],
        "cadence": "월별 점검에 맞춰 천천히 구축하고 비중을 유지",
        "add_rule": "중기 레짐 유지와 펀더멘털 개선이 확인될 때만 추가",
        "pause_rule": "목표 비중 도달 후에는 추가 매수보다 리밸런싱 우선",
        "review_rule": "월말마다 코어/위성 비중을 재설정하고 과열 자산은 감액",
    },
}


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


def as_float(value):
    try:
        if value is None or value == "N/A":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_text(value, default="데이터 없음"):
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def pct(value, digits=1, default="데이터 없음"):
    number = as_float(value)
    if number is None:
        return default
    sign = "+" if number >= 0 else ""
    return f"{sign}{number:.{digits}f}%"


def money(value):
    number = as_float(value)
    if number is None:
        return "0원"
    return f"{int(round(number)):,}원"


def number(value, digits=2, default="데이터 없음"):
    num = as_float(value)
    if num is None:
        return default
    return f"{num:.{digits}f}"


def signed_arrow(value):
    num = as_float(value)
    if num is None:
        return "보합"
    if num > 0:
        return f"▲{num:.2f}%"
    if num < 0:
        return f"▼{abs(num):.2f}%"
    return "0.00%"


def score_status(score: float | None) -> tuple[int, str, str]:
    num = as_float(score)
    if num is None:
        return 50, "중립", "데이터가 제한적이라 중립 관점으로 해석합니다."
    rounded = int(round(num))
    if rounded >= 65:
        return rounded, "긍정", "위험자산 선호가 강화된 상태입니다."
    if rounded >= 45:
        return rounded, "중립", "상승·하락 재료가 혼재된 구간입니다."
    return rounded, "경계", "방어적 해석이 더 유효한 구간입니다."


def get_period_row(macro: dict, label: str) -> dict:
    for row in macro.get("periods", []):
        if row.get("label") == label:
            return row.get("returns", {}) or {}
    return {}


def get_ret(macro: dict, label: str, key: str):
    return get_period_row(macro, label).get(key)


def get_regime_label(regime: str) -> str:
    return REGIME_LABELS.get(regime, regime)


def classify_data_status(docs: list[dict], macro: dict, etf: dict) -> str:
    has_macro = bool(macro)
    has_etf = bool(etf)
    if has_macro and has_etf and len(docs) >= 5:
        return "full"
    if has_macro and has_etf:
        return "partial"
    if has_macro or has_etf or docs:
        return "sparse"
    return "empty"


def source_catalog(docs: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for doc in docs:
        sid = doc.get("source_id", "unknown")
        bucket = grouped.setdefault(
            sid,
            {
                "source_id": sid,
                "label": SOURCE_NAMES.get(sid, sid),
                "count": 0,
                "latest": "",
                "region": doc.get("region", ""),
                "sector": doc.get("sector", ""),
                "doc_type": doc.get("document_type", ""),
                "url": doc.get("url", ""),
                "titles": [],
            },
        )
        bucket["count"] += 1
        bucket["latest"] = max(bucket["latest"], doc.get("published_date", ""))
        title = safe_text(doc.get("title"), "")
        if title and len(bucket["titles"]) < 3:
            bucket["titles"].append(title)
        if not bucket["url"] and doc.get("url"):
            bucket["url"] = doc.get("url")

    items = []
    for bucket in grouped.values():
        count = bucket["count"]
        title = f"{bucket['label']} {count}건 수집"
        if bucket["titles"]:
            title += f" · 예시: {bucket['titles'][0][:40]}"
        items.append(
            {
                "label": bucket["label"],
                "source": bucket["source_id"],
                "title": title,
                "examples": bucket["titles"],
                "published_at": bucket["latest"],
                "region": bucket["region"],
                "sector": bucket["sector"],
                "doc_type": bucket["doc_type"],
                "url": bucket["url"],
                "count": count,
            }
        )
    items.sort(key=lambda item: (-item["count"], item["label"]))
    return items


def select_sources(catalog: list[dict], preferred: list[str] | None = None, limit: int = 4) -> list[dict]:
    preferred = preferred or []
    ordered = []
    used = set()
    for source_id in preferred:
        for item in catalog:
            if item["source"] == source_id and item["source"] not in used:
                ordered.append(item)
                used.add(item["source"])
    for item in catalog:
        if item["source"] in used:
            continue
        ordered.append(item)
        used.add(item["source"])
    return ordered[:limit]


def translate_etf_name(item: dict) -> str:
    ticker = item.get("ticker", "")
    if ticker in ETF_NAME_OVERRIDES:
        return ETF_NAME_OVERRIDES[ticker]
    if item.get("id") in ETF_NAME_OVERRIDES:
        return ETF_NAME_OVERRIDES[item["id"]]
    return safe_text(item.get("name"))


def theme_from_etf(item: dict) -> str:
    ticker = item.get("ticker", "")
    asset_type = item.get("type", "")
    if "commodity" in asset_type or ticker in {"GLD", "KODEX_GOLD"}:
        return "인플레이션/불확실성 헤지"
    if "bond" in asset_type:
        return "방어형 채권"
    if "tech" in asset_type:
        return "기술주 반등"
    if ticker in {"XLE"}:
        return "에너지 강세"
    if item.get("region") == "KR":
        return "한국 주식"
    if item.get("region") == "JP":
        return "일본 분산"
    if item.get("region") == "EU":
        return "유럽 분산"
    return "지수 분산"


def etf_action_label(tier: str) -> str:
    return {
        "강력매수": "우선 검토",
        "매수": "관심 확대",
        "중립": "관찰 유지",
        "비중축소": "진입 보류",
        "회피": "회피",
    }.get(tier, "관찰 유지")


def etf_logo(item: dict) -> str:
    asset_type = item.get("type", "")
    if "commodity" in asset_type:
        return "🪙"
    if "bond" in asset_type:
        return "🏦"
    if item.get("region") == "KR":
        return "🇰🇷"
    if item.get("region") == "JP":
        return "🇯🇵"
    if item.get("region") == "EU":
        return "🇪🇺"
    return "📈"


def period_profile(period: str) -> dict:
    return PERIOD_EXECUTION.get(period, PERIOD_EXECUTION["1개월"])


def execution_rhythm(period: str) -> dict:
    return EXECUTION_RHYTHM.get(period, EXECUTION_RHYTHM["1개월"])


def split_amounts(total_amount: int, tranches: list[float]) -> list[int]:
    if total_amount <= 0 or not tranches:
        return []
    raw = [int(total_amount * ratio) for ratio in tranches]
    remainder = total_amount - sum(raw)
    for idx in range(remainder):
        raw[idx % len(raw)] += 1
    return raw


def ordinal_kr(index: int) -> str:
    return f"{index + 1}차"


def execution_step_lines(period: str, amount: int) -> list[str]:
    rules = execution_rhythm(period)
    amounts = split_amounts(amount, rules["tranches"])
    if not amounts:
        return []
    lines = []
    for idx, tranche_amount in enumerate(amounts):
        label = ordinal_kr(idx)
        if idx == 0:
            note = "초기 진입 물량으로 가격 확인에 집중"
        elif idx == len(amounts) - 1:
            note = "추세 확인 뒤 마지막 물량만 배치"
        else:
            note = "확인 매수로 평균단가와 방향성을 동시에 점검"
        lines.append(f"{label} {money(tranche_amount)} — {note}")
    return lines


def total_position_hint(item: dict) -> str:
    item_type = safe_text(item.get("type"), "").lower()
    if "bond" in item_type:
        return "총 투자금의 12~20% 범위 코어 방어축"
    if "commodity" in item_type:
        return "총 투자금의 8~12% 범위 헤지 축"
    if "sector" in item_type:
        return "총 투자금의 6~12% 범위 위성 테마"
    return "총 투자금의 15~25% 범위 코어 자산"


def idea_role_text(item: dict) -> str:
    item_type = safe_text(item.get("type"), "").lower()
    if "bond" in item_type:
        return "변동성 완충과 금리 하락 수혜를 노리는 방어 축입니다."
    if "commodity" in item_type:
        return "인플레이션·지정학 리스크를 막아주는 헤지 축입니다."
    if "sector" in item_type:
        return "레짐이 맞을 때 알파를 더하는 위성 테마 축입니다."
    return "포트폴리오 중심에 놓는 코어 지수 축입니다."


def idea_macro_context(item: dict, macro: dict) -> str:
    mi = macro.get("macro_inputs", {}) or {}
    item_type = safe_text(item.get("type"), "").lower()
    ticker = safe_text(item.get("ticker"), "")
    if "bond" in item_type:
        return (
            f"연준 {number(mi.get('fedfunds'), 2)}%, 미 10년물 {number(mi.get('us10y'), 2)}% 환경에서는 "
            f"채권 ETF가 방어와 금리 피크아웃 기대를 동시에 반영합니다."
        )
    if "commodity" in item_type or ticker in {"GLD", "XLE"}:
        return (
            f"유가 {number(mi.get('oil'), 2)}, 달러 {number(mi.get('dxy'), 1)} 조합은 "
            f"원자재 자산에 헤지 또는 전술적 강세 논리를 제공합니다."
        )
    if item.get("region") == "KR":
        return (
            f"원/달러 {number(mi.get('usd_krw'), 0)}원, 한국 기준금리 {number(mi.get('bok_rate'), 2)}%를 감안하면 "
            f"한국 ETF는 환율 부담과 수출주 강세를 함께 읽어야 합니다."
        )
    if item.get("region") == "JP":
        return "일본 ETF는 미국 단일 집중을 줄이면서 엔화·수출주 민감도 분산 역할을 합니다."
    if item.get("region") == "EU":
        return "유럽 ETF는 미국 기술주 편중을 낮추고 경기민감 업종 회복을 분산해서 담는 수단입니다."
    return (
        f"달러 {number(mi.get('dxy'), 1)}, 금리 {number(mi.get('us10y'), 2)}%, 변동성 {number(mi.get('vix'), 1)} 환경에서 "
        f"코어 지수 ETF는 종목 선택 리스크를 줄이는 기본 축으로 유효합니다."
    )


def source_item(label: str, source: str, title: str, published_at: str = "") -> dict:
    return {
        "label": label,
        "source": source,
        "title": title,
        "published_at": published_at,
    }


def source_bundle(period: str, macro: dict, etf: dict, portfolio_state: dict) -> list[dict]:
    return [
        source_item("퀀트 레짐", "macro_analysis", f"{period} 레짐 분석", macro.get("date", "")),
        source_item("ETF 추천", "etf_recommender", f"{period} ETF 점수화", etf.get("date", "")),
        source_item("포트폴리오 상태", "portfolio_state", "계좌별 현금 및 보유자산", portfolio_state.get("updated", "")),
    ]


def rsi_comment(rsi_value) -> str:
    rsi = as_float(rsi_value)
    if rsi is None:
        return "RSI 데이터가 제한적입니다."
    if rsi >= 75:
        return "단기 과열 구간이라 추격매수보다 분할 접근이 적합합니다."
    if rsi >= 60:
        return "추세는 양호하지만 신규 진입은 분할이 유리합니다."
    if rsi <= 30:
        return "과매도 영역이라 기술적 반등 후보로 볼 수 있습니다."
    return "극단적 과열·과매도는 아니어서 레짐 해석과 함께 보는 편이 좋습니다."


def asset_class_from_etf(item: dict) -> str:
    asset_type = safe_text(item.get("type"), "").lower()
    if "bond" in asset_type:
        return "채권"
    if "commodity" in asset_type:
        return "원자재"
    if "fx_" in asset_type:
        return "현금"
    return "주식"


def pick_etf(ranked: list[dict], exclude: set[str] | None = None, regions: set[str] | None = None, type_tokens: tuple[str, ...] = ()) -> dict | None:
    exclude = exclude or set()
    regions = regions or set()
    for item in ranked:
        if safe_text(item.get("ticker"), "") in exclude:
            continue
        if regions and item.get("region") not in regions:
            continue
        item_type = safe_text(item.get("type"), "").lower()
        if type_tokens and not any(token in item_type for token in type_tokens):
            continue
        return item
    return None


def allocation_desc(asset: str) -> str:
    return {
        "주식": "코어 지수와 선택 섹터를 담아 중기 상승 복원에 대응",
        "채권": "고금리 구간의 방어와 분산 역할",
        "원자재": "금·에너지로 인플레이션과 지정학 리스크 헤지",
        "현금": "추가 조정과 재진입 기회를 위한 대기 자금",
    }.get(asset, "")


def metric_chip(label: str, value: str, tone: str = "default") -> dict:
    return {"label": label, "value": value, "tone": tone}


def build_score_chips(macro: dict) -> list[dict]:
    scores = macro.get("scores", {}) or {}
    return [
        metric_chip("총점", f"{number(scores.get('total'), 1)}점", "score"),
        metric_chip("매크로", f"{number(scores.get('macro'), 1)}점", "score"),
        metric_chip("기술", f"{number(scores.get('technical'), 1)}점", "score"),
        metric_chip("퀀트", f"{number(scores.get('quant'), 1)}점", "score"),
        metric_chip("FX", f"{number(scores.get('fx'), 1)}점", "score"),
    ]


def build_metric_chips(period: str, macro: dict) -> list[dict]:
    mi = macro.get("macro_inputs", {}) or {}
    ti = macro.get("technical_inputs", {}) or {}
    if period == "1일":
        return [
            metric_chip("VIX", number(mi.get("vix"), 1), "risk"),
            metric_chip("RSI", number(ti.get("rsi_sp500"), 1), "signal"),
            metric_chip("S&P500", pct(get_ret(macro, period, "sp500")), "market"),
            metric_chip("NASDAQ", pct(get_ret(macro, period, "nasdaq")), "market"),
            metric_chip("DXY", number(mi.get("dxy"), 1), "macro"),
            metric_chip("미10년물", f"{number(mi.get('us10y'), 2)}%", "macro"),
        ]
    if period == "1주":
        return [
            metric_chip("S&P500 1주", pct(get_ret(macro, period, "sp500")), "market"),
            metric_chip("KOSPI 1주", pct(get_ret(macro, period, "kospi")), "market"),
            metric_chip("USD/KRW", number(mi.get("usd_krw"), 0), "macro"),
            metric_chip("HY 스프레드", number(mi.get("hy_spread"), 2), "risk"),
            metric_chip("유가 1주", pct(get_ret(macro, period, "wti")), "macro"),
            metric_chip("상대강도", number(ti.get("rel_strength_sp500_vs_kospi"), 2), "signal"),
        ]
    if period == "1개월":
        return [
            metric_chip("S&P500 1개월", pct(get_ret(macro, period, "sp500")), "market"),
            metric_chip("KOSPI 1개월", pct(get_ret(macro, period, "kospi")), "market"),
            metric_chip("금 1개월", pct(get_ret(macro, period, "gold")), "macro"),
            metric_chip("유가 1개월", pct(get_ret(macro, period, "wti")), "macro"),
            metric_chip("원/달러", number(mi.get("usd_krw"), 0), "macro"),
            metric_chip("3M 모멘텀", pct(ti.get("momentum_3m")), "signal"),
        ]
    if period == "3개월":
        return [
            metric_chip("S&P500 3개월", pct(get_ret(macro, period, "sp500")), "market"),
            metric_chip("KOSPI 3개월", pct(get_ret(macro, period, "kospi")), "market"),
            metric_chip("닛케이 3개월", pct(get_ret(macro, period, "nikkei")), "market"),
            metric_chip("DAX 3개월", pct(get_ret(macro, period, "dax")), "market"),
            metric_chip("기준금리", f"{number(mi.get('fedfunds'), 2)}%", "macro"),
            metric_chip("원화", number(mi.get("usd_krw"), 0), "macro"),
        ]
    return [
        metric_chip("S&P500 6개월", pct(get_ret(macro, period, "sp500")), "market"),
        metric_chip("KOSPI 6개월", pct(get_ret(macro, period, "kospi")), "market"),
        metric_chip("금 6개월", pct(get_ret(macro, period, "gold")), "macro"),
        metric_chip("유가 6개월", pct(get_ret(macro, period, "wti")), "macro"),
        metric_chip("10Y-2Y", number(mi.get("t10y2y_spread"), 2), "risk"),
        metric_chip("12M 모멘텀", pct(ti.get("momentum_12m")), "signal"),
    ]


def build_period_forecast(period: str, macro: dict, regime: str, catalog: list[dict]) -> dict:
    sp = pct(get_ret(macro, period, "sp500"))
    kospi = pct(get_ret(macro, period, "kospi"))
    nasdaq = pct(get_ret(macro, period, "nasdaq"))
    nikkei = pct(get_ret(macro, period, "nikkei"))
    dax = pct(get_ret(macro, period, "dax"))
    gold = pct(get_ret(macro, period, "gold"))
    oil = pct(get_ret(macro, period, "wti"))
    mi = macro.get("macro_inputs", {}) or {}
    ti = macro.get("technical_inputs", {}) or {}
    regime_kr = get_regime_label(regime)
    profile = period_profile(period)

    if period in {"1일", "1주"}:
        title = f"{period} 단기 방향성"
        text = (
            f"{period} 기준 미국은 S&P500 {sp}, NASDAQ {nasdaq}, 한국은 KOSPI {kospi}, 일본은 닛케이 {nikkei}, 유럽 DAX {dax} 흐름입니다. "
            f"지금 시장은 {regime_kr}으로 해석되며, VIX {number(mi.get('vix'), 1)}, DXY {number(mi.get('dxy'), 1)}, "
            f"미 10년물 {number(mi.get('us10y'), 2)}%, 원/달러 {number(mi.get('usd_krw'), 0)}원이 단기 의사결정의 핵심 축입니다. "
            f"{profile['guide']} 기술적으로는 RSI {number(ti.get('rsi_sp500'), 1)} 수준이라 {rsi_comment(ti.get('rsi_sp500'))}"
        )
    else:
        title = f"{period} 중기 방향성"
        text = (
            f"{period} 관점에서는 단일 기사보다 금리, 달러, 실적과 밸류에이션 부담이 어떤 레짐으로 굳어지는지가 중요합니다. "
            f"S&P500 {sp}, KOSPI {kospi}, 닛케이 {nikkei}, DAX {dax}, 금 {gold}, 유가 {oil} 흐름을 함께 보면 "
            f"지금은 {regime_kr} 성격이 강합니다. 따라서 3~6개월 투자에서는 추격매수보다 목표 비중을 세우고, "
            f"금리와 환율이 완화되는지를 보며 코어 ETF와 위성 테마의 비중을 조절하는 접근이 유효합니다."
        )

    return {
        "title": title,
        "text": text,
        "sources": select_sources(catalog, ["fred_api", "ecos_api", "opendart", "naver_research"], 4),
    }


def build_market_strategy_block(period: str, macro: dict, etf: dict, portfolio_state: dict, catalog: list[dict]) -> dict:
    regime = macro.get("regime", "Neutral")
    regime_kr = get_regime_label(regime)
    profile = period_profile(period)
    mi = macro.get("macro_inputs", {}) or {}
    ti = macro.get("technical_inputs", {}) or {}
    ranked = (etf.get("recommendations") or [])[:3]
    top_names = ", ".join(translate_etf_name(item) for item in ranked) if ranked else "ETF 후보 데이터가 제한적입니다."
    total_cash = money(portfolio_state.get("total_cash"))

    dollar_pressure = "높음" if (as_float(mi.get("dxy")) or 0) >= 105 or (as_float(mi.get("usd_krw")) or 0) >= 1450 else "보통"
    rate_pressure = "높음" if (as_float(mi.get("us10y")) or 0) >= 4.2 else "보통"
    inflation_note = "재상승 부담" if (as_float(mi.get("oil")) or 0) >= 70 else "안정권"

    considerations = [
        {
            "title": "금리와 할인율",
            "text": (
                f"연준 기준금리 {number(mi.get('fedfunds'), 2)}%, 미 10년물 {number(mi.get('us10y'), 2)}% 조합은 "
                f"성장주 밸류에이션에 아직 부담입니다. {period} 시점에서는 금리 하락이 확인되기 전까지 "
                f"방어형 채권과 현금 비중의 역할을 무시하면 안 됩니다."
            ),
        },
        {
            "title": "달러와 원화",
            "text": (
                f"DXY {number(mi.get('dxy'), 1)}, 원/달러 {number(mi.get('usd_krw'), 0)}원으로 달러 압력은 {dollar_pressure}입니다. "
                f"한국 위험자산은 환율 부담이 남아 있어 지수 전체보다 수출주·반도체·달러 수혜 자산으로 압축해서 보는 편이 낫습니다."
            ),
        },
        {
            "title": "원자재와 인플레이션",
            "text": (
                f"유가 {number(mi.get('oil'), 2)}, 금리 스프레드와 함께 보면 인플레이션 이슈는 {inflation_note}입니다. "
                f"그래서 금 ETF는 헤지, 에너지 ETF는 전술 아이디어로 분리해서 해석해야 합니다."
            ),
        },
        {
            "title": "기술적 위치",
            "text": (
                f"RSI {number(ti.get('rsi_sp500'), 1)}, 3개월 모멘텀 {pct(ti.get('momentum_3m'))}, ADX {number(ti.get('adx_sp500'), 1)}를 보면 "
                f"{rsi_comment(ti.get('rsi_sp500'))}"
            ),
        },
        {
            "title": "투자 방향성",
            "text": (
                f"{period} 관점의 질문은 '{profile['question']}' 입니다. 현재는 {regime_kr} 구간이므로 "
                f"{profile['guide']} 보유 현금 {total_cash}는 한 번에 쓰기보다 코어 ETF와 방어 자산에 나눠 넣고, "
                f"상위 아이디어 {top_names} 는 코어/위성 비중을 나눠 접근하는 편이 좋습니다."
            ),
        },
    ]

    summary_by_period = {
        "1일": (
            f"오늘은 변동성, 금리, 달러 압력이 동시에 높은 날인지 확인하는 단계입니다. "
            f"즉시 강하게 베팅하기보다 과매도 반등 여부와 당일 뉴스 충격의 지속성을 먼저 확인해야 합니다."
        ),
        "1주": (
            f"이번 주는 단순 하루 반등보다 정책 반응과 환율, 수급이 같은 방향으로 이어지는지를 확인하는 단계입니다. "
            f"즉시 풀베팅보다 코어 ETF를 늘릴 명분이 생기는지 점검해야 합니다."
        ),
        "1개월": (
            f"한 달 관점에서는 월간 레짐과 섹터 회전이 더 중요합니다. "
            f"금리 부담, 달러 압력, 원자재 흐름을 같이 보며 어떤 자산군을 중심 비중으로 둘지를 결정해야 합니다."
        ),
        "3개월": (
            f"3개월 관점에서는 실적 가시성과 금리 방향이 자산배분을 좌우합니다. "
            f"코어 ETF와 방어 자산의 틀을 만들고, 과열 테마는 위성 비중으로 제한하는 것이 핵심입니다."
        ),
        "6개월": (
            f"6개월 관점에서는 지금 무엇을 살지보다 어떤 비중을 유지하고 어떤 과열 자산을 줄일지가 더 중요합니다. "
            f"목표 비중과 리밸런싱 규칙을 먼저 세우는 접근이 유효합니다."
        ),
    }

    return {
        "title": f"{period}에서 보는 현재 변수와 투자 방향",
        "summary": summary_by_period.get(period, summary_by_period["1개월"]),
        "considerations": considerations,
        "sources": select_sources(catalog, ["fred_api", "ecos_api", "fed_speeches_rss", "naver_research"], 4) + source_bundle(period, macro, etf, portfolio_state)[:1],
    }


def build_period_insights(period: str, macro: dict, etf: dict, portfolio_state: dict, catalog: list[dict]) -> list[dict]:
    regime = macro.get("regime", "Neutral")
    regime_kr = get_regime_label(regime)
    scores = macro.get("scores", {}) or {}
    mi = macro.get("macro_inputs", {}) or {}
    ti = macro.get("technical_inputs", {}) or {}
    total_cash = int(as_float(portfolio_state.get("total_cash")) or 0)
    alloc = REGIME_ALLOC.get(regime, REGIME_ALLOC["Neutral"])

    sp = get_ret(macro, period, "sp500")
    kospi = get_ret(macro, period, "kospi")
    nasdaq = get_ret(macro, period, "nasdaq")
    nikkei = get_ret(macro, period, "nikkei")
    dax = get_ret(macro, period, "dax")
    gold = get_ret(macro, period, "gold")
    oil = get_ret(macro, period, "wti")

    top_etfs = (etf.get("recommendations") or [])[:3]
    top_names = ", ".join(translate_etf_name(item) for item in top_etfs) if top_etfs else "추천 ETF 데이터 없음"
    first_step = int(total_cash * 0.3)

    horizon_opening = {
        "1일": (
            f"1일 관점의 질문은 '오늘 바로 진입할 근거가 있는가' 입니다. "
            f"따라서 뉴스 충격, 변동성, 과매도 반등 가능성을 먼저 봐야 합니다."
        ),
        "1주": (
            f"1주 관점의 질문은 '이번 주의 반응이 추세로 이어질 수 있는가' 입니다. "
            f"정책 반응, 환율, 수급이 같은 방향으로 이어지는지 확인하는 것이 핵심입니다."
        ),
        "1개월": (
            f"1개월 관점에서는 월간 레짐이 어떤 자산군을 중심에 두라고 말하는지가 중요합니다. "
            f"지수의 단기 흔들림보다 섹터 회전과 자산군 상대강도를 더 중시해야 합니다."
        ),
        "3개월": (
            f"3개월 관점에서는 실적 가시성과 금리 방향을 토대로 코어 비중을 구축해야 합니다. "
            f"따라서 ETF 선택보다 자산배분의 큰 틀을 먼저 정하는 편이 맞습니다."
        ),
        "6개월": (
            f"6개월 관점에서는 지금 무엇을 살지보다 어느 자산이 과해졌을 때 줄일지까지 포함해 판단해야 합니다. "
            f"매수 신호가 있어도 최종 비중 상한은 별도로 관리해야 합니다."
        ),
    }

    insights = [
        {
            "category": "관점",
            "text": horizon_opening.get(period, horizon_opening["1개월"]),
            "sources": source_bundle(period, macro, etf, portfolio_state),
        },
        {
            "category": "레짐",
            "text": (
                f"{period} 기준 시장 레짐은 {regime_kr}입니다. "
                f"총점 {number(scores.get('total'), 1)} / 매크로 {number(scores.get('macro'), 1)} / "
                f"기술 {number(scores.get('technical'), 1)} / 퀀트 {number(scores.get('quant'), 1)} / FX {number(scores.get('fx'), 1)}."
            ),
            "sources": [{"label": "퀀트 레짐", "source": "macro_analysis", "title": f"{period} 레짐 분석", "published_at": macro.get("date", "")}],
        },
        {
            "category": "미국",
            "text": (
                f"미국 증시는 {period} 기준 S&P500 {pct(sp)}, NASDAQ {pct(nasdaq)}입니다. "
                f"RSI {number(ti.get('rsi_sp500'), 1)}, MA 갭 {pct(ti.get('ma_gap_sp500'))}, ADX {number(ti.get('adx_sp500'), 1)}를 보면 "
                f"{'기술적 반등 여지는 있지만 추세 전환 확인은 더 필요합니다.' if (as_float(ti.get('rsi_sp500')) or 50) < 35 else '추세 추종보다 선별 접근이 유효합니다.'}"
            ),
            "sources": select_sources(catalog, ["fred_api"], 2),
        },
        {
            "category": "한국",
            "text": (
                f"한국 시장은 {period} 기준 KOSPI {pct(kospi)}입니다. "
                f"원/달러 {number(mi.get('usd_krw'), 0)}원, 기준금리 {number(mi.get('bok_rate'), 2)}%는 외국인 수급과 밸류에이션에 직접 영향을 줍니다. "
                f"원화 약세가 길어질수록 지수 전반보다 수출주·반도체와 방어형 자산을 함께 보는 편이 유리합니다."
            ),
            "sources": select_sources(catalog, ["ecos_api", "opendart", "naver_research"], 3),
        },
        {
            "category": "환율",
            "text": (
                f"달러인덱스 DXY {number(mi.get('dxy'), 1)}, 원/달러 {number(mi.get('usd_krw'), 0)}원은 "
                f"{'국내 위험자산에 부담' if (as_float(mi.get('dxy')) or 0) >= 105 else '환율 부담 완화'}으로 해석됩니다. "
                f"환율이 높은 구간에서는 환노출 미국 ETF는 비중을 천천히 늘리고, 환헤지 상품과 현금 완충을 함께 가져가는 편이 안전합니다."
            ),
            "sources": select_sources(catalog, ["fred_api", "ecos_api"], 2),
        },
        {
            "category": "금리",
            "text": (
                f"연준 기준금리 {number(mi.get('fedfunds'), 2)}%, 미 10년물 {number(mi.get('us10y'), 2)}%, "
                f"하이일드 스프레드 {number(mi.get('hy_spread'), 2)}%p 조합은 아직 완전한 위험선호 복귀보다 '고금리 적응 구간'에 가깝습니다. "
                f"이 구간에서는 장기채 추격보다 중기채·단기채가 더 안정적입니다."
            ),
            "sources": select_sources(catalog, ["fred_api"], 2),
        },
        {
            "category": "원자재",
            "text": (
                f"금은 {period} {pct(gold)}, 유가는 {period} {pct(oil)}입니다. "
                f"유가 상승은 인플레이션 재자극과 비용 부담을 뜻하고, 금 강세는 위험회피 또는 통화가치 방어 수요를 시사합니다. "
                f"따라서 금 ETF는 헤지 자산, 에너지는 전술적 아이디어로 구분해 해석해야 합니다."
            ),
            "sources": select_sources(catalog, ["fred_api", "bis_speeches", "investing_com_rss"], 3),
        },
        {
            "category": "해외분산",
            "text": (
                f"일본 {pct(nikkei)}, 유럽 DAX {pct(dax)} 흐름을 보면 지역별 체력 차이가 있습니다. "
                f"미국이 흔들릴 때 일본·유럽 ETF를 소규모 섞으면 포트폴리오 변동성을 낮추는 데 도움이 됩니다."
            ),
            "sources": select_sources(catalog, ["investing_com_rss", "bis_speeches"], 2),
        },
        {
            "category": "ETF아이디어",
            "text": (
                f"현재 레짐에서 우선 체크할 ETF 후보는 {top_names}입니다. "
                f"개별 종목 추격보다 지수·섹터 ETF로 접근하면 레짐 변화에 대응하기 쉽습니다."
            ),
            "sources": [{"label": "ETF 추천", "source": "etf_recommender", "title": f"{period} ETF 아이디어", "published_at": etf.get("date", "")}],
        },
        {
            "category": "포트폴리오",
            "text": (
                f"총 현금 {money(total_cash)} 기준 권장 배분은 주식 {int(alloc['주식']*100)}% / 채권 {int(alloc['채권']*100)}% / "
                f"원자재 {int(alloc['원자재']*100)}% / 현금 {int(alloc['현금']*100)}%입니다. "
                f"한 번에 전액 진입보다 1차 {money(first_step)}를 먼저 배치하고 나머지는 변동성 완화 시점에 나누는 편이 적합합니다."
            ),
            "sources": [{"label": "포트폴리오 상태", "source": "portfolio_state", "title": "계좌별 현금 현황", "published_at": portfolio_state.get("updated", "")}],
        },
    ]

    if period == "1일":
        insights.append(
            {
                "category": "당일판단",
                "text": (
                    f"당일 시점에서는 VIX {number(mi.get('vix'), 1)}, RSI {number(ti.get('rsi_sp500'), 1)}, 원/달러 {number(mi.get('usd_krw'), 0)}원이 "
                    f"즉시 진입 강도를 결정합니다. 오늘은 소액 탐색 매수만 허용하고, 확인 전 대규모 진입은 보류하는 해석이 적합합니다."
                ),
                "sources": select_sources(catalog, ["fred_api", "ecos_api"], 2),
            }
        )
    if period == "1주":
        insights.append(
            {
                "category": "주간흐름",
                "text": (
                    f"주간 시점에서는 S&P500 {pct(sp)}, KOSPI {pct(kospi)}, 원/달러 {number(mi.get('usd_krw'), 0)}원 흐름을 함께 봐야 합니다. "
                    f"즉, 하루 반등보다 이번 주 동안 수급과 환율 부담이 완화되는지 확인한 뒤 코어 ETF 비중 확대를 판단해야 합니다."
                ),
                "sources": select_sources(catalog, ["fred_api", "ecos_api", "naver_research"], 3),
            }
        )
    if period == "1개월":
        insights.append(
            {
                "category": "월간레짐",
                "text": (
                    f"월간 시점에서는 S&P500 {pct(sp)}, KOSPI {pct(kospi)}, 금 {pct(gold)}, 유가 {pct(oil)} 흐름을 같이 봐야 자산군 상대강도가 보입니다. "
                    f"그래서 1개월 관점에서는 단기 타이밍보다 코어 자산군 구성과 섹터 로테이션 판단이 더 중요합니다."
                ),
                "sources": select_sources(catalog, ["fred_api", "ecos_api", "bis_speeches"], 3),
            }
        )
    if period in {"3개월", "6개월"}:
        insights.append(
            {
                "category": "중기판단",
                "text": (
                    f"{period} 관점의 핵심은 단기 뉴스의 강도가 아니라 레짐 지속 여부입니다. "
                    f"3~6개월 투자에서는 펀더멘털 방향성과 기술적 훼손 여부를 함께 보고, "
                    f"금리·달러가 꺾이기 전까지는 공격적 풀베팅보다 바벨형 자산배분이 더 적절합니다."
                ),
                "sources": select_sources(catalog, ["fred_api", "ecos_api", "naver_research"], 3),
            }
        )

    return insights[:10]


def build_indices(period: str, macro: dict) -> list[dict]:
    latest = macro.get("latest_prices", {}) or {}
    items = [
        ("S&P 500", latest.get("sp500"), get_ret(macro, period, "sp500")),
        ("KOSPI", latest.get("kospi"), get_ret(macro, period, "kospi")),
        ("NASDAQ", latest.get("nasdaq"), get_ret(macro, period, "nasdaq")),
        ("닛케이225", latest.get("nikkei"), get_ret(macro, period, "nikkei")),
        ("DAX", latest.get("dax"), get_ret(macro, period, "dax")),
        ("금", latest.get("gold"), get_ret(macro, period, "gold")),
        ("WTI", latest.get("wti"), get_ret(macro, period, "wti")),
        ("USD/KRW", latest.get("usdkrw"), get_ret(macro, period, "usdkrw")),
    ]
    rows = []
    for name, price, change in items:
        if price is None and change is None:
            continue
        rows.append(
            {
                "name": name,
                "price": safe_text(number(price, 2), "-"),
                "change": signed_arrow(change),
                "isUp": (as_float(change) or 0) >= 0,
            }
        )
    return rows


def build_news_list(period: str, macro: dict, etf: dict, catalog: list[dict]) -> list[dict]:
    regime = macro.get("regime", "Neutral")
    regime_kr = get_regime_label(regime)
    mi = macro.get("macro_inputs", {}) or {}
    top = (etf.get("recommendations") or [])[:4]
    profile = period_profile(period)

    items = [
        {
            "title": f"{period} 금리·정책 해석",
            "tags": ["거시", "정책", period],
            "summary": (
                f"현재 금리 축은 연준 {number(mi.get('fedfunds'), 2)}%, 미 10년물 {number(mi.get('us10y'), 2)}%입니다. "
                f"레짐은 {regime_kr}이며, 고금리가 길어질수록 성장주보다 현금흐름이 안정적인 자산이 상대적으로 유리합니다. "
                f"{period} 시점에서는 정책 변화 자체보다 금리 레벨이 실제로 내려오기 시작하는지가 더 중요합니다."
            ),
            "detailPoints": [
                f"지금은 정책 기대만으로 위험자산을 공격적으로 늘리기보다, 고금리의 실질 부담이 줄어드는지를 확인해야 합니다.",
                f"장기채는 금리 민감도가 높아 단기 흔들림이 크므로 {period} 구간에서는 분할 접근이 적절합니다.",
                f"결국 금리 피크아웃이 확인되기 전까지는 성장주 올인보다 코어 지수 + 채권 + 현금의 조합이 더 설득력 있습니다.",
            ],
            "portfolioImplication": (
                f"{period} 포트폴리오에서는 고금리 적응 구간이라는 판단 아래 코어 지수만 단독으로 늘리기보다 "
                f"채권과 현금을 함께 두는 바벨형 접근이 더 합리적입니다."
            ),
            "executionGuide": (
                f"매수는 한 번에 몰아넣지 말고 {execution_rhythm(period)['label']} 원칙으로 나누는 편이 좋습니다. "
                f"특히 금리 민감 자산은 이벤트 직후 급등 추격을 피해야 합니다."
            ),
            "impacts": [
                {"sector": "장기채", "isPositive": False, "desc": "금리 민감도가 높아 변동성 확대 위험이 큽니다."},
                {"sector": "단기채", "isPositive": True, "desc": "고금리 환경에서 방어적 수익률 확보가 가능합니다."},
                {"sector": "성장주", "isPositive": False, "desc": "할인율 부담으로 밸류에이션 압박을 받기 쉽습니다."},
            ],
            "sources": select_sources(catalog, ["fred_api", "fed_press_rss", "fed_speeches_rss"], 3),
        },
        {
            "title": f"{period} 환율·유동성 이슈",
            "tags": ["환율", "달러", period],
            "summary": (
                f"DXY {number(mi.get('dxy'), 1)}, 원/달러 {number(mi.get('usd_krw'), 0)}원은 한국 자산에 여전히 중요한 리스크 요인입니다. "
                f"달러 강세가 완화되지 않으면 국내 증시 반등은 지수 전체보다 수출주·방어주 중심으로 제한될 가능성이 큽니다. "
                f"환율은 단순 숫자가 아니라 외국인 수급과 밸류에이션 할인율을 동시에 움직이는 변수입니다."
            ),
            "detailPoints": [
                f"원화 약세는 수출 대형주에 유리할 수 있지만, 지수 전체로는 외국인 자금 유입을 막는 요인이 됩니다.",
                f"그래서 한국 비중을 늘릴 때도 지수 전체보다는 수출/반도체/대형주 ETF로 압축하는 편이 낫습니다.",
                f"{profile['portfolio_focus']} 따라서 환율이 진정되기 전까지는 현금과 달러 노출 자산을 완충재로 쓰는 전략이 유효합니다.",
            ],
            "portfolioImplication": (
                f"한국 비중을 확대하더라도 환율 부담이 크면 ISA 안에서 broad ETF와 반도체 ETF를 섞고, "
                f"토스 계좌에서는 달러 자산을 완충재로 두는 구조가 더 안전합니다."
            ),
            "executionGuide": (
                f"원/달러가 급등하는 날은 공격적 추가매수보다 대기 자금을 남기고, 환율이 진정되는 날 2차 분할매수를 고려하는 접근이 적합합니다."
            ),
            "impacts": [
                {"sector": "한국 증시", "isPositive": False, "desc": "외국인 수급이 약해지면 지수 상단이 제한됩니다."},
                {"sector": "달러 자산", "isPositive": True, "desc": "환노출 자산의 헤지 효과가 커집니다."},
                {"sector": "수출주", "isPositive": True, "desc": "원화 약세가 실적에 보탬이 될 수 있습니다."},
            ],
            "sources": select_sources(catalog, ["fred_api", "ecos_api"], 2),
        },
        {
            "title": f"{period} 섹터·원자재 연결",
            "tags": ["원자재", "섹터", period],
            "summary": (
                f"금 {pct(get_ret(macro, period, 'gold'))}, 유가 {pct(get_ret(macro, period, 'wti'))} 흐름은 단순 가격보다 "
                f"인플레이션 압력과 방어 수요를 보여줍니다. 에너지·금 ETF는 동일한 '원자재'라도 역할이 다르므로 구분해 접근해야 합니다. "
                f"유가가 올라가는 이유가 수요 회복인지 지정학 리스크인지에 따라 해석도 달라집니다."
            ),
            "detailPoints": [
                f"금은 불확실성 헤지 자산이고, 에너지는 이익 민감도가 높은 경기·공급 이슈 자산입니다.",
                f"따라서 금 ETF는 포트폴리오 안정판, 에너지 ETF는 수익 기회라는 다른 역할로 편입해야 합니다.",
                f"{period} 관점에서는 금과 에너지를 동시에 담더라도 비중과 목적을 분리해 놓는 것이 중요합니다.",
            ],
            "portfolioImplication": (
                f"원자재는 한 묶음이 아니라 금은 헤지, 에너지는 전술 비중으로 분리해서 들고 가야 합니다. "
                f"같은 10% 원자재 비중이라도 금 6~7%, 에너지 3~4%처럼 역할별로 쪼개는 편이 더 실전적입니다."
            ),
            "executionGuide": (
                f"원자재는 변동성이 크므로 broad 지수 ETF보다 작은 비중으로 시작하고, 가격이 급등한 날보다는 눌림 구간에서 분할 진입하는 편이 좋습니다."
            ),
            "impacts": [
                {"sector": "에너지", "isPositive": True, "desc": "유가 강세 구간에서는 실적 민감도가 높아집니다."},
                {"sector": "소비재", "isPositive": False, "desc": "원가 부담이 커질 수 있습니다."},
                {"sector": "금 ETF", "isPositive": True, "desc": "불확실성 헤지 수요를 받을 수 있습니다."},
            ],
            "sources": select_sources(catalog, ["fred_api", "investing_com_rss", "bis_speeches"], 3),
        },
        {
            "title": f"{period} ETF/테마 실행 아이디어",
            "tags": ["ETF", "테마", period],
            "summary": (
                f"현재 상위 ETF 후보는 {', '.join(translate_etf_name(item) for item in top[:3]) if top else '데이터 없음'} 입니다. "
                f"레짐이 아직 중립이라면 공격적 단일 베팅보다 방어형 자산과 섹터형 자산을 섞는 접근이 더 적합합니다. "
                f"상위 점수 ETF도 RSI와 변동성이 높으면 바로 풀사이즈로 들어가기보다 비중 상한을 정해야 합니다."
            ),
            "detailPoints": [
                f"점수가 높다는 것은 레짐 적합도와 모멘텀이 좋다는 뜻이지, 언제나 지금 전액 매수하라는 뜻은 아닙니다.",
                f"과열된 ETF는 위성 비중으로 두고, 코어 자산은 broad ETF와 채권, 금 같은 분산 축으로 세우는 편이 안정적입니다.",
                f"ETF 선택은 결국 {period}의 질문에 답해야 합니다. 단기면 타이밍, 중기면 비중 관리가 더 중요합니다.",
            ],
            "portfolioImplication": (
                f"ETF는 '무엇을 살까'보다 '어떤 역할로 넣을까'가 더 중요합니다. "
                f"코어 ETF는 비중 기반으로, 섹터 ETF는 상한 기반으로 다뤄야 포트폴리오가 흔들리지 않습니다."
            ),
            "executionGuide": (
                f"{period}에서는 상위 ETF라도 전액 매수보다 2~5회 분할매수로 평균단가와 타이밍 리스크를 줄이는 방식이 더 유효합니다."
            ),
            "impacts": [
                {"sector": "지수 ETF", "isPositive": True, "desc": "개별 종목보다 레짐 대응이 쉽습니다."},
                {"sector": "섹터 ETF", "isPositive": True, "desc": "에너지·반도체 등 강한 테마를 선별 반영할 수 있습니다."},
                {"sector": "개별 종목", "isPositive": False, "desc": "중립 레짐에서는 종목 단위 변동성이 더 큽니다."},
            ],
            "sources": [{"label": "ETF 추천", "source": "etf_recommender", "title": "ETF 랭킹 산출", "published_at": etf.get("date", "")}],
        },
    ]
    return items


def normalize_asset_class(value: str | None) -> str:
    text = safe_text(value, "").lower()
    if not text:
        return "주식"
    if any(token in text for token in ["bond", "채", "국채", "회사채", "treasury", "fixed income"]):
        return "채권"
    if any(token in text for token in ["gold", "oil", "원자재", "commodity", "energy", "metal"]):
        return "원자재"
    if any(token in text for token in ["cash", "현금", "mmf"]):
        return "현금"
    return "주식"


def infer_asset_class_from_holding(holding: dict) -> str:
    explicit = holding.get("asset_class") or holding.get("assetClass")
    if explicit:
        return normalize_asset_class(explicit)
    text = " ".join(
        str(holding.get(key, "")) for key in ["ticker", "name", "type", "theme", "sector"]
    )
    return normalize_asset_class(text)


def holding_value(holding: dict) -> float:
    for key in ["market_value", "marketValue", "current_value", "currentValue", "amount_won", "amount", "value"]:
        amount = as_float(holding.get(key))
        if amount is not None:
            return amount
    return 0.0


def calculate_current_mix(portfolio_state: dict) -> tuple[dict[str, float], float]:
    amounts = {"주식": 0.0, "채권": 0.0, "원자재": 0.0, "현금": 0.0}
    accounts = portfolio_state.get("accounts", {}) or {}
    for account in accounts.values():
        amounts["현금"] += as_float(account.get("cash")) or 0.0
        for holding in account.get("holdings", []) or []:
            asset_class = infer_asset_class_from_holding(holding)
            amounts[asset_class] = amounts.get(asset_class, 0.0) + holding_value(holding)
    total = sum(amounts.values())
    if total <= 0:
        total = as_float(portfolio_state.get("total_cash")) or 0.0
        amounts["현금"] = total
    return amounts, total


def portfolio_score_components(regime: str, portfolio_state: dict) -> dict:
    target = REGIME_ALLOC.get(regime, REGIME_ALLOC["Neutral"])
    amounts, total = calculate_current_mix(portfolio_state)
    if total <= 0:
        total = 1.0

    current_pct = {asset: round(amounts.get(asset, 0.0) / total * 100, 1) for asset in ["주식", "채권", "원자재", "현금"]}
    target_pct = {asset: round(target[asset] * 100, 1) for asset in ["주식", "채권", "원자재", "현금"]}
    gaps = {asset: round(abs(current_pct[asset] - target_pct[asset]), 1) for asset in current_pct}

    allocation_fit = round(max(0.0, 100.0 - sum(gaps.values()) / 2.0))

    active_non_cash = sum(1 for asset in ["주식", "채권", "원자재"] if current_pct[asset] >= 5)
    diversification_score = {0: 25, 1: 45, 2: 72}.get(active_non_cash, 90)
    if current_pct["현금"] >= 70:
        diversification_score = min(diversification_score, 40)

    target_cash = target_pct["현금"]
    cash_pct = current_pct["현금"]
    if cash_pct > target_cash + 40:
        cash_management_score = 55
    elif cash_pct > target_cash + 20:
        cash_management_score = 68
    elif cash_pct >= max(target_cash - 10, 0):
        cash_management_score = 86
    else:
        cash_management_score = 72

    final_score = round(allocation_fit * 0.55 + diversification_score * 0.25 + cash_management_score * 0.20)
    if final_score >= 80:
        grade = "우수"
    elif final_score >= 65:
        grade = "양호"
    elif final_score >= 50:
        grade = "보통"
    elif final_score >= 35:
        grade = "미흡"
    else:
        grade = "개선 필요"

    if current_pct["현금"] >= 90:
        summary = "현금 비중이 과도하게 높아 레짐 대비 배분 점수는 낮지만, 대기 자금은 충분합니다."
    elif allocation_fit >= 75:
        summary = "현재 포트폴리오는 현 레짐의 권장 자산배분과 비교적 잘 맞습니다."
    else:
        summary = "현재 포트폴리오는 현 레짐 대비 자산군 편차가 커서 단계적 재배분 여지가 있습니다."

    reasons = [
        f"레짐 적합도 {allocation_fit}점 — 목표 배분 대비 편차를 반영",
        f"분산도 {diversification_score}점 — 실제 보유 자산군 수와 집중도를 반영",
        f"현금 운용 {cash_management_score}점 — 목표 현금 비중 대비 과소·과다 여부를 반영",
    ]

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
            "cashManagement": cash_management_score,
        },
        "reasons": reasons,
    }


def build_portfolio_block(period: str, macro: dict, etf: dict, portfolio_state: dict, catalog: list[dict]) -> dict:
    regime = macro.get("regime", "Neutral")
    regime_kr = get_regime_label(regime)
    alloc = REGIME_ALLOC.get(regime, REGIME_ALLOC["Neutral"])
    total_cash = int(as_float(portfolio_state.get("total_cash")) or 0)
    accounts = portfolio_state.get("accounts", {}) or {}
    score = portfolio_score_components(regime, portfolio_state)
    profile = period_profile(period)
    rhythm = execution_rhythm(period)
    current_amounts, total_assets = calculate_current_mix(portfolio_state)
    total_assets = total_assets or float(total_cash)

    account_lines = []
    for key in ["ISA", "TOSS", "PENSION"]:
        account = accounts.get(key, {})
        if not account:
            continue
        strategy = ACCOUNT_STRATEGY.get(key, {})
        account_lines.append(
            f"{safe_text(account.get('label'), key)} {money(account.get('cash'))} · "
            f"{safe_text(strategy.get('note'), account.get('note'))}"
        )

    allocations = [
        {"name": "주식", "percent": round(alloc["주식"] * 100, 1), "color": "#2563eb", "desc": "지수·섹터 ETF 중심의 핵심 위험자산"},
        {"name": "채권", "percent": round(alloc["채권"] * 100, 1), "color": "#0f766e", "desc": "고금리 구간 방어 및 현금흐름 완충"},
        {"name": "원자재", "percent": round(alloc["원자재"] * 100, 1), "color": "#ca8a04", "desc": "금·에너지로 인플레이션 및 리스크 헤지"},
        {"name": "현금", "percent": round(alloc["현금"] * 100, 1), "color": "#6b7280", "desc": "추가 조정 대응용 대기 자금"},
    ]

    target_amounts = []
    for item in allocations:
        asset = item["name"]
        current_amount = current_amounts.get(asset, 0.0)
        target_amount = total_assets * alloc[asset]
        gap_amount = target_amount - current_amount
        target_amounts.append(
            {
                "name": asset,
                "color": item["color"],
                "percent": item["percent"],
                "currentAmount": money(current_amount),
                "targetAmount": money(target_amount),
                "gapAmount": money(abs(gap_amount)),
                "direction": "늘리기" if gap_amount > 0 else ("줄이기" if gap_amount < 0 else "유지"),
            }
        )

    deploy_now_total = int(total_cash * profile["deploy_ratio"])
    reserve_total = max(total_cash - deploy_now_total, 0)
    account_plans = []
    for key in ["ISA", "TOSS", "PENSION"]:
        account = accounts.get(key, {})
        if not account:
            continue
        strategy = ACCOUNT_STRATEGY.get(key, {})
        account_cash = int(as_float(account.get("cash")) or 0)
        deploy_now = int(account_cash * profile["deploy_ratio"])
        reserve = max(account_cash - deploy_now, 0)
        account_plans.append(
            {
                "account": safe_text(account.get("label"), key),
                "cash": money(account_cash),
                "deployNow": money(deploy_now),
                "reserve": money(reserve),
                "role": safe_text(strategy.get("note"), safe_text(account.get("note"))),
                "ideas": ", ".join(strategy.get("ideas", [])[:3]) or "추천 ETF 데이터 보강 예정",
                "method": f"{profile['action_label']} · {rhythm['label']}",
            }
        )

    if period in {"1일", "1주"}:
        return_rate = profile["action_label"]
        review_desc = (
            f"현재는 전액 현금 상태이므로 시장 하락을 직접 맞고 있지는 않습니다. "
            f"다만 {regime_kr} 구간에서는 현금이 단순 미투자 상태가 아니라 선택권을 보유한 전략 자산으로 작동합니다. "
            f"같은 포트폴리오라도 {period} 관점에서는 '{profile['question']}'가 핵심이라 진입 타이밍 판단 비중이 더 큽니다."
        )
    else:
        return_rate = profile["action_label"]
        review_desc = (
            f"중기 관점에서는 한 번에 진입하기보다 레짐 변화에 맞춰 2~4회로 나눠 집행하는 편이 유리합니다. "
            f"같은 포트폴리오라도 {period} 시점에서는 '{profile['question']}'가 중요하므로, "
            f"목표 비중을 미리 정하고 과열 자산은 상한을 두는 구조가 적합합니다."
        )

    return {
        "accountAlert": (
            f"총 투자 대기 현금 {money(total_cash)} · 현재 레짐은 {regime_kr} · "
            f"포트폴리오 점수 {score['score']}점({score['grade']})."
        ),
        "accountDetail": " | ".join(account_lines) if account_lines else "계좌 정보가 없습니다.",
        "portfolioScore": score,
        "scoreChips": [
            metric_chip("총점", f"{score['score']}점", "score"),
            metric_chip("레짐 적합도", f"{score['breakdown']['regimeFit']}점", "score"),
            metric_chip("분산도", f"{score['breakdown']['diversification']}점", "score"),
            metric_chip("현금 운용", f"{score['breakdown']['cashManagement']}점", "score"),
        ],
        "capitalPlan": {
            "totalCash": money(total_cash),
            "deployNow": money(deploy_now_total),
            "reserveCash": money(reserve_total),
            "cadence": rhythm["cadence"],
            "deployRatio": f"{int(profile['deploy_ratio'] * 100)}%",
        },
        "targetAmounts": target_amounts,
        "accountPlans": account_plans,
        "holdings": [],
        "weeklyReview": {
            "returnRate": return_rate,
            "desc": review_desc,
        },
        "horizonView": {
            "title": f"{period}에서 보는 현재 포트폴리오",
            "desc": (
                f"{period} 시점에서는 {profile['portfolio_focus']} "
                f"즉, 1일은 진입 타이밍, 1주와 1개월은 비중 확대 속도, 3개월과 6개월은 목표 비중 유지와 리밸런싱을 더 무겁게 봐야 합니다."
            ),
            "sources": select_sources(catalog, ["fred_api", "ecos_api"], 2) + source_bundle(period, macro, etf, portfolio_state)[2:],
        },
        "notes": [
            f"현재 점수 {score['score']}점은 손익률이 아니라 현 레짐에 대한 적합도입니다.",
            f"{period} 관점에서는 '{profile['question']}'에 답하는 방식으로 같은 포트폴리오를 다르게 해석해야 합니다.",
            f"따라서 1일 시점에서 매수 의견이 나와도 6개월 시점에서는 특정 섹터 비중 상한을 두라는 결론이 함께 나올 수 있습니다.",
            f"현재 포트폴리오는 전액 현금에 가까우므로, 당장의 핵심은 무엇을 팔지보다 어떤 순서로 얼마를 배치할지입니다.",
            f"실행 속도는 {rhythm['label']} 원칙을 따르되, {rhythm['pause_rule']} 조건에서는 추가 집행을 멈추는 편이 좋습니다.",
        ],
        "allocations": allocations,
        "planDesc": (
            f"{regime_kr} 기준 권장 배분은 주식 {int(alloc['주식']*100)}% / 채권 {int(alloc['채권']*100)}% / "
            f"원자재 {int(alloc['원자재']*100)}% / 현금 {int(alloc['현금']*100)}% 입니다. "
            f"이번 {period} 실행 예산은 {money(deploy_now_total)}이며, 나머지 {money(reserve_total)}는 "
            f"{rhythm['review_rule']} 원칙 아래 대기 자금으로 남깁니다."
        ),
        "sources": source_bundle(period, macro, etf, portfolio_state),
    }


def build_rebalancing_block(period: str, macro: dict, etf: dict, portfolio_state: dict, catalog: list[dict]) -> dict:
    regime = macro.get("regime", "Neutral")
    target = REGIME_ALLOC.get(regime, REGIME_ALLOC["Neutral"])
    profile = period_profile(period)
    rhythm = execution_rhythm(period)
    ranked = etf.get("recommendations") or []
    accounts = portfolio_state.get("accounts", {}) or {}
    used: set[str] = set()

    isa_core = pick_etf(ranked, used, {"KR"}, ("equity_broad",))
    if isa_core:
        used.add(safe_text(isa_core.get("ticker"), ""))
    isa_sat = pick_etf(ranked, used, {"KR"}, ("equity_sector",))
    if isa_sat:
        used.add(safe_text(isa_sat.get("ticker"), ""))
    toss_hedge = pick_etf(ranked, used, {"US"}, ("commodity",))
    if toss_hedge:
        used.add(safe_text(toss_hedge.get("ticker"), ""))
    toss_bond = pick_etf(ranked, used, set(), ("bond",))
    if toss_bond:
        used.add(safe_text(toss_bond.get("ticker"), ""))
    toss_tactical = pick_etf(ranked, used, {"US"}, ("equity_sector", "equity_broad"))
    if toss_tactical:
        used.add(safe_text(toss_tactical.get("ticker"), ""))
    pension_core = pick_etf(ranked, used, {"JP", "US", "EU"}, ("equity_broad",))
    if pension_core:
        used.add(safe_text(pension_core.get("ticker"), ""))
    pension_bond = pick_etf(ranked, used, set(), ("bond",))
    if pension_bond:
        used.add(safe_text(pension_bond.get("ticker"), ""))

    actions = []

    def add_action(account_key: str, ratio: float, item: dict | None, action: str, note: str):
        account = accounts.get(account_key, {})
        if not account or not item:
            return
        deploy_cash = int((as_float(account.get("cash")) or 0) * profile["deploy_ratio"] * ratio)
        if deploy_cash <= 0:
            return
        action_sources = select_sources(catalog, ["fred_api", "ecos_api", "naver_research", "opendart"], 3) + [
            source_item("ETF 추천", "etf_recommender", f"{period} {translate_etf_name(item)} 점수화", etf.get("date", "")),
            source_item("포트폴리오 상태", "portfolio_state", f"{safe_text(account.get('label'), account_key)} 현금 배치", portfolio_state.get("updated", "")),
        ]
        split_lines = execution_step_lines(period, deploy_cash)
        split_amount = split_amounts(deploy_cash, rhythm["tranches"])
        first_amount = split_amount[0] if split_amount else 0
        actions.append(
            {
                "account": safe_text(account.get("label"), account_key),
                "action": action,
                "name": translate_etf_name(item),
                "ticker": safe_text(item.get("ticker"), "-"),
                "amount": money(deploy_cash),
                "weightHint": f"계좌 현금의 약 {int(ratio * profile['deploy_ratio'] * 100)}%",
                "positionHint": total_position_hint(item),
                "assetRole": idea_role_text(item),
                "todayAmount": money(first_amount),
                "reason": (
                    f"{period} 기준 {profile['action_label']} 단계입니다. {translate_etf_name(item)} 는 점수 {safe_text(item.get('score'))}점, "
                    f"3개월 모멘텀 {pct(item.get('momentum_3m'))}, RSI {number(item.get('rsi'), 1)}로 '{safe_text(item.get('rationale'))}' 평가를 받았습니다. "
                    f"{note}"
                ),
                "executionStyle": rhythm["label"],
                "executionSummary": rhythm["cadence"],
                "splitPlan": split_lines,
                "addRule": rhythm["add_rule"],
                "pauseRule": rhythm["pause_rule"],
                "reviewRule": rhythm["review_rule"],
                "caution": rsi_comment(item.get("rsi")),
                "sources": action_sources,
            }
        )

    add_action("ISA", 0.65, isa_core, "매수", "국내 코어 지수 비중을 먼저 세우는 역할입니다.")
    add_action("ISA", 0.35, isa_sat, "매수", "국내 섹터 알파를 소규모 위성 비중으로 붙이는 용도입니다.")
    add_action("TOSS", 0.40, toss_hedge, "매수", "불확실성 헤지 자산으로 달러/금리 리스크를 완충하는 역할입니다.")
    add_action("TOSS", 0.35, toss_bond, "매수", "고금리 구간 방어와 중기 변동성 완화 축입니다.")
    add_action("TOSS", 0.25, toss_tactical, "분할매수", "미국 전술 아이디어는 비중 상한을 두고 분할로 접근하는 편이 안전합니다.")
    add_action("PENSION", 0.55, pension_bond, "매수", "연금 계좌에서는 장기 분산과 금리 하락 가능성을 함께 반영합니다.")
    add_action("PENSION", 0.45, pension_core, "매수", "장기 보유용 해외 broad ETF 성격으로 분산을 보완합니다.")

    if not actions:
        actions = [
            {
                "account": "전체 계좌",
                "action": "보류",
                "name": "데이터 부족",
                "ticker": "-",
                "amount": "0원",
                "weightHint": "0%",
                "positionHint": "데이터 확보 후 계산",
                "assetRole": "현재는 현금 유지가 기본 역할입니다.",
                "todayAmount": "0원",
                "reason": f"{period} 기준 리밸런싱 액션을 만들 충분한 ETF 데이터가 없습니다.",
                "executionStyle": rhythm["label"],
                "executionSummary": rhythm["cadence"],
                "splitPlan": [],
                "addRule": rhythm["add_rule"],
                "pauseRule": rhythm["pause_rule"],
                "reviewRule": rhythm["review_rule"],
                "caution": "데이터가 채워질 때까지 현금과 코어 자산 위주로 대기합니다.",
                "sources": source_bundle(period, macro, etf, portfolio_state),
            }
        ]

    total_cash = as_float(portfolio_state.get("total_cash")) or 0
    guided_cash = int(total_cash * profile["deploy_ratio"])
    keep_cash = int(total_cash - guided_cash)
    target_lines = ", ".join(f"{asset} {int(target[asset] * 100)}%" for asset in ["주식", "채권", "원자재", "현금"])

    return {
        "title": f"{period} 실행 가이드",
        "summary": (
            f"{period} 시점의 총 현금은 {money(total_cash)}입니다. "
            f"실행 예산은 약 {money(guided_cash)}입니다. 대기 자금은 {money(keep_cash)}입니다. "
            f"이 가이드는 같은 포트폴리오라도 기간에 따라 "
            f"매수 속도와 비중 상한이 달라져야 한다는 전제에서 작성되었습니다. "
            f"집행 리듬은 '{rhythm['label']}'이며, {rhythm['cadence']} 원칙을 따릅니다."
        ),
        "horizonNote": (
            f"{period}의 질문은 '{profile['question']}' 입니다. 그래서 1일 뷰에서는 초기 매수가 가능해 보여도, "
            f"6개월 뷰에서는 과열 테마의 최종 비중을 줄이라는 결론이 동시에 나올 수 있습니다."
        ),
        "actions": actions[:8],
        "footnotes": [
            f"현재 레짐 {get_regime_label(regime)} 기준 전략 비중은 {target_lines} 입니다.",
            f"{profile['guide']}",
            "매수 가이드는 즉시 전액 집행이 아니라 계좌별 분할 집행을 전제로 합니다.",
            f"현재 분할매수 원칙은 '{rhythm['label']}'이며, 추가 조건은 '{rhythm['add_rule']}', 보류 조건은 '{rhythm['pause_rule']}' 입니다.",
            "보유 종목이 생기면 이후에는 신규 매수뿐 아니라 비중 축소/교체 액션도 함께 계산하도록 확장할 수 있습니다.",
        ],
        "sources": select_sources(catalog, ["fred_api", "ecos_api", "naver_research", "opendart"], 4) + source_bundle(period, macro, etf, portfolio_state),
    }


def build_recommendations_block(period: str, macro: dict, etf: dict, regime: str, catalog: list[dict], signals: dict | None = None) -> dict:
    ranked = (etf.get("recommendations") or [])[:8]
    mi = macro.get("macro_inputs", {}) or {}
    rhythm = execution_rhythm(period)
    # Build signal lookup map by ETF id
    signal_map: dict[str, dict] = {}
    if signals:
        for sig in (signals.get("signals") or []):
            signal_map[sig.get("id", "")] = sig

    ideas = []
    for item in ranked[:4]:
        rationale = safe_text(item.get("rationale"))
        etf_id = safe_text(item.get("id"), "")
        sig_data = signal_map.get(etf_id, {})

        idea_sources = select_sources(catalog, ["fred_api", "ecos_api", "fed_speeches_rss", "naver_research"], 4) + [
            source_item("ETF 추천", "etf_recommender", f"{period} {translate_etf_name(item)} 점수화", etf.get("date", "")),
            source_item("퀀트 레짐", "macro_analysis", f"{period} 레짐과 점수 조합", macro.get("date", "")),
        ]

        # Signal-enhanced evidence points
        evidence_points = [
            idea_macro_context(item, macro),
            f"기술적으로 3개월 모멘텀 {pct(item.get('momentum_3m'))}, RSI {number(item.get('rsi'), 1)}, 20일 변동성 {number(item.get('volatility_20d'), 1)} 수준입니다.",
            f"{idea_role_text(item)} 포지션 상한은 {total_position_hint(item)} 정도로 두는 편이 안정적입니다.",
        ]
        if sig_data.get("reasons"):
            evidence_points += [r for r in sig_data["reasons"][:3] if r not in evidence_points]

        # Timing detail from signal engine
        timing_detail = ""
        td = sig_data.get("timing_details") or {}
        ma_al = td.get("ma_alignment") or {}
        bb = td.get("bollinger") or {}
        macd_d = td.get("macd") or {}
        ew = td.get("elliott_wave") or {}
        candle = td.get("candle") or {}
        timing_parts = []
        if ma_al.get("alignment"):
            timing_parts.append(f"이평선 {ma_al['alignment']}")
        if bb.get("position"):
            timing_parts.append(f"BB {bb['position']}(%B={bb.get('percent_b','?')})")
        if macd_d.get("crossover"):
            timing_parts.append(f"MACD {'골든크로스' if macd_d['crossover']=='bullish' else '데드크로스'}")
        elif macd_d.get("trend"):
            timing_parts.append(f"MACD {macd_d['trend']}")
        if ew.get("wave_phase"):
            timing_parts.append(f"엘리엇 {ew['wave_phase']}")
        if candle.get("pattern") and candle.get("pattern") != "없음":
            timing_parts.append(f"캔들 {candle['pattern']}")
        timing_detail = " | ".join(timing_parts) if timing_parts else "기술적 데이터 분석 중"

        signal_label = sig_data.get("signal", "관망")
        timing_grade = sig_data.get("timing_grade", "C")
        entry_conditions = sig_data.get("entry_conditions") or []
        exit_conditions = sig_data.get("exit_conditions") or []
        sizing = sig_data.get("position_sizing") or {}

        ideas.append(
            {
                "logo": etf_logo(item),
                "name": translate_etf_name(item),
                "ticker": safe_text(item.get("ticker"), "-"),
                "action": etf_action_label(safe_text(item.get("tier"), "중립")),
                "signal": signal_label,
                "timingGrade": timing_grade,
                "timingDetail": timing_detail,
                "linkedIssue": theme_from_etf(item),
                "scoreText": f"{int(round(as_float(item.get('score')) or 0))}점",
                "reason": (
                    f"{period} 기준 점수 {safe_text(item.get('score'), 'N/A')}점입니다. "
                    f"현재 금리 {number(mi.get('fedfunds'), 2)}%, 미 10년물 {number(mi.get('us10y'), 2)}%, 달러 {number(mi.get('dxy'), 1)} 조합을 감안할 때 "
                    f"{translate_etf_name(item)} 는 '{rationale}' 평가를 받았습니다."
                ),
                "whyBuy": (
                    f"사는 이유는 레짐 적합도와 모멘텀이 상대적으로 낫기 때문입니다. "
                    f"3개월 모멘텀 {pct(item.get('momentum_3m'))}, RSI {number(item.get('rsi'), 1)}를 보면 "
                    f"{'코어 비중보다 위성 비중으로 쓰기 좋은 자산' if 'sector' in safe_text(item.get('type'), '').lower() else '코어 또는 분산 자산으로 쓰기 좋은 후보'}입니다."
                ),
                "risk": (
                    f"우려 지점은 {rsi_comment(item.get('rsi'))} "
                    f"{'특히 과열 섹터는 장기 목표 비중 상한을 두는 편이 좋습니다.' if (as_float(item.get('rsi')) or 0) >= 70 else '레짐 훼손 시 비중 축소 기준을 미리 정해두는 것이 좋습니다.'}"
                ),
                "execution": (
                    f"{period}에서는 {'1차만 진입 후 확인' if period in {'1일', '1주'} else '목표 비중까지 단계적으로 구축'} 전략이 적합합니다. "
                    f"집행 리듬은 {rhythm['label']}이며, {rhythm['pause_rule']} 조건에서는 속도를 늦추는 편이 좋습니다. "
                    f"{safe_text(sizing.get('micro_plan'), '초기 진입 규모는 1~2% 단위로 시작하는 편이 좋습니다.')}"
                ),
                "entryConditions": entry_conditions[:3],
                "exitConditions": exit_conditions[:3],
                "positionSizing": {
                    "maxPct": sizing.get("max_allocation_pct"),
                    "firstPct": sizing.get("first_tranche_pct"),
                    "firstAmount": sizing.get("first_amount"),
                    "schedule": sizing.get("schedule"),
                },
                "macroContext": idea_macro_context(item, macro),
                "positioning": total_position_hint(item),
                "evidencePoints": evidence_points,
                "watchPoint": rhythm["pause_rule"],
                "sources": idea_sources,
            }
        )

    ranking = []
    for idx, item in enumerate(ranked, start=1):
        ranking.append(
            {
                "rank": idx,
                "name": translate_etf_name(item),
                "ticker": safe_text(item.get("ticker"), "-"),
                "score": int(round(as_float(item.get("score")) or 0)),
                "commentary": safe_text(item.get("rationale"), "설명 없음"),
            }
        )

    if not ideas:
        ideas = [
            {
                "logo": "📌",
                "name": "ETF 데이터 없음",
                "ticker": "-",
                "action": "관찰 유지",
                "linkedIssue": safe_text(get_regime_label(regime)),
                "scoreText": "0점",
                "reason": "현재 날짜의 ETF 추천 데이터가 부족합니다.",
                "whyBuy": "ETF 데이터가 채워지면 레짐·모멘텀·RSI를 근거로 설명을 보강합니다.",
                "risk": "현재는 데이터 부족이 가장 큰 리스크입니다.",
                "execution": "데이터 확보 전까지는 코어 자산과 현금 중심 접근이 적합합니다.",
                "macroContext": "데이터 확보 전까지는 매크로 컨텍스트 설명을 보수적으로 유지합니다.",
                "positioning": "총 투자금의 0%",
                "evidencePoints": [],
                "watchPoint": "충분한 ETF 데이터 확보 전까지는 과도한 해석을 피합니다.",
                "sources": source_bundle(period, macro, etf, {}),
            }
        ]

    return {"ideas": ideas, "etfRanking": ranking}


def build_period_data(period: str, macro: dict, etf: dict, portfolio_state: dict, catalog: list[dict], signals: dict | None = None) -> dict:
    score, status, desc = score_status((macro.get("scores") or {}).get("total"))
    regime = macro.get("regime", "Neutral")

    # Score label — clear description for UI
    score_label = "종합 시장 점수 (0~100, 50=중립, 높을수록 위험선호 환경 우세)"

    briefing = {
        "sentiment": {
            "score": score,
            "status": status,
            "label": score_label,
            "desc": f"{desc} 현재 해석은 {get_regime_label(regime)} 기준입니다.",
        },
        "scoreChips": build_score_chips(macro),
        "metricChips": build_metric_chips(period, macro),
        "forecast": build_period_forecast(period, macro, regime, catalog),
        "strategy": build_market_strategy_block(period, macro, etf, portfolio_state, catalog),
        "insights": build_period_insights(period, macro, etf, portfolio_state, catalog),
        "indices": build_indices(period, macro),
    }

    return {
        "briefing": briefing,
        "newsList": build_news_list(period, macro, etf, catalog),
        "portfolio": build_portfolio_block(period, macro, etf, portfolio_state, catalog),
        "rebalancing": build_rebalancing_block(period, macro, etf, portfolio_state, catalog),
        "recommendations": build_recommendations_block(period, macro, etf, regime, catalog, signals),
    }


def build_meta(docs: list[dict], catalog: list[dict], macro: dict, etf: dict, portfolio_state: dict) -> dict:
    by_region: dict[str, int] = {}
    by_doc_type: dict[str, int] = {}
    for doc in docs:
        by_region[doc.get("region", "unknown")] = by_region.get(doc.get("region", "unknown"), 0) + 1
        by_doc_type[doc.get("document_type", "unknown")] = by_doc_type.get(doc.get("document_type", "unknown"), 0) + 1

    return {
        "docsCount": len(docs),
        "sourceCatalog": catalog,
        "byRegion": by_region,
        "byDocumentType": by_doc_type,
        "portfolioUpdated": portfolio_state.get("updated", ""),
        "macroAvailable": bool(macro),
        "etfAvailable": bool(etf),
        "reportLanguage": "ko",
    }


def build_valuation_summary(valuation: dict) -> dict:
    """밸류에이션 요약 블록."""
    if not valuation:
        return {}
    sp = valuation.get("sp500") or {}
    kospi = valuation.get("kospi") or {}
    nas = valuation.get("nasdaq") or {}
    gold = valuation.get("gold") or {}
    summary = valuation.get("summary") or {}
    return {
        "marketValuation": summary.get("market_valuation", ""),
        "avgScore": summary.get("avg_score"),
        "sp500": {
            "grade": sp.get("valuation_grade"),
            "erp": sp.get("erp_pct"),
            "pe": sp.get("estimated_pe"),
            "range52w": sp.get("range_52w_pct"),
            "vsMa200": sp.get("vs_ma200_pct"),
            "erpAssessment": sp.get("erp_assessment"),
        },
        "kospi": {
            "grade": kospi.get("valuation_grade"),
            "pbr": kospi.get("estimated_pbr"),
            "pbrAssessment": kospi.get("pbr_assessment"),
            "range52w": kospi.get("range_52w_pct"),
            "vsMa200": kospi.get("vs_ma200_pct"),
        },
        "nasdaq": {
            "grade": nas.get("valuation_grade"),
            "erp": nas.get("erp_pct"),
            "range52w": nas.get("range_52w_pct"),
        },
        "gold": {
            "assessment": gold.get("assessment"),
            "range52w": gold.get("range_52w_pct"),
        },
    }


def build_signals_summary(signals: dict) -> dict:
    """매수/매도 신호 요약 블록."""
    if not signals:
        return {}
    ms = signals.get("market_signal") or {}
    top_buys = signals.get("top_buys") or []
    avoid = signals.get("avoid_list") or []
    acc_plans = signals.get("account_plans") or {}
    summary = signals.get("summary") or {}

    return {
        "marketSignal": {
            "action": ms.get("action"),
            "note": ms.get("note"),
            "deployablePct": ms.get("deployable_pct"),
            "marketScore": ms.get("market_score"),
        },
        "signalSummary": summary,
        "topBuys": [
            {
                "id": s.get("id"),
                "name": s.get("name"),
                "ticker": s.get("ticker"),
                "signal": s.get("signal"),
                "timingGrade": s.get("timing_grade"),
                "timingScore": s.get("timing_score"),
                "rsi": s.get("rsi"),
                "reasons": (s.get("reasons") or [])[:3],
                "firstAmount": (s.get("position_sizing") or {}).get("first_amount", 0),
                "schedule": (s.get("position_sizing") or {}).get("schedule", ""),
                "microPlan": (s.get("position_sizing") or {}).get("micro_plan", ""),
                "microStepAmount": (s.get("position_sizing") or {}).get("micro_step_amount", 0),
                "entryConditions": (s.get("entry_conditions") or [])[:3],
                "exitConditions": (s.get("exit_conditions") or [])[:3],
                "accountFit": s.get("account_fit") or [],
                "timingDetails": s.get("timing_details") or {},
            }
            for s in top_buys[:6]
        ],
        "avoidList": [
            {
                "id": s.get("id"),
                "name": s.get("name"),
                "reasons": (s.get("reasons") or [])[:2],
            }
            for s in avoid[:3]
        ],
        "accountPlans": acc_plans,
        "allSignals": [
            {
                "id": s.get("id"),
                "name": s.get("name"),
                "ticker": s.get("ticker"),
                "signal": s.get("signal"),
                "timingGrade": s.get("timing_grade"),
                "rsi": s.get("rsi"),
                "volatility": s.get("volatility_20d"),
                "quant_score": s.get("etf_quant_score"),
                "currency": s.get("currency"),
            }
            for s in (signals.get("signals") or [])
        ],
    }


def build_llm_insights_block(llm: dict) -> dict:
    """LLM 인사이트 블록."""
    if not llm:
        return {}
    return {
        "marketNarrative": llm.get("market_narrative", ""),
        "regimeAssessment": llm.get("regime_assessment", ""),
        "keySignals": llm.get("key_signals") or [],
        "sectorCalls": llm.get("sector_calls") or [],
        "riskFactors": llm.get("risk_factors") or [],
        "timingGuidance": llm.get("timing_guidance", ""),
        "portfolioComment": llm.get("portfolio_comment", ""),
        "newsHighlights": llm.get("news_highlights") or [],
        "apiUsed": llm.get("api_used", False),
        "generatedBy": llm.get("generated_by", ""),
    }


def build(root: Path, date_str: str) -> dict:
    macro = load_json(root / "data" / "macro_analysis" / f"{date_str}.json") or {}
    etf = load_json(root / "data" / "etf_recommendations" / f"{date_str}.json") or {}
    docs = load_jsonl(root / "data" / "normalized" / date_str / "documents.jsonl")
    portfolio_state = load_json(PORTFOLIO_STATE_FILE) or {}
    valuation = load_json(root / "data" / "valuation" / f"{date_str}.json") or {}
    signals = load_json(root / "data" / "signals" / f"{date_str}.json") or {}
    llm_insights = load_json(root / "data" / "llm_insights" / f"{date_str}.json") or {}

    regime = macro.get("regime", "Neutral")
    catalog = source_catalog(docs)
    result = {
        "date": f"{date_str} 기준 업데이트",
        "generatedAt": date_str,
        "dataStatus": classify_data_status(docs, macro, etf),
        "regime": regime,
        "regimeKr": get_regime_label(regime),
        "totalScore": (macro.get("scores") or {}).get("total"),
        "valuation": build_valuation_summary(valuation),
        "signals": build_signals_summary(signals),
        "llmInsights": build_llm_insights_block(llm_insights),
        "dataByPeriod": {
            period: build_period_data(period, macro, etf, portfolio_state, catalog, signals) for period in PERIODS
        },
        "meta": build_meta(docs, catalog, macro, etf, portfolio_state),
    }

    out_dir = root / "site" / date_str
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))

    template_src = root / "site" / "template" / "index.html"
    if not template_src.exists():
        candidates = sorted(
            [path for path in (root / "site").glob("*/index.html") if path.parent.name != date_str],
            reverse=True,
        )
        template_src = candidates[0] if candidates else None

    dst_html = out_dir / "index.html"
    if template_src and template_src.exists() and template_src.resolve() != dst_html.resolve():
        shutil.copy(template_src, dst_html)

    print(f"wrote {out_dir / 'result.json'}")
    return result


def update_date_status(root: Path, date_str: str, status: str, doc_count: int):
    status_file = root / "site" / "date_status.json"
    existing = load_json(status_file) or {}
    existing[date_str] = {"count": doc_count, "status": status}
    status_file.write_text(json.dumps(dict(sorted(existing.items(), reverse=True)), ensure_ascii=False, indent=2))
    print(f"updated {status_file}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--base-dir", default=str(ROOT))
    args = parser.parse_args()

    root = Path(args.base_dir)
    docs = load_jsonl(root / "data" / "normalized" / args.date / "documents.jsonl")
    result = build(root, args.date)
    update_date_status(root, args.date, result.get("dataStatus", "empty"), len(docs))


if __name__ == "__main__":
    main()
