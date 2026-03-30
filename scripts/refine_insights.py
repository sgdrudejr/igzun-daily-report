#!/usr/bin/env python3
import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDF_JSON = ROOT / "data/processed_pdf_texts.json"
RAW_BASE = Path(os.getenv("IGZUN_REPORTING_RAW_BASE", "/Users/seo/.openclaw/workspace/2_Project/Reporting/input/raw"))
COLLECTED_RAW_BASE = ROOT / "data" / "raw"
OUT = ROOT / "data/refined_insights_inventory.json"

PROMPT_TEMPLATE = """다음 금융/매크로 리포트 본문을 읽고 반드시 JSON만 출력하라.
조건:
- 한국어로 쓸 것
- core_subject는 핵심 주제를 짧게
- sentiment.score는 -1.0 ~ 1.0
- key_takeaways는 정확히 3개
- impact_assets는 USD, Bonds, Stocks 3개 키를 반드시 포함
- 과도한 추측 금지. 본문에 없는 것은 보수적으로 작성

출력 JSON 스키마:
{
  "core_subject": "string",
  "sentiment": {"score": 0.0, "rationale": "string"},
  "key_takeaways": ["string", "string", "string"],
  "impact_assets": {"USD": "string", "Bonds": "string", "Stocks": "string"}
}

문서 제목: {title}
문서 본문:
{text}
"""

TITLE_MAP = [
    ("fomc", "연준 금리 동결 및 향후 전망"),
    ("inflation", "인플레이션 및 금리 경로 점검"),
    ("oil", "유가 상승과 에너지 시장 영향"),
    ("iran", "이란 리스크와 글로벌 시장 파급"),
    ("housing", "미국 주택시장 전망"),
    ("market outlook", "시장 전망"),
    ("outlook", "거시 및 시장 전망"),
    ("daily", "일일 시장 브리핑"),
]


def clean_text(text):
    return re.sub(r"\s+", " ", text).strip()


def heuristic_item(source_file, source_path, date_value, text):
    lowered = text.lower()
    score = 0.0
    rationale = []
    if "hold rates steady" in lowered or "동결" in text:
        score -= 0.2
        rationale.append("금리 동결")
    if "inflation" in lowered or "인플레" in text:
        score -= 0.3
        rationale.append("인플레이션 부담")
    if "rate cuts" in lowered or "금리 인하" in text:
        score += 0.2
        rationale.append("금리 인하 기대")
    if "oil" in lowered or "유가" in text:
        score -= 0.2
        rationale.append("유가 부담")
    score = max(-1.0, min(1.0, score))
    subject = "거시/시장 리포트 요약"
    lowered_title = (source_file + " " + text[:500]).lower()
    for key, label in TITLE_MAP:
        if key in lowered_title:
            subject = label
            break
    sentences = re.split(r"(?<=[.!?])\s+", text)
    takeaways = []
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 40:
            continue
        takeaways.append(sentence[:140] + ("..." if len(sentence) > 140 else ""))
        if len(takeaways) == 3:
            break
    while len(takeaways) < 3:
        takeaways.append("추가 핵심 문장 추출 필요")
    impact = {"USD": "중립", "Bonds": "중립", "Stocks": "중립"}
    if "inflation" in lowered or "유가" in text or "oil" in lowered:
        impact = {"USD": "강세", "Bonds": "금리 상승/가격 하락", "Stocks": "약세"}
    elif "rate cuts" in lowered or "금리 인하" in text:
        impact = {"USD": "약세 가능", "Bonds": "가격 상승 가능", "Stocks": "완화적"}
    return {
        "source_file": source_file,
        "date": date_value,
        "core_subject": subject,
        "sentiment": {"score": score, "rationale": ", ".join(rationale) if rationale else "원문 기반 중립 판정"},
        "key_takeaways": takeaways,
        "impact_assets": impact,
        "source_meta": {
            "display_name": source_file,
            "broker_or_source": source_path.split("/raw/")[-1].split("/")[0] if "/raw/" in source_path else "",
            "path": source_path,
        },
    }


def try_llm(title, text, retries=2):
    prompt = PROMPT_TEMPLATE.format(title=title, text=text[:12000])
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as handle:
        handle.write(prompt)
        prompt_path = handle.name
    try:
        for attempt in range(retries + 1):
            try:
                proc = subprocess.run(
                    ["summarize", prompt_path, "--length", "short"],
                    capture_output=True,
                    text=True,
                    timeout=180,
                )
                if proc.returncode != 0:
                    raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
                match = re.search(r"\{.*\}", proc.stdout.strip(), flags=re.S)
                if not match:
                    raise ValueError("JSON not found in LLM output")
                return json.loads(match.group(0))
            except Exception:
                if attempt >= retries:
                    raise
                time.sleep(1.5 * (attempt + 1))
    finally:
        try:
            Path(prompt_path).unlink()
        except Exception:
            pass


def extract_date(path_str):
    match = re.search(r"(20\d{2}-\d{2}-\d{2})", path_str)
    return match.group(1) if match else ""


def load_txt_files():
    items = []
    if not RAW_BASE.exists():
        return items
    for path in sorted(RAW_BASE.rglob("*.txt")):
        try:
            text = path.read_text(errors="ignore")
        except Exception:
            continue
        items.append(
            {
                "source_file": path.name,
                "source_path": str(path),
                "date": extract_date(str(path)),
                "clean_text": clean_text(text),
            }
        )
    return items


def load_collected_txt_files():
    items = []
    if not COLLECTED_RAW_BASE.exists():
        return items

    best_paths = {}
    for path in sorted(COLLECTED_RAW_BASE.rglob("*.txt")):
        key = str(path).replace("_detail.txt", ".txt")
        rank = 1 if path.name.endswith("_detail.txt") else 2
        current = best_paths.get(key)
        if current and current[0] >= rank:
            continue
        best_paths[key] = (rank, path)

    for _, path in best_paths.values():
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        items.append(
            {
                "source_file": path.name,
                "source_path": str(path),
                "date": extract_date(str(path)),
                "clean_text": clean_text(text),
            }
        )
    return items


def build_item(source_file, source_path, date_value, clean_text_value):
    text = clean_text(clean_text_value or "")
    if not text:
        return heuristic_item(source_file, source_path, date_value, text)
    try:
        llm = try_llm(source_file, text)
        return {
            "source_file": source_file,
            "date": date_value,
            "core_subject": llm.get("core_subject", "거시/시장 리포트 요약"),
            "sentiment": llm.get("sentiment", {"score": 0.0, "rationale": "LLM 응답 누락"}),
            "key_takeaways": llm.get("key_takeaways", ["요약 누락", "요약 누락", "요약 누락"])[:3],
            "impact_assets": llm.get("impact_assets", {"USD": "중립", "Bonds": "중립", "Stocks": "중립"}),
            "source_meta": {
                "display_name": source_file,
                "broker_or_source": source_path.split("/raw/")[-1].split("/")[0] if "/raw/" in source_path else "",
                "path": source_path,
            },
            "analysis_mode": "llm",
        }
    except Exception:
        item = heuristic_item(source_file, source_path, date_value, text)
        item["analysis_mode"] = "heuristic_fallback"
        return item


def main():
    pdf_items = json.loads(PDF_JSON.read_text()) if PDF_JSON.exists() else []
    txt_items = load_txt_files()
    collected_txt_items = load_collected_txt_files()
    results = []
    for item in pdf_items:
        results.append(
            build_item(
                item.get("source_file", ""),
                item.get("source_path", ""),
                extract_date(item.get("source_path", "")),
                item.get("clean_text", ""),
            )
        )
    for item in txt_items:
        results.append(build_item(item["source_file"], item["source_path"], item["date"], item["clean_text"]))
    for item in collected_txt_items:
        results.append(build_item(item["source_file"], item["source_path"], item["date"], item["clean_text"]))
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print("wrote", OUT, "count=", len(results))


if __name__ == "__main__":
    main()
