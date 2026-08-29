"""Integration tests for the scoring orchestrator (spec §6.2, §8.2, §8.3)."""

from __future__ import annotations

import pytest

from stock_radar.scoring.repository import delete_scores_for_weight_set, save_score
from stock_radar.scoring.scorer import (
    DisclosureNotFoundError,
    WeightSetNotFoundError,
    score_disclosure,
)
from stock_radar.scoring.weight_sets import ensure_baseline_weight_set


def _insert_company(conn, ticker="4840", market_cap_yen=8_500_000_000):
    conn.execute(
        "INSERT INTO companies (ticker, company_name, market_cap_yen, listing_status, updated_at) "
        "VALUES (?, ?, ?, 'active', '2026-08-28T00:00:00+09:00')",
        (ticker, f"Company {ticker}", market_cap_yen),
    )


def _insert_disclosure(
    conn, ticker="4840", disclosed_at="2026-08-20T15:05:00+09:00",
    title="業績予想の上方修正に関するお知らせ",
    positive_raw=30, negative_raw=0, is_hard_block=0,
):
    cur = conn.execute(
        """
        INSERT INTO disclosures
            (ticker, title, raw_text, disclosed_at, market_available_at,
             system_available_at, fetched_at, positive_material_raw,
             negative_penalty_raw, is_hard_block)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (ticker, title, title, disclosed_at, disclosed_at, disclosed_at, disclosed_at,
         positive_raw, negative_raw, is_hard_block),
    )
    return cur.lastrowid


def _insert_price(conn, ticker, trade_date, volume, avg_volume_20d):
    conn.execute(
        """
        INSERT INTO price_data
            (ticker, trade_date, open, high, low, close, volume,
             avg_volume_20d, market_snapshot_at, session_type)
        VALUES (?, ?, 100, 105, 99, 103, ?, ?, ?, 'close')
        """,
        (ticker, trade_date, volume, avg_volume_20d, f"{trade_date}T15:00:00+09:00"),
    )


def test_score_disclosure_post_close_uses_same_day_price(empty_conn):
    conn = empty_conn
    _insert_company(conn)
    weight_set_id = ensure_baseline_weight_set(conn)
    _insert_price(conn, "4840", "2026-08-20", volume=1000, avg_volume_20d=100)
    disclosure_id = _insert_disclosure(conn, disclosed_at="2026-08-20T15:05:00+09:00")

    result = score_disclosure(conn, disclosure_id, weight_set_id)

    assert result.material_score == 30  # positive_raw=30, no negative, no hard block
    assert result.volume_ratio == pytest.approx(10.0)
    assert result.supply_demand_score > 0
    assert result.total_score == result.material_score + result.supply_demand_score + result.theme_score
    assert result.dataset_tag == "case_study"  # 4840 is a case-study ticker
    assert result.scoring_basis_time == "2026-08-20T15:05:00+09:00"


def test_score_disclosure_intraday_ignores_same_day_price(empty_conn):
    """spec §8.2: an intraday disclosure must not see that day's volume —
    the scorer should fall back to the prior confirmed day (or None)."""
    conn = empty_conn
    _insert_company(conn)
    weight_set_id = ensure_baseline_weight_set(conn)
    _insert_price(conn, "4840", "2026-08-19", volume=200, avg_volume_20d=100)
    _insert_price(conn, "4840", "2026-08-20", volume=9999, avg_volume_20d=100)  # must be invisible
    disclosure_id = _insert_disclosure(conn, disclosed_at="2026-08-20T10:00:00+09:00")

    result = score_disclosure(conn, disclosure_id, weight_set_id)

    assert result.volume_ratio == pytest.approx(2.0)  # from 2026-08-19 (200/100), not 2026-08-20


def test_score_disclosure_hard_block_zeroes_material_only(empty_conn):
    conn = empty_conn
    _insert_company(conn)
    weight_set_id = ensure_baseline_weight_set(conn)
    _insert_price(conn, "4840", "2026-08-20", volume=1000, avg_volume_20d=100)
    disclosure_id = _insert_disclosure(
        conn, disclosed_at="2026-08-20T15:05:00+09:00", positive_raw=0, negative_raw=-50, is_hard_block=1,
    )

    result = score_disclosure(conn, disclosure_id, weight_set_id)

    assert result.material_score == 0
    assert result.supply_demand_score > 0  # HARD_BLOCK must not suppress the other axes


def test_score_disclosure_no_price_data_has_no_volume_ratio(empty_conn):
    conn = empty_conn
    # market_cap_yen=None so supply_demand_score isolates the volume component
    _insert_company(conn, market_cap_yen=None)
    weight_set_id = ensure_baseline_weight_set(conn)
    disclosure_id = _insert_disclosure(conn)

    result = score_disclosure(conn, disclosure_id, weight_set_id)

    assert result.supply_demand_score == 0
    assert result.volume_ratio is None


def test_score_disclosure_missing_disclosure_raises(empty_conn):
    conn = empty_conn
    weight_set_id = ensure_baseline_weight_set(conn)
    with pytest.raises(DisclosureNotFoundError):
        score_disclosure(conn, disclosure_id=9999, weight_set_id=weight_set_id)


def test_score_disclosure_missing_weight_set_raises(empty_conn):
    conn = empty_conn
    _insert_company(conn)
    disclosure_id = _insert_disclosure(conn)
    with pytest.raises(WeightSetNotFoundError):
        score_disclosure(conn, disclosure_id, weight_set_id=9999)


def test_save_score_persists_result(empty_conn):
    conn = empty_conn
    _insert_company(conn)
    weight_set_id = ensure_baseline_weight_set(conn)
    _insert_price(conn, "4840", "2026-08-20", volume=1000, avg_volume_20d=100)
    disclosure_id = _insert_disclosure(conn)

    result = score_disclosure(conn, disclosure_id, weight_set_id)
    score_id = save_score(conn, result)

    row = conn.execute("SELECT * FROM scores WHERE score_id = ?", (score_id,)).fetchone()
    assert row["disclosure_id"] == disclosure_id
    assert row["total_score"] == result.total_score
    assert row["notification_rank"] == result.notification_rank


def test_delete_scores_for_weight_set_clears_prior_rows(empty_conn):
    conn = empty_conn
    _insert_company(conn)
    weight_set_id = ensure_baseline_weight_set(conn)
    disclosure_id = _insert_disclosure(conn)
    result = score_disclosure(conn, disclosure_id, weight_set_id)
    save_score(conn, result)
    save_score(conn, result)  # simulate a duplicate from a naive re-run
    assert conn.execute("SELECT COUNT(*) AS n FROM scores").fetchone()["n"] == 2

    delete_scores_for_weight_set(conn, weight_set_id)
    assert conn.execute("SELECT COUNT(*) AS n FROM scores").fetchone()["n"] == 0
