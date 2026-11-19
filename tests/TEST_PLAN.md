# Test plan: Market briefing

Rules for every test: no internet, no API calls, no cost, and no writing into `docs/`.
The whole set should run in about a second with `pytest`.

Status (2026-11-19): phase 1 and phase 2 are written and pass (30 tests). Phase 3 is still open.

## Phase 1: tests on the current code (no code changes)

| # | Function | Test | Expected |
|---|---|---|---|
| A1 | `slug` | `"^AEX"`, `"DFEN.DE"`, `"NVDA"` | `"AEX"`, `"DFEN_DE"`, `"NVDA"` |
| A2 | `change_since` | last close 110, previous day 100, offset 1 day | `+10.0` |
| A3 | `change_since` | Friday 100, Monday 105, offset 1 day from Monday | `+5.0` (falls back to Friday) |
| A4 | `change_since` | last close of previous year 200, now 250, YTD offset | `+25.0` |
| A5 | `pct` | `1.234` / `-0.5` / `0` | `+1.23%` class `up` / `-0.50%` class `down` / `+0.00%` class `up` |
| A6 | `vs_average` | average is NaN (not enough history) | `""` |
| A7 | `sources_html` | `javascript:` link, `ftp://` link, a number | all dropped |
| A8 | `sources_html` | `www.reuters.com/a` and `reuters.com/b` | one link, labelled `reuters.com` |
| A9 | `sources_html` | URL containing `"` | escaped as `&quot;` |
| A10 | `sources_html` | `None` or `[]` | `""` |
| A11 | `why_html` | explanation stored under `"^AEX"` or `"AEX"` | found in both cases |
| A12 | `why_html` | text contains `<script>` | escaped (`&lt;script&gt;`) |
| A13 | `why_html` | `agent_answer` is `None` / fund missing | "not available today" / "No explanation found." |
| A14 | `summary_html` | no significant moves | standard text, no AI label |
| A15 | `summary_html` | significant moves but the agent failed | "not available" text |

## Phase 2: `analyze()` with a fake Yahoo (no code changes)

`analyze()` fetches its own data, so the tests replace `yf.Ticker` with a small fake class that returns
made-up prices (pytest's `monkeypatch`). Values below were checked against the current code.

| # | Made-up data | Expected |
|---|---|---|
| C1 | 70 days alternating +1%/-1%, then +5% | z ≈ 4.96, significant |
| C2 | same, last day +1% | z ≈ 0.99, not significant |
| C3 | same, last day -5% | z ≈ -4.96, significant |
| C4 | rising / falling for 300 days | `"Uptrend"` / `"Downtrend"` |
| C5 | flat at 100, one peak of 120, now 90 | `from_high = -25.0` |
| C6 | only 30 days of data | no crash; z is computed over the days available, not significant |

## Phase 3: connections (integration)

| # | Test | Expected |
|---|---|---|
| D1 | `build_page` with fake results and `agent_answer=None`, `PAGE_FILE` pointed at a temporary folder | file written, contains every fund name and "not investment advice" |
| D2 | fake Yahoo -> `analyze` -> `build_page` | the whole chain runs without internet |
