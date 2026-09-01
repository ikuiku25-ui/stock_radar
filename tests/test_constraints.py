"""Constraint tests: CHECK/UNIQUE/FK enforcement, including the 3 additions
approved in Phase 0 beyond the spec's literal DDL text (see schema.sql header).
"""

from __future__ import annotations

import sqlite3

import pytest


def _insert_company(conn, ticker="1234", listing_status="active"):
    conn.execute(
        """
        INSERT INTO companies (ticker, company_name, listing_status, updated_at)
        VALUES (?, 'テスト株式会社', ?, '2026-08-28T00:00:00+09:00')
        """,
        (ticker, listing_status),
    )


def test_companies_listing_status_check_rejects_invalid_value(empty_conn):
    with pytest.raises(sqlite3.IntegrityError):
        _insert_company(empty_conn, listing_status="bankrupt")


def test_companies_listing_status_check_accepts_valid_values(empty_conn):
    for i, status in enumerate(["active", "delisted", "suspended"]):
        _insert_company(empty_conn, ticker=f"100{i}", listing_status=status)
    rows = empty_conn.execute("SELECT ticker FROM companies").fetchall()
    assert len(rows) == 3


def _insert_disclosure(conn, ticker="1234"):
    cur = conn.execute(
        """
        INSERT INTO disclosures
            (ticker, title, raw_text, disclosed_at, market_available_at,
             system_available_at, fetched_at, availability_confidence,
             category, positive_material_raw, negative_penalty_raw,
             is_hard_block, dataset_tag)
        VALUES (?, 'お知らせ', '本文', '2026-08-20T15:00:00+09:00',
                '2026-08-20T15:00:00+09:00', '2026-08-20T15:01:00+09:00',
                '2026-08-20T15:01:05+09:00', 'HIGH', 'A', 10, 0, 0, 'statistical')
        """,
        (ticker,),
    )
    return cur.lastrowid


def _insert_weight_set(conn):
    cur = conn.execute(
        """
        INSERT INTO weight_sets
            (weight_material, weight_supply_demand, weight_theme, created_at)
        VALUES (50, 30, 20, '2026-08-28T00:00:00+09:00')
        """
    )
    return cur.lastrowid


def test_scores_notification_rank_check_rejects_invalid_value(empty_conn):
    conn = empty_conn
    _insert_company(conn)
    disclosure_id = _insert_disclosure(conn)
    weight_set_id = _insert_weight_set(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO scores
                (disclosure_id, ticker, weight_set_id, material_score,
                 supply_demand_score, theme_score, total_score,
                 notification_rank, scored_at, scoring_basis_time)
            VALUES (?, '1234', ?, 10, 10, 10, 30, 'X', '2026-08-20T15:05:00+09:00',
                    '2026-08-20T15:01:00+09:00')
            """,
            (disclosure_id, weight_set_id),
        )


def test_disclosures_availability_confidence_check(empty_conn):
    conn = empty_conn
    _insert_company(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO disclosures
                (ticker, title, raw_text, disclosed_at, market_available_at,
                 system_available_at, fetched_at, availability_confidence)
            VALUES ('1234', 'お知らせ', '本文', '2026-08-20T15:00:00+09:00',
                    '2026-08-20T15:00:00+09:00', '2026-08-20T15:01:00+09:00',
                    '2026-08-20T15:01:05+09:00', 'CERTAIN')
            """
        )


def test_price_data_session_type_check(empty_conn):
    conn = empty_conn
    _insert_company(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO price_data
                (ticker, trade_date, market_snapshot_at, session_type)
            VALUES ('1234', '2026-08-20', '2026-08-20T15:00:00+09:00', 'intraday')
            """
        )


def test_disclosures_dataset_tag_check(empty_conn):
    conn = empty_conn
    _insert_company(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO disclosures
                (ticker, title, raw_text, disclosed_at, market_available_at,
                 system_available_at, fetched_at, dataset_tag)
            VALUES ('1234', 'お知らせ', '本文', '2026-08-20T15:00:00+09:00',
                    '2026-08-20T15:00:00+09:00', '2026-08-20T15:01:00+09:00',
                    '2026-08-20T15:01:05+09:00', 'other')
            """
        )


def test_backtest_runs_confidence_mode_check(empty_conn):
    conn = empty_conn
    weight_set_id = _insert_weight_set(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO backtest_runs
                (run_name, confidence_mode, weight_set_id, started_at)
            VALUES ('run-1', 'LOW_ONLY', ?, '2026-08-28T00:00:00+09:00')
            """,
            (weight_set_id,),
        )


def test_disclosures_ticker_foreign_key_enforced(empty_conn):
    conn = empty_conn
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO disclosures
                (ticker, title, raw_text, disclosed_at, market_available_at,
                 system_available_at, fetched_at)
            VALUES ('9999', 'お知らせ', '本文', '2026-08-20T15:00:00+09:00',
                    '2026-08-20T15:00:00+09:00', '2026-08-20T15:01:00+09:00',
                    '2026-08-20T15:01:05+09:00')
            """
        )


def _insert_score(conn):
    _insert_company(conn)
    disclosure_id = _insert_disclosure(conn)
    weight_set_id = _insert_weight_set(conn)
    cur = conn.execute(
        """
        INSERT INTO scores
            (disclosure_id, ticker, weight_set_id, material_score,
             supply_demand_score, theme_score, total_score,
             notification_rank, scored_at, scoring_basis_time)
        VALUES (?, '1234', ?, 30, 20, 10, 60, 'A', '2026-08-20T15:05:00+09:00',
                '2026-08-20T15:01:00+09:00')
        """,
        (disclosure_id, weight_set_id),
    )
    return cur.lastrowid


def test_outcome_tracking_score_id_unique(empty_conn):
    """Spec §10.2: scores<->outcome_tracking must be 1:0 or 1:1."""
    conn = empty_conn
    score_id = _insert_score(conn)
    conn.execute(
        """
        INSERT INTO outcome_tracking (score_id, ticker, recorded_at)
        VALUES (?, '1234', '2026-08-21T15:00:00+09:00')
        """,
        (score_id,),
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO outcome_tracking (score_id, ticker, recorded_at)
            VALUES (?, '1234', '2026-08-21T15:05:00+09:00')
            """,
            (score_id,),
        )


def test_theme_hot_status_theme_id_foreign_key_enforced(empty_conn):
    with pytest.raises(sqlite3.IntegrityError):
        empty_conn.execute(
            """
            INSERT INTO theme_hot_status (trade_date, theme_id, theme_as_of_time, hot_flag)
            VALUES ('2026-08-20', 9999, '2026-08-20T15:00:00+09:00', 1)
            """
        )


def test_hard_block_forces_material_score_zero_convention(empty_conn):
    """Spec §8.3: material_score = 0 whenever is_hard_block is set, regardless
    of positive_material_raw. This test documents the convention the
    scoring module (Phase 4) must follow; the DB does not compute the score
    itself, so we assert the raw inputs plus the formula here.
    """
    conn = empty_conn
    _insert_company(conn)
    cur = conn.execute(
        """
        INSERT INTO disclosures
            (ticker, title, raw_text, disclosed_at, market_available_at,
             system_available_at, fetched_at, category,
             positive_material_raw, negative_penalty_raw, is_hard_block)
        VALUES ('1234', '民事再生法の適用申請', '本文', '2026-08-20T15:00:00+09:00',
                '2026-08-20T15:00:00+09:00', '2026-08-20T15:01:00+09:00',
                '2026-08-20T15:01:05+09:00', 'F', 25, -50, 1)
        """
    )
    row = conn.execute(
        "SELECT * FROM disclosures WHERE disclosure_id = ?", (cur.lastrowid,)
    ).fetchone()

    def material_score(row):
        if row["is_hard_block"]:
            return 0
        return max(0, row["positive_material_raw"] + row["negative_penalty_raw"])

    assert row["positive_material_raw"] == 25  # positive material was NOT discarded
    assert material_score(row) == 0  # but HARD_BLOCK still zeroes the score
