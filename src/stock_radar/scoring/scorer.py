"""Scoring orchestrator (spec §6.2, §8.2, §8.3): ties together material,
supply-demand, and theme scores for one disclosure under one weight_set.

Reads price data ONLY through get_available_price_asof() — never queries
price_data directly — so the §8.2 look-ahead-bias guard built in Phase 2
can't be silently bypassed here.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from stock_radar.collectors.repository import dataset_tag_for_ticker, get_available_price_asof

from .material import compute_material_score
from .rank import determine_rank
from .supply_demand import compute_supply_demand_score
from .theme import compute_theme_score


class DisclosureNotFoundError(RuntimeError):
    pass


class WeightSetNotFoundError(RuntimeError):
    pass


@dataclass
class ScoreResult:
    disclosure_id: int
    ticker: str
    weight_set_id: int
    material_score: int
    supply_demand_score: int
    theme_score: int
    total_score: int
    notification_rank: str
    scored_at: str
    scoring_basis_time: str
    dataset_tag: str
    volume_ratio: Optional[float]  # audit detail, not persisted as its own column


def score_disclosure(conn: sqlite3.Connection, disclosure_id: int, weight_set_id: int) -> ScoreResult:
    disclosure = conn.execute(
        "SELECT ticker, title, raw_text, disclosed_at, system_available_at, "
        "positive_material_raw, negative_penalty_raw, is_hard_block "
        "FROM disclosures WHERE disclosure_id = ?",
        (disclosure_id,),
    ).fetchone()
    if disclosure is None:
        raise DisclosureNotFoundError(f"disclosure_id={disclosure_id} not found")

    weight_set = conn.execute(
        "SELECT weight_material, weight_supply_demand, weight_theme "
        "FROM weight_sets WHERE weight_set_id = ?",
        (weight_set_id,),
    ).fetchone()
    if weight_set is None:
        raise WeightSetNotFoundError(f"weight_set_id={weight_set_id} not found")

    company = conn.execute(
        "SELECT market_cap_yen FROM companies WHERE ticker = ?", (disclosure["ticker"],)
    ).fetchone()
    market_cap_yen = company["market_cap_yen"] if company else None

    price_row = get_available_price_asof(conn, disclosure["ticker"], disclosure["disclosed_at"])
    volume = price_row["volume"] if price_row else None
    avg_volume_20d = price_row["avg_volume_20d"] if price_row else None

    material_score = compute_material_score(
        disclosure["positive_material_raw"],
        disclosure["negative_penalty_raw"],
        bool(disclosure["is_hard_block"]),
        weight_set["weight_material"],
    )
    supply_demand_detail = compute_supply_demand_score(
        volume, avg_volume_20d, market_cap_yen, weight_set["weight_supply_demand"]
    )
    text = f"{disclosure['title']}\n{disclosure['raw_text']}"
    theme_score = compute_theme_score(conn, text, disclosure["disclosed_at"], weight_set["weight_theme"])

    total_score = material_score + supply_demand_detail.score + theme_score

    return ScoreResult(
        disclosure_id=disclosure_id,
        ticker=disclosure["ticker"],
        weight_set_id=weight_set_id,
        material_score=material_score,
        supply_demand_score=supply_demand_detail.score,
        theme_score=theme_score,
        total_score=total_score,
        notification_rank=determine_rank(total_score),
        scored_at=datetime.now(timezone.utc).isoformat(),
        scoring_basis_time=disclosure["system_available_at"],  # spec §6.1 DDL comment
        dataset_tag=dataset_tag_for_ticker(disclosure["ticker"]),
        volume_ratio=supply_demand_detail.volume_ratio,
    )
