"""TDnet disclosure collector (spec §4, §8.1, §13 rule 5).

RISK / UNCERTAINTY NOTICE (do not remove — spec's 補足 flags this as
"要確認... 実装着手時に再確認必須"):
  This client talks to an UNOFFICIAL, personally-run JSON API that mirrors
  TDnet (the class of service the spec calls "個人運営の非公式TDnet API",
  e.g. the やのしん氏-style API at webapi.yanoshin.jp). It is NOT the
  official JPX/TDnet service. Before relying on this in a real run:
    1. Verify the service is still online and its terms still allow this
       use (personal, non-commercial, considerate request volume).
    2. Verify the response JSON shape against a live call — the parsing
       below (_parse_record) is written against the publicly documented
       shape as of spec authoring time and has NOT been verified live in
       this sandbox (outbound network access to this host is blocked
       here; see scripts/tdnet_connectivity_probe.py to check it from a
       machine with real internet access).
    3. This is a single point of failure: the service can disappear
       without notice (spec §4.1). Do not assume availability.

  A minimum polling interval is enforced (see min_interval_seconds) per
  spec §13 rule 5 ("Interval設定を必ず組み込むこと") to avoid hammering a
  free, personally-run service.
"""

from __future__ import annotations

import email.utils
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

import requests

JST = timezone(timedelta(hours=9))

DEFAULT_BASE_URL = "https://webapi.yanoshin.jp/webapi/tdnet/list"
# Conservative default: real-time detection only needs to beat "next
# business day", not sub-minute latency, so err toward less server load.
DEFAULT_MIN_INTERVAL_SECONDS = 30.0
DEFAULT_TIMEOUT_SECONDS = 15.0


@dataclass
class RawDisclosure:
    """One disclosure as collected, before material classification (Phase 3)."""

    ticker: str
    company_name: str
    title: str
    pdf_url: Optional[str]
    disclosed_at: str  # ISO8601, JST — from the API's pubdate field
    fetched_at: str  # ISO8601, JST — when this HTTP request was made
    system_available_at: str  # ISO8601, JST — when our poller observed it (== fetched_at here)
    availability_confidence: str  # HIGH/MEDIUM/LOW/UNKNOWN


class TDnetClientError(RuntimeError):
    """Raised when the unofficial API returns an unexpected shape."""


class TDnetClient:
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        min_interval_seconds: float = DEFAULT_MIN_INTERVAL_SECONDS,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        session: Optional[requests.Session] = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        clock: Callable[[], datetime] = lambda: datetime.now(JST),
        monotonic_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._min_interval_seconds = min_interval_seconds
        self._timeout_seconds = timeout_seconds
        self._session = session or requests.Session()
        self._sleep_fn = sleep_fn
        self._clock = clock
        self._monotonic_fn = monotonic_fn
        self._last_request_at: Optional[float] = None

    def fetch_recent(self, limit: int = 100) -> list[RawDisclosure]:
        """Fetch the most recent disclosures across all tickers."""
        return self._fetch(f"{self._base_url}/recent/{limit}.json")

    def fetch_by_ticker(self, ticker: str, limit: int = 100) -> list[RawDisclosure]:
        """Fetch recent disclosures for a single 4-digit ticker."""
        return self._fetch(f"{self._base_url}/{ticker}/{limit}.json")

    def _fetch(self, url: str) -> list[RawDisclosure]:
        self._throttle()
        fetched_at_dt = self._clock()
        response = self._session.get(url, timeout=self._timeout_seconds)
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError as exc:
            # requests.exceptions.JSONDecodeError subclasses ValueError;
            # catching the parent keeps this independent of the JSON
            # backend requests uses under the hood.
            snippet = response.text[:500]
            raise TDnetClientError(
                f"Non-JSON response from {url} "
                f"(HTTP {response.status_code}, content-type "
                f"{response.headers.get('Content-Type')!r}): {snippet!r}"
            ) from exc
        return self._parse_items(payload, fetched_at_dt)

    def _throttle(self) -> None:
        """Enforce min_interval_seconds between successive HTTP requests."""
        now = self._monotonic_fn()
        if self._last_request_at is not None:
            elapsed = now - self._last_request_at
            remaining = self._min_interval_seconds - elapsed
            if remaining > 0:
                self._sleep_fn(remaining)
        self._last_request_at = now

    def _parse_items(self, payload, fetched_at_dt: datetime) -> list[RawDisclosure]:
        items = payload.get("items") if isinstance(payload, dict) else None
        if items is None:
            shape = list(payload.keys()) if isinstance(payload, dict) else type(payload).__name__
            raise TDnetClientError(f"Unexpected TDnet API response shape: {shape}")

        fetched_at_iso = fetched_at_dt.isoformat()
        disclosures = []
        for entry in items:
            record = entry.get("Tdnet") if isinstance(entry, dict) else None
            if record is None:
                continue
            disclosures.append(self._parse_record(record, fetched_at_dt, fetched_at_iso))
        return disclosures

    def _parse_record(self, record: dict, fetched_at_dt: datetime, fetched_at_iso: str) -> RawDisclosure:
        ticker = _normalize_ticker(record.get("company_code", ""))
        disclosed_at_dt = _parse_pubdate(record.get("pubdate"))
        disclosed_at_iso = disclosed_at_dt.isoformat() if disclosed_at_dt else fetched_at_iso
        confidence = _estimate_confidence(disclosed_at_dt, fetched_at_dt, self._min_interval_seconds)
        return RawDisclosure(
            ticker=ticker,
            company_name=record.get("company_name", ""),
            title=record.get("title", ""),
            pdf_url=record.get("document_url") or None,
            disclosed_at=disclosed_at_iso,
            fetched_at=fetched_at_iso,
            system_available_at=fetched_at_iso,
            availability_confidence=confidence,
        )


def _normalize_ticker(company_code: str) -> str:
    """The unofficial API is documented as reporting a 5-digit code (4-digit
    ticker + check digit, e.g. '72030' for ticker '7203'). Falls back to the
    raw value if it doesn't match that shape — MUST be re-verified against a
    live response (see module docstring) before trusting this in production.
    """
    code = (company_code or "").strip()
    if len(code) == 5 and code.isdigit():
        return code[:4]
    return code


def _parse_pubdate(pubdate: Optional[str]) -> Optional[datetime]:
    if not pubdate:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(pubdate)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=JST)
    return parsed.astimezone(JST)


def _estimate_confidence(
    disclosed_at_dt: Optional[datetime], fetched_at_dt: datetime, min_interval_seconds: float
) -> str:
    """Heuristic for availability_confidence (spec §3.1/§8.1 define the enum
    but not how to derive it — this is a Phase 2 design decision): confidence
    that system_available_at faithfully reflects "when this became knowable"
    degrades as the observed poll lag (fetch time minus disclosed time)
    grows. A negative lag (fetched "before" the reported disclosure time)
    signals clock skew or a stale cache and is treated as UNKNOWN rather
    than trusted.
    """
    if disclosed_at_dt is None:
        return "UNKNOWN"
    lag_seconds = (fetched_at_dt - disclosed_at_dt).total_seconds()
    if lag_seconds < 0:
        return "UNKNOWN"
    if lag_seconds <= max(min_interval_seconds * 3, 60):
        return "HIGH"
    if lag_seconds <= 3600:
        return "MEDIUM"
    return "LOW"
