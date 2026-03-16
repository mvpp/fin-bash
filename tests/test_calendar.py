"""Tests for fin_bash.calendar — market calendar logic."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from fin_bash.calendar import (
    SessionInfo,
    _get_calendar,
    get_next_sessions,
    get_session_info,
    is_market_open,
    is_trading_day,
)


# ── Known dates ────────────────────────────────────────────────────────────────

class TestIsTradingDay:
    """is_trading_day with NYSE (XNYS)."""

    def test_weekday_is_session(self):
        # 2026-03-13 is a Friday
        assert is_trading_day("XNYS", date(2026, 3, 13)) is True

    def test_saturday_not_session(self):
        assert is_trading_day("XNYS", date(2026, 3, 14)) is False

    def test_sunday_not_session(self):
        assert is_trading_day("XNYS", date(2026, 3, 15)) is False

    def test_christmas_not_session(self):
        assert is_trading_day("XNYS", date(2025, 12, 25)) is False

    def test_new_years_not_session(self):
        assert is_trading_day("XNYS", date(2026, 1, 1)) is False

    def test_july_4th_not_session(self):
        # Independence Day 2025 is a Friday
        assert is_trading_day("XNYS", date(2025, 7, 4)) is False


# ── Session info & early close ─────────────────────────────────────────────────

class TestGetSessionInfo:
    """get_session_info returns correct times and early-close flag."""

    def test_regular_session_times(self):
        info = get_session_info("XNYS", date(2026, 3, 13))
        assert info.market_open.hour == 9
        assert info.market_open.minute == 30
        assert info.market_close.hour == 16
        assert info.market_close.minute == 0

    def test_early_close_thanksgiving_eve(self):
        # Day before Thanksgiving 2026: Nov 27 — closes at 13:00
        info = get_session_info("XNYS", date(2026, 11, 27))
        assert info.market_close.hour == 13
        assert info.market_close.minute == 0

    def test_non_session_raises_value_error(self):
        with pytest.raises(ValueError, match="not a trading session"):
            get_session_info("XNYS", date(2026, 3, 14))  # Saturday

    def test_timezone_is_exchange_tz(self):
        info = get_session_info("XNYS", date(2026, 3, 13))
        tz = info.market_open.tzinfo
        assert str(tz) == "America/New_York"

    def test_london_exchange_tz(self):
        info = get_session_info("XLON", date(2026, 3, 13))
        tz = info.market_open.tzinfo
        assert "Europe/London" in str(tz) or "GMT" in str(tz)

    def test_format_times_contains_timezone(self):
        info = get_session_info("XNYS", date(2026, 3, 13))
        formatted = info.format_times()
        assert "America/New_York" in formatted
        assert "09:30" in formatted
        assert "16:00" in formatted


# ── Timezone-aware session checks ──────────────────────────────────────────────

class TestIsMarketOpen:
    """is_market_open with explicit `now` to test timezone handling."""

    def test_any_session_ignores_time(self):
        # 3 AM ET on a trading day — "any" should still return True
        now = datetime(2026, 3, 13, 3, 0, tzinfo=ZoneInfo("America/New_York"))
        assert is_market_open("XNYS", date(2026, 3, 13), session_type="any", now=now) is True

    def test_regular_during_hours(self):
        now = datetime(2026, 3, 13, 12, 0, tzinfo=ZoneInfo("America/New_York"))
        assert is_market_open("XNYS", date(2026, 3, 13), session_type="regular", now=now) is True

    def test_regular_before_open(self):
        now = datetime(2026, 3, 13, 8, 0, tzinfo=ZoneInfo("America/New_York"))
        assert is_market_open("XNYS", date(2026, 3, 13), session_type="regular", now=now) is False

    def test_regular_after_close(self):
        now = datetime(2026, 3, 13, 17, 0, tzinfo=ZoneInfo("America/New_York"))
        assert is_market_open("XNYS", date(2026, 3, 13), session_type="regular", now=now) is False

    def test_regular_at_exact_open(self):
        now = datetime(2026, 3, 13, 9, 30, tzinfo=ZoneInfo("America/New_York"))
        assert is_market_open("XNYS", date(2026, 3, 13), session_type="regular", now=now) is True

    def test_regular_at_exact_close(self):
        now = datetime(2026, 3, 13, 16, 0, tzinfo=ZoneInfo("America/New_York"))
        assert is_market_open("XNYS", date(2026, 3, 13), session_type="regular", now=now) is True

    def test_pre_market_window(self):
        now = datetime(2026, 3, 13, 5, 0, tzinfo=ZoneInfo("America/New_York"))
        assert is_market_open("XNYS", date(2026, 3, 13), session_type="pre", now=now) is True

    def test_pre_market_too_early(self):
        now = datetime(2026, 3, 13, 3, 0, tzinfo=ZoneInfo("America/New_York"))
        assert is_market_open("XNYS", date(2026, 3, 13), session_type="pre", now=now) is False

    def test_post_market_window(self):
        now = datetime(2026, 3, 13, 18, 0, tzinfo=ZoneInfo("America/New_York"))
        assert is_market_open("XNYS", date(2026, 3, 13), session_type="post", now=now) is True

    def test_post_market_too_late(self):
        now = datetime(2026, 3, 13, 21, 0, tzinfo=ZoneInfo("America/New_York"))
        assert is_market_open("XNYS", date(2026, 3, 13), session_type="post", now=now) is False

    def test_non_trading_day_always_false(self):
        now = datetime(2026, 3, 14, 12, 0, tzinfo=ZoneInfo("America/New_York"))
        assert is_market_open("XNYS", date(2026, 3, 14), session_type="any", now=now) is False
        assert is_market_open("XNYS", date(2026, 3, 14), session_type="regular", now=now) is False

    def test_invalid_session_type_raises(self):
        now = datetime(2026, 3, 13, 12, 0, tzinfo=ZoneInfo("America/New_York"))
        with pytest.raises(ValueError, match="Unknown session_type"):
            is_market_open("XNYS", date(2026, 3, 13), session_type="invalid", now=now)

    # ── Timezone conversion: caller in a different timezone ────────────────

    def test_regular_from_utc(self):
        """Pass `now` in UTC; should still work via astimezone."""
        # 12:00 ET = 16:00 UTC (during EDT, March 2026)
        now_utc = datetime(2026, 3, 13, 16, 0, tzinfo=ZoneInfo("UTC"))
        assert is_market_open("XNYS", date(2026, 3, 13), session_type="regular", now=now_utc) is True

    def test_regular_from_pacific(self):
        """Caller is in Pacific time, exchange is in Eastern."""
        # 9:00 AM PT = 12:00 PM ET (during PDT/EDT)
        now_pt = datetime(2026, 3, 13, 9, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
        assert is_market_open("XNYS", date(2026, 3, 13), session_type="regular", now=now_pt) is True

    def test_regular_from_tokyo(self):
        """Caller in Asia/Tokyo — should be outside NYSE hours."""
        # 9:00 AM JST on Mar 13 = ~7 PM ET on Mar 12 (market closed)
        now_tokyo = datetime(2026, 3, 13, 9, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
        assert is_market_open("XNYS", date(2026, 3, 13), session_type="regular", now=now_tokyo) is False

    def test_london_exchange_from_eastern(self):
        """Check LSE hours with caller in Eastern time."""
        # LSE hours: 08:00–16:30 London time
        # 10:00 AM London = 5:00 AM ET (during GMT/EST)
        now_et = datetime(2026, 3, 13, 5, 0, tzinfo=ZoneInfo("America/New_York"))
        assert is_market_open("XLON", date(2026, 3, 13), session_type="regular", now=now_et) is True

    def test_early_close_regular_after_early_close(self):
        """On a half day, 14:00 ET should be outside regular hours."""
        # Nov 27, 2026 closes at 13:00 ET
        now = datetime(2026, 11, 27, 14, 0, tzinfo=ZoneInfo("America/New_York"))
        assert is_market_open("XNYS", date(2026, 11, 27), session_type="regular", now=now) is False

    def test_early_close_regular_before_close(self):
        """On a half day, 12:30 ET should still be regular hours."""
        now = datetime(2026, 11, 27, 12, 30, tzinfo=ZoneInfo("America/New_York"))
        assert is_market_open("XNYS", date(2026, 11, 27), session_type="regular", now=now) is True


# ── Next sessions ──────────────────────────────────────────────────────────────

class TestGetNextSessions:
    def test_returns_requested_count(self):
        sessions = get_next_sessions("XNYS", count=5, after=date(2026, 3, 13))
        assert len(sessions) == 5

    def test_all_sessions_are_after_start_date(self):
        after = date(2026, 3, 13)
        sessions = get_next_sessions("XNYS", count=5, after=after)
        for s in sessions:
            assert s.date > after

    def test_skips_weekends(self):
        # After Friday 2026-03-13, next should be Monday 2026-03-16
        sessions = get_next_sessions("XNYS", count=1, after=date(2026, 3, 13))
        assert sessions[0].date == date(2026, 3, 16)


# ── Error handling: invalid exchange ───────────────────────────────────────────

class TestInvalidExchange:
    def test_invalid_exchange_exits(self):
        with pytest.raises(SystemExit, match="Unknown exchange"):
            _get_calendar("INVALID_CODE")

    def test_is_trading_day_invalid_exchange(self):
        with pytest.raises(SystemExit, match="Unknown exchange"):
            is_trading_day("NOPE", date(2026, 3, 13))
