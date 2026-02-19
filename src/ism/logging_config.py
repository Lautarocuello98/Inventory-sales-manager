from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _handler(path: Path, level: int) -> RotatingFileHandler:
    fh = RotatingFileHandler(path, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    fh.setFormatter(JsonFormatter(datefmt="%Y-%m-%d %H:%M:%S"))
    fh.setLevel(level)
    return fh


def setup_logging(logs_dir: Path, level: int = logging.INFO) -> None:
    logs_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(level)
    if root.handlers:
        return

    app_handler = _handler(logs_dir / "app.log", logging.INFO)
    err_handler = _handler(logs_dir / "errors.log", logging.ERROR)
    root.addHandler(app_handler)
    root.addHandler(err_handler)

    sales_handler = _handler(logs_dir / "sales.log", logging.INFO)
    logging.getLogger("ism.sales").addHandler(sales_handler)
    logging.getLogger("ism.sales").setLevel(logging.INFO)

    fx_handler = _handler(logs_dir / "fx.log", logging.INFO)
    logging.getLogger("ism.fx").addHandler(fx_handler)
    logging.getLogger("ism.fx").setLevel(logging.INFO)
