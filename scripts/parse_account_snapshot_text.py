#!/usr/bin/env python3
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "data/account_snapshot_inbox"
OUT = INBOX / f"{date.today().isoformat()}_snapshot.json"
LATEST = ROOT / "data/account_snapshot_latest.json"


def parse_money(value):
    normalized = value.replace(",", "").replace("원", "").strip()
    match = re.search(r"-?\d+(?:\.\d+)?", normalized)
    return float(match.group(0)) if match else 0.0


BROKER_TOKENS = [
    ("TOSS", ["토스증권", "toss securities"]),
    ("ISA", ["isa", "신한 isa", "신한은행 isa", "개인종합자산관리"]),
    ("PENSION", ["연금저축", "신한은행 연금", "pension"]),
]


def detect_broker(lines: list[str]) -> str:
    joined = " ".join(lines).lower()
    for key, tokens in BROKER_TOKENS:
        if any(t in joined for t in tokens):
            return key
    return "admin_bot_ocr"


def parse_text(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    result = {
        "account_date": date.today().isoformat(),
        "broker": detect_broker(lines),
        "currency": "KRW",
        "total_deposit": 0,
        "cash": 0,
        "total_equity": 0,
        "positions": [],
    }
    for line in lines:
        if "총 예수금" in line:
            result["total_deposit"] = parse_money(line)
        elif "예수금" in line and result["cash"] == 0:
            result["cash"] = parse_money(line)
        elif "평가금액" in line or "총자산" in line or "총 평가금액" in line:
            result["total_equity"] = max(result["total_equity"], parse_money(line))
    for line in lines:
        match = re.search(r"([A-Z]{1,5})\s+([^\d]+?)\s+(\d+(?:\.\d+)?)\s+([\d,]+(?:\.\d+)?)\s+([\d,]+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)%", line)
        if not match:
            continue
        ticker, name, qty, avg_price, current_price, alloc = match.groups()
        quantity = float(qty)
        avg_price = parse_money(avg_price)
        current_price = parse_money(current_price)
        allocation = float(alloc)
        market_value = quantity * current_price
        pnl_amount = (current_price - avg_price) * quantity
        pnl_pct = ((current_price / avg_price) - 1) * 100 if avg_price else 0
        result["positions"].append(
            {
                "ticker": ticker,
                "name": name.strip(),
                "quantity": quantity,
                "avg_price": avg_price,
                "current_price": current_price,
                "market_value": market_value,
                "pnl_amount": pnl_amount,
                "pnl_pct": pnl_pct,
                "allocation": allocation,
                "currency": "KRW",
            }
        )
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("src", help="OCR text file path")
    parser.add_argument("--account", help="Account key override: TOSS | ISA | PENSION")
    args = parser.parse_args()

    src = Path(args.src)
    result = parse_text(src.read_text(errors="ignore"))

    # --account flag overrides broker detection from OCR text
    if args.account:
        result["broker"] = args.account.upper()

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    LATEST.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print("wrote", OUT)
    print("updated latest", LATEST)


if __name__ == "__main__":
    main()
