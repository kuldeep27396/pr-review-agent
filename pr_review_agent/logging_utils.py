from __future__ import annotations

import json
import logging
from pathlib import Path


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        return json.dumps(payload)


def configure_logging(level: str, log_format: str = "plain") -> logging.Logger:
    logger = logging.getLogger("pr_review_agent")
    if logger.handlers:
        return logger

    logger.setLevel(level)
    formatter: logging.Formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        "%Y-%m-%dT%H:%M:%S%z",
    )
    if log_format == "json":
        formatter = JsonFormatter()

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    log_dir = Path("logs")
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_dir / "app.log")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        logger.warning("File logging disabled; logs directory is not writable")

    return logger
