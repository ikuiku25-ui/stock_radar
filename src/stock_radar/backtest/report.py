"""Score-band outcome report (spec §9's own SQL example, §12 Phase 6).

CRITICAL per spec §10.3: statistical validation MUST filter to
dataset_tag='statistical'. The 4 case-study tickers (dataset_tag=
'case_study') exist only to check that materials are fetched/classified/
scored correctly — never to judge whether the model "works". This module
defaults to 'statistical' and requires an explicit opt-in to include
case_study rows (see include_case_study_for_debugging_only), so a caller
can't silently produce a "statistical" report over demo data.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Optional

CONFIDENCE_MODE_VALUES = {
    "HIGH_ONLY": ("HIGH",),
    "HIGH_MEDIUM": ("HIGH", "MEDIUM"),
}


def create_backtest_run(
    conn: sqlite3.Connection,
    run_name: str,
    confidence_mode: str,
    weight_set_id: int,
    dataset_tag: str = "statistical",
    notes: Optional[str] = None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO backtest_runs (run_name, confidence_mode, weight_set_id, dataset_tag, started_at, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (run_name, confidence_mode, weight_set_id, dataset_tag, datetime.now(timezone.utc).isoformat(), notes),
    )
    return cur.lastrowid


def finish_backtest_run(conn: sqlite3.Connection, run_id: int) -> None:
    conn.execute(
        "UPDATE backtest_runs SET finished_at = ? WHERE run_id = ?",
        (datetime.now(timezone.utc).isoformat(), run_id),
    )


def score_band_report(
    conn: sqlite3.Connection,
    weight_set_id: int,
    confidence_mode: str = "HIGH_ONLY",
    include_case_study_for_debugging_only: bool = False,
) -> list[sqlite3.Row]:
    if confidence_mode not in CONFIDENCE_MODE_VALUES:
        raise ValueError(f"confidence_mode must be one of {list(CONFIDENCE_MODE_VALUES)}, got {confidence_mode!r}")
    confidence_values = CONFIDENCE_MODE_VALUES[confidence_mode]
    confidence_placeholders = ",".join("?" * len(confidence_values))

    dataset_tag_clause = "s.dataset_tag = 'statistical'"
    if include_case_study_for_debugging_only:
        dataset_tag_clause = "s.dataset_tag IN ('statistical', 'case_study')"

    query = f"""
        SELECT
          CASE
            WHEN s.total_score >= 90 THEN '90+'
            WHEN s.total_score >= 80 THEN '80-89'
            WHEN s.total_score >= 70 THEN '70-79'
            ELSE '<70'
          END AS score_band,
          COUNT(*) AS n,
          AVG(o.max_intraday_gain_pct) AS avg_max_gain,
          AVG(CASE WHEN o.hit_plus5pct THEN 1.0 ELSE 0 END) AS hit_rate_5pct,
          AVG(CASE WHEN o.hit_upper_limit THEN 1.0 ELSE 0 END) AS hit_rate_stop_high
        FROM scores s
        JOIN outcome_tracking o ON o.score_id = s.score_id
        JOIN disclosures d ON d.disclosure_id = s.disclosure_id
        WHERE {dataset_tag_clause}
          AND s.weight_set_id = ?
          AND d.availability_confidence IN ({confidence_placeholders})
        GROUP BY score_band
    """
    return conn.execute(query, (weight_set_id, *confidence_values)).fetchall()


def generate_score_band_report(
    conn: sqlite3.Connection,
    weight_set_id: int,
    confidence_mode: str = "HIGH_ONLY",
    run_name: str = "score_band_report",
) -> tuple[int, list[sqlite3.Row]]:
    """Runs score_band_report() while recording it as a backtest_runs row
    (spec §6.1's backtest_runs table), so every report has an audit trail
    of which weight_set/confidence_mode produced it."""
    run_id = create_backtest_run(conn, run_name, confidence_mode, weight_set_id)
    rows = score_band_report(conn, weight_set_id, confidence_mode)
    finish_backtest_run(conn, run_id)
    return run_id, rows
