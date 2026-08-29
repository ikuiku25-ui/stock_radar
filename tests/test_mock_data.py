"""Sanity checks for the Phase 1/2/3 mock dataset (4 case-study tickers)."""

from __future__ import annotations

from stock_radar.classification.classifier import classify_disclosure
from stock_radar.mock_data import CASE_STUDY_TICKERS
from stock_radar.scoring.material import compute_material_score
from stock_radar.scoring.rank import determine_rank


def test_all_case_study_tickers_present(seeded_conn):
    rows = seeded_conn.execute("SELECT ticker FROM companies ORDER BY ticker").fetchall()
    tickers = {row["ticker"] for row in rows}
    assert tickers == set(CASE_STUDY_TICKERS)


def test_disclosures_tagged_case_study_only(seeded_conn):
    rows = seeded_conn.execute("SELECT DISTINCT dataset_tag FROM disclosures").fetchall()
    assert [row["dataset_tag"] for row in rows] == ["case_study"]


def test_scores_tagged_case_study_only(seeded_conn):
    rows = seeded_conn.execute("SELECT DISTINCT dataset_tag FROM scores").fetchall()
    assert [row["dataset_tag"] for row in rows] == ["case_study"]


def test_hard_block_ticker_scored_zero_material(seeded_conn):
    row = seeded_conn.execute(
        """
        SELECT s.material_score, d.is_hard_block
        FROM scores s JOIN disclosures d ON d.disclosure_id = s.disclosure_id
        WHERE s.ticker = '3907'
        """
    ).fetchone()
    assert row["is_hard_block"] == 1
    assert row["material_score"] == 0


def test_pts_reference_rows_excluded_by_default_session_filter(seeded_conn):
    """Spec §8.2: PTS data must be physically separated from 'close' data and
    excluded from scoring queries by construction (filter on session_type)."""
    all_rows = seeded_conn.execute(
        "SELECT * FROM price_data WHERE ticker = '3907'"
    ).fetchall()
    close_only = seeded_conn.execute(
        "SELECT * FROM price_data WHERE ticker = '3907' AND session_type = 'close'"
    ).fetchall()
    assert len(all_rows) > len(close_only)
    assert all(row["session_type"] == "close" for row in close_only)


def test_watchlist_only_contains_s_and_a_ranks(seeded_conn):
    rows = seeded_conn.execute(
        """
        SELECT s.notification_rank
        FROM watchlist w JOIN scores s ON s.score_id = w.score_id
        """
    ).fetchall()
    ranks = {row["notification_rank"] for row in rows}
    assert ranks <= {"S", "A"}


def test_disclosure_classification_fields_match_live_classifier(seeded_conn):
    """Guards against the mock dataset silently drifting from the real
    Phase 3 classifier's behavior (they were hand-picked and out of sync
    before Phase 3 introduced classify_disclosure())."""
    rows = seeded_conn.execute(
        "SELECT title, raw_text, category, positive_material_raw, "
        "negative_penalty_raw, is_hard_block FROM disclosures"
    ).fetchall()
    assert len(rows) == 4
    for row in rows:
        expected = classify_disclosure(row["title"], row["raw_text"])
        assert row["category"] == expected.category
        assert row["positive_material_raw"] == expected.positive_material_raw
        assert row["negative_penalty_raw"] == expected.negative_penalty_raw
        assert bool(row["is_hard_block"]) == expected.is_hard_block


def test_score_fields_match_live_scoring_functions(seeded_conn):
    """Guards against the mock scores drifting from the real Phase 4
    material_score/rank logic the same way test_disclosure_classification_
    fields_match_live_classifier guards Phase 3."""
    rows = seeded_conn.execute(
        """
        SELECT s.material_score, s.total_score, s.notification_rank,
               d.positive_material_raw, d.negative_penalty_raw, d.is_hard_block
        FROM scores s JOIN disclosures d ON d.disclosure_id = s.disclosure_id
        """
    ).fetchall()
    assert len(rows) == 4
    for row in rows:
        expected_material = compute_material_score(
            row["positive_material_raw"], row["negative_penalty_raw"],
            bool(row["is_hard_block"]), weight_material=50,
        )
        assert row["material_score"] == expected_material
        assert row["notification_rank"] == determine_rank(row["total_score"])


def test_mock_scores_span_all_rank_tiers(seeded_conn):
    """The illustrative supply_demand/theme constants were chosen so the 4
    disclosures land on S/A/B/none respectively — demonstrating the full
    ranking spread end to end."""
    rows = seeded_conn.execute(
        "SELECT ticker, notification_rank FROM scores ORDER BY ticker"
    ).fetchall()
    ranks_by_ticker = {row["ticker"]: row["notification_rank"] for row in rows}
    assert ranks_by_ticker == {"3907": "none", "3987": "B", "4840": "S", "7743": "A"}


def test_outcome_tracking_covers_every_score(seeded_conn):
    scores_count = seeded_conn.execute("SELECT COUNT(*) AS n FROM scores").fetchone()["n"]
    outcomes_count = seeded_conn.execute(
        "SELECT COUNT(*) AS n FROM outcome_tracking"
    ).fetchone()["n"]
    assert scores_count == outcomes_count
