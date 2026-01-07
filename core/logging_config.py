from __future__ import annotations

import logging
from pathlib import Path

LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "app.log"
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"


def configure_logging() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATEFMT)
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    file_handler_exists = False
    for handler in root.handlers:
        if isinstance(handler, logging.FileHandler):
            if Path(getattr(handler, "baseFilename", "")).resolve() == LOG_FILE.resolve():
                file_handler_exists = True
                break

    if not file_handler_exists:
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    has_stream_handler = any(isinstance(handler, logging.StreamHandler) for handler in root.handlers)
    if not has_stream_handler:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        root.addHandler(stream_handler)

    logging.getLogger("watchfiles.main").setLevel(logging.WARNING)
