from __future__ import annotations

import pytest

from stock_radar.scoring.supply_demand import compute_supply_demand_score


def test_no_volume_data_scores_zero():
    detail = compute_supply_demand_score(None, None, None, weight_supply_demand=30)
    assert detail.score == 0
    assert detail.volume_ratio is None


def test_zero_avg_volume_avoids_division_by_zero():
    detail = compute_supply_demand_score(1000, 0, None, weight_supply_demand=30)
    assert detail.volume_ratio is None
    assert detail.score == 0


@pytest.mark.parametrize(
    "volume,avg,expected_points",
    [
        (600, 100, 20),   # ratio 6.0 -> >=5.0
        (400, 100, 15),   # ratio 4.0 -> >=3.0
        (250, 100, 10),   # ratio 2.5 -> >=2.0
        (160, 100, 5),    # ratio 1.6 -> >=1.5
        (110, 100, 0),    # ratio 1.1 -> below all bands
    ],
)
def test_volume_ratio_bands(volume, avg, expected_points):
    detail = compute_supply_demand_score(volume, avg, None, weight_supply_demand=30)
    assert detail.volume_points == expected_points


def test_small_cap_bonus_under_100_oku():
    detail = compute_supply_demand_score(None, None, 9_000_000_000, weight_supply_demand=30)
    assert detail.small_cap_bonus == 10


def test_small_cap_bonus_under_300_oku():
    detail = compute_supply_demand_score(None, None, 25_000_000_000, weight_supply_demand=30)
    assert detail.small_cap_bonus == 5


def test_no_bonus_for_large_cap():
    detail = compute_supply_demand_score(None, None, 500_000_000_000, weight_supply_demand=30)
    assert detail.small_cap_bonus == 0


def test_score_caps_at_weight_supply_demand():
    detail = compute_supply_demand_score(1000, 100, 5_000_000_000, weight_supply_demand=25)
    # volume_points=20 + small_cap_bonus=10 = 30, but weight caps at 25
    assert detail.score == 25


def test_score_sums_volume_and_small_cap_within_cap():
    detail = compute_supply_demand_score(300, 100, 5_000_000_000, weight_supply_demand=30)
    assert detail.volume_points == 15  # ratio 3.0
    assert detail.small_cap_bonus == 10
    assert detail.score == 25
