"""Market calendar logic using exchange_calendars."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Optional
from zoneinfo import ZoneInfo

import exchange_calendars as xcals


@dataclass
class SessionInfo:
    """Information about a single trading session."""

    date: date
    market_open: datetime
    market_close: datetime
    is_early_close: bool

    def format_times(self) -> str:
        """Return a human-readable string of open/close times."""
        tz = self.market_open.tzinfo
        open_str = self.market_open.strftime("%H:%M")
        close_str = self.market_close.strftime("%H:%M")
        tz_name = str(tz) if tz else "UTC"
        early = " (early close)" if self.is_early_close else ""
        return f"{open_str} – {close_str} {tz_name}{early}"


# Pre-market and post-market offset assumptions (exchange_calendars doesn't
# track these natively, so we use widely-accepted US conventions as defaults).
_PRE_MARKET_MINUTES = 330   # 5.5 hours before open  (04:00 ET for NYSE)
_POST_MARKET_MINUTES = 240  # 4 hours after close     (20:00 ET for NYSE)


def _get_calendar(exchange: str) -> xcals.ExchangeCalendar:
    """Get an exchange calendar, raising a clear error on bad codes."""
    try:
        return xcals.get_calendar(exchange)
    except xcals.errors.InvalidCalendarName:
        valid = sorted(xcals.get_calendar_names())
        raise SystemExit(
            f"Unknown exchange '{exchange}'. Valid codes include:\n"
            + ", ".join(valid[:30]) + " …"
        )


def exchange_local_date(exchange: str) -> date:
    """Return today's date in the exchange's own timezone.

    Use this instead of date.today() when running from a machine that may be
    in a very different timezone from the exchange (e.g. checking XHKG from
    California late at night, where it is already the next calendar day in HK).
    """
    cal = _get_calendar(exchange)
    tz = ZoneInfo(str(cal.tz))
    return datetime.now(tz=tz).date()


def is_trading_day(exchange: str, target_date: date) -> bool:
    """Check if *target_date* is a trading session on *exchange*."""
    cal = _get_calendar(exchange)
    return cal.is_session(target_date)


def is_market_open(
    exchange: str,
    target_date: date,
    session_type: str = "any",
    now: Optional[datetime] = None,
) -> bool:
    """Determine whether a job should run based on session type.

    session_type:
        "any"     — True if target_date is a trading day (ignores time).
        "regular" — True if current time is within regular trading hours.
        "pre"     — True if current time is in the pre-market window.
        "post"    — True if current time is in the post-market window.
    """
    cal = _get_calendar(exchange)

    if not cal.is_session(target_date):
        return False

    if session_type == "any":
        return True

    # Need time-of-day checks for regular / pre / post.
    info = get_session_info(exchange, target_date)
    tz = info.market_open.tzinfo
    if now is None:
        now = datetime.now(tz=tz)
    else:
        now = now.astimezone(tz)

    if session_type == "regular":
        return info.market_open <= now <= info.market_close

    if session_type == "pre":
        from datetime import timedelta

        pre_open = info.market_open - timedelta(minutes=_PRE_MARKET_MINUTES)
        return pre_open <= now < info.market_open

    if session_type == "post":
        from datetime import timedelta

        post_close = info.market_close + timedelta(minutes=_POST_MARKET_MINUTES)
        return info.market_close < now <= post_close

    raise ValueError(f"Unknown session_type: {session_type!r}")


def get_session_info(exchange: str, target_date: date) -> SessionInfo:
    """Return open/close times and early-close flag for a session."""
    cal = _get_calendar(exchange)

    if not cal.is_session(target_date):
        raise ValueError(f"{target_date} is not a trading session on {exchange}")

    schedule = cal.schedule.loc[str(target_date)]
    tz = cal.tz

    market_open = schedule["open"].to_pydatetime().astimezone(ZoneInfo(str(tz)))
    market_close = schedule["close"].to_pydatetime().astimezone(ZoneInfo(str(tz)))

    # Detect early close by comparing to typical close time.
    # We compare against the *previous* regular session's close time.
    # A simpler heuristic: check if this date appears in special_closes.
    is_early = False
    for dt_list, _ in cal.special_closes:
        if hasattr(dt_list, '__iter__'):
            for d in dt_list:
                if d.date() == target_date or d == target_date:
                    is_early = True
                    break
        if is_early:
            break

    # Fallback: also check special_closes_adhoc
    if not is_early and hasattr(cal, 'special_closes_adhoc'):
        adhoc = cal.special_closes_adhoc
        if hasattr(adhoc, '__iter__'):
            for adhoc_times, adhoc_dates in adhoc:
                for d in adhoc_dates:
                    if (hasattr(d, 'date') and d.date() == target_date) or d == target_date:
                        is_early = True
                        break
                if is_early:
                    break

    return SessionInfo(
        date=target_date,
        market_open=market_open,
        market_close=market_close,
        is_early_close=is_early,
    )


def get_next_sessions(
    exchange: str,
    count: int = 10,
    after: Optional[date] = None,
) -> list[SessionInfo]:
    """Return the next *count* trading sessions after *after* (default: today)."""
    cal = _get_calendar(exchange)

    if after is None:
        after = date.today()

    # Use sessions_in_range which handles non-session start dates gracefully.
    from datetime import timedelta
    end_date = after + timedelta(days=count * 3)  # generous window
    sessions = cal.sessions_in_range(after, end_date)

    # Filter to sessions strictly after `after`
    result: list[SessionInfo] = []
    for sess in sessions:
        sess_date = sess.date() if hasattr(sess, 'date') else sess
        if sess_date > after:
            try:
                result.append(get_session_info(exchange, sess_date))
            except ValueError:
                continue
            if len(result) >= count:
                break

    return result
