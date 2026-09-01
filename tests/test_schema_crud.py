"""CRUD smoke tests for every table in schema.sql (Phase 1 completion condition)."""

from __future__ import annotations


def test_companies_crud(empty_conn):
    conn = empty_conn
    conn.execute(
        """
        INSERT INTO companies
            (ticker, company_name, market_segment, sector, market_cap_yen,
             float_shares_ratio, latest_annual_sales_yen, listing_status,
             delisted_at, updated_at)
        VALUES ('1234', 'テスト株式会社', 'プライム', 'サービス業', 1000000000,
                0.5, 500000000, 'active', NULL, '2026-08-28T00:00:00+09:00')
        """
    )
    row = conn.execute("SELECT * FROM companies WHERE ticker = '1234'").fetchone()
    assert row["company_name"] == "テスト株式会社"

    conn.execute("UPDATE companies SET company_name = ? WHERE ticker = '1234'", ("改称後株式会社",))
    row = conn.execute("SELECT company_name FROM companies WHERE ticker = '1234'").fetchone()
    assert row["company_name"] == "改称後株式会社"

    conn.execute("DELETE FROM companies WHERE ticker = '1234'")
    row = conn.execute("SELECT * FROM companies WHERE ticker = '1234'").fetchone()
    assert row is None


def _insert_company(conn, ticker="1234"):
    conn.execute(
        """
        INSERT INTO companies
            (ticker, company_name, listing_status, updated_at)
        VALUES (?, 'テスト株式会社', 'active', '2026-08-28T00:00:00+09:00')
        """,
        (ticker,),
    )


def test_disclosures_crud(empty_conn):
    conn = empty_conn
    _insert_company(conn)
    cur = conn.execute(
        """
        INSERT INTO disclosures
            (ticker, title, raw_text, disclosed_at, market_available_at,
             system_available_at, fetched_at, availability_confidence,
             category, positive_material_raw, negative_penalty_raw,
             is_hard_block, dataset_tag)
        VALUES ('1234', 'お知らせ', '本文', '2026-08-20T15:00:00+09:00',
                '2026-08-20T15:00:00+09:00', '2026-08-20T15:01:00+09:00',
                '2026-08-20T15:01:05+09:00', 'HIGH', 'A', 10, 0, 0, 'statistical')
        """
    )
    disclosure_id = cur.lastrowid

    row = conn.execute(
        "SELECT * FROM disclosures WHERE disclosure_id = ?", (disclosure_id,)
    ).fetchone()
    assert row["ticker"] == "1234"
    assert row["dataset_tag"] == "statistical"

    conn.execute(
        "UPDATE disclosures SET positive_material_raw = 20 WHERE disclosure_id = ?",
        (disclosure_id,),
    )
    row = conn.execute(
        "SELECT positive_material_raw FROM disclosures WHERE disclosure_id = ?",
        (disclosure_id,),
    ).fetchone()
    assert row["positive_material_raw"] == 20

    conn.execute("DELETE FROM disclosures WHERE disclosure_id = ?", (disclosure_id,))
    row = conn.execute(
        "SELECT * FROM disclosures WHERE disclosure_id = ?", (disclosure_id,)
    ).fetchone()
    assert row is None


def test_price_data_crud(empty_conn):
    conn = empty_conn
    _insert_company(conn)
    conn.execute(
        """
        INSERT INTO price_data
            (ticker, trade_date, open, high, low, close, volume,
             avg_volume_20d, market_snapshot_at, session_type)
        VALUES ('1234', '2026-08-20', 100.0, 105.0, 99.0, 103.0, 10000,
                9000.0, '2026-08-20T15:00:00+09:00', 'close')
        """
    )
    row = conn.execute(
        "SELECT * FROM price_data WHERE ticker = '1234' AND trade_date = '2026-08-20'"
    ).fetchone()
    assert row["close"] == 103.0

    conn.execute(
        "UPDATE price_data SET close = 110.0 WHERE ticker = '1234' AND trade_date = '2026-08-20' AND session_type = 'close'"
    )
    row = conn.execute(
        "SELECT close FROM price_data WHERE ticker = '1234' AND trade_date = '2026-08-20'"
    ).fetchone()
    assert row["close"] == 110.0

    conn.execute(
        "DELETE FROM price_data WHERE ticker = '1234' AND trade_date = '2026-08-20' AND session_type = 'close'"
    )
    row = conn.execute(
        "SELECT * FROM price_data WHERE ticker = '1234' AND trade_date = '2026-08-20'"
    ).fetchone()
    assert row is None


def test_theme_keywords_and_hot_status_crud(empty_conn):
    conn = empty_conn
    cur = conn.execute(
        """
        INSERT INTO theme_keywords (theme_name, keyword_regex, is_active, created_at)
        VALUES ('半導体', '半導体|ウエハ', 1, '2026-01-01T00:00:00+09:00')
        """
    )
    theme_id = cur.lastrowid

    conn.execute(
        """
        INSERT INTO theme_hot_status (trade_date, theme_id, theme_as_of_time, hot_flag)
        VALUES ('2026-08-20', ?, '2026-08-20T15:00:00+09:00', 1)
        """,
        (theme_id,),
    )
    row = conn.execute(
        "SELECT * FROM theme_hot_status WHERE trade_date = '2026-08-20' AND theme_id = ?",
        (theme_id,),
    ).fetchone()
    assert row["hot_flag"] == 1

    conn.execute(
        "UPDATE theme_hot_status SET hot_flag = 0 WHERE trade_date = '2026-08-20' AND theme_id = ?",
        (theme_id,),
    )
    row = conn.execute(
        "SELECT hot_flag FROM theme_hot_status WHERE trade_date = '2026-08-20' AND theme_id = ?",
        (theme_id,),
    ).fetchone()
    assert row["hot_flag"] == 0

    # theme_hot_status.theme_id references theme_keywords, so the child row
    # must be removed first (FK enforcement verified in test_constraints.py).
    conn.execute(
        "DELETE FROM theme_hot_status WHERE trade_date = '2026-08-20' AND theme_id = ?",
        (theme_id,),
    )
    conn.execute("DELETE FROM theme_keywords WHERE theme_id = ?", (theme_id,))
    row = conn.execute("SELECT * FROM theme_keywords WHERE theme_id = ?", (theme_id,)).fetchone()
    assert row is None


def test_weight_sets_crud(empty_conn):
    conn = empty_conn
    cur = conn.execute(
        """
        INSERT INTO weight_sets
            (weight_material, weight_supply_demand, weight_theme, created_at, notes)
        VALUES (50, 30, 20, '2026-08-28T00:00:00+09:00', 'baseline')
        """
    )
    weight_set_id = cur.lastrowid

    row = conn.execute(
        "SELECT * FROM weight_sets WHERE weight_set_id = ?", (weight_set_id,)
    ).fetchone()
    assert row["weight_material"] == 50

    conn.execute(
        "UPDATE weight_sets SET notes = 'updated' WHERE weight_set_id = ?", (weight_set_id,)
    )
    row = conn.execute(
        "SELECT notes FROM weight_sets WHERE weight_set_id = ?", (weight_set_id,)
    ).fetchone()
    assert row["notes"] == "updated"

    conn.execute("DELETE FROM weight_sets WHERE weight_set_id = ?", (weight_set_id,))
    row = conn.execute(
        "SELECT * FROM weight_sets WHERE weight_set_id = ?", (weight_set_id,)
    ).fetchone()
    assert row is None


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


def test_scores_crud(empty_conn):
    conn = empty_conn
    _insert_company(conn)
    disclosure_id = _insert_disclosure(conn)
    weight_set_id = _insert_weight_set(conn)

    cur = conn.execute(
        """
        INSERT INTO scores
            (disclosure_id, ticker, weight_set_id, material_score,
             supply_demand_score, theme_score, total_score,
             notification_rank, scored_at, scoring_basis_time, dataset_tag)
        VALUES (?, '1234', ?, 30, 20, 10, 60, 'A', '2026-08-20T15:05:00+09:00',
                '2026-08-20T15:01:00+09:00', 'statistical')
        """,
        (disclosure_id, weight_set_id),
    )
    score_id = cur.lastrowid

    row = conn.execute("SELECT * FROM scores WHERE score_id = ?", (score_id,)).fetchone()
    assert row["total_score"] == 60

    conn.execute("UPDATE scores SET notification_rank = 'S' WHERE score_id = ?", (score_id,))
    row = conn.execute(
        "SELECT notification_rank FROM scores WHERE score_id = ?", (score_id,)
    ).fetchone()
    assert row["notification_rank"] == "S"

    conn.execute("DELETE FROM scores WHERE score_id = ?", (score_id,))
    row = conn.execute("SELECT * FROM scores WHERE score_id = ?", (score_id,)).fetchone()
    assert row is None


def _insert_score(conn):
    _insert_company(conn)
    disclosure_id = _insert_disclosure(conn)
    weight_set_id = _insert_weight_set(conn)
    cur = conn.execute(
        """
        INSERT INTO scores
            (disclosure_id, ticker, weight_set_id, material_score,
             supply_demand_score, theme_score, total_score,
             notification_rank, scored_at, scoring_basis_time, dataset_tag)
        VALUES (?, '1234', ?, 30, 20, 10, 60, 'A', '2026-08-20T15:05:00+09:00',
                '2026-08-20T15:01:00+09:00', 'statistical')
        """,
        (disclosure_id, weight_set_id),
    )
    return cur.lastrowid


def test_watchlist_crud(empty_conn):
    conn = empty_conn
    score_id = _insert_score(conn)

    cur = conn.execute(
        """
        INSERT INTO watchlist (ticker, score_id, added_at, note)
        VALUES ('1234', ?, '2026-08-20T15:06:00+09:00', 'メモ')
        """,
        (score_id,),
    )
    watchlist_id = cur.lastrowid

    row = conn.execute(
        "SELECT * FROM watchlist WHERE watchlist_id = ?", (watchlist_id,)
    ).fetchone()
    assert row["note"] == "メモ"

    conn.execute(
        "UPDATE watchlist SET note = '更新済み' WHERE watchlist_id = ?", (watchlist_id,)
    )
    row = conn.execute(
        "SELECT note FROM watchlist WHERE watchlist_id = ?", (watchlist_id,)
    ).fetchone()
    assert row["note"] == "更新済み"

    conn.execute("DELETE FROM watchlist WHERE watchlist_id = ?", (watchlist_id,))
    row = conn.execute(
        "SELECT * FROM watchlist WHERE watchlist_id = ?", (watchlist_id,)
    ).fetchone()
    assert row is None


def test_outcome_tracking_crud(empty_conn):
    conn = empty_conn
    score_id = _insert_score(conn)

    cur = conn.execute(
        """
        INSERT INTO outcome_tracking
            (score_id, ticker, next_day_open, next_day_high, next_day_low,
             next_day_close, prev_close, gap_up_pct, max_intraday_gain_pct,
             max_intraday_loss_pct, hit_plus5pct, hit_plus10pct,
             hit_upper_limit, recorded_at)
        VALUES (?, '1234', 105.0, 110.0, 104.0, 108.0, 103.0, 1.94, 6.80, 0.97,
                1, 0, 0, '2026-08-21T15:00:00+09:00')
        """,
        (score_id,),
    )
    outcome_id = cur.lastrowid

    row = conn.execute(
        "SELECT * FROM outcome_tracking WHERE outcome_id = ?", (outcome_id,)
    ).fetchone()
    assert row["hit_plus5pct"] == 1

    conn.execute(
        "UPDATE outcome_tracking SET hit_plus10pct = 1 WHERE outcome_id = ?", (outcome_id,)
    )
    row = conn.execute(
        "SELECT hit_plus10pct FROM outcome_tracking WHERE outcome_id = ?", (outcome_id,)
    ).fetchone()
    assert row["hit_plus10pct"] == 1

    conn.execute("DELETE FROM outcome_tracking WHERE outcome_id = ?", (outcome_id,))
    row = conn.execute(
        "SELECT * FROM outcome_tracking WHERE outcome_id = ?", (outcome_id,)
    ).fetchone()
    assert row is None


def test_backtest_runs_crud(empty_conn):
    conn = empty_conn
    weight_set_id = _insert_weight_set(conn)

    cur = conn.execute(
        """
        INSERT INTO backtest_runs
            (run_name, confidence_mode, weight_set_id, dataset_tag, started_at)
        VALUES ('run-1', 'HIGH_ONLY', ?, 'statistical', '2026-08-28T00:00:00+09:00')
        """,
        (weight_set_id,),
    )
    run_id = cur.lastrowid

    row = conn.execute("SELECT * FROM backtest_runs WHERE run_id = ?", (run_id,)).fetchone()
    assert row["confidence_mode"] == "HIGH_ONLY"

    conn.execute(
        "UPDATE backtest_runs SET finished_at = '2026-08-28T00:05:00+09:00' WHERE run_id = ?",
        (run_id,),
    )
    row = conn.execute(
        "SELECT finished_at FROM backtest_runs WHERE run_id = ?", (run_id,)
    ).fetchone()
    assert row["finished_at"] == "2026-08-28T00:05:00+09:00"

    conn.execute("DELETE FROM backtest_runs WHERE run_id = ?", (run_id,))
    row = conn.execute("SELECT * FROM backtest_runs WHERE run_id = ?", (run_id,)).fetchone()
    assert row is None
