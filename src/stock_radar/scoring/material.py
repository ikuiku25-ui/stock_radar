"""Material score (spec §6.2, §8.3): 0..weight_material points."""

from __future__ import annotations


def compute_material_score(
    positive_material_raw: int,
    negative_penalty_raw: int,
    is_hard_block: bool,
    weight_material: int,
) -> int:
    """material_score = 0 if HARD_BLOCK, else max(0, positive+negative)
    (spec §8.3's formula verbatim). The spec states material's range as
    "0〜50点" but its formula has no explicit upper bound — a disclosure
    matching multiple categories (e.g. A+E = 30+25 = 55) can exceed 50, so
    this additionally caps at weight_material (the applicable weight_set's
    declared max) to keep the score inside its documented range.
    """
    if is_hard_block:
        return 0
    return min(weight_material, max(0, positive_material_raw + negative_penalty_raw))
