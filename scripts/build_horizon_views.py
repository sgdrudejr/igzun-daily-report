#!/usr/bin/env python3
"""
Build horizon-specific view files from accumulated daily result.json files.

Writes:
  - site/horizon_index.json
  - site/horizons/daily/*.json
  - site/horizons/weekly/*.json
  - site/horizons/monthly/*.json
  - site/horizons/quarterly/*.json
  - site/horizons/halfyearly/*.json
"""

import argparse
import copy
import json
import shutil
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

HORIZON_CONFIG = [
    ("1일", "daily"),
    ("1주", "weekly"),
    ("1개월", "monthly"),
    ("3개월", "quarterly"),
    ("6개월", "halfyearly"),
]

STATUS_RANK = {"empty": 0, "sparse": 1, "partial": 2, "full": 3}
WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]


def load_json(path: Path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def save_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))


def as_float(value):
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def weekday_label(dt: date) -> str:
    return WEEKDAY_KR[dt.weekday()]


def month_week(dt: date) -> int:
    return ((dt.day - 1) // 7) + 1


def bucket_info(dt: date, horizon: str) -> tuple[str, str]:
    if horizon == "1일":
        return dt.isoformat(), f"{dt.month}/{dt.day}({weekday_label(dt)})"
    if horizon == "1주":
        week_no = month_week(dt)
        return f"{dt.year}-{dt.month:02d}-w{week_no}", f"{dt.year}년 {dt.month}월 {week_no}주"
    if horizon == "1개월":
        return f"{dt.year}-{dt.month:02d}", f"{dt.year}년 {dt.month}월"
    if horizon == "3개월":
        quarter = ((dt.month - 1) // 3) + 1
        return f"{dt.year}-q{quarter}", f"{dt.year}년 {quarter}분기"
    half = 1 if dt.month <= 6 else 2
    half_label = "상반기" if half == 1 else "하반기"
    return f"{dt.year}-h{half}", f"{dt.year}년 {half_label}"


def source_path(folder: str, bucket_id: str) -> str:
    return f"horizons/{folder}/{bucket_id}.json"


def deep_copy(value):
    return copy.deepcopy(value)


def score_display(value) -> str:
    number = as_float(value)
    if number is None:
        return "데이터 없음"
    if float(number).is_integer():
        return str(int(number))
    return f"{number:.1f}"


def iter_daily_results(root: Path) -> list[dict]:
    rows = []
    for path in sorted((root / "site").glob("20*-*-*/result.json")):
        ds = path.parent.name
        try:
            dt = date.fromisoformat(ds)
        except ValueError:
            continue
        payload = load_json(path)
        if not payload or "dataByPeriod" not in payload:
            continue
        rows.append(
            {
                "date": ds,
                "dt": dt,
                "path": path,
                "payload": payload,
                "score": as_float(payload.get("totalScore")),
                "status": payload.get("dataStatus", "partial"),
                "meta": payload.get("meta", {}) or {},
            }
        )
    rows.sort(key=lambda item: item["dt"])
    return rows


def collect_source_labels(entries: list[dict], limit: int = 4) -> list[str]:
    counts = defaultdict(int)
    for entry in entries:
        for item in entry["meta"].get("sourceCatalog", []) or []:
            label = item.get("label") or item.get("source") or "출처"
            counts[label] += int(item.get("count", 1) or 1)
    pairs = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    return [label for label, _ in pairs[:limit]]


def build_summary(entry_group: list[dict]) -> dict:
    scores = [entry["score"] for entry in entry_group if entry["score"] is not None]
    avg_score = round(sum(scores) / len(scores), 1) if scores else None
    best_score = round(max(scores), 1) if scores else None
    worst_score = round(min(scores), 1) if scores else None
    start_score = round(scores[0], 1) if scores else None
    end_score = round(scores[-1], 1) if scores else None
    docs_total = sum(int(entry["meta"].get("docsCount", 0) or 0) for entry in entry_group)
    statuses = [entry["status"] for entry in entry_group]
    status = max(statuses, key=lambda item: STATUS_RANK.get(item, 0)) if statuses else "empty"
    return {
        "count": len(entry_group),
        "fromDate": entry_group[0]["date"],
        "toDate": entry_group[-1]["date"],
        "avgScore": avg_score,
        "bestScore": best_score,
        "worstScore": worst_score,
        "startScore": start_score,
        "endScore": end_score,
        "docsTotal": docs_total,
        "status": status,
        "sourceLabels": collect_source_labels(entry_group),
    }


def aggregated_sources(entry_group: list[dict]) -> list[dict]:
    counts = defaultdict(lambda: {"label": "", "count": 0})
    for entry in entry_group:
        for item in entry["meta"].get("sourceCatalog", []) or []:
            key = item.get("source") or item.get("label") or "unknown"
            counts[key]["label"] = item.get("label") or key
            counts[key]["count"] += int(item.get("count", 1) or 1)
    items = []
    for source, meta in counts.items():
        items.append(
            {
                "label": meta["label"],
                "source": source,
                "title": f"{meta['label']} 누적 {meta['count']}건",
                "published_at": entry_group[-1]["date"],
            }
        )
    items.sort(key=lambda item: (-counts[item["source"]]["count"], item["label"]))
    return items[:4]


def enrich_view(view: dict, horizon: str, bucket_label: str, entry_group: list[dict]) -> dict:
    view = deep_copy(view)
    summary = build_summary(entry_group)
    sources = aggregated_sources(entry_group)
    avg_score_text = score_display(summary["avgScore"])
    end_score_text = score_display(summary["endScore"])
    best_score_text = score_display(summary["bestScore"])
    worst_score_text = score_display(summary["worstScore"])
    score_text = (
        f"평균 점수 {avg_score_text}, 최근 점수 {end_score_text}, "
        f"최고 {best_score_text}, 최저 {worst_score_text}"
        if summary["avgScore"] is not None or summary["endScore"] is not None
        else "점수 데이터가 제한적입니다."
    )
    source_text = ", ".join(summary["sourceLabels"]) if summary["sourceLabels"] else "출처 정보 없음"

    briefing = view.get("briefing", {}) or {}
    sentiment = briefing.get("sentiment", {}) or {}
    forecast = briefing.get("forecast", {}) or {}
    insights = list(briefing.get("insights", []) or [])

    if sentiment:
        desc = sentiment.get("desc", "")
        sentiment["desc"] = (
            f"{desc} | {bucket_label} 누적 {summary['count']}회 업데이트, {score_text}"
            if desc
            else f"{bucket_label} 누적 {summary['count']}회 업데이트, {score_text}"
        )
        briefing["sentiment"] = sentiment

    if forecast:
        original_text = forecast.get("text", "")
        forecast["title"] = f"{bucket_label} 누적 판단"
        forecast["text"] = (
            f"{bucket_label} 동안 {summary['count']}회 일간 업데이트가 누적되었습니다. "
            f"{score_text}. 누적 문서 {summary['docsTotal']}건, 주요 출처 {source_text}. "
            f"{original_text}"
        )
        forecast["sources"] = sources
        briefing["forecast"] = forecast

    insights.insert(
        0,
        {
            "category": "누적요약",
            "text": (
                f"{bucket_label} 구간은 {summary['fromDate']}~{summary['toDate']} 사이 "
                f"{summary['count']}회 업데이트를 기준으로 집계했습니다. {score_text}."
            ),
            "sources": sources,
        },
    )
    insights.insert(
        1,
        {
            "category": "데이터",
            "text": (
                f"누적 문서 {summary['docsTotal']}건, 주요 출처는 {source_text}입니다. "
                f"매일 결과를 누적해 {horizon} 관점으로 다시 정리한 뷰입니다."
            ),
            "sources": sources,
        },
    )
    briefing["insights"] = insights[:10]
    view["briefing"] = briefing

    news_list = list(view.get("newsList", []) or [])
    news_list.insert(
        0,
        {
            "title": f"{bucket_label} 누적 요약",
            "tags": [horizon, "누적", "집계"],
            "summary": (
                f"{bucket_label} 동안 {summary['count']}회 업데이트가 쌓였고, "
                f"{score_text}. 주요 출처는 {source_text}입니다."
            ),
            "impacts": [
                {"sector": "거시", "isPositive": True, "desc": f"{horizon} 관점에서 노이즈보다 추세 해석에 유리합니다."},
                {"sector": "포트폴리오", "isPositive": True, "desc": "단일 기사보다 누적 흐름을 기준으로 자산배분 판단이 가능합니다."},
                {"sector": "섹터", "isPositive": False, "desc": "단기 뉴스와 중기 방향성을 분리해서 해석해야 합니다."},
            ],
            "sources": sources,
        },
    )
    view["newsList"] = news_list[:6]

    portfolio = view.get("portfolio", {}) or {}
    if portfolio:
        portfolio["accountAlert"] = (
            f"{portfolio.get('accountAlert', '')} "
            f"| {bucket_label} 누적 {summary['count']}회 업데이트 기준."
        ).strip()
        review = portfolio.get("weeklyReview", {}) or {}
        trailing = (
            f"또한 {bucket_label} 누적 흐름 기준으로 최근 점수는 {end_score_text}입니다."
            if summary["endScore"] is not None
            else f"또한 {bucket_label} 누적 흐름 기준 점수 데이터는 아직 제한적입니다."
        )
        review["desc"] = f"{review.get('desc', '')} {trailing}".strip()
        portfolio["weeklyReview"] = review
        view["portfolio"] = portfolio

    recommendations = view.get("recommendations", {}) or {}
    ideas = list(recommendations.get("ideas", []) or [])
    if ideas:
        ideas[0]["reason"] = f"{bucket_label} 누적 기준. {ideas[0].get('reason', '')}".strip()
        recommendations["ideas"] = ideas
        view["recommendations"] = recommendations

    return view


def build_bucket_payload(horizon: str, bucket_id: str, bucket_label: str, entry_group: list[dict]) -> dict:
    latest = entry_group[-1]
    section = deep_copy((latest["payload"].get("dataByPeriod", {}) or {}).get(horizon, {}))
    section = enrich_view(section, horizon, bucket_label, entry_group)
    summary = build_summary(entry_group)
    return {
        "horizonType": horizon,
        "bucketId": bucket_id,
        "bucketLabel": bucket_label,
        "dataStatus": summary["status"],
        "memberDates": [entry["date"] for entry in entry_group],
        "fromDate": summary["fromDate"],
        "toDate": summary["toDate"],
        "updateCount": summary["count"],
        "avgScore": summary["avgScore"],
        "briefing": section.get("briefing", {}),
        "newsList": section.get("newsList", []),
        "portfolio": section.get("portfolio", {}),
        "recommendations": section.get("recommendations", {}),
        "meta": {
            "docsTotal": summary["docsTotal"],
            "sourceLabels": summary["sourceLabels"],
            "latestDailyDate": latest["date"],
        },
    }


def bucket_folder(horizon: str) -> str:
    return {
        "1일": "daily",
        "1주": "weekly",
        "1개월": "monthly",
        "3개월": "quarterly",
        "6개월": "halfyearly",
    }[horizon]


def build_horizon_views(root: Path) -> dict:
    entries = iter_daily_results(root)
    horizon_index = {"generatedAt": datetime.now().isoformat(), "latestDailyDate": entries[-1]["date"] if entries else "", "horizons": {}}

    for horizon, folder in HORIZON_CONFIG:
        grouped: dict[str, dict] = {}
        for entry in entries:
            if horizon not in (entry["payload"].get("dataByPeriod", {}) or {}):
                continue
            bucket_id, bucket_label = bucket_info(entry["dt"], horizon)
            if bucket_id not in grouped:
                grouped[bucket_id] = {"label": bucket_label, "entries": []}
            grouped[bucket_id]["entries"].append(entry)

        bucket_items = []
        for bucket_id, info in grouped.items():
            payload = build_bucket_payload(horizon, bucket_id, info["label"], info["entries"])
            rel_path = source_path(folder, bucket_id)
            save_json(root / "site" / rel_path, payload)
            bucket_items.append(
                {
                    "id": bucket_id,
                    "label": info["label"],
                    "source": rel_path,
                    "fromDate": payload["fromDate"],
                    "toDate": payload["toDate"],
                    "updateCount": payload["updateCount"],
                    "dataStatus": payload["dataStatus"],
                }
            )

        bucket_items.sort(key=lambda item: item["toDate"], reverse=True)
        horizon_index["horizons"][horizon] = bucket_items

    save_json(root / "site" / "horizon_index.json", horizon_index)
    template = root / "site" / "template" / "index.html"
    if template.exists():
        for page_dir in sorted((root / "site").glob("20*-*-*")):
            if page_dir.is_dir():
                shutil.copy(template, page_dir / "index.html")
    latest = horizon_index["latestDailyDate"]
    if latest:
        (root / "index.html").write_text(
            "\n".join(
                [
                    "<!doctype html>",
                    "<html>",
                    "<head>",
                    f'  <meta http-equiv="refresh" content="0; url=./site/{latest}/" />',
                    '  <meta charset="utf-8" />',
                    f"  <title>글로벌 매크로·ETF 리포트 - {latest}</title>",
                    "</head>",
                    "<body>",
                    f'  If you are not redirected, <a href="./site/{latest}/">open latest report</a>.',
                    "</body>",
                    "</html>",
                ]
            )
        )
    return horizon_index


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-dir", default=str(ROOT))
    args = parser.parse_args()
    root = Path(args.base_dir)
    index = build_horizon_views(root)
    print(f"wrote {root / 'site' / 'horizon_index.json'}")
    for horizon, items in index["horizons"].items():
        print(f"{horizon}: {len(items)} buckets")


if __name__ == "__main__":
    main()
