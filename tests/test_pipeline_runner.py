"""Integration tests for the Phase 7 daily pipeline orchestrator."""

from __future__ import annotations

from stock_radar.collectors.tdnet import RawDisclosure, TDnetClientError
from stock_radar.collectors.yfinance_client import PriceBar
from stock_radar.pipeline.runner import run_daily_pipeline


class FakeTDnetClient:
    def __init__(self, disclosures=None, error=None):
        self._disclosures = disclosures or []
        self._error = error
        self.fetch_recent_calls = 0

    def fetch_recent(self, limit=300):
        self.fetch_recent_calls += 1
        if self._error:
            raise self._error
        return self._disclosures


class FakeYFinanceClient:
    def __init__(self, bars_by_ticker=None, error_tickers=None):
        self._bars_by_ticker = bars_by_ticker or {}
        self._error_tickers = error_tickers or set()

    def fetch_daily_bars(self, ticker, period="3mo"):
        if ticker in self._error_tickers:
            raise RuntimeError(f"yfinance down for {ticker}")
        return self._bars_by_ticker.get(ticker, [_default_bar(ticker)])


def _default_bar(ticker, trade_date="2026-08-20"):
    return PriceBar(
        ticker=ticker, trade_date=trade_date, open=100.0, high=105.0, low=99.0,
        close=103.0, volume=1000, avg_volume_20d=500.0,
        market_snapshot_at=f"{trade_date}T15:00:00+09:00", session_type="close",
    )


def _sample_disclosure(ticker="9001", title="業績予想の上方修正に関するお知らせ", disclosed_at="2026-08-20T15:05:00+09:00"):
    return RawDisclosure(
        ticker=ticker, company_name=f"会社{ticker}", title=title, pdf_url=None,
        disclosed_at=disclosed_at, fetched_at=disclosed_at, system_available_at=disclosed_at,
        availability_confidence="HIGH",
    )


def test_full_run_collects_classifies_scores_and_notifies(empty_conn):
    conn = empty_conn
    disclosure = _sample_disclosure()
    tdnet = FakeTDnetClient(disclosures=[disclosure])
    yfinance = FakeYFinanceClient()
    sent = []

    summary = run_daily_pipeline(
        conn, tdnet_client=tdnet, yfinance_client=yfinance,
        notifiers=[lambda subject, body: sent.append((subject, body))],
    )

    assert summary.ok
    assert summary.new_disclosures == 1
    assert summary.tickers_priced == 1
    assert summary.classified == 1
    assert summary.scored == 1

    company = conn.execute("SELECT * FROM companies WHERE ticker = '9001'").fetchone()
    assert company is not None
    disclosure_row = conn.execute("SELECT category FROM disclosures WHERE ticker = '9001'").fetchone()
    assert disclosure_row["category"] == "A"


def test_rerun_does_not_duplicate_disclosures(empty_conn):
    conn = empty_conn
    disclosure = _sample_disclosure()
    tdnet = FakeTDnetClient(disclosures=[disclosure])
    yfinance = FakeYFinanceClient()

    run_daily_pipeline(conn, tdnet_client=tdnet, yfinance_client=yfinance)
    run_daily_pipeline(conn, tdnet_client=tdnet, yfinance_client=yfinance)

    count = conn.execute("SELECT COUNT(*) AS n FROM disclosures").fetchone()["n"]
    assert count == 1


def test_rerun_does_not_duplicate_or_overwrite_scores(empty_conn):
    conn = empty_conn
    disclosure = _sample_disclosure()
    tdnet = FakeTDnetClient(disclosures=[disclosure])
    yfinance = FakeYFinanceClient()

    run_daily_pipeline(conn, tdnet_client=tdnet, yfinance_client=yfinance)
    run_daily_pipeline(conn, tdnet_client=tdnet, yfinance_client=yfinance)

    count = conn.execute("SELECT COUNT(*) AS n FROM scores").fetchone()["n"]
    assert count == 1


def test_tdnet_failure_does_not_crash_the_run(empty_conn):
    conn = empty_conn
    tdnet = FakeTDnetClient(error=TDnetClientError("service down"))
    yfinance = FakeYFinanceClient()

    summary = run_daily_pipeline(conn, tdnet_client=tdnet, yfinance_client=yfinance)

    assert not summary.ok
    assert "tdnet_collection" in summary.stage_errors
    assert summary.new_disclosures == 0


def test_unexpected_tdnet_exception_type_also_does_not_crash_the_run(empty_conn):
    """Regression: a raw network-level exception (e.g. requests.exceptions.
    ProxyError, before tdnet.py started wrapping those) must not propagate
    past this stage either — only TDnetClientError was ever special-cased
    here, so this guards against that narrowing coming back."""
    conn = empty_conn
    tdnet = FakeTDnetClient(error=RuntimeError("unexpected failure shape"))
    yfinance = FakeYFinanceClient()

    summary = run_daily_pipeline(conn, tdnet_client=tdnet, yfinance_client=yfinance)

    assert not summary.ok
    assert "tdnet_collection" in summary.stage_errors


def test_yfinance_failure_for_one_ticker_does_not_stop_others(empty_conn):
    conn = empty_conn
    disclosures = [_sample_disclosure(ticker="9001"), _sample_disclosure(ticker="9002", disclosed_at="2026-08-20T15:06:00+09:00")]
    tdnet = FakeTDnetClient(disclosures=disclosures)
    yfinance = FakeYFinanceClient(error_tickers={"9001"})

    summary = run_daily_pipeline(conn, tdnet_client=tdnet, yfinance_client=yfinance)

    assert "yfinance:9001" in summary.stage_errors
    assert summary.tickers_priced == 1  # 9002 still succeeded
    # classification/scoring still proceed for both disclosures regardless of price data
    assert summary.classified == 2
    assert summary.scored == 2


def test_notify_only_fires_for_s_and_a_ranks(empty_conn):
    """A weak disclosure (no material match) should not generate a
    notification even though it goes through the full pipeline."""
    conn = empty_conn
    disclosure = _sample_disclosure(title="株主優待制度の変更に関するお知らせ")
    tdnet = FakeTDnetClient(disclosures=[disclosure])
    yfinance = FakeYFinanceClient()
    sent = []

    summary = run_daily_pipeline(
        conn, tdnet_client=tdnet, yfinance_client=yfinance,
        notifiers=[lambda subject, body: sent.append((subject, body))],
    )

    assert summary.notifications_sent == 0
    assert sent == []


def test_outcomes_recorded_once_next_day_price_exists(empty_conn):
    conn = empty_conn
    disclosure = _sample_disclosure(disclosed_at="2026-08-20T15:05:00+09:00")
    tdnet = FakeTDnetClient(disclosures=[disclosure])
    yfinance = FakeYFinanceClient(bars_by_ticker={"9001": [_default_bar("9001", "2026-08-20")]})

    run_daily_pipeline(conn, tdnet_client=tdnet, yfinance_client=yfinance)

    # Simulate the next trading day's price arriving on a later run.
    conn.execute(
        """
        INSERT INTO price_data
            (ticker, trade_date, open, high, low, close, volume,
             avg_volume_20d, market_snapshot_at, session_type)
        VALUES ('9001', '2026-08-21', 104, 110, 103, 108, 1200, 500, '2026-08-21T15:00:00+09:00', 'close')
        """
    )
    conn.commit()

    tdnet_no_new = FakeTDnetClient(disclosures=[])
    summary = run_daily_pipeline(conn, tdnet_client=tdnet_no_new, yfinance_client=yfinance)

    assert summary.outcomes_recorded == 1
