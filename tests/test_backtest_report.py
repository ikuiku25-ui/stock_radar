"""Tests for the §9 score-band report, including the §10.3 dataset_tag
guard and the availability_confidence mode filter (spec §8.1)."""

from __future__ import annotations

from stock_radar.backtest.report import generate_score_band_report, score_band_report


def _insert_company(conn, ticker):
    conn.execute(
        "INSERT INTO companies (ticker, company_name, listing_status, updated_at) "
        "VALUES (?, ?, 'active', '2026-08-28T00:00:00+09:00')",
        (ticker, f"Company {ticker}"),
    )


def _insert_scored_outcome(
    conn, ticker, total_score, weight_set_id, dataset_tag="statistical",
    availability_confidence="HIGH", max_intraday_gain_pct=3.0, hit_plus5pct=0, hit_upper_limit=0,
):
    cur = conn.execute(
        """
        INSERT INTO disclosures
            (ticker, title, raw_text, disclosed_at, market_available_at,
             system_available_at, fetched_at, availability_confidence, dataset_tag)
        VALUES (?, 'お知らせ', '本文', '2026-08-20T15:00:00+09:00',
                '2026-08-20T15:00:00+09:00', '2026-08-20T15:00:00+09:00',
                '2026-08-20T15:00:00+09:00', ?, ?)
        """,
        (ticker, availability_confidence, dataset_tag),
    )
    disclosure_id = cur.lastrowid

    cur = conn.execute(
        """
        INSERT INTO scores
            (disclosure_id, ticker, weight_set_id, material_score,
             supply_demand_score, theme_score, total_score,
             notification_rank, scored_at, scoring_basis_time, dataset_tag)
        VALUES (?, ?, ?, 0, 0, 0, ?, 'S', '2026-08-20T15:05:00+09:00',
                '2026-08-20T15:00:00+09:00', ?)
        """,
        (disclosure_id, ticker, weight_set_id, total_score, dataset_tag),
    )
    score_id = cur.lastrowid

    conn.execute(
        """
        INSERT INTO outcome_tracking
            (score_id, ticker, max_intraday_gain_pct, hit_plus5pct,
             hit_plus10pct, hit_upper_limit, recorded_at)
        VALUES (?, ?, ?, ?, 0, ?, '2026-08-21T15:00:00+09:00')
        """,
        (score_id, ticker, max_intraday_gain_pct, hit_plus5pct, hit_upper_limit),
    )
    return score_id


def _insert_weight_set(conn):
    return conn.execute(
        "INSERT INTO weight_sets (weight_material, weight_supply_demand, weight_theme, created_at) "
        "VALUES (50, 30, 20, '2026-08-28T00:00:00+09:00')"
    ).lastrowid


def test_groups_by_score_band(empty_conn):
    conn = empty_conn
    _insert_company(conn, "1001")
    weight_set_id = _insert_weight_set(conn)
    _insert_scored_outcome(conn, "1001", 95, weight_set_id, max_intraday_gain_pct=12.0, hit_plus5pct=1)
    _insert_scored_outcome(conn, "1001", 72, weight_set_id, max_intraday_gain_pct=1.0)

    rows = score_band_report(conn, weight_set_id)
    bands = {row["score_band"]: row for row in rows}
    assert bands["90+"]["n"] == 1
    assert bands["70-79"]["n"] == 1
    assert bands["90+"]["hit_rate_5pct"] == 1.0
    assert bands["70-79"]["hit_rate_5pct"] == 0.0


def test_excludes_case_study_by_default(empty_conn):
    conn = empty_conn
    _insert_company(conn, "4840")
    weight_set_id = _insert_weight_set(conn)
    _insert_scored_outcome(conn, "4840", 95, weight_set_id, dataset_tag="case_study")

    rows = score_band_report(conn, weight_set_id)
    assert rows == []


def test_includes_case_study_when_explicitly_requested(empty_conn):
    conn = empty_conn
    _insert_company(conn, "4840")
    weight_set_id = _insert_weight_set(conn)
    _insert_scored_outcome(conn, "4840", 95, weight_set_id, dataset_tag="case_study")

    rows = score_band_report(conn, weight_set_id, include_case_study_for_debugging_only=True)
    assert len(rows) == 1
    assert rows[0]["score_band"] == "90+"


def test_high_only_excludes_medium_confidence(empty_conn):
    conn = empty_conn
    _insert_company(conn, "1001")
    weight_set_id = _insert_weight_set(conn)
    _insert_scored_outcome(conn, "1001", 95, weight_set_id, availability_confidence="MEDIUM")

    rows = score_band_report(conn, weight_set_id, confidence_mode="HIGH_ONLY")
    assert rows == []

    rows = score_band_report(conn, weight_set_id, confidence_mode="HIGH_MEDIUM")
    assert len(rows) == 1


def test_generate_score_band_report_records_backtest_run(empty_conn):
    conn = empty_conn
    _insert_company(conn, "1001")
    weight_set_id = _insert_weight_set(conn)
    _insert_scored_outcome(conn, "1001", 95, weight_set_id)

    run_id, rows = generate_score_band_report(conn, weight_set_id, run_name="test-run")

    run_row = conn.execute("SELECT * FROM backtest_runs WHERE run_id = ?", (run_id,)).fetchone()
    assert run_row["run_name"] == "test-run"
    assert run_row["weight_set_id"] == weight_set_id
    assert run_row["finished_at"] is not None
    assert len(rows) == 1
