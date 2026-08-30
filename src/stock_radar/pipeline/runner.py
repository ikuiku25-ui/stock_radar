"""Daily pipeline orchestrator (spec §5, §12 Phase 7).

Meant to be invoked once per day by an OS-level scheduler (cron/launchd/
Task Scheduler — see README) shortly after market close, not run as a
long-lived process itself (spec's "ZERO cost, local" philosophy favors the
OS's own battle-tested scheduler over a custom daemon).

Each stage is isolated in its own try/except so one stage's failure (e.g.
TDnet unreachable) doesn't prevent the others from running against
whatever data already exists — this is the "エラー監視" spec §12 Phase 7
asks for: failures are recorded (returned to the caller for logging/
alerting) rather than silently causing partial, inconsistent state or an
unhandled crash.

Uses the same TDnet.fetch_recent() Phase 2 already had, across ALL
tickers rather than just the 4 case-study ones — this is what starts
accumulating dataset_tag='statistical' data (spec §10.3), which Phase 6
had none of yet.

Classification and scoring are INCREMENTAL here (only disclosures/scores
that don't exist yet), unlike scripts/classify_disclosures.py and
scripts/score_disclosures.py's full-refresh behavior meant for occasional
manual re-runs after a dictionary/logic change. Daily automation should
never silently rewrite already-scored history — especially once Phase 6
has recorded an outcome against it (spec §10.2).
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Callable, Optional

from stock_radar.backtest.recorder import record_outcome_for_score
from stock_radar.classification.classifier import classify_disclosure
from stock_radar.classification.repository import save_classification
from stock_radar.collectors.repository import disclosure_exists, save_disclosure, save_price_bars
from stock_radar.collectors.tdnet import TDnetClient
from stock_radar.collectors.yfinance_client import YFinanceClient
from stock_radar.notification.service import NotifierFn, notify_and_watchlist
from stock_radar.scoring.repository import has_score_for_weight_set, save_score
from stock_radar.scoring.scorer import score_disclosure
from stock_radar.scoring.weight_sets import ensure_baseline_weight_set

logger = logging.getLogger("stock_radar.pipeline")


@dataclass
class PipelineRunSummary:
    new_disclosures: int = 0
    tickers_priced: int = 0
    classified: int = 0
    scored: int = 0
    notifications_sent: int = 0
    outcomes_recorded: int = 0
    stage_errors: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.stage_errors


def run_daily_pipeline(
    conn: sqlite3.Connection,
    tdnet_client: Optional[TDnetClient] = None,
    yfinance_client: Optional[YFinanceClient] = None,
    notifiers: Optional[list[NotifierFn]] = None,
    tdnet_limit: int = 300,
    price_period: str = "3mo",
) -> PipelineRunSummary:
    summary = PipelineRunSummary()
    tdnet_client = tdnet_client or TDnetClient()
    yfinance_client = yfinance_client or YFinanceClient()
    notifiers = notifiers if notifiers is not None else []

    weight_set_id = ensure_baseline_weight_set(conn)
    conn.commit()

    new_tickers = _collect_disclosures(conn, tdnet_client, tdnet_limit, summary)
    _collect_prices(conn, yfinance_client, new_tickers, price_period, summary)
    _classify_new(conn, summary)
    _score_new(conn, weight_set_id, summary)
    _notify(conn, notifiers, summary)
    _record_outcomes(conn, summary)

    return summary


def _collect_disclosures(
    conn: sqlite3.Connection, tdnet_client: TDnetClient, limit: int, summary: PipelineRunSummary
) -> set[str]:
    new_tickers: set[str] = set()
    try:
        disclosures = tdnet_client.fetch_recent(limit=limit)
    except Exception as exc:  # noqa: BLE001 - TDnetClientError is expected, but nothing here may crash the run
        logger.exception("TDnet collection failed")
        summary.stage_errors["tdnet_collection"] = str(exc)
        return new_tickers

    for disclosure in disclosures:
        if disclosure_exists(conn, disclosure.ticker, disclosure.title, disclosure.disclosed_at):
            continue
        conn.execute(
            "INSERT OR IGNORE INTO companies (ticker, company_name, listing_status, updated_at) "
            "VALUES (?, ?, 'active', datetime('now'))",
            (disclosure.ticker, disclosure.company_name or disclosure.ticker),
        )
        save_disclosure(conn, disclosure)
        new_tickers.add(disclosure.ticker)
        summary.new_disclosures += 1
    conn.commit()
    return new_tickers


def _collect_prices(
    conn: sqlite3.Connection,
    yfinance_client: YFinanceClient,
    tickers: set[str],
    price_period: str,
    summary: PipelineRunSummary,
) -> None:
    for ticker in sorted(tickers):
        try:
            bars = yfinance_client.fetch_daily_bars(ticker, period=price_period)
            save_price_bars(conn, bars)
            summary.tickers_priced += 1
        except Exception as exc:  # noqa: BLE001 - one bad ticker must not stop the run
            logger.exception("yfinance collection failed for %s", ticker)
            summary.stage_errors[f"yfinance:{ticker}"] = str(exc)
    conn.commit()


def _classify_new(conn: sqlite3.Connection, summary: PipelineRunSummary) -> None:
    try:
        rows = conn.execute(
            "SELECT disclosure_id, title, raw_text FROM disclosures "
            "WHERE category IS NULL AND positive_material_raw = 0 "
            "AND negative_penalty_raw = 0 AND is_hard_block = 0"
        ).fetchall()
        for row in rows:
            result = classify_disclosure(row["title"], row["raw_text"])
            save_classification(conn, row["disclosure_id"], result)
            summary.classified += 1
        conn.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Classification stage failed")
        summary.stage_errors["classification"] = str(exc)


def _score_new(conn: sqlite3.Connection, weight_set_id: int, summary: PipelineRunSummary) -> None:
    try:
        disclosure_ids = [row["disclosure_id"] for row in conn.execute("SELECT disclosure_id FROM disclosures")]
        for disclosure_id in disclosure_ids:
            if has_score_for_weight_set(conn, disclosure_id, weight_set_id):
                continue
            result = score_disclosure(conn, disclosure_id, weight_set_id)
            save_score(conn, result)
            summary.scored += 1
        conn.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Scoring stage failed")
        summary.stage_errors["scoring"] = str(exc)


def _notify(conn: sqlite3.Connection, notifiers: list[NotifierFn], summary: PipelineRunSummary) -> None:
    try:
        outcomes = notify_and_watchlist(conn, notifiers)
        conn.commit()
        summary.notifications_sent = sum(1 for outcome in outcomes if outcome.sent)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Notification stage failed")
        summary.stage_errors["notification"] = str(exc)


def _record_outcomes(conn: sqlite3.Connection, summary: PipelineRunSummary) -> None:
    try:
        score_ids = [row["score_id"] for row in conn.execute("SELECT score_id FROM scores")]
        for score_id in score_ids:
            result = record_outcome_for_score(conn, score_id)
            if result.outcome_id is not None:
                summary.outcomes_recorded += 1
        conn.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Outcome recording stage failed")
        summary.stage_errors["outcome_recording"] = str(exc)
