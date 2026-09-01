"""Logging setup for unattended daily runs (spec §12 Phase 7: "エラー監視").

Writes to both the console (useful when run manually) and a rotating log
file, so a scheduler-invoked run (cron/launchd/Task Scheduler, which
usually discard stdout) still leaves a record to check after the fact.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Union

DEFAULT_LOG_DIR = Path("logs")
DEFAULT_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
DEFAULT_BACKUP_COUNT = 5


def configure_logging(log_dir: Union[str, Path] = DEFAULT_LOG_DIR) -> Path:
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "stock_radar.log"

    root_logger = logging.getLogger("stock_radar")
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()  # avoid duplicate handlers if called more than once

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    file_handler = RotatingFileHandler(
        log_path, maxBytes=DEFAULT_MAX_BYTES, backupCount=DEFAULT_BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    return log_path
