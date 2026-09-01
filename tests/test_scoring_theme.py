"""Tests for theme scoring, including the look-ahead-bias guard on
theme_hot_status (mirrors get_available_price_asof's intraday rule)."""

from __future__ import annotations

from stock_radar.scoring.theme import compute_theme_score, is_theme_hot_asof, match_theme_ids


def _insert_theme(conn, name="生成AI", regex=r"生成AI|LLM"):
    cur = conn.execute(
        "INSERT INTO theme_keywords (theme_name, keyword_regex, is_active, created_at) "
        "VALUES (?, ?, 1, '2026-01-01T00:00:00+09:00')",
        (name, regex),
    )
    return cur.lastrowid


def _insert_hot_status(conn, theme_id, trade_date, hot_flag):
    conn.execute(
        "INSERT INTO theme_hot_status (trade_date, theme_id, theme_as_of_time, hot_flag) "
        "VALUES (?, ?, ?, ?)",
        (trade_date, theme_id, f"{trade_date}T15:00:00+09:00", hot_flag),
    )


def test_match_theme_ids_finds_active_theme(empty_conn):
    theme_id = _insert_theme(empty_conn)
    matched = match_theme_ids(empty_conn, "当社は生成AI事業に参入します")
    assert matched == [theme_id]


def test_match_theme_ids_ignores_inactive_theme(empty_conn):
    conn = empty_conn
    conn.execute(
        "INSERT INTO theme_keywords (theme_name, keyword_regex, is_active, created_at) "
        "VALUES ('半導体', '半導体', 0, '2026-01-01T00:00:00+09:00')"
    )
    matched = match_theme_ids(conn, "半導体事業の拡大について")
    assert matched == []


def test_match_theme_ids_no_match_returns_empty(empty_conn):
    _insert_theme(empty_conn)
    matched = match_theme_ids(empty_conn, "無関係なお知らせ")
    assert matched == []


def test_is_theme_hot_asof_post_close_uses_same_day(empty_conn):
    theme_id = _insert_theme(empty_conn)
    _insert_hot_status(empty_conn, theme_id, "2026-08-20", 1)
    assert is_theme_hot_asof(empty_conn, theme_id, "2026-08-20T15:30:00+09:00") is True


def test_is_theme_hot_asof_intraday_uses_prior_day(empty_conn):
    """Look-ahead-bias guard: a pre-15:00 disclosure on 2026-08-20 must not
    see that day's (not-yet-final) hot status, even if it's already set."""
    conn = empty_conn
    theme_id = _insert_theme(conn)
    _insert_hot_status(conn, theme_id, "2026-08-19", 0)
    _insert_hot_status(conn, theme_id, "2026-08-20", 1)  # same-day, must be invisible
    assert is_theme_hot_asof(conn, theme_id, "2026-08-20T10:00:00+09:00") is False


def test_is_theme_hot_asof_returns_false_when_no_row(empty_conn):
    theme_id = _insert_theme(empty_conn)
    assert is_theme_hot_asof(empty_conn, theme_id, "2026-08-20T15:30:00+09:00") is False


def test_compute_theme_score_zero_when_no_theme_matches(empty_conn):
    score = compute_theme_score(empty_conn, "無関係なお知らせ", "2026-08-20T15:30:00+09:00", weight_theme=20)
    assert score == 0


def test_compute_theme_score_full_credit_when_hot(empty_conn):
    conn = empty_conn
    theme_id = _insert_theme(conn)
    _insert_hot_status(conn, theme_id, "2026-08-20", 1)
    score = compute_theme_score(conn, "生成AI新製品のお知らせ", "2026-08-20T15:30:00+09:00", weight_theme=20)
    assert score == 20


def test_compute_theme_score_partial_credit_when_matched_not_hot(empty_conn):
    conn = empty_conn
    theme_id = _insert_theme(conn)
    _insert_hot_status(conn, theme_id, "2026-08-20", 0)
    score = compute_theme_score(conn, "生成AI新製品のお知らせ", "2026-08-20T15:30:00+09:00", weight_theme=20)
    assert score == 10
