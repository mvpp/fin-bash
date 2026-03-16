"""Tests for fin_bash.logger and fin_bash.config."""

import logging
import os
import tempfile
from pathlib import Path

import pytest
import yaml

from fin_bash.config import Config, LoggingConfig
from fin_bash.logger import setup_logging


# ── Config loading ─────────────────────────────────────────────────────────────

class TestConfig:
    def test_default_config(self):
        """Config.load with no file should return hardcoded defaults."""
        config = Config.load("/nonexistent/path/config.yaml")
        assert config.exchange == "XNYS"
        assert config.session == "any"
        assert config.logging.level == "INFO"

    def test_load_from_yaml(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({
            "exchange": "XLON",
            "session": "regular",
            "logging": {"level": "DEBUG", "file": str(tmp_path / "test.log")},
        }))
        config = Config.load(str(config_file))
        assert config.exchange == "XLON"
        assert config.session == "regular"
        assert config.logging.level == "DEBUG"

    def test_partial_yaml_uses_defaults(self, tmp_path):
        """YAML with only exchange — other fields should use defaults."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({"exchange": "XTKS"}))
        config = Config.load(str(config_file))
        assert config.exchange == "XTKS"
        assert config.session == "any"  # default
        assert config.logging.level == "INFO"  # default

    def test_empty_yaml_uses_defaults(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        config = Config.load(str(config_file))
        assert config.exchange == "XNYS"

    def test_tilde_expansion_in_log_path(self):
        lc = LoggingConfig(file="~/some/path/log.txt")
        resolved = lc.resolved_file
        assert "~" not in str(resolved)
        assert str(resolved).startswith("/")


# ── Logging ────────────────────────────────────────────────────────────────────

class TestLogging:
    def test_log_file_created(self, tmp_path):
        """setup_logging should create the log file and its parent dirs."""
        log_file = tmp_path / "subdir" / "fin-bash.log"
        config = Config(
            exchange="XNYS",
            session="any",
            logging=LoggingConfig(level="INFO", file=str(log_file)),
        )
        # Clear any previously registered handlers for this logger name
        logger = logging.getLogger("fin-bash")
        logger.handlers.clear()

        logger = setup_logging(config)
        logger.info("test message")

        # Flush handlers
        for h in logger.handlers:
            h.flush()

        assert log_file.exists()
        content = log_file.read_text()
        assert "test message" in content

    def test_log_format_contains_timestamp_and_level(self, tmp_path):
        log_file = tmp_path / "fin-bash.log"
        config = Config(
            logging=LoggingConfig(level="DEBUG", file=str(log_file)),
        )
        logger = logging.getLogger("fin-bash")
        logger.handlers.clear()

        logger = setup_logging(config)
        logger.info("formatted check")

        for h in logger.handlers:
            h.flush()

        content = log_file.read_text()
        assert "INFO" in content
        assert "formatted check" in content
        # Timestamp format: YYYY-MM-DD HH:MM:SS
        import re
        assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", content)

    def test_debug_messages_logged_at_debug_level(self, tmp_path):
        log_file = tmp_path / "fin-bash.log"
        config = Config(
            logging=LoggingConfig(level="DEBUG", file=str(log_file)),
        )
        logger = logging.getLogger("fin-bash")
        logger.handlers.clear()

        logger = setup_logging(config)
        logger.debug("debug detail")

        for h in logger.handlers:
            h.flush()

        content = log_file.read_text()
        assert "debug detail" in content

    def test_debug_messages_not_logged_at_info_level(self, tmp_path):
        log_file = tmp_path / "fin-bash.log"
        config = Config(
            logging=LoggingConfig(level="INFO", file=str(log_file)),
        )
        logger = logging.getLogger("fin-bash")
        logger.handlers.clear()

        logger = setup_logging(config)
        logger.debug("should not appear")

        for h in logger.handlers:
            h.flush()

        content = log_file.read_text()
        assert "should not appear" not in content

    def test_console_only_shows_warnings(self, tmp_path, capsys):
        """Console handler (stderr) should only show WARNING+."""
        log_file = tmp_path / "fin-bash.log"
        config = Config(
            logging=LoggingConfig(level="INFO", file=str(log_file)),
        )
        logger = logging.getLogger("fin-bash")
        logger.handlers.clear()

        logger = setup_logging(config)
        logger.info("info msg")
        logger.warning("warn msg")

        captured = capsys.readouterr()
        assert "info msg" not in captured.err
        assert "warn msg" in captured.err

    def test_multiple_setup_calls_no_duplicate_handlers(self, tmp_path):
        """Calling setup_logging twice should not duplicate handlers."""
        log_file = tmp_path / "fin-bash.log"
        config = Config(
            logging=LoggingConfig(level="INFO", file=str(log_file)),
        )
        logger = logging.getLogger("fin-bash")
        logger.handlers.clear()

        logger1 = setup_logging(config)
        handler_count = len(logger1.handlers)
        logger2 = setup_logging(config)
        assert len(logger2.handlers) == handler_count

    def test_log_records_skip_event(self, tmp_path):
        """Simulate what a skipped-run log entry looks like."""
        log_file = tmp_path / "fin-bash.log"
        config = Config(
            logging=LoggingConfig(level="INFO", file=str(log_file)),
        )
        logger = logging.getLogger("fin-bash")
        logger.handlers.clear()

        logger = setup_logging(config)
        logger.info(
            "Market CLOSED — skipping: scan.sh (exchange=%s, date=%s, session=%s)",
            "XNYS", "2026-03-14", "any",
        )

        for h in logger.handlers:
            h.flush()

        content = log_file.read_text()
        assert "Market CLOSED" in content
        assert "scan.sh" in content
        assert "XNYS" in content
        assert "2026-03-14" in content

    def test_log_records_run_event(self, tmp_path):
        """Simulate what an executed-run log entry looks like."""
        log_file = tmp_path / "fin-bash.log"
        config = Config(
            logging=LoggingConfig(level="INFO", file=str(log_file)),
        )
        logger = logging.getLogger("fin-bash")
        logger.handlers.clear()

        logger = setup_logging(config)
        logger.info(
            "Market OPEN — executing: /bin/bash scan.sh (exchange=%s, date=%s)",
            "XNYS", "2026-03-13",
        )

        for h in logger.handlers:
            h.flush()

        content = log_file.read_text()
        assert "Market OPEN" in content
        assert "executing" in content
        assert "scan.sh" in content
