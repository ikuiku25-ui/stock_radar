"""Enforces spec §10.2's code-review requirement as an automated check:
"予測ロジック（材料分類・スコアリング）はoutcome_trackingテーブルを参照する
コードパスを持たないことをコードレビュー時のチェック項目とする". Prediction
code (classification/scoring/collectors) must never mention
outcome_tracking — only backtest/ may.
"""

from __future__ import annotations

from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parent.parent / "src" / "stock_radar"
PREDICTION_PACKAGES = ("classification", "scoring", "collectors", "db")


def test_prediction_code_never_references_outcome_tracking():
    offenders = []
    for package in PREDICTION_PACKAGES:
        package_dir = SRC_ROOT / package
        if not package_dir.exists():
            continue
        for path in package_dir.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "outcome_tracking" in text:
                offenders.append(str(path.relative_to(SRC_ROOT)))
    assert offenders == [], (
        f"spec §10.2 violation: prediction-path modules reference outcome_tracking: {offenders}"
    )


def test_backtest_package_is_the_only_one_touching_outcome_tracking():
    """Sanity check that the guard above isn't vacuously trivial — confirm
    outcome_tracking IS referenced somewhere (in backtest/), so a typo that
    silently excluded everything would be caught."""
    backtest_dir = SRC_ROOT / "backtest"
    found = any(
        "outcome_tracking" in path.read_text(encoding="utf-8") for path in backtest_dir.rglob("*.py")
    )
    assert found, "expected backtest/ to reference outcome_tracking somewhere"
