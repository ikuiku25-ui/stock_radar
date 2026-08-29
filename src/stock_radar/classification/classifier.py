"""Material classifier (spec §8.3, §12 Phase 3).

Populates disclosures.category / positive_material_raw / negative_penalty_raw
/ is_hard_block from a disclosure's title+text. Does NOT apply the
HARD_BLOCK zeroing itself — that's the scores.material_score formula
(spec §8.3, Phase 4's job), applied downstream from these raw fields.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from .keywords import HARD_BLOCK_PATTERNS, POSITIVE_CATEGORIES, SOFT_NEGATIVE_PATTERNS


@dataclass
class ClassificationResult:
    category: str | None  # comma-separated category codes, e.g. "A,G"; None if no positive match
    positive_material_raw: int
    negative_penalty_raw: int  # <= 0
    is_hard_block: bool
    matched_positive_names: list[str] = field(default_factory=list)
    matched_hard_block_terms: list[str] = field(default_factory=list)
    matched_soft_negative_terms: list[str] = field(default_factory=list)


def classify_disclosure(title: str, raw_text: str) -> ClassificationResult:
    """Classify one disclosure. Title and raw_text are concatenated and
    NFKC-normalized (spec §5 pipeline: "正規化（NFKC正規化...)") before
    matching, so full-width/half-width keyword variants (e.g. 'Ｍ＆Ａ' vs
    'M&A') are both caught by the same pattern.
    """
    text = _normalize(f"{title}\n{raw_text}")

    matched_codes: list[str] = []
    matched_names: list[str] = []
    positive_total = 0
    for category in POSITIVE_CATEGORIES:
        if any(re.search(pattern, text) for pattern in category.patterns):
            matched_codes.append(category.code)
            matched_names.append(category.name)
            positive_total += category.points

    matched_hard_block = [name for name, pattern in HARD_BLOCK_PATTERNS if re.search(pattern, text)]

    matched_soft_negative = []
    negative_total = 0
    for name, pattern, points in SOFT_NEGATIVE_PATTERNS:
        if re.search(pattern, text):
            matched_soft_negative.append(name)
            negative_total += points

    return ClassificationResult(
        category=",".join(matched_codes) if matched_codes else None,
        positive_material_raw=positive_total,
        negative_penalty_raw=negative_total,
        is_hard_block=bool(matched_hard_block),
        matched_positive_names=matched_names,
        matched_hard_block_terms=matched_hard_block,
        matched_soft_negative_terms=matched_soft_negative,
    )


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "")
