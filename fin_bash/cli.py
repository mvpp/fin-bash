"""CLI entry point for fin-bash.

Usage in crontab:
    30 9 * * 1-5  fin-bash myjob.sh
    30 9 * * 1-5  fin-bash --exchange XNYS myjob.sh
    30 9 * * 1-5  fin-bash --exchange XLON --session regular myjob.sh

Subcommands:
    fin-bash check [--exchange XNYS] [--date 2026-03-16]
    fin-bash next  [--exchange XNYS] [--count 10]
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime

from fin_bash.calendar import exchange_local_date, get_next_sessions, get_session_info, is_market_open, is_trading_day
from fin_bash.config import Config
from fin_bash.logger import setup_logging

# Exit codes
EXIT_OK = 0
EXIT_SKIPPED = 10

# Known subcommands (everything else is treated as a script to run)
_SUBCOMMANDS = {"check", "next"}


def _parse_date(s: str) -> date:
    """Parse a YYYY-MM-DD date string."""
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date format: {s!r}  (expected YYYY-MM-DD)")


def _build_global_parser() -> argparse.ArgumentParser:
    """Parser for global flags only (no subcommands)."""
    parser = argparse.ArgumentParser(
        prog="fin-bash",
        description="Market-aware cron wrapper — only runs your script on trading days.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  fin-bash myjob.sh                       # run on NYSE trading days\n"
            "  fin-bash --exchange XLON myjob.sh       # run on LSE trading days\n"
            "  fin-bash --dry-run myjob.sh             # preview without running\n"
            "  fin-bash check                          # is today a trading day?\n"
            "  fin-bash check --date 2026-03-16        # check a specific date\n"
            "  fin-bash next --count 5                 # list next 5 trading days\n"
        ),
    )
    parser.add_argument("--exchange", metavar="CODE", help="Exchange code (default: XNYS / NYSE)")
    parser.add_argument("--session", choices=["any", "regular", "pre", "post"],
                        help="Session type to check (default: any)")
    parser.add_argument("--config", metavar="PATH", help="Path to YAML config file")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview: print whether the job would run, then exit")
    parser.add_argument("--date", type=_parse_date, default=None,
                        help="Override the date to check (useful with --dry-run)")
    parser.add_argument("--tz-aware", action="store_true",
                        help="Resolve 'today' in the exchange's local timezone instead of the machine's")
    return parser


def _build_check_parser() -> argparse.ArgumentParser:
    """Parser for `fin-bash check`."""
    parser = argparse.ArgumentParser(prog="fin-bash check")
    parser.add_argument("--exchange", metavar="CODE", help="Exchange code (default: XNYS)")
    parser.add_argument("--session", choices=["any", "regular", "pre", "post"])
    parser.add_argument("--config", metavar="PATH")
    parser.add_argument("--date", type=_parse_date, default=None,
                        help="Date to check (default: today)")
    parser.add_argument("--tz-aware", action="store_true",
                        help="Resolve 'today' in the exchange's local timezone instead of the machine's")
    return parser


def _build_next_parser() -> argparse.ArgumentParser:
    """Parser for `fin-bash next`."""
    parser = argparse.ArgumentParser(prog="fin-bash next")
    parser.add_argument("--exchange", metavar="CODE", help="Exchange code (default: XNYS)")
    parser.add_argument("--config", metavar="PATH")
    parser.add_argument("--count", "-n", type=int, default=10,
                        help="Number of days to show (default: 10)")
    parser.add_argument("--tz-aware", action="store_true",
                        help="Resolve 'today' in the exchange's local timezone instead of the machine's")
    return parser


def _detect_subcommand(argv: list[str]) -> str | None:
    """Find the first positional arg and check if it's a subcommand."""
    # Skip known flag-value pairs (--exchange CODE, --config PATH, etc.)
    flags_with_values = {"--exchange", "--session", "--config", "--date"}
    flags_no_value = {"--dry-run", "-h", "--help"}

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in flags_with_values:
            i += 2  # skip flag + its value
        elif arg in flags_no_value or arg.startswith("-"):
            i += 1
        else:
            # First positional arg — is it a subcommand?
            return arg if arg in _SUBCOMMANDS else None
    return None


def _cmd_check(args: argparse.Namespace, config: Config, logger) -> int:
    """Handle `fin-bash check`."""
    exchange = args.exchange or config.exchange
    tz_aware = getattr(args, "tz_aware", False)
    if args.date:
        target = args.date
    elif tz_aware:
        target = exchange_local_date(exchange)
    else:
        target = date.today()

    if is_trading_day(exchange, target):
        info = get_session_info(exchange, target)
        print(f"✓  {target}  is a trading day on {exchange}")
        print(f"   Session: {info.format_times()}")
        if tz_aware:
            from zoneinfo import ZoneInfo
            import exchange_calendars as xcals
            cal = xcals.get_calendar(exchange)
            print(f"   (date resolved in exchange timezone: {cal.tz})")
        return EXIT_OK
    else:
        print(f"✗  {target}  is NOT a trading day on {exchange}")
        return EXIT_SKIPPED


def _cmd_next(args: argparse.Namespace, config: Config, logger) -> int:
    """Handle `fin-bash next`."""
    exchange = args.exchange or config.exchange
    count = args.count
    tz_aware = getattr(args, "tz_aware", False)
    after = exchange_local_date(exchange) if tz_aware else date.today()
    sessions = get_next_sessions(exchange, count=count, after=after)

    print(f"Next {len(sessions)} trading days on {exchange}:\n")
    for info in sessions:
        day_name = info.date.strftime("%a")
        early_tag = "  ⚡ early close" if info.is_early_close else ""
        print(f"  {info.date}  {day_name}  {info.format_times()}{early_tag}")

    return EXIT_OK


def _cmd_run(args: argparse.Namespace, script_args: list[str], config: Config, logger) -> int:
    """Default mode: check market, then run the script via /bin/bash."""
    exchange = args.exchange or config.exchange
    session = args.session or config.session
    tz_aware = getattr(args, "tz_aware", False)
    if args.date:
        target = args.date
    elif tz_aware:
        target = exchange_local_date(exchange)
    else:
        target = date.today()
    dry_run = args.dry_run

    if not script_args and not dry_run:
        print("fin-bash: no script specified. Use 'fin-bash --help' for usage.", file=sys.stderr)
        return 1

    cmd_display = " ".join(script_args) if script_args else "(no command)"

    if is_market_open(exchange, target, session_type=session):
        if dry_run:
            print(f"✓  DRY RUN: would execute on {target} ({exchange}, session={session})")
            print(f"   Command: /bin/bash {cmd_display}")
            logger.info("DRY RUN — would run: %s (exchange=%s, date=%s)", cmd_display, exchange, target)
            return EXIT_OK
        else:
            logger.info("Market OPEN — executing: /bin/bash %s (exchange=%s, date=%s)", cmd_display, exchange, target)
            # Replace this process with /bin/bash running the script.
            # os.execvp never returns on success.
            os.execvp("/bin/bash", ["/bin/bash"] + script_args)
            # If we get here, exec failed.
            logger.error("Failed to exec /bin/bash %s", cmd_display)
            return 1
    else:
        if dry_run:
            print(f"✗  DRY RUN: would SKIP on {target} ({exchange}, session={session})")
            print(f"   Command: /bin/bash {cmd_display}")
        logger.info("Market CLOSED — skipping: %s (exchange=%s, date=%s, session=%s)",
                     cmd_display, exchange, target, session)
        return EXIT_SKIPPED


def main() -> None:
    argv = sys.argv[1:]
    subcmd = _detect_subcommand(argv)

    if subcmd == "check":
        # Remove 'check' from argv, parse the rest
        argv.remove("check")
        parser = _build_check_parser()
        args = parser.parse_args(argv)
        config = Config.load(args.config)
        logger = setup_logging(config)
        sys.exit(_cmd_check(args, config, logger))

    elif subcmd == "next":
        argv.remove("next")
        parser = _build_next_parser()
        args = parser.parse_args(argv)
        config = Config.load(args.config)
        logger = setup_logging(config)
        sys.exit(_cmd_next(args, config, logger))

    else:
        # Default: run mode. Parse known flags, everything else is the script.
        parser = _build_global_parser()
        args, script_args = parser.parse_known_args(argv)
        config = Config.load(args.config)
        logger = setup_logging(config)
        sys.exit(_cmd_run(args, script_args, config, logger))


if __name__ == "__main__":
    main()
