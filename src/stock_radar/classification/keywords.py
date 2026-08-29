"""Material classification dictionary (spec §7, §8.3, §12 Phase 3).

PROVENANCE NOTICE: v1.3 does not carry over v1.2's actual category
dictionary (the spec document only narrates what v1.2 got wrong, not its
keyword lists) and the user confirmed they don't have it either. This
dictionary is a FRESH design, built from:
  - spec §7's category table (上方修正/増配/自社株買い/大型受注・契約/
    M&A・資本業務提携/新製品・特許・承認/株式分割)
  - spec §8.3's HARD_BLOCK/SOFT_NEGATIVE definitions
  - general Japanese IR disclosure terminology
It has NOT been tuned against a large disclosure corpus. Spec §12 Phase 3's
completion condition requires a manual precision/recall check against the
4 case-study tickers' real disclosures (scripts/review_classifications.py)
before this is trusted — expect to revise these patterns based on that
review, and re-run scripts/classify_disclosures.py afterward (it's a full
re-classify each time, not an incremental update).

Category letters intentionally run A-G (spec's DDL comment says "A〜F",
but 株式分割 doesn't fit cleanly as a same-weight 7th sibling of the other
six — see CategoryDef for G below). The `disclosures.category` column has
no CHECK constraint, so this doesn't require a schema change.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CategoryDef:
    code: str
    name: str
    patterns: tuple[str, ...]
    points: int  # positive_material_raw contribution when matched


# Positive material categories (spec §7). `points` are base scores for a
# bare classification match — §7's "本文の数値抽出"/"規模比較" refinements
# (修正率、契約金額÷売上高、等) are explicitly deferred to Phase 4+ per
# spec §7's own policy ("Phase 4以降で段階的に追加する拡張項目").
POSITIVE_CATEGORIES: tuple[CategoryDef, ...] = (
    CategoryDef(
        code="A",
        name="業績予想の上方修正",
        # '特別利益の発生' added after Phase 3 manual review (real ticker
        # 4840 disclosures): a one-time gain is the direct positive mirror
        # of SOFT_NEGATIVE's '特別損失' and was being missed entirely.
        patterns=("上方修正", "増額修正", "予想を上回る見通し", "上振れ", "特別利益"),
        points=30,
    ),
    CategoryDef(
        code="B",
        name="増配",
        patterns=("増配", r"配当予想.{0,10}増額", "記念配当", "特別配当"),
        points=20,
    ),
    CategoryDef(
        code="C",
        name="自己株式取得（自社株買い）",
        # '自己株式消却' (retirement, not acquisition) added after manual
        # review — a related but distinct shareholder-friendly action that
        # the original 'X株式.取得' pattern doesn't cover.
        patterns=(r"自己株式.{0,10}取得", "自社株買い", r"自己株式.{0,10}消却"),
        points=15,
    ),
    CategoryDef(
        code="D",
        name="大型受注・契約",
        # Plain '受注' false-positived on '受注損失引当金繰入額の計上'
        # (a LOSS provision on a contract, i.e. bad news) during manual
        # review of real ticker 3907 data — excluded via negative lookahead
        # rather than dropping '受注' entirely, since bare '受注...のお知らせ'
        # is the common positive case. '戦略的提携' added for the real
        # ticker 4840 case that used that wording instead of '業務提携'.
        patterns=(r"受注(?!損失)", "契約締結", r"業務提携.{0,10}契約", "大型契約", "戦略的提携"),
        points=20,
    ),
    CategoryDef(
        code="E",
        name="M&A・資本業務提携",
        # '株式公開買付' was too narrow to match the real wording used by an
        # actual TOB disclosure against ticker 7743 ('公開買付けの開始に
        # 関するお知らせ', no '株式' prefix) — missing this is a severe
        # recall failure since a TOB is one of the most material events a
        # stock can have. Broadened to bare '公開買付'. '株式取得'/
        # '事業譲受'/'会社分割' added for other real misses found in the
        # same review (4840, 3987, 7743).
        # '株式取得' excludes a '自己'/'自社' prefix so it doesn't collide
        # with category C's self-buyback disclosures (e.g. '自己株式取得
        # に関するお知らせ' contains '株式取得' as a bare substring).
        patterns=(
            "資本業務提携", "子会社化", "公開買付", "TOB", "M&A",
            r"(?<!自己)(?<!自社)株式取得", "事業譲受", "会社分割",
        ),
        points=25,
    ),
    CategoryDef(
        code="F",
        name="新製品・特許・承認",
        patterns=("新製品", r"特許.{0,10}取得", r"承認.{0,10}取得", "世界初", "業界初"),
        points=15,
    ),
    CategoryDef(
        code="G",
        name="株式分割",
        patterns=("株式分割",),
        points=10,
    ),
)

# HARD_BLOCK (spec §8.3): survival/trust-threatening only. Forces
# material_score=0 downstream (Phase 4) — is_hard_block is recorded here,
# but the zeroing itself is NOT applied at classification time (spec §8.3's
# formula operates on scores, not on the raw disclosure fields).
HARD_BLOCK_PATTERNS: tuple[tuple[str, str], ...] = (
    ("民事再生", "民事再生"),
    ("会社更生", "会社更生"),
    ("破産手続", "破産手続"),
    ("特別清算", "特別清算"),
    ("上場廃止", "上場廃止"),
    ("監理銘柄指定", "監理銘柄"),
    ("整理銘柄指定", "整理銘柄"),
    ("不適切な会計処理", "不適切な会計"),
    ("不正会計", "不正会計"),
    ("有価証券報告書の訂正", r"有価証券報告書.{0,10}訂正"),
    ("継続企業の前提に関する重要事象", "継続企業の前提"),
)

# SOFT_NEGATIVE (spec §8.3): penalizes but coexists with positive material
# (this is the direct fix for C3 — no more forced-zero on compound
# disclosures like "減損＋上方修正").
SOFT_NEGATIVE_PATTERNS: tuple[tuple[str, str, int], ...] = (
    ("業績予想の下方修正", "下方修正", -20),
    ("減額修正", "減額修正", -20),
    ("下振れ", r"予想を下回る見通し|下振れ", -20),
    ("減損損失", "減損損失", -15),
    ("特別損失", "特別損失", -15),
    ("受注損失引当金", "受注損失", -15),
    ("減配", r"配当予想.{0,10}減額|減配|無配", -15),
    ("訴訟提起", r"訴訟.{0,10}提起|損害賠償.{0,10}請求", -10),
    ("行政処分", r"行政処分|業務改善命令|課徴金", -15),
)
