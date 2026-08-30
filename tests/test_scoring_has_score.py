from __future__ import annotations

from stock_radar.scoring.repository import has_score_for_weight_set, save_score
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


def test_has_score_for_weight_set(empty_conn):
    conn = empty_conn
    _insert_company(conn)
    weight_set_id = ensure_baseline_weight_set(conn)
    disclosure_id = _insert_disclosure(conn)

    assert has_score_for_weight_set(conn, disclosure_id, weight_set_id) is False

    save_score(conn, score_disclosure(conn, disclosure_id, weight_set_id))

    assert has_score_for_weight_set(conn, disclosure_id, weight_set_id) is True
