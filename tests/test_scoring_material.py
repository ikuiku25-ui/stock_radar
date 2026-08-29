from __future__ import annotations

from stock_radar.scoring.material import compute_material_score


def test_hard_block_forces_zero_regardless_of_raw_values():
    assert compute_material_score(30, 0, True, weight_material=50) == 0
    assert compute_material_score(0, -50, True, weight_material=50) == 0


def test_positive_and_negative_combine():
    assert compute_material_score(30, -10, False, weight_material=50) == 20


def test_floor_at_zero():
    assert compute_material_score(15, -50, False, weight_material=50) == 0


def test_caps_at_weight_material():
    """A+E category match (30+25=55) must not exceed the weight_set's
    declared max."""
    assert compute_material_score(55, 0, False, weight_material=50) == 50


def test_no_match_scores_zero():
    assert compute_material_score(0, 0, False, weight_material=50) == 0


def test_respects_custom_weight_material():
    assert compute_material_score(60, 0, False, weight_material=40) == 40
