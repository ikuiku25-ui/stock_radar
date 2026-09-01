"""Supply-demand score (spec §6.2, §8.2): 0..weight_supply_demand points.

HYPOTHESIS NOTICE: the spec defines volume_ratio's DENOMINATOR precisely
(trailing 20 trading days, excluding the disclosure day — already enforced
by collectors/yfinance_client.py when avg_volume_20d is computed) but does
NOT specify the point bands below, nor the small-cap bonus's thresholds.
Spec §6.2 explicitly calls the small-cap bonus "a hypothesis... that should
be validated by backtesting" — the volume_ratio bands here carry the same
status. Treat every constant in this module as tunable once Phase 6
backtest data exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# volume_ratio -> points, checked from the top down (first match wins).
VOLUME_RATIO_BANDS: tuple[tuple[float, int], ...] = (
    (5.0, 20),
    (3.0, 15),
    (2.0, 10),
    (1.5, 5),
)

# market_cap_yen -> bonus points, checked from the top down. Values are
# round-number JPY thresholds (100億円 / 300億円), not derived from any
# cited source.
SMALL_CAP_BONUS_BANDS: tuple[tuple[int, int], ...] = (
    (10_000_000_000, 10),
    (30_000_000_000, 5),
)


@dataclass
class SupplyDemandScoreDetail:
    score: int
    volume_ratio: Optional[float]
    volume_points: int
    small_cap_bonus: int


def compute_supply_demand_score(
    volume: Optional[int],
    avg_volume_20d: Optional[float],
    market_cap_yen: Optional[int],
    weight_supply_demand: int,
) -> SupplyDemandScoreDetail:
    volume_ratio = None
    if volume is not None and avg_volume_20d and avg_volume_20d > 0:
        volume_ratio = volume / avg_volume_20d

    volume_points = 0
    if volume_ratio is not None:
        for threshold, points in VOLUME_RATIO_BANDS:
            if volume_ratio >= threshold:
                volume_points = points
                break

    small_cap_bonus = 0
    if market_cap_yen is not None:
        for threshold, bonus in SMALL_CAP_BONUS_BANDS:
            if market_cap_yen < threshold:
                small_cap_bonus = bonus
                break

    score = min(weight_supply_demand, volume_points + small_cap_bonus)
    return SupplyDemandScoreDetail(
        score=score,
        volume_ratio=volume_ratio,
        volume_points=volume_points,
        small_cap_bonus=small_cap_bonus,
    )
