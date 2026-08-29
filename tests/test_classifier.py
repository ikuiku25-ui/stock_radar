"""Tests for the Phase 3 material classifier (spec §7, §8.3).

This dictionary is a fresh design (see keywords.py's provenance notice) —
these tests lock in its intended behavior; spec §12 Phase 3's real
precision/recall check is a manual review against the 4 case-study
tickers' actual disclosures (scripts/review_classifications.py), not this
suite.
"""

from __future__ import annotations

from stock_radar.classification.classifier import classify_disclosure


def test_no_match_returns_empty_result():
    result = classify_disclosure("株主・投資家の皆様からのお問い合わせについてのご回答", "本文")
    assert result.category is None
    assert result.positive_material_raw == 0
    assert result.negative_penalty_raw == 0
    assert result.is_hard_block is False


def test_upward_revision_category_a():
    result = classify_disclosure("業績予想の上方修正に関するお知らせ", "通期業績予想を上方修正いたします。")
    assert result.category == "A"
    assert result.positive_material_raw == 30
    assert result.negative_penalty_raw == 0
    assert result.is_hard_block is False


def test_dividend_increase_category_b():
    result = classify_disclosure("配当予想の修正（増配）に関するお知らせ", "増配を実施いたします。")
    assert "B" in result.category.split(",")
    assert result.positive_material_raw >= 20


def test_share_buyback_category_c():
    result = classify_disclosure("自己株式取得に関するお知らせ", "自己株式の取得を決議しました。")
    assert result.category == "C"
    assert result.positive_material_raw == 15


def test_large_order_category_d():
    result = classify_disclosure("大型契約締結のお知らせ", "新規に大型受注を獲得しました。")
    assert "D" in result.category.split(",")


def test_ma_category_e():
    result = classify_disclosure("資本業務提携に関するお知らせ", "当社は子会社化を通じてM&Aを実施します。")
    assert "E" in result.category.split(",")


def test_new_product_category_f():
    result = classify_disclosure("新製品発表のお知らせ", "世界初の技術を用いた新製品の特許を取得しました。")
    assert "F" in result.category.split(",")


def test_stock_split_category_g():
    result = classify_disclosure("株式分割に関するお知らせ", "1株を2株に株式分割いたします。")
    assert result.category == "G"
    assert result.positive_material_raw == 10


def test_multiple_categories_combine_additively():
    result = classify_disclosure(
        "上方修正及び自己株式取得に関するお知らせ",
        "業績予想を上方修正するとともに、自己株式の取得を決議しました。",
    )
    assert set(result.category.split(",")) == {"A", "C"}
    assert result.positive_material_raw == 30 + 15


def test_hard_block_civil_rehabilitation():
    result = classify_disclosure("民事再生法の適用申請に関するお知らせ", "東京地方裁判所に民事再生法の適用を申請いたしました。")
    assert result.is_hard_block is True
    assert result.matched_hard_block_terms == ["民事再生"]


def test_hard_block_delisting():
    result = classify_disclosure("上場廃止に関するお知らせ", "本日、上場廃止となることが決定いたしました。")
    assert result.is_hard_block is True


def test_soft_negative_impairment():
    result = classify_disclosure("特別損失の計上に関するお知らせ", "一部資産について減損損失を計上いたします。")
    assert result.is_hard_block is False
    assert result.negative_penalty_raw < 0
    assert result.category is None


def test_soft_negative_coexists_with_positive_material():
    """This is the direct C3 fix: a compound disclosure (impairment +
    upward revision) must NOT be forced to zero — both signals coexist."""
    result = classify_disclosure(
        "特別損失の計上及び業績予想の上方修正に関するお知らせ",
        "一部資産について減損損失を計上する一方、通期業績予想を上方修正いたします。",
    )
    assert result.category == "A"
    assert result.positive_material_raw == 30
    assert result.negative_penalty_raw < 0
    assert result.is_hard_block is False


def test_hard_block_does_not_suppress_recorded_positive_raw():
    """spec §8.3: HARD_BLOCK zeroes material_score downstream, but the raw
    fields recorded on the disclosure itself are NOT zeroed/discarded here
    (matches the Phase 1 convention test in test_constraints.py)."""
    result = classify_disclosure(
        "民事再生法の適用申請及び新製品の特許取得に関するお知らせ",
        "民事再生法の適用を申請するとともに、新製品について世界初の特許を取得しました。",
    )
    assert result.is_hard_block is True
    assert result.category == "F"
    assert result.positive_material_raw == 15


def test_downward_revision_is_soft_negative_not_hard_block():
    result = classify_disclosure("業績予想の下方修正に関するお知らせ", "通期業績予想を下方修正いたします。")
    assert result.is_hard_block is False
    assert result.negative_penalty_raw < 0


def test_fullwidth_text_is_normalized_before_matching():
    """spec §5 pipeline requires NFKC normalization; a full-width 'Ｍ＆Ａ'
    must still match the half-width 'M&A' pattern. Deliberately avoids any
    other category-E keyword so this isolates the normalization behavior."""
    result = classify_disclosure("Ｍ＆Ａの実施に関するお知らせ", "本件はＭ＆Ａによるものです。")
    assert result.category == "E"


def test_matched_names_and_terms_are_populated_for_audit():
    result = classify_disclosure("上方修正のお知らせ", "業績予想を上方修正いたします。")
    assert result.matched_positive_names == ["業績予想の上方修正"]
    assert result.matched_hard_block_terms == []
    assert result.matched_soft_negative_terms == []
