#!/usr/bin/env python3
"""Phase 6: score-band outcome report (spec §9, §12 Phase 6's completion
condition: "スコア帯別実績レポートが出力できる").

Only dataset_tag='statistical' rows count (spec §10.3) — the 4
case-study tickers never contribute to this report. Pass
--include-case-study-for-debugging-only to see them anyway, clearly
labeled as not meaningful statistically (e.g. to sanity-check the query
itself while no statistical data has been collected yet).

Usage:
    python scripts/backtest_report.py --db-path data/stock_radar.db3
    python scripts/backtest_report.py --db-path data/stock_radar.db3 --confidence-mode HIGH_MEDIUM
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from stock_radar.backtest.report import generate_score_band_report, score_band_report  # noqa: E402
from stock_radar.db.connection import get_connection  # noqa: E402
from stock_radar.scoring.weight_sets import ensure_baseline_weight_set  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db-path", default="data/stock_radar.db3")
    parser.add_argument("--confidence-mode", choices=["HIGH_ONLY", "HIGH_MEDIUM"], default="HIGH_ONLY")
    parser.add_argument(
        "--include-case-study-for-debugging-only",
        action="store_true",
        help="also include the 4 case-study tickers (NOT for statistical conclusions, spec §10.3)",
    )
    args = parser.parse_args()

    conn = get_connection(args.db_path)
    weight_set_id = ensure_baseline_weight_set(conn)
    conn.commit()

    if args.include_case_study_for_debugging_only:
        rows = score_band_report(
            conn, weight_set_id, args.confidence_mode, include_case_study_for_debugging_only=True
        )
        print("*** DEBUGGING VIEW: includes case_study rows — NOT a statistical result (spec §10.3) ***\n")
    else:
        run_id, rows = generate_score_band_report(conn, weight_set_id, args.confidence_mode)
        conn.commit()
        print(f"backtest_runs.run_id={run_id}  weight_set_id={weight_set_id}  confidence_mode={args.confidence_mode}\n")

    conn.close()

    if not rows:
        print("(no rows — likely because no dataset_tag='statistical' scores have outcome_tracking data yet; "
              "the 4 case-study tickers are excluded by design, see spec §10.3)")
        return

    print(f"{'band':<8}{'n':>6}{'avg_max_gain':>16}{'hit_rate_5pct':>16}{'hit_rate_stop_high':>20}")
    for row in rows:
        print(
            f"{row['score_band']:<8}{row['n']:>6}"
            f"{row['avg_max_gain']:>16.2f}{row['hit_rate_5pct']:>16.2%}{row['hit_rate_stop_high']:>20.2%}"
        )


if __name__ == "__main__":
    main()
