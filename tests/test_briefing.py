"""Tests for briefing.py. They use made-up data: no internet, no API calls, no cost."""
import re
from pathlib import Path

import pandas as pd
import pytest

import briefing


# --- A1: slug ---------------------------------------------------------------

def test_slug_removes_caret_and_dots():
    assert briefing.slug("^AEX") == "AEX"
    assert briefing.slug("DFEN.DE") == "DFEN_DE"
    assert briefing.slug("NVDA") == "NVDA"


# --- A2-A4: change_since ----------------------------------------------------

def make_closes(prices_by_date):
    """A made-up price series: {"2026-11-16": 100, ...} -> pandas Series with dates as index."""
    return pd.Series(list(prices_by_date.values()),
                     index=pd.to_datetime(list(prices_by_date.keys())))


def test_change_since_one_day():
    close = make_closes({"2026-11-16": 100, "2026-11-17": 110})
    assert briefing.change_since(close, pd.DateOffset(days=1)) == pytest.approx(10.0)


def test_change_since_over_weekend_uses_friday():
    # Monday's 1-day change: Sunday has no price, so it must fall back to Friday.
    close = make_closes({"2026-11-13": 100, "2026-11-16": 105})
    assert briefing.change_since(close, pd.DateOffset(days=1)) == pytest.approx(5.0)


def test_change_since_year_to_date():
    close = make_closes({"2025-12-31": 200, "2026-11-17": 250})
    latest_day = close.index[-1]
    ytd_offset = latest_day - latest_day.replace(month=1, day=1)   # same as in analyze()
    assert briefing.change_since(close, ytd_offset) == pytest.approx(25.0)

    # --- A5-A6: number formatting -----------------------------------------------

def test_pct_positive_is_green():
    html = briefing.pct(1.234)
    assert "+1.23%" in html
    assert 'class="up"' in html


def test_pct_negative_is_red():
    html = briefing.pct(-0.5)
    assert "-0.50%" in html
    assert 'class="down"' in html


def test_pct_zero_counts_as_up():
    assert 'class="up"' in briefing.pct(0)


def test_vs_average_without_enough_history_is_empty():
    # A fund with less than 200 days of data has no 200-day average (NaN)
    assert briefing.vs_average(10, float("nan")) == ""


# --- A7-A10: source links (safety of AI output) ------------------------------

def test_sources_drop_unsafe_and_non_web_links():
    assert briefing.sources_html(["javascript:alert(1)", "ftp://x.com/file", 5]) == ""


def test_sources_show_each_website_once():
    html = briefing.sources_html(["https://www.reuters.com/a", "https://reuters.com/b"])
    assert html.count("<a ") == 1
    assert ">reuters.com<" in html


def test_sources_escape_quotes_in_url():
    html = briefing.sources_html(['https://example.com/a"b'])
    assert "&quot;" in html
    assert 'a"b' not in html


@pytest.mark.parametrize("empty", [None, []])
def test_sources_empty_input_gives_nothing(empty):
    assert briefing.sources_html(empty) == ""


# --- A11-A13: "Why it moved" -------------------------------------------------

NVIDIA = {"symbol": "NVDA", "name": "NVIDIA"}
AEX = {"symbol": "^AEX", "name": "AEX index"}


@pytest.mark.parametrize("fund, key", [
    (AEX, "^AEX"),        # exactly the symbol
    (AEX, "AEX"),         # the agent dropped the ^
    (NVIDIA, "NVIDIA"),   # the agent used the name
])
def test_why_finds_explanation_under_any_key(fund, key):
    answer = {"explanations": {key: {"text": "Chip demand rose.", "sources": []}}}
    assert "Chip demand rose." in briefing.why_html(fund, answer)


def test_why_escapes_html_in_ai_text():
    answer = {"explanations": {"NVDA": {"text": "<script>alert(1)</script>"}}}
    html = briefing.why_html(NVIDIA, answer)
    assert "&lt;script&gt;" in html
    assert "<script>" not in html


def test_why_when_agent_failed():
    assert "not available today" in briefing.why_html(NVIDIA, None)


def test_why_when_fund_missing_from_answer():
    assert "No explanation found." in briefing.why_html(NVIDIA, {"explanations": {}})


# --- A14-A15: "Today in brief" -----------------------------------------------

def test_summary_quiet_day_has_no_ai_label():
    html = briefing.summary_html(None, [])
    assert "No significant moves today" in html
    assert "Written by an AI" not in html


def test_summary_when_agent_failed():
    html = briefing.summary_html(None, [NVIDIA])
    assert "not available today" in html
    assert "Written by an AI" not in html


def test_summary_with_ai_text_is_escaped_and_labelled():
    html = briefing.summary_html({"market_summary": "Stocks <b>rose</b>."}, [NVIDIA])
    assert "Stocks &lt;b&gt;rose&lt;/b&gt;." in html
    assert "Written by an AI" in html

    # --- C1-C6: analyze() with a fake Yahoo --------------------------------------

def fake_yahoo(monkeypatch, prices, pe=15.0, end="2026-11-17"):
    """Make briefing.analyze() see our made-up prices instead of asking Yahoo Finance."""
    dates = pd.bdate_range(end=end, periods=len(prices))   # working days only

    class FakeTicker:
        def __init__(self, symbol):
            self.info = {"trailingPE": pe}

        def history(self, period):
            return pd.DataFrame({"Close": prices}, index=dates)

    monkeypatch.setattr(briefing.yf, "Ticker", FakeTicker)


def calm_then(last_move):
    """70 calm days (alternating +1% and -1%), then one day that moves `last_move` percent."""
    prices = [100.0]
    for day in range(70):
        prices.append(prices[-1] * (1.01 if day % 2 == 0 else 0.99))
    prices.append(prices[-1] * (1 + last_move / 100))
    return prices


def test_big_rise_is_significant(monkeypatch):
    fake_yahoo(monkeypatch, calm_then(+5))
    result = briefing.analyze("TEST")
    assert result["z"] == pytest.approx(4.96, abs=0.01)
    assert result["significant"]


def test_normal_day_is_not_significant(monkeypatch):
    fake_yahoo(monkeypatch, calm_then(+1))
    result = briefing.analyze("TEST")
    assert result["z"] == pytest.approx(0.99, abs=0.01)
    assert not result["significant"]


def test_big_fall_is_significant_too(monkeypatch):
    fake_yahoo(monkeypatch, calm_then(-5))
    result = briefing.analyze("TEST")
    assert result["z"] == pytest.approx(-4.96, abs=0.01)
    assert result["significant"]


@pytest.mark.parametrize("prices, trend", [
    ([100 + day for day in range(300)], "Uptrend"),
    ([400 - day for day in range(300)], "Downtrend"),
])
def test_trend_from_moving_averages(monkeypatch, prices, trend):
    fake_yahoo(monkeypatch, prices)
    assert briefing.analyze("TEST")["trend"] == trend


def test_distance_from_52_week_high(monkeypatch):
    fake_yahoo(monkeypatch, [100] * 100 + [120] + [100] * 50 + [90])
    assert briefing.analyze("TEST")["from_high"] == pytest.approx(-25.0)


def test_short_history_does_not_crash(monkeypatch):
    # A newly listed stock: only 30 days. z is computed over the days that exist.
    fake_yahoo(monkeypatch, [100 + day % 3 for day in range(30)])
    result = briefing.analyze("TEST")
    assert not result["significant"]


def test_pe_is_passed_through(monkeypatch):
    fake_yahoo(monkeypatch, calm_then(+1), pe=21.5)
    assert briefing.analyze("TEST")["pe"] == 21.5


# --- New listings: show them, but honestly -----------------------------------

def test_listed_today_is_skipped(monkeypatch):
    # T1: only today's (unfinished) row exists: after dropping it, nothing is left to show.
    today = pd.Timestamp.now().normalize()
    fake_yahoo(monkeypatch, [100.0], end=today)
    assert briefing.analyze("NEW") is None


def test_one_day_old_is_shown_without_daily_change(monkeypatch):
    # T2: one finished day: we know the price, but there is no previous day to compare with.
    fake_yahoo(monkeypatch, [100.0])
    result = briefing.analyze("NEW")
    assert result is not None
    assert result["close"] == 100.0
    assert pd.isna(result["change_1d"])
    assert result["new_listing"]
    assert result["days"] == 1
    assert not result["significant"]


def test_big_jump_of_new_listing_is_not_flagged(monkeypatch):
    # T3: +30% on day 5 is huge, but 4 earlier days say nothing about what is "normal".
    fake_yahoo(monkeypatch, [100.0, 101.0, 102.0, 103.0, 133.9])
    result = briefing.analyze("NEW")
    assert result["new_listing"]
    assert result["days"] == 5
    assert not result["significant"]


def test_ten_days_has_one_week_but_no_one_month_change(monkeypatch):
    # T4: 10 working days ending Tue 17 Nov 2026 start on Wed 4 Nov.
    # One week back (Tue 10 Nov) exists: price 100 -> 110 is +10%. One month back does not exist.
    fake_yahoo(monkeypatch, [100.0] * 9 + [110.0])
    result = briefing.analyze("NEW")
    assert result["change_1w"] == pytest.approx(10.0)
    assert pd.isna(result["change_1m"])


def test_trend_needs_both_averages(monkeypatch):
    # T5: 100 days is enough for the 50-day average but not for the 200-day one.
    fake_yahoo(monkeypatch, [100.0 + day for day in range(100)])
    result = briefing.analyze("NEW")
    assert result["trend"] == "n/a"
    assert not result["new_listing"]          # 100 days is past the minimum


def test_pct_of_missing_value_is_grey_na():
    # T6
    html = briefing.pct(float("nan"))
    assert "n/a" in html
    assert "nan%" not in html
    assert 'class="down"' not in html


def test_exactly_minimum_history_is_a_normal_fund(monkeypatch):
    # T7: the edge of the rule: exactly MIN_HISTORY_DAYS days counts as enough.
    days = briefing.MIN_HISTORY_DAYS
    fake_yahoo(monkeypatch, [100.0 + day for day in range(days)])
    result = briefing.analyze("NEW")
    assert not result["new_listing"]
    assert result["days"] == days


def test_page_section_of_new_listing(monkeypatch):
    # T8: the fund block on the page shows the label and never the word "nan".
    fake_yahoo(monkeypatch, [100.0, 101.0, 102.0, 103.0, 104.0])
    result = briefing.analyze("NEW")
    result["name"] = "New Co"
    result["about"] = ""
    result["chart"] = Path("charts/NEW.svg")
    html = briefing.fund_section(result, result["date"].date(), None)
    assert "New listing" in html
    assert "5 days" in html
    assert re.search(r"\bnan\b", html) is None
    assert "σ" not in html                    # no z-score shown for a new listing


def test_new_listing_without_daily_move_is_neither_green_nor_red(monkeypatch):
    # T9: red/green means the last day's move. Without a previous day there is no move: neutral.
    fake_yahoo(monkeypatch, [100.0])
    result = briefing.analyze("NEW")
    assert briefing.direction(result) == "flat"