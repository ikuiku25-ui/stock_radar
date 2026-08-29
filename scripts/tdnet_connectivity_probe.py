#!/usr/bin/env python3
"""Manual connectivity probe for the unofficial TDnet API.

Phase 2's completion condition requires a real 1-ticker connectivity test
(spec §12). This sandbox's outbound network policy blocks the target host,
so run this script on a machine with normal internet access instead
(see README.md "Phase 2" section).

This makes exactly ONE real HTTP request per run and prints the parsed
result, so you can sanity-check the response schema before trusting
scripts/collect_case_study_data.py. See collectors/tdnet.py's module
docstring for the known risks (unofficial/personal service, unverified
schema, single point of failure).

Usage:
    python scripts/tdnet_connectivity_probe.py --ticker 7203 --limit 5
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from stock_radar.collectors.tdnet import TDnetClient, TDnetClientError  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ticker", default="7203", help="4-digit ticker to query (default: 7203)")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    client = TDnetClient()
    print(f"Fetching up to {args.limit} recent disclosure(s) for ticker {args.ticker} ...", file=sys.stderr)
    try:
        disclosures = client.fetch_by_ticker(args.ticker, limit=args.limit)
    except TDnetClientError as exc:
        print(f"FAILED to parse response: {exc}", file=sys.stderr)
        print("The API's response shape may have changed — check collectors/tdnet.py's _parse_record.", file=sys.stderr)
        sys.exit(1)

    print(f"Parsed {len(disclosures)} disclosure(s):\n")
    for d in disclosures:
        print(json.dumps(dataclasses.asdict(d), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
