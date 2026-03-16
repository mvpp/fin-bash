"""Tests for fin_bash.cli — CLI argument parsing and command routing."""

import subprocess
import sys
from unittest.mock import patch

import pytest

from fin_bash.cli import _detect_subcommand, _build_global_parser, EXIT_OK, EXIT_SKIPPED


# ── Subcommand detection ───────────────────────────────────────────────────────

class TestDetectSubcommand:
    """_detect_subcommand should find 'check'/'next' among flags."""

    def test_bare_check(self):
        assert _detect_subcommand(["check"]) == "check"

    def test_bare_next(self):
        assert _detect_subcommand(["next"]) == "next"

    def test_check_with_flags_before(self):
        assert _detect_subcommand(["--exchange", "XLON", "check"]) == "check"

    def test_check_with_flags_after(self):
        assert _detect_subcommand(["check", "--date", "2026-03-13"]) == "check"

    def test_script_name_not_subcommand(self):
        assert _detect_subcommand(["myjob.sh"]) is None

    def test_script_after_flags(self):
        assert _detect_subcommand(["--exchange", "XNYS", "myjob.sh"]) is None

    def test_dry_run_with_script(self):
        assert _detect_subcommand(["--dry-run", "myjob.sh"]) is None

    def test_empty_argv(self):
        assert _detect_subcommand([]) is None

    def test_only_flags_no_positional(self):
        assert _detect_subcommand(["--exchange", "XNYS", "--dry-run"]) is None

    def test_session_flag_with_script(self):
        assert _detect_subcommand(["--session", "regular", "myjob.sh"]) is None

    def test_all_flags_with_check(self):
        argv = ["--exchange", "XLON", "--config", "/tmp/c.yaml", "check", "--date", "2026-01-01"]
        assert _detect_subcommand(argv) == "check"


# ── Global parser ──────────────────────────────────────────────────────────────

class TestGlobalParser:
    """parse_known_args correctly separates flags from script args."""

    def test_script_only(self):
        parser = _build_global_parser()
        args, remainder = parser.parse_known_args(["myjob.sh"])
        assert remainder == ["myjob.sh"]
        assert args.exchange is None
        assert args.dry_run is False

    def test_exchange_and_script(self):
        parser = _build_global_parser()
        args, remainder = parser.parse_known_args(["--exchange", "XLON", "myjob.sh"])
        assert args.exchange == "XLON"
        assert remainder == ["myjob.sh"]

    def test_dry_run_and_script(self):
        parser = _build_global_parser()
        args, remainder = parser.parse_known_args(["--dry-run", "myjob.sh"])
        assert args.dry_run is True
        assert remainder == ["myjob.sh"]

    def test_script_with_args(self):
        parser = _build_global_parser()
        args, remainder = parser.parse_known_args(["myjob.sh", "--verbose", "arg1"])
        assert remainder == ["myjob.sh", "--verbose", "arg1"]

    def test_all_flags_with_script(self):
        parser = _build_global_parser()
        args, remainder = parser.parse_known_args([
            "--exchange", "XLON",
            "--session", "regular",
            "--date", "2026-03-13",
            "--dry-run",
            "myjob.sh", "extra_arg",
        ])
        assert args.exchange == "XLON"
        assert args.session == "regular"
        assert args.dry_run is True
        assert remainder == ["myjob.sh", "extra_arg"]

    def test_date_parsing(self):
        parser = _build_global_parser()
        args, _ = parser.parse_known_args(["--date", "2026-12-25", "myjob.sh"])
        from datetime import date
        assert args.date == date(2026, 12, 25)


# ── Full CLI integration (subprocess) ─────────────────────────────────────────

FIN_BASH = [sys.executable, "-m", "fin_bash.cli"]


class TestCLIIntegration:
    """Run fin-bash as a subprocess to test real behavior."""

    def test_check_trading_day(self):
        result = subprocess.run(
            FIN_BASH + ["check", "--date", "2026-03-13"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "is a trading day" in result.stdout
        assert "XNYS" in result.stdout

    def test_check_non_trading_day(self):
        result = subprocess.run(
            FIN_BASH + ["check", "--date", "2026-03-14"],
            capture_output=True, text=True,
        )
        assert result.returncode == EXIT_SKIPPED
        assert "is NOT a trading day" in result.stdout

    def test_check_with_exchange(self):
        result = subprocess.run(
            FIN_BASH + ["--exchange", "XLON", "check", "--date", "2026-03-13"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "XLON" in result.stdout

    def test_next_default_count(self):
        result = subprocess.run(
            FIN_BASH + ["next", "--count", "3"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        # Should print 3 dates
        lines_with_dates = [l for l in result.stdout.splitlines() if "202" in l]
        assert len(lines_with_dates) == 3

    def test_dry_run_skip_on_weekend(self):
        result = subprocess.run(
            FIN_BASH + ["--dry-run", "--date", "2026-03-14", "myjob.sh"],
            capture_output=True, text=True,
        )
        assert result.returncode == EXIT_SKIPPED
        assert "DRY RUN" in result.stdout
        assert "SKIP" in result.stdout

    def test_dry_run_would_run_on_trading_day(self):
        result = subprocess.run(
            FIN_BASH + ["--dry-run", "--date", "2026-03-13", "myjob.sh"],
            capture_output=True, text=True,
        )
        assert result.returncode == EXIT_OK
        assert "DRY RUN" in result.stdout
        assert "would execute" in result.stdout

    def test_no_script_no_dry_run_shows_error(self):
        result = subprocess.run(
            FIN_BASH + ["--date", "2026-03-13"],
            capture_output=True, text=True,
        )
        assert result.returncode == 1
        assert "no script specified" in result.stderr

    def test_invalid_exchange_shows_error(self):
        result = subprocess.run(
            FIN_BASH + ["--exchange", "BOGUS", "check"],
            capture_output=True, text=True,
        )
        assert result.returncode != 0
        assert "Unknown exchange" in result.stderr

    def test_help_flag(self):
        result = subprocess.run(
            FIN_BASH + ["--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "Market-aware cron wrapper" in result.stdout

    def test_session_regular_dry_run(self):
        result = subprocess.run(
            FIN_BASH + ["--session", "regular", "--dry-run", "--date", "2026-03-13", "scan.sh"],
            capture_output=True, text=True,
        )
        # At test time we're not inside regular hours, but date override +
        # dry-run should still produce clean output (either would-run or would-skip)
        assert result.returncode in (EXIT_OK, EXIT_SKIPPED)
        assert "DRY RUN" in result.stdout

    def test_script_with_arguments_preserved(self):
        """Script args should appear in dry-run output."""
        result = subprocess.run(
            FIN_BASH + ["--dry-run", "--date", "2026-03-13", "myjob.sh", "--verbose", "--output", "/tmp/out"],
            capture_output=True, text=True,
        )
        assert "myjob.sh --verbose --output /tmp/out" in result.stdout
