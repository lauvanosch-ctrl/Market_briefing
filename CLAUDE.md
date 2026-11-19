# Market briefing agent

A daily market briefing: Python fetches prices and computes the numbers, flags unusual moves,
and a Claude agent with web search explains *why* the flagged funds moved. Output is a dark-themed
`briefing.html` with a watchlist, per-fund explanation, chart and key stats.

## Run
```
.venv\Scripts\python briefing.py
```
Best run time on weekdays is about 09:15-09:30, when Yahoo has filled in the European closes.
Output: `docs/briefing.html` and `docs/charts/*.svg`. These ARE committed: GitHub Pages serves `docs/`
as the live demo at https://lauvanosch-ctrl.github.io/Market_briefing/briefing.html.
The venv uses python.org Python 3.13; `jiter==0.17.0` is pinned because newer builds are blocked by Smart App Control.

## How briefing.py is organised
1. Settings: `SYSTEM_PROMPT`, `AGENT_MODEL = "claude-haiku-5-5"`, `AGENT_EFFORT = "high"`, `MAX_FETCHES = 5`,
   `PRICES`, `FUNDS` (name, symbol, about), `SIGMA_THRESHOLD = 2`.
2. `analyze(symbol)`: 2 years of closes, drop NaN and today's unfinished row; changes 1d to YTD;
   z-score of the last daily return vs the previous 60 trading days; MA50/MA200 trend; P/E; distance from 52w high.
3. `make_charts`: SVG of the last year.
4. `build_agent_input`: today's date + the significant funds (full stats) + the other funds (1-day move, as context).
   The date goes in the user message, not in `SYSTEM_PROMPT`, so the system prompt stays identical every day.
5. `ask_agent` ("research mode"): only called when at least one fund is significant.
   - Tools: `web_search_20250305` (capped at `min(2 * n_significant + 1, 8)`) and `web_fetch_20250910`
     (`MAX_FETCHES` full articles, `max_content_tokens` per page). The prompt tells the agent to read the
     2-3 most relevant articles in full instead of relying on search snippets.
   - `output_config={"effort": AGENT_EFFORT}`, `max_tokens = 8000` (thinking counts toward it).
   - Handles `pause_turn` (up to 3 continuations) and `stop_reason == "refusal"` (returns None, page builds without AI text).
   - Prints searches, pages read, tokens and cost. Returns JSON `{market_summary, explanations: {SYMBOL: {text, sources}}}`.
6. `build_page`: the HTML page. It must still build when the agent fails.

## Cost
- Web fetch has no fee beyond tokens; web search costs $0.01 per search.
- A research-mode run costs roughly $0.04-0.10 (first run 2026-11-19: 3 searches, 3 pages, ~110K tokens in).
- Haiku 5.5 has two rate cards: $0.10/$0.50 per MTok up to a 100K-token prompt, $0.50/$2.50 above it,
  per API call. The printed cost assumes the low card, so a large run can be underestimated: check the Console.

## Principles
- Python does the arithmetic and detection; the LLM only explains.
- Cost guardrails: no agent call on quiet days, search cap, cheapest good-enough model, cost printed.
- AI text is `html.escape`d; only http(s) source links; duplicate domains removed.
- Red/green always means the last trading day's move.
- Spot-check the agent's claims against its sources; it sometimes states unsupported figures.

## Lessons learned
- Yahoo often leaves the last close of European ETFs as NaN until the next morning: drop NaNs, show a per-fund date.
- `.loc` for dates, `.iloc` for positions; `pd.DateOffset(days=1)`, not `day=1`.
- Fat tails: 3σ days happen several times a year, so 2σ means "worth explaining", not "rare".
- Agent JSON can be truncated at `max_tokens`: keep the warning and the fallback.
- Code after a `for ... break` loop must be dedented out of the loop.
- A counter used with `+=` needs a starting value (`fetches = 0`), or Python raises `UnboundLocalError`.
- Haiku 5.5 with search tools: give today's date, and tell it explicitly to use `web_fetch`, or it relies on snippets.

## Never
- Read, print or commit `.env`.
