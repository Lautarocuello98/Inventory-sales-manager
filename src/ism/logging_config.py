from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(logs_dir: Path, level: int = logging.INFO) -> None:
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "app.log"

    logger = logging.getLogger()
    logger.setLevel(level)

    # Prevent duplicate handlers if main() called multiple times
    if any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
        return

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    fh = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    fh.setFormatter(fmt)
    fh.setLevel(level)

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    sh.setLevel(level)

    logger.addHandler(fh)
    logger.addHandler(sh)
