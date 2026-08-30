"""Persistence for scoring results (spec §6.1 `scores` table).

The schema has no UNIQUE(disclosure_id, weight_set_id) constraint (v1.3's
own DDL doesn't declare one, and this project hasn't added one — unlike
the Phase 0 additions — because a real DB may already hold scores rows
from before this constraint existed, and adding it now would need a table
rebuild migration out of scope for Phase 4).

This module intentionally has NO knowledge of outcome_tracking (spec
§10.2: prediction-path code — classification/scoring — must never
reference it; enforced by tests/test_backtest_separation.py). The "don't
delete a score whose real-world outcome is already recorded" guard is a
backtest-integrity concern, not a scoring concern, so it lives in
backtest.repository.delete_rescoreable_scores_for_weight_set() instead —
callers that need re-scoring safety (scripts/score_disclosures.py, the
Phase 7 pipeline) use that, not a bare DELETE here.
"""

from __future__ import annotations

import sqlite3

from .scorer import ScoreResult


def delete_scores_for_weight_set(conn: sqlite3.Connection, weight_set_id: int) -> None:
    """Deletes ALL scores for this weight_set, with no awareness of
    outcome_tracking. Raises sqlite3.IntegrityError if any of them are
    outcome-tracked (Phase 0's FK) — callers that might hit that case (any
    DB where Phase 6 has recorded outcomes) should use
    backtest.repository.delete_rescoreable_scores_for_weight_set() instead.
    """
    conn.execute("DELETE FROM scores WHERE weight_set_id = ?", (weight_set_id,))


def has_score_for_weight_set(conn: sqlite3.Connection, disclosure_id: int, weight_set_id: int) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM scores WHERE disclosure_id = ? AND weight_set_id = ?",
            (disclosure_id, weight_set_id),
        ).fetchone()
        is not None
    )


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
