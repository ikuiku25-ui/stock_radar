"""TSE daily price limit table (値幅制限), for stop-high detection
(outcome_tracking.hit_upper_limit, spec §10.1).

VERIFICATION NOTICE: this table is built from general/public knowledge of
TSE's price-limit band structure, NOT fetched or confirmed against an
official current source (this sandbox has no outbound access to verify
it, and TSE has revised these bands over time). Before trusting
hit_upper_limit for any real conclusion, cross-check a few known real
stop-high days against this table's output. If wrong, only this table
needs correcting — nothing else depends on its exact values.

Bands are (upper_bound_exclusive, limit_width): a previous close of
`prev_close` uses the first band whose upper_bound_exclusible is >
prev_close. The upper limit price is prev_close + limit_width.
"""

from __future__ import annotations

PRICE_LIMIT_BANDS: tuple[tuple[float, float], ...] = (
    (100, 30),
    (200, 50),
    (500, 80),
    (700, 100),
    (1_000, 150),
    (1_500, 300),
    (2_000, 400),
    (3_000, 500),
    (5_000, 700),
    (7_000, 1_000),
    (10_000, 1_500),
    (15_000, 3_000),
    (20_000, 4_000),
    (30_000, 5_000),
    (50_000, 7_000),
    (70_000, 10_000),
    (100_000, 15_000),
    (150_000, 30_000),
    (200_000, 40_000),
    (300_000, 50_000),
    (500_000, 70_000),
    (700_000, 100_000),
    (1_000_000, 150_000),
    (1_500_000, 300_000),
    (2_000_000, 400_000),
    (3_000_000, 500_000),
    (5_000_000, 700_000),
    (7_000_000, 1_000_000),
    (10_000_000, 1_500_000),
    (15_000_000, 3_000_000),
    (20_000_000, 4_000_000),
    (30_000_000, 5_000_000),
    (50_000_000, 7_000_000),
)
# Above the last band's upper bound.
_FALLBACK_WIDTH = 10_000_000


def limit_width(prev_close: float) -> float:
    for upper_bound, width in PRICE_LIMIT_BANDS:
        if prev_close < upper_bound:
            return width
    return _FALLBACK_WIDTH


def upper_limit_price(prev_close: float) -> float:
    return prev_close + limit_width(prev_close)
