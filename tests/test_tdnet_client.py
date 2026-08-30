"""Offline tests for TDnetClient: HTTP is mocked (see spec 補足 — the real
unofficial API's reachability/schema was not verifiable in this sandbox and
must be checked live via scripts/tdnet_connectivity_probe.py)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
import requests

from stock_radar.collectors.tdnet import JST, TDnetClient, TDnetClientError

DISCLOSED_AT = datetime(2026, 8, 20, 15, 0, 0, tzinfo=JST)
DISCLOSED_AT_PUBDATE = "2026-08-20 15:00:00"  # real API format: 'YYYY-MM-DD HH:MM:SS', implicitly JST


class FakeResponse:
    def __init__(self, payload=None, raw_text=None, status_code=200, content_type="application/json", url=""):
        self._payload = payload
        self.text = raw_text if raw_text is not None else ""
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}
        self.url = url

    def raise_for_status(self):
        pass

    def json(self):
        if self._payload is None:
            raise ValueError("Expecting value: line 1 column 1 (char 0)")
        return self._payload


class FakeSession:
    def __init__(self, payload=None, response=None, raise_exc=None):
        self._payload = payload
        self._response = response
        self._raise_exc = raise_exc
        self.requested_urls: list[str] = []  # (url, params) tuples

    def get(self, url, params=None, timeout=None):
        self.requested_urls.append((url, params))
        if self._raise_exc:
            raise self._raise_exc
        return self._response or FakeResponse(self._payload, url=url)


class RaisingResponse(FakeResponse):
    def raise_for_status(self):
        raise requests.exceptions.HTTPError("500 Server Error")


def _make_client(payload, clock_dt, session=None, **kwargs):
    return TDnetClient(
        session=session or FakeSession(payload),
        sleep_fn=lambda seconds: None,
        clock=lambda: clock_dt,
        monotonic_fn=_counter(),
        **kwargs,
    )


def _counter():
    value = [0.0]

    def _next():
        value[0] += 1.0
        return value[0]

    return _next


def _sample_payload(company_code="72030", pubdate=DISCLOSED_AT_PUBDATE):
    return {
        "items": [
            {
                "Tdnet": {
                    "company_code": company_code,
                    "company_name": "テスト株式会社",
                    "title": "業績予想の上方修正に関するお知らせ",
                    "pubdate": pubdate,
                    "document_url": "https://example.invalid/disclosure.pdf",
                }
            }
        ]
    }


def test_parses_five_digit_company_code_to_four_digit_ticker():
    client = _make_client(_sample_payload(), DISCLOSED_AT + timedelta(seconds=5))
    disclosures = client.fetch_recent(limit=10)
    assert disclosures[0].ticker == "7203"


def test_fetch_by_ticker_builds_expected_url():
    session = FakeSession(_sample_payload())
    client = _make_client(_sample_payload(), DISCLOSED_AT, session=session)
    client.fetch_by_ticker("7203", limit=5)
    assert session.requested_urls == [
        ("https://webapi.yanoshin.jp/webapi/tdnet/list/7203.json", {"limit": 5})
    ]


def test_fetch_recent_builds_expected_url():
    session = FakeSession(_sample_payload())
    client = _make_client(_sample_payload(), DISCLOSED_AT, session=session)
    client.fetch_recent(limit=10)
    assert session.requested_urls == [
        ("https://webapi.yanoshin.jp/webapi/tdnet/list/recent.json", {"limit": 10})
    ]


def test_fetch_by_tickers_joins_with_hyphen():
    session = FakeSession(_sample_payload())
    client = _make_client(_sample_payload(), DISCLOSED_AT, session=session)
    client.fetch_by_tickers(["7203", "130A", "9984"], limit=20)
    assert session.requested_urls == [
        ("https://webapi.yanoshin.jp/webapi/tdnet/list/7203-130A-9984.json", {"limit": 20})
    ]


def test_confidence_is_high_for_small_lag():
    client = _make_client(_sample_payload(), DISCLOSED_AT + timedelta(seconds=10))
    disclosures = client.fetch_recent()
    assert disclosures[0].availability_confidence == "HIGH"


def test_confidence_is_medium_for_moderate_lag():
    client = _make_client(_sample_payload(), DISCLOSED_AT + timedelta(minutes=20))
    disclosures = client.fetch_recent()
    assert disclosures[0].availability_confidence == "MEDIUM"


def test_confidence_is_low_for_large_lag():
    client = _make_client(_sample_payload(), DISCLOSED_AT + timedelta(hours=5))
    disclosures = client.fetch_recent()
    assert disclosures[0].availability_confidence == "LOW"


def test_confidence_is_unknown_when_pubdate_unparseable():
    client = _make_client(_sample_payload(pubdate="not-a-date"), DISCLOSED_AT)
    disclosures = client.fetch_recent()
    assert disclosures[0].availability_confidence == "UNKNOWN"


def test_confidence_is_unknown_on_negative_lag_clock_skew():
    client = _make_client(_sample_payload(), DISCLOSED_AT - timedelta(minutes=5))
    disclosures = client.fetch_recent()
    assert disclosures[0].availability_confidence == "UNKNOWN"


def test_pdf_url_and_company_name_passthrough():
    client = _make_client(_sample_payload(), DISCLOSED_AT + timedelta(seconds=1))
    disclosures = client.fetch_recent()
    d = disclosures[0]
    assert d.pdf_url == "https://example.invalid/disclosure.pdf"
    assert d.company_name == "テスト株式会社"


def test_parses_real_world_sample_response():
    """Regression test pinned to an actual live response captured during
    Phase 2 development (ticker 7203, 2026-08-29) — guards against
    reverting to the earlier wrong pubdate format assumption."""
    payload = {
        "total_count": 1,
        "condition_desc": "7203の適時開示情報一覧",
        "items": [
            {
                "Tdnet": {
                    "id": "1272885",
                    "pubdate": "2026-08-07 15:30:00",
                    "company_code": "72030",
                    "company_name": "トヨタ自",
                    "title": "従業員に対する株式交付制度としての自己株式の処分の処分価額等の決定に関するお知らせ",
                    "document_url": "https://webapi.yanoshin.jp/rd.php?https://www.release.tdnet.info/inbs/140120260807514302.pdf",
                    "markets_string": "東名",
                }
            }
        ],
        "actions": ["7203"],
    }
    client = _make_client(payload, datetime(2026, 8, 7, 15, 30, 5, tzinfo=JST))
    disclosures = client.fetch_by_ticker("7203", limit=1)
    d = disclosures[0]
    assert d.ticker == "7203"
    assert d.company_name == "トヨタ自"
    assert d.disclosed_at == "2026-08-07T15:30:00+09:00"
    assert d.availability_confidence == "HIGH"


def test_fetch_raw_by_ticker_returns_unparsed_payload():
    payload = _sample_payload()
    client = _make_client(payload, DISCLOSED_AT)
    raw = client.fetch_raw_by_ticker("7203", limit=5)
    assert raw == payload


def test_unexpected_response_shape_raises():
    client = _make_client({"unexpected": True}, DISCLOSED_AT)
    with pytest.raises(TDnetClientError):
        client.fetch_recent()


def test_non_json_response_raises_with_diagnostic_detail():
    """Reproduces the real-world failure seen against the live unofficial
    API: an empty/non-JSON body must surface status code + body snippet,
    not a bare requests.JSONDecodeError, so it's actually debuggable."""
    session = FakeSession(response=FakeResponse(payload=None, raw_text="", status_code=404, content_type="text/html"))
    client = _make_client(None, DISCLOSED_AT, session=session)
    with pytest.raises(TDnetClientError) as exc_info:
        client.fetch_recent()
    message = str(exc_info.value)
    assert "404" in message
    assert "text/html" in message


def test_connection_error_is_wrapped_as_tdnet_client_error():
    """Reproduces a real crash seen in Phase 7: a network-level failure
    (proxy error, DNS failure, timeout, connection refused — anything
    under requests.exceptions.RequestException) must not propagate as a
    raw requests exception, since the daily pipeline only catches
    TDnetClientError-shaped failures for this stage."""
    session = FakeSession(raise_exc=requests.exceptions.ProxyError("Unable to connect to proxy"))
    client = _make_client(None, DISCLOSED_AT, session=session)
    with pytest.raises(TDnetClientError, match="Unable to connect to proxy"):
        client.fetch_recent()


def test_connection_timeout_is_wrapped_as_tdnet_client_error():
    session = FakeSession(raise_exc=requests.exceptions.Timeout("timed out"))
    client = _make_client(None, DISCLOSED_AT, session=session)
    with pytest.raises(TDnetClientError):
        client.fetch_recent()


def test_http_error_status_is_wrapped_as_tdnet_client_error():
    session = FakeSession(response=RaisingResponse())
    client = _make_client(None, DISCLOSED_AT, session=session)
    with pytest.raises(TDnetClientError, match="500 Server Error"):
        client.fetch_recent()


def test_throttle_sleeps_for_remaining_interval():
    sleep_calls = []
    monotonic_values = iter([0.0, 5.0])  # two calls, 5s apart
    client = TDnetClient(
        session=FakeSession(_sample_payload()),
        sleep_fn=lambda seconds: sleep_calls.append(seconds),
        clock=lambda: DISCLOSED_AT,
        monotonic_fn=lambda: next(monotonic_values),
        min_interval_seconds=30.0,
    )
    client.fetch_recent()
    client.fetch_recent()
    assert sleep_calls == [25.0]


def test_throttle_does_not_sleep_after_interval_elapsed():
    sleep_calls = []
    monotonic_values = iter([0.0, 40.0])
    client = TDnetClient(
        session=FakeSession(_sample_payload()),
        sleep_fn=lambda seconds: sleep_calls.append(seconds),
        clock=lambda: DISCLOSED_AT,
        monotonic_fn=lambda: next(monotonic_values),
        min_interval_seconds=30.0,
    )
    client.fetch_recent()
    client.fetch_recent()
    assert sleep_calls == []
