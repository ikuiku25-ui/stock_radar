"""Tests for the S/A notify-and-watchlist orchestration (spec §5, §12 Phase 5)."""

from __future__ import annotations

from stock_radar.notification.service import find_unwatchlisted_s_a_scores, notify_and_watchlist


def _insert_company(conn, ticker="4840"):
    conn.execute(
        "INSERT INTO companies (ticker, company_name, listing_status, updated_at) "
        "VALUES (?, ?, 'active', '2026-08-28T00:00:00+09:00')",
        (ticker, f"Company {ticker}"),
    )


def _insert_disclosure(conn, ticker="4840"):
    cur = conn.execute(
        """
        INSERT INTO disclosures
            (ticker, title, raw_text, disclosed_at, market_available_at,
             system_available_at, fetched_at, category)
        VALUES (?, 'お知らせ', '本文', '2026-08-20T15:00:00+09:00',
                '2026-08-20T15:00:00+09:00', '2026-08-20T15:00:00+09:00',
                '2026-08-20T15:00:00+09:00', 'A')
        """,
        (ticker,),
    )
    return cur.lastrowid


def _insert_weight_set(conn):
    cur = conn.execute(
        "INSERT INTO weight_sets (weight_material, weight_supply_demand, weight_theme, created_at) "
        "VALUES (50, 30, 20, '2026-08-28T00:00:00+09:00')"
    )
    return cur.lastrowid


def _insert_score(conn, ticker, rank, disclosure_id=None, weight_set_id=None):
    disclosure_id = disclosure_id or _insert_disclosure(conn, ticker)
    weight_set_id = weight_set_id or _insert_weight_set(conn)
    cur = conn.execute(
        """
        INSERT INTO scores
            (disclosure_id, ticker, weight_set_id, material_score,
             supply_demand_score, theme_score, total_score,
             notification_rank, scored_at, scoring_basis_time)
        VALUES (?, ?, ?, 30, 20, 10, 60, ?, '2026-08-20T15:05:00+09:00', '2026-08-20T15:00:00+09:00')
        """,
        (disclosure_id, ticker, weight_set_id, rank),
    )
    return cur.lastrowid


def test_find_unwatchlisted_returns_only_s_and_a(empty_conn):
    conn = empty_conn
    _insert_company(conn, "4840")
    _insert_score(conn, "4840", "S")
    _insert_score(conn, "4840", "A")
    _insert_score(conn, "4840", "B")
    _insert_score(conn, "4840", "none")

    rows = find_unwatchlisted_s_a_scores(conn)
    ranks = {row["notification_rank"] for row in rows}
    assert ranks == {"S", "A"}
    assert len(rows) == 2


def test_find_unwatchlisted_excludes_already_watchlisted(empty_conn):
    conn = empty_conn
    _insert_company(conn, "4840")
    score_id = _insert_score(conn, "4840", "S")
    conn.execute(
        "INSERT INTO watchlist (ticker, score_id, added_at) VALUES ('4840', ?, '2026-08-20T15:10:00+09:00')",
        (score_id,),
    )
    rows = find_unwatchlisted_s_a_scores(conn)
    assert rows == []


def test_notify_and_watchlist_success_inserts_watchlist_row(empty_conn):
    conn = empty_conn
    _insert_company(conn, "4840")
    score_id = _insert_score(conn, "4840", "S")

    sent_messages = []
    outcomes = notify_and_watchlist(conn, [lambda subject, body: sent_messages.append((subject, body))])

    assert len(outcomes) == 1
    assert outcomes[0].sent is True
    assert outcomes[0].error is None
    assert len(sent_messages) == 1

    watchlist_row = conn.execute(
        "SELECT score_id FROM watchlist WHERE score_id = ?", (score_id,)
    ).fetchone()
    assert watchlist_row is not None


def test_notify_and_watchlist_all_notifiers_fail_does_not_watchlist(empty_conn):
    conn = empty_conn
    _insert_company(conn, "4840")
    score_id = _insert_score(conn, "4840", "S")

    def failing_notifier(subject, body):
        raise RuntimeError("smtp down")

    outcomes = notify_and_watchlist(conn, [failing_notifier])

    assert outcomes[0].sent is False
    assert "smtp down" in outcomes[0].error
    watchlist_row = conn.execute(
        "SELECT score_id FROM watchlist WHERE score_id = ?", (score_id,)
    ).fetchone()
    assert watchlist_row is None


def test_notify_and_watchlist_partial_failure_still_watchlists(empty_conn):
    conn = empty_conn
    _insert_company(conn, "4840")
    _insert_score(conn, "4840", "A")

    def failing_notifier(subject, body):
        raise RuntimeError("desktop unsupported")

    sent_messages = []
    outcomes = notify_and_watchlist(
        conn, [failing_notifier, lambda subject, body: sent_messages.append((subject, body))]
    )

    assert outcomes[0].sent is True
    assert "desktop unsupported" in outcomes[0].error
    assert len(sent_messages) == 1


def test_rerun_does_not_renotify_already_watchlisted(empty_conn):
    conn = empty_conn
    _insert_company(conn, "4840")
    _insert_score(conn, "4840", "S")

    sent_messages = []
    notify_and_watchlist(conn, [lambda subject, body: sent_messages.append((subject, body))])
    outcomes_second_run = notify_and_watchlist(
        conn, [lambda subject, body: sent_messages.append((subject, body))]
    )

    assert len(sent_messages) == 1  # not notified twice
    assert outcomes_second_run == []


def test_failed_notification_is_retried_on_next_run(empty_conn):
    """A score whose delivery failed entirely must NOT be watchlisted, so
    the next run retries it (e.g. after the user fixes SMTP credentials)."""
    conn = empty_conn
    _insert_company(conn, "4840")
    _insert_score(conn, "4840", "S")

    notify_and_watchlist(conn, [lambda subject, body: (_ for _ in ()).throw(RuntimeError("fail"))])
    sent_messages = []
    outcomes = notify_and_watchlist(conn, [lambda subject, body: sent_messages.append((subject, body))])

    assert len(outcomes) == 1
    assert outcomes[0].sent is True
    assert len(sent_messages) == 1
