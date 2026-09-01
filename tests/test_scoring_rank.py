from __future__ import annotations

import pytest

from stock_radar.scoring.rank import determine_rank


@pytest.mark.parametrize(
    "total_score,expected_rank",
    [
        (100, "S"),
        (80, "S"),
        (79, "A"),
        (60, "A"),
        (59, "B"),
        (40, "B"),
        (39, "none"),
        (0, "none"),
    ],
)
def test_determine_rank_boundaries(total_score, expected_rank):
    assert determine_rank(total_score) == expected_rank
