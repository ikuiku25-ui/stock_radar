from __future__ import annotations

import logging

from stock_radar.pipeline.logging_config import configure_logging


def test_creates_log_file_and_writes_to_it(tmp_path):
    log_dir = tmp_path / "logs"
    log_path = configure_logging(log_dir)

    logger = logging.getLogger("stock_radar.pipeline")
    logger.info("test message")
    for handler in logging.getLogger("stock_radar").handlers:
        handler.flush()

    assert log_path.exists()
    assert "test message" in log_path.read_text(encoding="utf-8")


def test_reconfiguring_does_not_duplicate_handlers(tmp_path):
    log_dir = tmp_path / "logs"
    configure_logging(log_dir)
    configure_logging(log_dir)

    root_logger = logging.getLogger("stock_radar")
    assert len(root_logger.handlers) == 2  # file + console, not doubled
