#!/usr/bin/env python3
"""Phase 3: classify every disclosure in the DB into categories A-G and
detect HARD_BLOCK/SOFT_NEGATIVE material (spec §8.3, §12 Phase 3).

Safe to re-run: classifies ALL disclosures each time (not just unclassified
ones), overwriting category/positive_material_raw/negative_penalty_raw/
is_hard_block — so re-running after a dictionary tweak
(collectors/classification/keywords.py) picks up the change everywhere.

Usage:
    python scripts/classify_disclosures.py --db-path data/stock_radar.db3
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from stock_radar.classification.classifier import classify_disclosure  # noqa: E402
from stock_radar.classification.repository import save_classification  # noqa: E402
from stock_radar.db.connection import get_connection  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db-path", default="data/stock_radar.db3")
    args = parser.parse_args()

    conn = get_connection(args.db_path)
    rows = conn.execute("SELECT disclosure_id, title, raw_text FROM disclosures").fetchall()

    hard_block_count = 0
    categorized_count = 0
    for row in rows:
        result = classify_disclosure(row["title"], row["raw_text"])
        save_classification(conn, row["disclosure_id"], result)
        if result.is_hard_block:
            hard_block_count += 1
        if result.category:
            categorized_count += 1
    conn.commit()
    conn.close()

    print(f"Classified {len(rows)} disclosure(s):")
    print(f"  {categorized_count} matched at least one positive category")
    print(f"  {hard_block_count} flagged HARD_BLOCK")
    print(f"  {len(rows) - categorized_count} matched no positive category (still checked for HARD_BLOCK/SOFT_NEGATIVE)")
    print("\nRun scripts/review_classifications.py to manually spot-check precision/recall (spec §12 Phase 3).")


if __name__ == "__main__":
    main()
