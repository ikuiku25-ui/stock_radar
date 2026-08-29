"""Theme score (spec §6.2, §8.2): 0..weight_theme points.

Matches a disclosure's text against theme_keywords, then checks whether
any matched theme was "hot" (theme_hot_status.hot_flag) on the applicable
trading day — using the SAME intraday/post-close look-ahead-bias split as
collectors.repository.get_available_price_asof(), because "is theme X hot"
is itself derived from that day's close-based gainers ranking (spec's
theme_as_of_time) and isn't knowable before the close. A pre-15:00
disclosure must therefore see the PRIOR trading day's hot status, not the
same day's (which wouldn't exist yet in a real-time pipeline).

HYPOTHESIS NOTICE: the point split below (full credit for a hot theme,
partial credit for a matched-but-not-hot theme) is not specified in the
spec and should be revisited once backtest data exists (same status as
scoring/supply_demand.py's bands).

DATA GAP: theme_hot_status has no populating pipeline yet anywhere in this
project — nothing computes "today's biggest gainers by theme" (the spec
never designs a data source for that either). Until one exists, this will
return 0 for every real disclosure whenever no theme_hot_status rows exist
for the relevant date, which is the case for all real data collected so
far (only mock_data.py seeds any).
"""

from __future__ import annotations

import re
import sqlite3
import unicodedata

from stock_radar.collectors.repository import INTRADAY_CUTOFF, to_jst

FULL_CREDIT_FRACTION = 1.0
PARTIAL_CREDIT_FRACTION = 0.5  # matched a theme, but it wasn't hot that day


def match_theme_ids(conn: sqlite3.Connection, text: str) -> list[int]:
    """Return the theme_ids of all active theme_keywords whose regex
    matches the NFKC-normalized text (title, currently — see spec 補足 on
    raw_text being title-only)."""
    normalized = unicodedata.normalize("NFKC", text or "")
    rows = conn.execute(
        "SELECT theme_id, keyword_regex FROM theme_keywords WHERE is_active = 1"
    ).fetchall()
    return [row["theme_id"] for row in rows if re.search(row["keyword_regex"], normalized)]


def is_theme_hot_asof(conn: sqlite3.Connection, theme_id: int, disclosed_at_iso: str) -> bool:
    """Look up hot_flag for the applicable trading day, applying the same
    intraday-disclosure look-ahead-bias rule as get_available_price_asof().
    Returns False (not just "unknown") when no row exists — a plain
    absence-of-evidence default consistent with how the rest of the scoring
    pipeline treats missing data.
    """
    dt = to_jst(disclosed_at_iso)
    disclosure_date = dt.date().isoformat()

    if dt.time() < INTRADAY_CUTOFF:
        query = (
            "SELECT hot_flag FROM theme_hot_status WHERE theme_id = ? "
            "AND trade_date < ? ORDER BY trade_date DESC LIMIT 1"
        )
    else:
        query = (
            "SELECT hot_flag FROM theme_hot_status WHERE theme_id = ? "
            "AND trade_date <= ? ORDER BY trade_date DESC LIMIT 1"
        )
    row = conn.execute(query, (theme_id, disclosure_date)).fetchone()
    return bool(row["hot_flag"]) if row else False


def compute_theme_score(
    conn: sqlite3.Connection, text: str, disclosed_at_iso: str, weight_theme: int
) -> int:
    theme_ids = match_theme_ids(conn, text)
    if not theme_ids:
        return 0
    if any(is_theme_hot_asof(conn, theme_id, disclosed_at_iso) for theme_id in theme_ids):
        return round(weight_theme * FULL_CREDIT_FRACTION)
    return round(weight_theme * PARTIAL_CREDIT_FRACTION)
