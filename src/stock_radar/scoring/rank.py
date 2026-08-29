"""Notification rank (spec §5 pipeline, §9): S/A/B/none from total_score.

HYPOTHESIS NOTICE: spec §9 is explicit that the 100-point score is "a
ranking heuristic with no statistical meaning" and defers validating even
the 50/30/20 weight split to backtesting — it never states rank cutoffs
either. These thresholds (against a 0-100 scale, since weight_material +
weight_supply_demand + weight_theme = 100 for the baseline weight_set) are
this project's own placeholder and are exactly the kind of thing spec §9's
score-band query (SELECT ... GROUP BY score_band) is meant to validate in
Phase 6 — expect to move these once backtest data exists.

REAL-DATA FINDING (Phase 4 manual review, user decision: keep as-is): only
1/80 real disclosures reached rank B, none reached S/A. This is NOT a bug
— confirmed via --show-volume-ratio that a real TOB disclosure against
ticker 7743 (disclosed after close) correctly scored volume_ratio=0.73
(unremarkable), because a post-close disclosure's "same-day confirmed
volume" (spec §6.2) is necessarily volume from BEFORE the announcement,
not a reaction to it. Combined with theme_score being ~0 for all real data
(see scoring/theme.py's DATA GAP notice), the practical ceiling right now
sits well under 100. The user chose not to rescale these thresholds to
compensate, preferring to validate the real formula via Phase 6 backtest
data rather than curve-fit the thresholds to produce more S/A ranks today.
"""

from __future__ import annotations

RANK_THRESHOLDS: tuple[tuple[int, str], ...] = (
    (80, "S"),
    (60, "A"),
    (40, "B"),
)


def determine_rank(total_score: int) -> str:
    for threshold, rank in RANK_THRESHOLDS:
        if total_score >= threshold:
            return rank
    return "none"
