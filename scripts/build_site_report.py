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


def build_period_forecast(period: str, macro: dict, regime: str, catalog: list[dict]) -> dict:
    sp = pct(get_ret(macro, period, "sp500"))
    kospi = pct(get_ret(macro, period, "kospi"))
    nasdaq = pct(get_ret(macro, period, "nasdaq"))
    gold = pct(get_ret(macro, period, "gold"))
    oil = pct(get_ret(macro, period, "wti"))
    fx = pct(get_ret(macro, period, "usdkrw"))
    mi = macro.get("macro_inputs", {}) or {}
    regime_kr = get_regime_label(regime)

    if period in {"1일", "1주"}:
        title = f"{period} 단기 방향성"
        text = (
            f"{period} 기준 미국 주식은 S&P500 {sp}, NASDAQ {nasdaq}, 한국은 KOSPI {kospi} 흐름입니다. "
            f"동시에 금 {gold}, 유가 {oil}, 원/달러 {fx}가 움직이며 위험선호보다 변동성 관리가 우선인 구간입니다. "
            f"현재 시장은 {regime_kr}으로 해석되며, 단기적으로는 VIX {number(mi.get('vix'), 1)}, "
            f"DXY {number(mi.get('dxy'), 1)}, 미 10년물 {number(mi.get('us10y'), 2)}%가 핵심 체크포인트입니다."
        )
    else:
        title = f"{period} 중기 방향성"
        text = (
            f"{period} 관점에서는 시장이 단순 뉴스보다 금리·달러·실적 부담 속에서 어떤 레짐으로 굳어지는지가 중요합니다. "
            f"S&P500 {sp}, KOSPI {kospi}, 금 {gold}, 유가 {oil} 흐름을 함께 보면 "
            f"지금은 {regime_kr} 성격이 강하며, 3~6개월 투자에서는 추격매수보다 단계적 자산배분과 섹터 선별이 유효합니다."
        )

    return {
        "title": title,
        "text": text,
        "sources": select_sources(catalog, ["fred_api", "ecos_api", "opendart", "naver_research"], 4),
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

    insights = [
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

    items = [
        {
            "title": f"{period} 금리·정책 해석",
            "tags": ["거시", "정책", period],
            "summary": (
                f"현재 금리 축은 연준 {number(mi.get('fedfunds'), 2)}%, 미 10년물 {number(mi.get('us10y'), 2)}%입니다. "
                f"레짐은 {regime_kr}이며, 고금리가 길어질수록 성장주보다 현금흐름이 안정적인 자산이 상대적으로 유리합니다."
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
                f"달러 강세가 완화되지 않으면 국내 증시 반등은 지수 전체보다 수출주·방어주 중심으로 제한될 가능성이 큽니다."
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
                f"인플레이션 압력과 방어 수요를 보여줍니다. 에너지·금 ETF는 동일한 '원자재'라도 역할이 다르므로 구분해 접근해야 합니다."
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
                f"레짐이 아직 중립이라면 공격적 단일 베팅보다 방어형 자산과 섹터형 자산을 섞는 접근이 더 적합합니다."
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


def build_portfolio_block(period: str, macro: dict, portfolio_state: dict) -> dict:
    regime = macro.get("regime", "Neutral")
    regime_kr = get_regime_label(regime)
    alloc = REGIME_ALLOC.get(regime, REGIME_ALLOC["Neutral"])
    total_cash = int(as_float(portfolio_state.get("total_cash")) or 0)
    accounts = portfolio_state.get("accounts", {}) or {}
    score = portfolio_score_components(regime, portfolio_state)

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

    if period in {"1일", "1주"}:
        return_rate = "현금 100% 대기"
        review_desc = (
            f"현재는 전액 현금 상태이므로 시장 하락을 직접 맞고 있지는 않습니다. "
            f"다만 {regime_kr} 구간에서는 현금이 단순 미투자 상태가 아니라 선택권을 보유한 전략 자산으로 작동합니다."
        )
    else:
        return_rate = f"3~6개월 분할진입 준비"
        review_desc = (
            f"중기 관점에서는 한 번에 진입하기보다 레짐 변화에 맞춰 2~4회로 나눠 집행하는 편이 유리합니다. "
            f"지금은 자산군별 첫 비중을 정하고, 변동성 확대 시 추가 집행하는 구조가 적합합니다."
        )

    return {
        "accountAlert": (
            f"총 투자 대기 현금 {money(total_cash)} · 현재 레짐은 {regime_kr} · "
            f"포트폴리오 점수 {score['score']}점({score['grade']})."
        ),
        "accountDetail": " | ".join(account_lines) if account_lines else "계좌 정보가 없습니다.",
        "portfolioScore": score,
        "holdings": [],
        "weeklyReview": {
            "returnRate": return_rate,
            "desc": review_desc,
        },
        "allocations": allocations,
        "planDesc": (
            f"{regime_kr} 기준 권장 배분은 주식 {int(alloc['주식']*100)}% / 채권 {int(alloc['채권']*100)}% / "
            f"원자재 {int(alloc['원자재']*100)}% / 현금 {int(alloc['현금']*100)}% 입니다. "
            f"ISA는 국내 ETF, 토스증권은 미국 ETF, 연금저축은 장기 분산형 ETF에 우선 배분합니다."
        ),
    }


def build_recommendations_block(period: str, etf: dict, regime: str) -> dict:
    ranked = (etf.get("recommendations") or [])[:8]
    ideas = []
    for item in ranked[:4]:
        ideas.append(
            {
                "logo": etf_logo(item),
                "name": translate_etf_name(item),
                "ticker": safe_text(item.get("ticker"), "-"),
                "action": etf_action_label(safe_text(item.get("tier"), "중립")),
                "linkedIssue": theme_from_etf(item),
                "reason": (
                    f"{period} 기준 점수 {safe_text(item.get('score'), 'N/A')}점, "
                    f"3개월 모멘텀 {pct(item.get('momentum_3m'))}, RSI {safe_text(item.get('rsi'), 'N/A')}, "
                    f"해석은 '{safe_text(item.get('rationale'))}' 입니다. "
                    f"{'레짐과 잘 맞는 후보입니다.' if safe_text(item.get('tier')) in {'강력매수', '매수'} else '즉시 추격보다 관찰 후 접근이 더 적합합니다.'}"
                ),
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
                "reason": "현재 날짜의 ETF 추천 데이터가 부족합니다.",
            }
        ]

    return {"ideas": ideas, "etfRanking": ranking}


def build_period_data(period: str, macro: dict, etf: dict, portfolio_state: dict, catalog: list[dict]) -> dict:
    score, status, desc = score_status((macro.get("scores") or {}).get("total"))
    regime = macro.get("regime", "Neutral")
    briefing = {
        "sentiment": {
            "score": score,
            "status": status,
            "desc": f"{desc} 현재 해석은 {get_regime_label(regime)} 기준입니다.",
        },
        "forecast": build_period_forecast(period, macro, regime, catalog),
        "insights": build_period_insights(period, macro, etf, portfolio_state, catalog),
        "indices": build_indices(period, macro),
    }

    return {
        "briefing": briefing,
        "newsList": build_news_list(period, macro, etf, catalog),
        "portfolio": build_portfolio_block(period, macro, portfolio_state),
        "recommendations": build_recommendations_block(period, etf, regime),
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


def build(root: Path, date_str: str) -> dict:
    macro = load_json(root / "data" / "macro_analysis" / f"{date_str}.json") or {}
    etf = load_json(root / "data" / "etf_recommendations" / f"{date_str}.json") or {}
    docs = load_jsonl(root / "data" / "normalized" / date_str / "documents.jsonl")
    portfolio_state = load_json(PORTFOLIO_STATE_FILE) or {}

    regime = macro.get("regime", "Neutral")
    catalog = source_catalog(docs)
    result = {
        "date": f"{date_str} 기준 업데이트",
        "generatedAt": date_str,
        "dataStatus": classify_data_status(docs, macro, etf),
        "regime": regime,
        "regimeKr": get_regime_label(regime),
        "totalScore": (macro.get("scores") or {}).get("total"),
        "dataByPeriod": {
            period: build_period_data(period, macro, etf, portfolio_state, catalog) for period in PERIODS
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
