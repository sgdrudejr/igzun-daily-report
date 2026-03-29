#!/usr/bin/env python3
"""
Historical backfill runner for the existing collection/report pipeline.

Goals:
  - fill missing daily site data for a historical range
  - use historical-safe sources first
  - keep outputs compatible with the current site/horizon structure
"""
import argparse
import json
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable
SAFE_SOURCES = ["fred_api", "opendart"]
SNAPSHOT_ONLY_SOURCES = [
    "fed_speeches_rss",
    "fed_press_rss",
    "ecos_api",
    "naver_research",
    "kr_brokerage_kb",
    "kr_brokerage_mirae",
    "bis_speeches",
    "investing_com_rss",
]


def parse_iso_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def iter_dates(start: date, end: date, include_weekends: bool) -> list[date]:
    days = []
    current = start
    while current <= end:
        if include_weekends or current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def run_cmd(cmd: list[str], cwd: Path) -> dict:
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    tail = "\n".join(line for line in output.strip().splitlines()[-10:] if line.strip())
    return {"ok": proc.returncode == 0, "returncode": proc.returncode, "tail": tail}


def maybe_run_collectors(root: Path, day: str, sources: list[str], summary: dict):
    for source in sources:
        result = run_cmd(
            [PYTHON, "-m", "collectors.runner", "--date", day, "--source", source, "--base-dir", str(root)],
            root,
        )
        summary["commands"].append({"date": day, "step": f"collect:{source}", **result})


def main():
    parser = argparse.ArgumentParser(description="Backfill historical dates into the current report pipeline")
    parser.add_argument("--start-date", required=True, help="Backfill start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", required=True, help="Backfill end date (YYYY-MM-DD)")
    parser.add_argument("--base-dir", default=str(ROOT), help="Project root directory")
    parser.add_argument("--include-weekends", action="store_true", help="Include weekends")
    parser.add_argument("--include-bridge", action="store_true", help="Also append normalized docs to refined_insights inventory")
    parser.add_argument("--skip-existing-site", action="store_true", help="Skip dates that already have site/<date>/result.json")
    parser.add_argument(
        "--sources",
        help="Comma-separated source IDs to collect. Defaults to historical-safe sources only.",
    )
    args = parser.parse_args()

    root = Path(args.base_dir)
    start = parse_iso_date(args.start_date)
    end = parse_iso_date(args.end_date)
    collect_sources = [item.strip() for item in (args.sources or ",".join(SAFE_SOURCES)).split(",") if item.strip()]
    days = iter_dates(start, end, args.include_weekends)

    history_start = start - timedelta(days=400)
    market_cache = root / "data" / "market_data_history" / f"{args.start_date}_to_{args.end_date}.json"
    price_cache = root / "data" / "etf_price_history" / f"{args.start_date}_to_{args.end_date}.json"

    summary = {
        "generated_at": datetime.now().isoformat(),
        "start_date": args.start_date,
        "end_date": args.end_date,
        "dates_requested": [day.isoformat() for day in days],
        "dates_processed": [],
        "dates_skipped": [],
        "collect_sources": collect_sources,
        "skipped_snapshot_only_sources": SNAPSHOT_ONLY_SOURCES,
        "market_cache": str(market_cache),
        "etf_price_cache": str(price_cache),
        "commands": [],
    }

    market_cache.parent.mkdir(parents=True, exist_ok=True)
    price_cache.parent.mkdir(parents=True, exist_ok=True)

    preload_commands = [
        [
            PYTHON,
            str(root / "scripts" / "load_market_data.py"),
            "--base-dir",
            str(root),
            "--start-date",
            history_start.isoformat(),
            "--end-date",
            args.end_date,
            "--output",
            str(market_cache),
        ],
        [
            PYTHON,
            str(root / "scripts" / "etf_recommender.py"),
            "--base-dir",
            str(root),
            "--date",
            args.end_date,
            "--history-start-date",
            history_start.isoformat(),
            "--history-end-date",
            args.end_date,
            "--write-price-history",
            str(price_cache),
        ],
    ]

    for cmd in preload_commands:
        result = run_cmd(cmd, root)
        summary["commands"].append({"date": args.end_date, "step": Path(cmd[1]).name, **result})
        if not result["ok"]:
            raise SystemExit(f"backfill preload failed: {cmd[1]}\n{result['tail']}")

    for day in days:
        day_str = day.isoformat()
        site_result = root / "site" / day_str / "result.json"
        if args.skip_existing_site and site_result.exists():
            summary["dates_skipped"].append({"date": day_str, "reason": "site_result_exists"})
            continue

        maybe_run_collectors(root, day_str, collect_sources, summary)

        if args.include_bridge:
            result = run_cmd([PYTHON, "-m", "collectors.bridge", "--date", day_str, "--base-dir", str(root)], root)
            summary["commands"].append({"date": day_str, "step": "bridge", **result})

        for cmd in [
            [
                PYTHON,
                str(root / "scripts" / "macro_analysis.py"),
                "--base-dir",
                str(root),
                "--date",
                day_str,
                "--market-data-file",
                str(market_cache),
            ],
            [
                PYTHON,
                str(root / "scripts" / "etf_recommender.py"),
                "--base-dir",
                str(root),
                "--date",
                day_str,
                "--price-history-file",
                str(price_cache),
            ],
            [
                PYTHON,
                str(root / "scripts" / "build_site_report.py"),
                "--base-dir",
                str(root),
                "--date",
                day_str,
            ],
        ]:
            result = run_cmd(cmd, root)
            summary["commands"].append({"date": day_str, "step": Path(cmd[1]).name, **result})

        summary["dates_processed"].append(day_str)

    out_dir = root / "data" / "backfills"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{args.start_date}_to_{args.end_date}.json"
    out_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2))

    result = run_cmd([PYTHON, str(root / "scripts" / "build_horizon_views.py"), "--base-dir", str(root)], root)
    summary["commands"].append({"date": args.end_date, "step": "build_horizon_views.py", **result})
    out_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2))

    print(f"wrote {out_file}")
    print(f"processed {len(summary['dates_processed'])} dates")
    if summary["dates_skipped"]:
        print(f"skipped {len(summary['dates_skipped'])} dates")


if __name__ == "__main__":
    main()
