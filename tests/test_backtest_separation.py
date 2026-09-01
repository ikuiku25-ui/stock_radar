"""Enforces spec §10.2's code-review requirement as an automated check:
"予測ロジック（材料分類・スコアリング）はoutcome_trackingテーブルを参照する
コードパスを持たないことをコードレビュー時のチェック項目とする". Prediction
code (classification/scoring/collectors/db) must have no executable code
path referencing outcome_tracking — only backtest/ may.

Checks only non-docstring string literals (via `ast`), not raw text: a
docstring is allowed to explain, in prose, why a module deliberately
avoids outcome_tracking (scoring/repository.py does exactly this) without
that explanation itself being flagged as a violation. Comments are never
part of the AST, so they're excluded automatically.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parent.parent / "src" / "stock_radar"
PREDICTION_PACKAGES = ("classification", "scoring", "collectors", "db")

_DOCSTRING_OWNER_TYPES = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def _docstring_node_ids(tree: ast.AST) -> set[int]:
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, _DOCSTRING_OWNER_TYPES) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                ids.add(id(first.value))
    return ids


def _references_outcome_tracking_in_code(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    docstring_ids = _docstring_node_ids(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstring_ids:
            if "outcome_tracking" in node.value:
                return True
    return False


def test_prediction_code_never_references_outcome_tracking():
    offenders = []
    for package in PREDICTION_PACKAGES:
        package_dir = SRC_ROOT / package
        if not package_dir.exists():
            continue
        for path in package_dir.rglob("*.py"):
            if _references_outcome_tracking_in_code(path):
                offenders.append(str(path.relative_to(SRC_ROOT)))
    assert offenders == [], (
        f"spec §10.2 violation: prediction-path modules reference outcome_tracking: {offenders}"
    )


def test_detector_still_catches_a_real_code_reference(tmp_path):
    """Guards against the ast-based refinement becoming too lenient: an
    actual SQL string literal (not a docstring) must still be caught."""
    offending_file = tmp_path / "offender.py"
    offending_file.write_text(
        '"""A harmless module docstring that never mentions the forbidden table."""\n'
        "import sqlite3\n"
        "def leak(conn: sqlite3.Connection):\n"
        "    return conn.execute('SELECT * FROM outcome_tracking').fetchall()\n",
        encoding="utf-8",
    )
    assert _references_outcome_tracking_in_code(offending_file) is True


def test_detector_ignores_docstring_only_mentions(tmp_path):
    clean_file = tmp_path / "clean.py"
    clean_file.write_text(
        '"""This module deliberately avoids outcome_tracking, see spec §10.2."""\n'
        "def noop():\n"
        "    pass\n",
        encoding="utf-8",
    )
    assert _references_outcome_tracking_in_code(clean_file) is False


def test_backtest_package_is_the_only_one_touching_outcome_tracking():
    """Sanity check that the guard above isn't vacuously trivial — confirm
    outcome_tracking IS referenced somewhere (in backtest/), so a typo that
    silently excluded everything would be caught."""
    backtest_dir = SRC_ROOT / "backtest"
    found = any(_references_outcome_tracking_in_code(path) for path in backtest_dir.rglob("*.py"))
    assert found, "expected backtest/ to reference outcome_tracking somewhere"
