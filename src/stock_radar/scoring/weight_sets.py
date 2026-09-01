"""weight_sets helpers (spec §6.1, §8.4, §9)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

BASELINE_NOTES = "Baseline weight set per spec §6.2 (unoptimized hypothesis weights)."


def ensure_baseline_weight_set(conn: sqlite3.Connection) -> int:
    """Return the id of a baseline 50/30/20 weight_set (spec §6.1's column
    defaults), creating one if none exists yet. A "baseline" here means
    training_period/evaluation_period are both NULL — it wasn't produced by
    walk-forward optimization (spec §8.4), so there's no window it could
    violate; it's simply always applicable. Safe to call repeatedly: it
    reuses the first baseline row it finds rather than creating duplicates.
    """
    row = conn.execute(
        "SELECT weight_set_id FROM weight_sets "
        "WHERE training_period_start IS NULL AND evaluation_period_start IS NULL "
        "ORDER BY weight_set_id LIMIT 1"
    ).fetchone()
    if row:
        return row["weight_set_id"]

    cur = conn.execute(
        """
        INSERT INTO weight_sets
            (weight_material, weight_supply_demand, weight_theme,
             training_period_start, training_period_end,
             evaluation_period_start, evaluation_period_end,
             created_at, notes)
        VALUES (50, 30, 20, NULL, NULL, NULL, NULL, ?, ?)
        """,
        (datetime.now(timezone.utc).isoformat(), BASELINE_NOTES),
    )
    return cur.lastrowid
