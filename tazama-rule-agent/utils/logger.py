# utils/logger.py
import logging
import os
from datetime import datetime
from rich.logging import RichHandler
from config import cfg

os.makedirs(cfg.LOG_DIR, exist_ok=True)

def get_logger(name: str) -> logging.Logger:
    log_file = os.path.join(
        cfg.LOG_DIR,
        f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, cfg.LOG_LEVEL, logging.DEBUG))

    if not logger.handlers:
        # Console — rich colored output
        console = RichHandler(rich_tracebacks=True, markup=True)
        console.setLevel(getattr(logging, cfg.LOG_LEVEL))
        logger.addHandler(console)

        # File — plain text, always DEBUG
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        ))
        logger.addHandler(file_handler)

    return logger
