"""Tests for saving classification results back onto disclosures."""

from __future__ import annotations

from stock_radar.classification.classifier import ClassificationResult
from stock_radar.classification.repository import save_classification


def _insert_company(conn, ticker="4840"):
    conn.execute(
        "INSERT INTO companies (ticker, company_name, listing_status, updated_at) "
        "VALUES (?, ?, 'active', '2026-08-28T00:00:00+09:00')",
        (ticker, f"Company {ticker}"),
    )


def _insert_unclassified_disclosure(conn, ticker="4840"):
    cur = conn.execute(
        """
        INSERT INTO disclosures
            (ticker, title, raw_text, disclosed_at, market_available_at,
             system_available_at, fetched_at)
        VALUES (?, 'お知らせ', '本文', '2026-08-20T15:00:00+09:00',
                '2026-08-20T15:00:00+09:00', '2026-08-20T15:00:30+09:00',
                '2026-08-20T15:00:30+09:00')
        """,
        (ticker,),
    )
    return cur.lastrowid


def test_save_classification_updates_disclosure_row(empty_conn):
    conn = empty_conn
    _insert_company(conn)
    disclosure_id = _insert_unclassified_disclosure(conn)

    result = ClassificationResult(
        category="A,C",
        positive_material_raw=45,
        negative_penalty_raw=-15,
        is_hard_block=False,
    )
    save_classification(conn, disclosure_id, result)

    row = conn.execute(
        "SELECT category, positive_material_raw, negative_penalty_raw, is_hard_block "
        "FROM disclosures WHERE disclosure_id = ?",
        (disclosure_id,),
    ).fetchone()
    assert row["category"] == "A,C"
    assert row["positive_material_raw"] == 45
    assert row["negative_penalty_raw"] == -15
    assert row["is_hard_block"] == 0


def test_save_classification_persists_hard_block_flag(empty_conn):
    conn = empty_conn
    _insert_company(conn)
    disclosure_id = _insert_unclassified_disclosure(conn)

    result = ClassificationResult(
        category=None,
        positive_material_raw=0,
        negative_penalty_raw=-50,
        is_hard_block=True,
    )
    save_classification(conn, disclosure_id, result)

    row = conn.execute(
        "SELECT is_hard_block FROM disclosures WHERE disclosure_id = ?", (disclosure_id,)
    ).fetchone()
    assert row["is_hard_block"] == 1


def test_save_classification_is_idempotent_reclassify(empty_conn):
    """Re-running classification (e.g. after tweaking the dictionary) must
    overwrite the previous result, not accumulate/duplicate."""
    conn = empty_conn
    _insert_company(conn)
    disclosure_id = _insert_unclassified_disclosure(conn)

    save_classification(
        conn, disclosure_id,
        ClassificationResult(category="A", positive_material_raw=30, negative_penalty_raw=0, is_hard_block=False),
    )
    save_classification(
        conn, disclosure_id,
        ClassificationResult(category="A,G", positive_material_raw=40, negative_penalty_raw=0, is_hard_block=False),
    )

    row = conn.execute(
        "SELECT category, positive_material_raw FROM disclosures WHERE disclosure_id = ?",
        (disclosure_id,),
    ).fetchone()
    assert row["category"] == "A,G"
    assert row["positive_material_raw"] == 40
