"""YAML configuration loading for fin-bash."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


_DEFAULT_CONFIG_PATH = Path("~/.config/fin-bash/config.yaml").expanduser()

# Defaults
_DEFAULTS = {
    "exchange": "XNYS",
    "session": "any",
    "logging": {
        "level": "INFO",
        "file": "~/.local/log/fin-bash/fin-bash.log",
    },
}


@dataclass
class LoggingConfig:
    level: str = "INFO"
    file: str = "~/.local/log/fin-bash/fin-bash.log"

    @property
    def resolved_file(self) -> Path:
        return Path(os.path.expanduser(self.file))


@dataclass
class Config:
    exchange: str = "XNYS"
    session: str = "any"
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    @classmethod
    def load(cls, path: Optional[str] = None) -> "Config":
        """Load config from YAML file, falling back to defaults.

        Resolution order: CLI --config > default path > hardcoded defaults.
        """
        config_path = Path(path) if path else _DEFAULT_CONFIG_PATH

        data: dict = {}
        if config_path.exists():
            with open(config_path) as f:
                data = yaml.safe_load(f) or {}

        # Merge with defaults
        exchange = data.get("exchange", _DEFAULTS["exchange"])
        session = data.get("session", _DEFAULTS["session"])

        log_data = data.get("logging", {})
        log_defaults = _DEFAULTS["logging"]
        logging_cfg = LoggingConfig(
            level=log_data.get("level", log_defaults["level"]),
            file=log_data.get("file", log_defaults["file"]),
        )

        return cls(exchange=exchange, session=session, logging=logging_cfg)
