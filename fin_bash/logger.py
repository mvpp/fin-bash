"""Logging setup for fin-bash."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from fin_bash.config import Config


def setup_logging(config: Config) -> logging.Logger:
    """Configure and return the fin-bash logger.

    - File handler: logs all messages at configured level.
    - Console (stderr): only WARNING and above (keeps cron output clean).
    """
    logger = logging.getLogger("fin-bash")
    logger.setLevel(config.logging.level.upper())

    # Avoid duplicate handlers on repeated calls
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # --- File handler ---
    log_path = config.logging.resolved_file
    log_path.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(config.logging.level.upper())
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # --- Console handler (stderr, warnings+ only) ---
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.WARNING)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    return logger
