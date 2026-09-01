"""Phase 7 fix: delete_rescoreable_scores_for_weight_set() must never
delete a score that already has an outcome_tracking row (spec §10.2 — a
scored-and-observed record is closed; also a hard FK/UNIQUE requirement
from Phase 0). This lives in backtest.repository, not scoring.repository,
because the guard needs to know about outcome_tracking — which
scoring/ itself must never reference (enforced by
tests/test_backtest_separation.py)."""

from __future__ import annotations

from stock_radar.backtest.repository import delete_rescoreable_scores_for_weight_set
from stock_radar.scoring.repository import save_score
from stock_radar.scoring.scorer import score_disclosure
from stock_radar.scoring.weight_sets import ensure_baseline_weight_set


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
             system_available_at, fetched_at)
        VALUES (?, 'お知らせ', '本文', '2026-08-20T15:05:00+09:00',
                '2026-08-20T15:05:00+09:00', '2026-08-20T15:05:00+09:00',
                '2026-08-20T15:05:00+09:00')
        """,
        (ticker,),
    )
    return cur.lastrowid


def test_delete_skips_outcome_tracked_score(empty_conn):
    conn = empty_conn
    _insert_company(conn)
    weight_set_id = ensure_baseline_weight_set(conn)
    disclosure_id = _insert_disclosure(conn)
    result = score_disclosure(conn, disclosure_id, weight_set_id)
    score_id = save_score(conn, result)
    conn.execute(
        "INSERT INTO outcome_tracking (score_id, ticker, recorded_at) VALUES (?, '4840', '2026-08-21T15:00:00+09:00')",
        (score_id,),
    )

    delete_rescoreable_scores_for_weight_set(conn, weight_set_id)

    row = conn.execute("SELECT * FROM scores WHERE score_id = ?", (score_id,)).fetchone()
    assert row is not None


def test_delete_still_removes_scores_without_outcome(empty_conn):
    conn = empty_conn
    _insert_company(conn)
    weight_set_id = ensure_baseline_weight_set(conn)
    disclosure_id = _insert_disclosure(conn)
    result = score_disclosure(conn, disclosure_id, weight_set_id)
    score_id = save_score(conn, result)

    delete_rescoreable_scores_for_weight_set(conn, weight_set_id)

    row = conn.execute("SELECT * FROM scores WHERE score_id = ?", (score_id,)).fetchone()
    assert row is None


def test_delete_does_not_raise_integrity_error_with_mixed_scores(empty_conn):
    """Reproduces the real hazard: deleting a weight_set's scores when some
    are outcome-tracked and some aren't must not raise FOREIGN KEY errors."""
    conn = empty_conn
    _insert_company(conn, "4840")
    _insert_company(conn, "7743")
    weight_set_id = ensure_baseline_weight_set(conn)

    tracked_disclosure_id = _insert_disclosure(conn, "4840")
    tracked_score_id = save_score(conn, score_disclosure(conn, tracked_disclosure_id, weight_set_id))
    conn.execute(
        "INSERT INTO outcome_tracking (score_id, ticker, recorded_at) VALUES (?, '4840', '2026-08-21T15:00:00+09:00')",
        (tracked_score_id,),
    )

    untracked_disclosure_id = _insert_disclosure(conn, "7743")
    untracked_score_id = save_score(conn, score_disclosure(conn, untracked_disclosure_id, weight_set_id))

    delete_rescoreable_scores_for_weight_set(conn, weight_set_id)  # must not raise

    assert conn.execute("SELECT 1 FROM scores WHERE score_id = ?", (tracked_score_id,)).fetchone() is not None
    assert conn.execute("SELECT 1 FROM scores WHERE score_id = ?", (untracked_score_id,)).fetchone() is None
