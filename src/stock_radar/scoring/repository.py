"""Persistence for scoring results (spec §6.1 `scores` table).

The schema has no UNIQUE(disclosure_id, weight_set_id) constraint (v1.3's
own DDL doesn't declare one, and this project hasn't added one — unlike
the Phase 0 additions — because a real DB may already hold scores rows
from before this constraint existed, and adding it now would need a table
rebuild migration out of scope for Phase 4). Re-scoring is instead made
idempotent at the application level: delete_scores_for_weight_set() clears
prior rows for that weight_set before scripts/score_disclosures.py
re-inserts, so re-running after a scoring-logic change doesn't accumulate
duplicates.
"""

from __future__ import annotations

import sqlite3

from .scorer import ScoreResult


def delete_scores_for_weight_set(conn: sqlite3.Connection, weight_set_id: int) -> None:
    conn.execute("DELETE FROM scores WHERE weight_set_id = ?", (weight_set_id,))


def save_score(conn: sqlite3.Connection, result: ScoreResult) -> int:
    cur = conn.execute(
        """
        INSERT INTO scores
            (disclosure_id, ticker, weight_set_id, material_score,
             supply_demand_score, theme_score, total_score,
             notification_rank, scored_at, scoring_basis_time, dataset_tag)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            result.disclosure_id,
            result.ticker,
            result.weight_set_id,
            result.material_score,
            result.supply_demand_score,
            result.theme_score,
            result.total_score,
            result.notification_rank,
            result.scored_at,
            result.scoring_basis_time,
            result.dataset_tag,
        ),
    )
    return cur.lastrowid
