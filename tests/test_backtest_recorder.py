"""Tests for the outcome-recording orchestrator (spec §10.1, §10.2)."""

from __future__ import annotations

import pytest

from stock_radar.backtest.recorder import ScoreNotFoundError, record_outcome_for_score


def _insert_company(conn, ticker="4840"):
    conn.execute(
        "INSERT INTO companies (ticker, company_name, listing_status, updated_at) "
        "VALUES (?, ?, 'active', '2026-08-28T00:00:00+09:00')",
        (ticker, f"Company {ticker}"),
    )


def _insert_disclosure(conn, ticker="4840", disclosed_at="2026-08-20T15:05:00+09:00"):
    cur = conn.execute(
        """
        INSERT INTO disclosures
            (ticker, title, raw_text, disclosed_at, market_available_at,
             system_available_at, fetched_at)
        VALUES (?, 'お知らせ', '本文', ?, ?, ?, ?)
        """,
        (ticker, disclosed_at, disclosed_at, disclosed_at, disclosed_at),
    )
    return cur.lastrowid


def _insert_score(conn, ticker="4840", disclosure_id=None):
    disclosure_id = disclosure_id or _insert_disclosure(conn, ticker)
    weight_set_id = conn.execute(
        "INSERT INTO weight_sets (weight_material, weight_supply_demand, weight_theme, created_at) "
        "VALUES (50, 30, 20, '2026-08-28T00:00:00+09:00')"
    ).lastrowid
    cur = conn.execute(
        """
        INSERT INTO scores
            (disclosure_id, ticker, weight_set_id, material_score,
             supply_demand_score, theme_score, total_score,
             notification_rank, scored_at, scoring_basis_time)
        VALUES (?, ?, ?, 30, 20, 10, 60, 'A', '2026-08-20T15:05:00+09:00', '2026-08-20T15:05:00+09:00')
        """,
        (disclosure_id, ticker, weight_set_id),
    )
    return cur.lastrowid


def _insert_price(conn, ticker, trade_date, open_, high, low, close):
    conn.execute(
        """
        INSERT INTO price_data
            (ticker, trade_date, open, high, low, close, volume,
             avg_volume_20d, market_snapshot_at, session_type)
        VALUES (?, ?, ?, ?, ?, ?, 1000, 500, ?, 'close')
        """,
        (ticker, trade_date, open_, high, low, close, f"{trade_date}T15:00:00+09:00"),
    )


def test_records_outcome_using_next_trading_day(empty_conn):
    conn = empty_conn
    _insert_company(conn, "4840")
    _insert_price(conn, "4840", "2026-08-20", 1240, 1260, 1230, 1250)
    _insert_price(conn, "4840", "2026-08-21", 1260, 1300, 1255, 1290)
    score_id = _insert_score(conn, "4840", _insert_disclosure(conn, "4840", "2026-08-20T15:05:00+09:00"))

    result = record_outcome_for_score(conn, score_id)

    assert result.outcome_id is not None
    row = conn.execute("SELECT * FROM outcome_tracking WHERE score_id = ?", (score_id,)).fetchone()
    assert row["prev_close"] == 1250
    assert row["next_day_open"] == 1260
    assert row["next_day_high"] == 1300


def test_skips_when_already_recorded(empty_conn):
    conn = empty_conn
    _insert_company(conn, "4840")
    _insert_price(conn, "4840", "2026-08-20", 1240, 1260, 1230, 1250)
    _insert_price(conn, "4840", "2026-08-21", 1260, 1300, 1255, 1290)
    score_id = _insert_score(conn, "4840", _insert_disclosure(conn, "4840", "2026-08-20T15:05:00+09:00"))

    record_outcome_for_score(conn, score_id)
    result = record_outcome_for_score(conn, score_id)

    assert result.outcome_id is None
    assert result.skipped_reason == "already recorded"
    count = conn.execute("SELECT COUNT(*) AS n FROM outcome_tracking").fetchone()["n"]
    assert count == 1


def test_skips_when_no_baseline_price_data(empty_conn):
    conn = empty_conn
    _insert_company(conn, "4840")
    score_id = _insert_score(conn, "4840", _insert_disclosure(conn, "4840", "2026-08-20T15:05:00+09:00"))

    result = record_outcome_for_score(conn, score_id)

    assert result.outcome_id is None
    assert result.skipped_reason == "no baseline price data"


def test_skips_when_next_trading_day_not_yet_available(empty_conn):
    conn = empty_conn
    _insert_company(conn, "4840")
    _insert_price(conn, "4840", "2026-08-20", 1240, 1260, 1230, 1250)
    score_id = _insert_score(conn, "4840", _insert_disclosure(conn, "4840", "2026-08-20T15:05:00+09:00"))

    result = record_outcome_for_score(conn, score_id)

    assert result.outcome_id is None
    assert result.skipped_reason == "next trading day not yet available"


def test_raises_for_missing_score(empty_conn):
    with pytest.raises(ScoreNotFoundError):
        record_outcome_for_score(empty_conn, score_id=9999)


def test_intraday_disclosure_uses_prior_day_as_baseline(empty_conn):
    """spec §8.2: an intraday disclosure's baseline must be the PRIOR
    confirmed close, and the 'next trading day' after THAT baseline is the
    disclosure day itself (still a valid, confirmed bar by then)."""
    conn = empty_conn
    _insert_company(conn, "4840")
    _insert_price(conn, "4840", "2026-08-19", 1200, 1220, 1190, 1210)
    _insert_price(conn, "4840", "2026-08-20", 1215, 1280, 1210, 1270)
    score_id = _insert_score(conn, "4840", _insert_disclosure(conn, "4840", "2026-08-20T10:00:00+09:00"))

    result = record_outcome_for_score(conn, score_id)

    row = conn.execute("SELECT * FROM outcome_tracking WHERE score_id = ?", (score_id,)).fetchone()
    assert result.outcome_id is not None
    assert row["prev_close"] == 1210  # 2026-08-19's close
    assert row["next_day_open"] == 1215  # 2026-08-20's own bar
