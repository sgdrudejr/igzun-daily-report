#!/usr/bin/env python3
"""
경량 GraphRAG용 로컬 리서치 그래프 생성기.

목적:
- 최근 인덱싱된 문서에서 topic/source/region/asset 간의 관계를 JSON 그래프로 만든다.
- 무거운 그래프 DB 없이도 수동/반자동 딥리서치에서 관계 탐색을 지원한다.

Output:
- data/research_graph/{date}.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


ASSET_RULES = {
    "SPY": ["s&p500", "spy", "미국 대형지수"],
    "QQQ": ["나스닥", "qqq", "미국 기술주"],
    "KODEX_SEMI": ["반도체", "hbm", "semiconductor"],
    "GLD": ["금", "gold"],
    "IEF": ["국채", "채권", "금리"],
    "KODEX_USD": ["달러", "usd", "환율"],
    "HANARO_KDEFENSE": ["방산", "국방", "미사일"],
    "BIO": ["바이오", "헬스케어", "제약"],
}


def _load_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _add_node(nodes: dict, node_id: str, label: str, node_type: str):
    if node_id not in nodes:
        nodes[node_id] = {
            "id": node_id,
            "label": label,
            "type": node_type,
        }


def _add_edge(edges: list, source: str, target: str, relation: str):
    edges.append({"source": source, "target": target, "relation": relation})


def _infer_assets(texts: list[str]) -> list[str]:
    blob = " ".join(texts).lower()
    assets = []
    for asset_id, keywords in ASSET_RULES.items():
        if any(keyword.lower() in blob for keyword in keywords):
            assets.append(asset_id)
    return assets


def build_research_graph(root: Path, date_str: str) -> dict:
    index = _load_json(root / "data" / "research_index" / "hierarchical" / f"{date_str}.json") or {}
    documents = index.get("documents") or []

    nodes = {}
    edges = []
    topic_counter = Counter()
    asset_counter = Counter()
    source_counter = Counter()

    for doc in documents:
        doc_id = f"doc:{doc.get('doc_id')}"
        _add_node(nodes, doc_id, doc.get("title") or doc.get("doc_id"), "document")

        source_id = doc.get("source_id") or "unknown"
        source_node = f"source:{source_id}"
        _add_node(nodes, source_node, doc.get("source_label") or source_id, "source")
        _add_edge(edges, doc_id, source_node, "from_source")
        source_counter[source_id] += 1

        region = doc.get("region") or "unknown"
        region_node = f"region:{region}"
        _add_node(nodes, region_node, region, "region")
        _add_edge(edges, doc_id, region_node, "belongs_region")

        topic_names = doc.get("topics") or []
        for topic in topic_names:
            topic_node = f"topic:{topic}"
            _add_node(nodes, topic_node, topic, "topic")
            _add_edge(edges, doc_id, topic_node, "mentions_topic")
            topic_counter[topic] += 1

        assets = _infer_assets([doc.get("title") or "", doc.get("coarse_summary") or ""] + topic_names)
        for asset in assets:
            asset_node = f"asset:{asset}"
            _add_node(nodes, asset_node, asset, "asset")
            _add_edge(edges, doc_id, asset_node, "impacts_asset")
            asset_counter[asset] += 1
            for topic in topic_names:
                _add_edge(edges, f"topic:{topic}", asset_node, "linked_asset")

    communities = {
        "top_topics": [{"topic": topic, "count": count} for topic, count in topic_counter.most_common(8)],
        "top_assets": [{"asset": asset, "count": count} for asset, count in asset_counter.most_common(8)],
        "top_sources": [{"source": source, "count": count} for source, count in source_counter.most_common(6)],
    }

    return {
        "date": date_str,
        "summary": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "document_count": len(documents),
        },
        "communities": communities,
        "nodes": list(nodes.values()),
        "edges": edges,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--base-dir", default=str(ROOT))
    args = parser.parse_args()

    root = Path(args.base_dir)
    graph = build_research_graph(root, args.date)

    out_dir = root / "data" / "research_graph"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{args.date}.json"
    out_file.write_text(json.dumps(graph, ensure_ascii=False, indent=2))
    print(f"wrote {out_file}")
    print(json.dumps(graph["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
