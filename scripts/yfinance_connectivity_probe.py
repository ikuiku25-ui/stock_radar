#!/usr/bin/env python3
"""Manual connectivity probe for yfinance.

Phase 2's completion condition requires a real 1-ticker connectivity test
(spec §12). This sandbox's outbound network policy blocks Yahoo Finance,
so run this script on a machine with normal internet access instead
(see README.md "Phase 2" section).

Usage:
    python scripts/yfinance_connectivity_probe.py --ticker 7203 --period 5d
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from stock_radar.collectors.yfinance_client import YFinanceClient  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ticker", default="7203", help="4-digit ticker to query (default: 7203)")
    parser.add_argument("--period", default="5d", help="yfinance period string, e.g. '5d', '3mo'")
    args = parser.parse_args()

    client = YFinanceClient()
    print(f"Fetching {args.period} of daily bars for ticker {args.ticker} ...", file=sys.stderr)
    bars = client.fetch_daily_bars(args.ticker, period=args.period)

    print(f"Parsed {len(bars)} bar(s):\n")
    for bar in bars:
        print(json.dumps(dataclasses.asdict(bar), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
