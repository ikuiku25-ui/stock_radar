"""Persistence for classification results (spec §12 Phase 3)."""

from __future__ import annotations

import sqlite3

from .classifier import ClassificationResult


def save_classification(conn: sqlite3.Connection, disclosure_id: int, result: ClassificationResult) -> None:
    conn.execute(
        """
        UPDATE disclosures
        SET category = ?, positive_material_raw = ?, negative_penalty_raw = ?, is_hard_block = ?
        WHERE disclosure_id = ?
        """,
        (
            result.category,
            result.positive_material_raw,
            result.negative_penalty_raw,
            1 if result.is_hard_block else 0,
            disclosure_id,
        ),
    )
