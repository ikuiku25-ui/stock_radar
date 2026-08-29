"""Tests for collector persistence and the §8.2 look-ahead-bias read guard."""

from __future__ import annotations

from stock_radar.collectors.repository import (
    CASE_STUDY_TICKERS,
    dataset_tag_for_ticker,
    get_available_price_asof,
    is_intraday_disclosure,
    save_disclosure,
    save_price_bars,
)
from stock_radar.collectors.tdnet import RawDisclosure
from stock_radar.collectors.yfinance_client import PriceBar


def _insert_company(conn, ticker):
    conn.execute(
        "INSERT INTO companies (ticker, company_name, listing_status, updated_at) "
        "VALUES (?, ?, 'active', '2026-08-28T00:00:00+09:00')",
        (ticker, f"Company {ticker}"),
    )


def _sample_disclosure(ticker="4840"):
    return RawDisclosure(
        ticker=ticker,
        company_name="テスト株式会社",
        title="お知らせ",
        pdf_url="https://example.invalid/x.pdf",
        disclosed_at="2026-08-20T15:00:00+09:00",
        fetched_at="2026-08-20T15:00:30+09:00",
        system_available_at="2026-08-20T15:00:30+09:00",
        availability_confidence="HIGH",
    )


def test_dataset_tag_for_case_study_tickers():
    for ticker in CASE_STUDY_TICKERS:
        assert dataset_tag_for_ticker(ticker) == "case_study"


def test_dataset_tag_for_other_tickers():
    assert dataset_tag_for_ticker("9999") == "statistical"


def test_save_disclosure_persists_three_time_model_and_dataset_tag(empty_conn):
    conn = empty_conn
    _insert_company(conn, "4840")
    disclosure_id = save_disclosure(conn, _sample_disclosure("4840"))

    row = conn.execute(
        "SELECT * FROM disclosures WHERE disclosure_id = ?", (disclosure_id,)
    ).fetchone()
    assert row["disclosed_at"] == "2026-08-20T15:00:00+09:00"
    assert row["market_available_at"] == "2026-08-20T15:00:00+09:00"
    assert row["system_available_at"] == "2026-08-20T15:00:30+09:00"
    assert row["fetched_at"] == "2026-08-20T15:00:30+09:00"
    assert row["availability_confidence"] == "HIGH"
    assert row["dataset_tag"] == "case_study"
    assert row["raw_text"] == "お知らせ"  # placeholder until Phase 3 PDF extraction


def test_save_disclosure_tags_non_case_study_ticker_statistical(empty_conn):
    conn = empty_conn
    _insert_company(conn, "9999")
    disclosure_id = save_disclosure(conn, _sample_disclosure("9999"))
    row = conn.execute(
        "SELECT dataset_tag FROM disclosures WHERE disclosure_id = ?", (disclosure_id,)
    ).fetchone()
    assert row["dataset_tag"] == "statistical"


def _sample_bar(ticker, trade_date, volume=1000, avg_volume_20d=None):
    return PriceBar(
        ticker=ticker,
        trade_date=trade_date,
        open=100.0, high=105.0, low=99.0, close=103.0,
        volume=volume,
        avg_volume_20d=avg_volume_20d,
        market_snapshot_at=f"{trade_date}T15:00:00+09:00",
        session_type="close",
    )


def test_save_price_bars_persists_rows(empty_conn):
    conn = empty_conn
    _insert_company(conn, "4840")
    save_price_bars(conn, [_sample_bar("4840", "2026-08-20"), _sample_bar("4840", "2026-08-21")])
    rows = conn.execute("SELECT * FROM price_data WHERE ticker = '4840'").fetchall()
    assert len(rows) == 2


def test_save_price_bars_is_idempotent_upsert(empty_conn):
    conn = empty_conn
    _insert_company(conn, "4840")
    save_price_bars(conn, [_sample_bar("4840", "2026-08-20", volume=1000)])
    save_price_bars(conn, [_sample_bar("4840", "2026-08-20", volume=9999)])
    rows = conn.execute("SELECT * FROM price_data WHERE ticker = '4840'").fetchall()
    assert len(rows) == 1
    assert rows[0]["volume"] == 9999


def test_is_intraday_disclosure_before_1500():
    assert is_intraday_disclosure("2026-08-20T14:59:00+09:00") is True


def test_is_intraday_disclosure_at_or_after_1500():
    assert is_intraday_disclosure("2026-08-20T15:00:00+09:00") is False
    assert is_intraday_disclosure("2026-08-20T16:30:00+09:00") is False


def _seed_price_history(conn, ticker):
    _insert_company(conn, ticker)
    save_price_bars(
        conn,
        [
            _sample_bar(ticker, "2026-08-18", volume=100),
            _sample_bar(ticker, "2026-08-19", volume=200),
            _sample_bar(ticker, "2026-08-20", volume=300),
        ],
    )


def test_intraday_disclosure_cannot_see_same_day_price(empty_conn):
    """spec §8.2: a pre-15:00 disclosure on 2026-08-20 must not see that
    day's (unconfirmed) price_data — only 2026-08-19 or earlier."""
    conn = empty_conn
    _seed_price_history(conn, "4840")
    row = get_available_price_asof(conn, "4840", "2026-08-20T10:00:00+09:00")
    assert row["trade_date"] == "2026-08-19"


def test_post_close_disclosure_can_see_same_day_price(empty_conn):
    conn = empty_conn
    _seed_price_history(conn, "4840")
    row = get_available_price_asof(conn, "4840", "2026-08-20T15:30:00+09:00")
    assert row["trade_date"] == "2026-08-20"


def test_post_close_disclosure_falls_back_when_same_day_price_missing(empty_conn):
    conn = empty_conn
    _insert_company(conn, "4840")
    save_price_bars(conn, [_sample_bar("4840", "2026-08-18", volume=100)])
    row = get_available_price_asof(conn, "4840", "2026-08-20T16:00:00+09:00")
    assert row["trade_date"] == "2026-08-18"


def test_get_available_price_asof_never_returns_pts_reference_rows(empty_conn):
    conn = empty_conn
    _insert_company(conn, "4840")
    pts_bar = _sample_bar("4840", "2026-08-20")
    pts_bar.session_type = "pts_reference"
    save_price_bars(conn, [pts_bar])
    row = get_available_price_asof(conn, "4840", "2026-08-20T16:00:00+09:00")
    assert row is None
