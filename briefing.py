#This script is made with the use of AI and compares the close of the day with the day before.
#The script always uses the last finished trading day (so if it runs on the day of it will show
#with respect to the close the day before.)

import yfinance as yf
import pandas as pd
from pathlib import Path
import matplotlib
matplotlib.use("Agg")          # draw to files only, without opening windows
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import json
from html import escape        # makes AI text safe to put in HTML
from urllib.parse import urlparse
import anthropic
from dotenv import load_dotenv

# === Settings
load_dotenv()   # reads ANTHROPIC_API_KEY from .env

SYSTEM_PROMPT = """You are a financial news analyst writing a short morning briefing for a private investor.
You receive the latest numbers for a watchlist. Your job is to explain WHY the significant moves happened.

Rules:
- Only explain the funds listed under SIGNIFICANT MOVES. The other funds are context.
- Search efficiently: at most two searches per significant fund. If several funds moved in the
  same direction on the same day, first do one search for a market-wide cause.
- Search for news from the trading day of the close (the date is given per fund), not from today.
- Base every explanation on what you found. Write "likely" or "possibly" when a cause is not confirmed.
- If you cannot find a clear reason, say so. Never invent one.
- Never give buy or sell advice.
- Keep each explanation to 2-3 sentences of plain English.
- Only state figures that appear in your sources, and make sure they are for the right day.
- Briefly mention a major theme from the past week if it explains today's move.
- Confirm the main cause of each move with at least two independent sources
  (different websites). Copies of the same news agency report (e.g. Reuters) count as
  one source. If you can only find one source, say so in the explanation.
- If your sources disagree, mention both views.
- Do not describe your search process or your sources in the explanation text.
  Put the URLs in the "sources" list only.
- The figures in the input are correct closing data. Do not look up or contradict them;
  use your sources only to explain the cause. Ignore figures from intraday or opening reports.

When you are done, answer with ONLY a JSON object in exactly this format, with no text before or after it:
{"market_summary": "one or two sentences about the market as a whole",
 "explanations": {"SYMBOL": {"text": "your explanation", "sources": ["https://..."]}}}
 Use the symbol exactly as written in brackets in the input, including any ^ (e.g. "^AEX").
"""

AGENT_MODEL = "claude-haiku-5-5"

PRICES = {  # $ per million tokens: (input, output)
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
}
PRICE_SEARCH = 0.01

FUNDS = [
    {"name": "AEX", "symbol": "^AEX",
     "about": "Main Dutch index: 30 largest companies on Euronext Amsterdam. ASML is the biggest weight, "
              "so chip news often moves it. Also Shell, ING, Unilever."},
    {"name": "S&P 500", "symbol": "^GSPC",
     "about": "500 large US companies, dominated by big tech. Moves on US interest rates, "
              "inflation data and big tech earnings."},
    {"name": "VanEck Defense", "symbol": "DFEN.DE",
     "about": "Global defense and cybersecurity companies, e.g. Rheinmetall, Thales, Palantir. "
              "Moves on defense budgets, NATO spending, conflicts and peace talks."},
    {"name": "Vanguard FTSE Dev. Europe", "symbol": "VEUR.AS",
     "about": "Broad fund of large and mid-sized companies in developed Europe. Moves on European "
              "economic data, ECB interest rates and trade policy."},
    {"name": "NVIDIA", "symbol": "NVDA",
     "about": "US chip designer, market leader in AI data-center chips. Moves on AI demand, "
              "big tech investment plans, quarterly results and US export rules for China."},
    {"name": "Avantium N.V.", "symbol": "AVTX.AS",
     "about": "Dutch small cap making FDCA for the plant-based plastic PEF. Starting up its first "
              "commercial plant in Delfzijl. Moves on plant progress, financing and offtake/licensing deals."},
    {"name": "Sif Holding N.V.", "symbol": "SIFG.AS",
     "about": "Dutch maker of steel monopile foundations for offshore wind, factory in Rotterdam. "
              "Moves on offshore wind contracts, production output, financing and sector news."},
]

SIGMA_THRESHOLD = 2

CHART_DIR = Path(__file__).parent / "charts"
# C:\Users\lauva\Documents\Market_briefing\charts   
PAGE_FILE = Path(__file__).parent / "briefing.html"        


CSS = """
:root { --bg: #121826; --surface: #1B2333; --border: #2A3446; --text: #E6EAF2; --muted: #8B95A7;
        --up: #34C77B; --down: #F2555A; --accent: #8B7CFF; --alert: #FFC93C; }
html { scroll-behavior: smooth; }
@media (prefers-reduced-motion: reduce) { html { scroll-behavior: auto; } }
body { margin: 0; background: var(--bg); color: var(--text);
       font-family: "Segoe UI", system-ui, sans-serif; line-height: 1.5; }
main { max-width: 920px; margin: 0 auto; padding: 2.5rem 1.25rem 4rem; }
h1 { font-size: 2.8rem; font-weight: 800; letter-spacing: -0.02em; margin: 0; }
.subtitle { color: var(--muted); margin: 0.25rem 0 2rem; }
a { color: #A99CFF; }

/* direction colour: every fund and tile gets pos or neg from today's move */
.pos { --c: var(--up); }
.neg { --c: var(--down); }
.up { color: var(--up); }
.down { color: var(--down); }

/* summary and watchlist */
.summary { background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
           padding: 1rem 1.25rem; margin: 0 0 1.5rem; }
.summary h2, .why h3, .watch-head h2 { font-size: 1.3rem; font-weight: 700; }
.summary h2 { margin: 0 0 0.4rem; }
.summary p { margin: 0; }
.ai-label { color: var(--muted); font-size: 0.8rem; margin-top: 0.6rem !important; }
.watch-head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 0.6rem; }
.watch-head h2 { margin: 0; }
.watch-head span { color: var(--muted); font-size: 0.85rem; }
.tiles { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.75rem; margin-bottom: 2rem; }
.tile { display: block; text-decoration: none; color: var(--text); background: var(--surface);
        border: 1px solid var(--border); border-left: 4px solid var(--c); border-radius: 8px;
        padding: 0.65rem 0.8rem; transition: background 0.15s, border-color 0.15s, box-shadow 0.15s; }
.tile:hover { background: color-mix(in srgb, var(--c) 14%, var(--surface)); border-color: var(--c);
              box-shadow: 0 0 18px color-mix(in srgb, var(--c) 35%, transparent); }
.tile:focus-visible { outline: 2px solid var(--c); outline-offset: 2px; }
.tile-top { display: flex; justify-content: space-between; align-items: center; gap: 0.4rem; }
.tile-name { font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tile-price { color: var(--muted); font-size: 0.85rem; font-variant-numeric: tabular-nums; }
.tile-change { font-size: 1.15rem; font-weight: 700; font-variant-numeric: tabular-nums; }
@media (max-width: 760px) { .tiles { grid-template-columns: repeat(2, 1fr); } }

/* one fund */
.group-title { color: var(--muted); font-size: 0.85rem; font-weight: 600; margin: 2rem 0 0.5rem; }
.fund { border-top: 1px solid var(--border); scroll-margin-top: 1rem; }
.fund-head { display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap;
             gap: 0.5rem; padding: 1rem 0.5rem 1rem 0.9rem; cursor: pointer; list-style: none;
             border-left: 4px solid transparent; border-radius: 0 6px 6px 0;
             transition: background 0.15s, border-color 0.15s, box-shadow 0.15s; }
.fund-head::-webkit-details-marker { display: none; }
.fund-head h2 { font-size: 1.7rem; margin: 0; transition: color 0.15s; }
.fund-head h2::before { content: ""; display: inline-block; width: 0.4em; height: 0.4em;
                        margin-right: 0.7em; vertical-align: 0.2em;
                        border-right: 2px solid var(--muted); border-bottom: 2px solid var(--muted);
                        transform: rotate(-45deg); transition: transform 0.15s, border-color 0.15s; }
.fund[open] .fund-head h2::before { transform: rotate(45deg); }
.fund-head:hover { border-left-color: var(--c); background: color-mix(in srgb, var(--c) 9%, transparent);
                   box-shadow: 0 0 22px color-mix(in srgb, var(--c) 22%, transparent); }
.fund-head:hover h2 { color: var(--c); }
.fund-head:hover h2::before { border-color: var(--c); }
.fund-head:focus-visible { outline: 2px solid var(--c); outline-offset: 2px; }
.tag { font-size: 0.85rem; font-weight: 600; color: var(--muted); margin-left: 0.5rem; }
.tag.sigma { color: var(--c); }
.alert { display: inline-flex; align-items: center; justify-content: center;
         width: 1.25em; height: 1.25em; margin-left: 0.6rem; border-radius: 50%;
         background: var(--alert); color: #1A1E27; font-size: 0.85rem; font-weight: 800;
         vertical-align: 0.15em; }
.price { margin: 0; font-size: 1.4rem; font-weight: 700; font-variant-numeric: tabular-nums; }
.fund-body { padding: 0 0 1.5rem 0.9rem; }

.why { background: var(--surface); border-left: 4px solid var(--accent); border-radius: 6px;
       padding: 0.8rem 1rem; margin: 0 0 1rem; }
.why h3 { margin: 0 0 0.3rem; }
.why p { margin: 0; }
.sources { font-size: 0.85rem; color: var(--muted); margin-top: 0.5rem !important; }
.sources a { margin-right: 0.6rem; }
.stale { background: #3A2E14; border-left: 4px solid #C77700; color: #F2D9A6; font-size: 0.9rem;
         padding: 0.6rem 1rem; border-radius: 6px; margin: 0 0 1rem; }

.chart { background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
         padding: 0.5rem 0.75rem; margin: 0 0 0.5rem; }
img { display: block; width: 100%; height: auto; }

.group { color: var(--muted); font-size: 0.8rem; font-weight: 600; margin: 1.1rem 0 0.4rem; }
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(125px, 1fr)); gap: 0.6rem; }
.stat { background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
        padding: 0.55rem 0.75rem; }
.stat-label { color: var(--muted); font-size: 0.78rem; }
.stat-value { font-size: 1.2rem; font-weight: 700; font-variant-numeric: tabular-nums; }
.stat-sub { color: var(--muted); font-size: 0.78rem; font-variant-numeric: tabular-nums; }
.back { margin: 1.25rem 0 0; font-size: 0.85rem; }

.footnote { color: var(--muted); font-size: 0.85rem; border-top: 1px solid var(--border);
            padding-top: 1rem; margin-top: 2rem; }
"""

SCRIPT = """
document.querySelectorAll(".tile").forEach(function (tile) {
  tile.addEventListener("click", function () {
    var fund = document.querySelector(tile.getAttribute("href"));
    if (fund) fund.open = true;      // a closed fund opens when you jump to it
  });
});
"""

def slug(symbol):
    """Symbol made safe for file names and HTML ids, e.g. ^AEX -> AEX, DFEN.DE -> DFEN_DE."""
    return symbol.replace("^", "").replace(".", "_")


def change_since(close,offset):
    latest=close.iloc[-1]
    past= close.asof(close.index[-1]-offset)
    return (latest-past)/past*100

# === Analyze the provided FUNDS

def analyze(symbol):
    # Ask Yahoo Finance for the index corresponding to the symbol
    ticker = yf.Ticker(symbol)
    history = ticker.history(period="2y")
    if history.empty:
        print(f"No data for {symbol}, check the ticker.")
        return None
    
    # --- Valuation: P/E ratio (only exists for stocks, not for indices) ---
    try:
        pe = ticker.info.get("trailingPE")
    except Exception:
        pe = None

# Show the last 5 rows of the table
#print(history.tail())
#Take the close of the index for every day
    close=history["Close"]
    print(close.tail())
    print(f"{symbol}: {close.isna().sum()} empty values")
    print(close[close.isna()])

# Safety check: drop today's row if it exists, because that day isn't finished yet
        # Take the closing prices and remove empty values (Yahoo sometimes has gaps)
    close = history["Close"].dropna()

    # Safety check: keep only the days before today, because today isn't finished yet
    today = pd.Timestamp.now(tz=close.index.tz).normalize()
    close = close[close.index < today]
#select the last two days to calculate percentual difference.
    latest=close.iloc[-1]
    previous=close.iloc[-2]
    day_change=(latest-previous)/previous *100
    print(f"Latest close: {latest:.2f}")
    #print(f"Change since yesterday: {day_change:+.2f}%")

    latest_day=close.index[-1]
    start_of_year=latest_day.replace(month=1,day=1)

    print(f"1 day: {change_since(close,pd.DateOffset(days=1)):+.2f}")
    print(f"1 week: {change_since(close,pd.DateOffset(weeks=1)):+.2f}")
    print(f"1 month: {change_since(close,pd.DateOffset(months=1)):+.2f}")
    print(f"3 month: {change_since(close,pd.DateOffset(months=3)):+.2f}")
    print(f"6 months: {change_since(close,pd.DateOffset(months=6)):+.2f}")
    print(f"YTD: {change_since(close,latest_day-start_of_year):+.2f}")


    # === To determine if the change is larger enough to report 
    #calculate the change between rows in percentage
    daily_change=close.pct_change()*100

    #calculate the 
    window = daily_change.iloc[-61:-1]          # the 60 stock days before the latest day atleast 12 weeks
    mean_move = window.mean()
    normal_move = window.std()
    print(f"mean move: {mean_move:.3f}, normal move: {normal_move:.3f}")
    z = (daily_change.iloc[-1] - mean_move) / normal_move
    if abs(z)>=SIGMA_THRESHOLD:
        print(f"Significant move of "+symbol)
    else:
        print(f"normal day for "+symbol)  

     #rolling_mean = daily_change.rolling(60).mean().shift(1)
     #rolling_std = daily_change.rolling(60).std().shift(1)
     #z_all = (daily_change - rolling_mean) / rolling_std
    
     #    for t in [1.5, 2, 2.5, 3]:
     #        print(f"{symbol}: |z| >= {t}: {(z_all.abs() >= t).sum()} days")

        # --- Trend: moving averages ---
    ma50 = close.rolling(50).mean()
    ma200 = close.rolling(200).mean()

    price = close.iloc[-1]
    if price > ma50.iloc[-1] > ma200.iloc[-1]:
        trend = "Uptrend"
    elif price < ma50.iloc[-1] < ma200.iloc[-1]:
        trend = "Downtrend"
    else:
        trend = "Mixed"

    high_52w = close.loc[close.index[-1]-pd.DateOffset(years=1):].max()
    from_high = (price - high_52w) / high_52w * 100   # e.g. -12.3%

        
    return {
        "symbol": symbol,
        "date": latest_day,
        "close": close.iloc[-1],
        "change_1d": change_since(close, pd.DateOffset(days=1)),
        "change_1w": change_since(close, pd.DateOffset(weeks=1)),
        "change_1m": change_since(close, pd.DateOffset(months=1)),
        "change_3m": change_since(close, pd.DateOffset(months=3)),
        "change_ytd": change_since(close, latest_day - start_of_year),
        "z": z,
        "significant": abs(z) >= SIGMA_THRESHOLD,
        "trend": trend,
        "ma50": ma50.iloc[-1],
        "ma200": ma200.iloc[-1],
        "pe": pe,
        "close_series": close,
        "ma50_series": ma50,
        "ma200_series": ma200,
        "from_high": from_high,
    }

#=== Script used for plotting of all the things we want to see
def make_charts(result):
    start = result["close_series"].index[-1] - pd.DateOffset(years=1)
    close = result["close_series"].loc[start:]
    ma50 = result["ma50_series"].loc[start:]
    ma200 = result["ma200_series"].loc[start:]

    # colours that match the dark page
    text_color, grid_color, line_color = "#8B95A7", "#2A3446", "#8B7CFF"

    # matplotlib handles dates without a time zone best, so we strip it for the chart
    dates = close.index.tz_localize(None)

    # y-range: fit the price and both averages, with a little air below the lowest value
    values = pd.concat([close, ma50, ma200]).dropna()
    low, high = values.min(), values.max()
    bottom = low - 0.05 * (high - low)

    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.plot(dates, ma200, color="#4FC3D9", linewidth=1.2, linestyle="--", alpha=0.85, label="200-day average")
    ax.plot(dates, ma50, color="#F5B94A", linewidth=1.2, linestyle="--", alpha=0.85, label="50-day average")
    ax.plot(dates, close, color=line_color, linewidth=2, label="Closing price")
    ax.fill_between(dates, close, bottom, color=line_color, alpha=0.13)   # soft fill under the price
    ax.set_ylim(bottom, high + 0.05 * (high - low))

    # dot and label on the last close (no chart title: the name is in the header)
    last = close.iloc[-1]
    ax.plot(dates[-1], last, "o", color=line_color, markersize=6)
    ax.annotate(f"{last:,.2f}", (dates[-1], last), xytext=(-8, 10), textcoords="offset points",
                ha="right", color="#E6EAF2", fontsize=9, fontweight="bold")

    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=3, frameon=False, fontsize=9,
              labelcolor=text_color)
    ax.grid(axis="y", color=grid_color, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color(grid_color)
    ax.tick_params(length=0, labelsize=9, colors=text_color)
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))

    CHART_DIR.mkdir(exist_ok=True)
    path = CHART_DIR / f"{slug(result['symbol'])}.svg"
    fig.savefig(path, bbox_inches="tight", transparent=True)
    plt.close(fig)
    return path


results = []


for fund in FUNDS:
    result = analyze(fund["symbol"])
    if result is None:
        continue                     # skip this fund, go to the next one
    result["name"] = fund["name"]
    result["about"] = fund.get("about", "")
    result["chart"] = make_charts(result)
    results.append(result)

# Significant funds first. sort() is stable: within each group the FUNDS order is kept.
results.sort(key=lambda r: not r["significant"])

# Print a summary table
for r in results:
    flag = "<-- SIGNIFICANT" if r["significant"] else ""
    print(f"{r['name']:<27} {r['date']:%d %b}  {r['close']:>10.2f}  {r['change_1d']:+6.2f}%   z = {r['z']:+.1f}  {flag}")
    pe_text = f"{r['pe']:.1f}" if r["pe"] is not None else "n/a"
    print(f"{r['name']:<27} {r['trend']:<10} P/E: {pe_text}")


def describe_fund(r):
    """One fund as a few lines of plain text, for the agent to read."""
    pe_text = f"{r['pe']:.1f}" if r["pe"] is not None else "n/a"
    return (
        f"{r['name']} ({r['symbol']}): {r['about']}\n"
        f"  Close of {r['date']:%A %d %B %Y}: {r['close']:.2f}\n"
        f"  Change: 1 day {r['change_1d']:+.2f}%, 1 week {r['change_1w']:+.2f}%, "
        f"1 month {r['change_1m']:+.2f}%, 3 months {r['change_3m']:+.2f}%, YTD {r['change_ytd']:+.2f}%\n"
        f"  Daily move compared to normal: {r['z']:+.1f} sigma. Trend: {r['trend']}. "
        f"{r['from_high']:.1f}% from 52-week high. P/E: {pe_text}"
    )


def build_agent_input(results):
    """Everything the agent needs to know, as one piece of text."""
    significant = [r for r in results if r["significant"]]
    others = [r for r in results if not r["significant"]]
    text = "SIGNIFICANT MOVES (explain these):\n\n"
    text += "\n\n".join(describe_fund(r) for r in significant)
    text += "\n\nOTHER FUNDS (context only, to judge whether a move is market-wide):\n"
    text += "\n".join(f"- {r['name']}: {r['change_1d']:+.2f}% on {r['date']:%d %b}" for r in others)
    return text


def ask_agent(agent_input, max_searches):
    """Send the numbers to the agent, let it search the web, and return its explanations."""
    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": agent_input}]
    tokens_in = tokens_out = searches = 0

    for _ in range(3):  # the agent may pause during a long search session; then we let it continue
        response = client.messages.create(
            model=AGENT_MODEL,
            max_tokens=4000,
            system=SYSTEM_PROMPT,
            messages=messages,
          tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": max_searches}],)
        tokens_in += response.usage.input_tokens
        tokens_out += response.usage.output_tokens
        if response.usage.server_tool_use:
            searches += response.usage.server_tool_use.web_search_requests
        if response.stop_reason == "max_tokens":
            print("Warning: the agent's answer was cut off because it reached max_tokens.")
        if response.stop_reason != "pause_turn":
            break
        messages = [messages[0], {"role": "assistant", "content": response.content}]

    price_in, price_out = PRICES[AGENT_MODEL]
    cost = tokens_in * price_in / 1e6 + tokens_out * price_out / 1e6 + searches * PRICE_SEARCH
    print(f"Agent: {searches} searches, {tokens_in} tokens in, {tokens_out} out, cost ${cost:.4f}")

    # The answer can be split over several text blocks: glue them together
    text = "".join(block.text for block in response.content if block.type == "text")
    try:
        return json.loads(text[text.find("{"): text.rfind("}") + 1])
    except json.JSONDecodeError:
        print("Could not read the agent's answer as JSON. Raw answer:")
        print(text)
        return None

significant = [r for r in results if r["significant"]]
max_searches = min(2 * len(significant) + 1, 8)
agent_answer = None
if significant:
    agent_answer = ask_agent(build_agent_input(results), max_searches)
    print(json.dumps(agent_answer, indent=2))
else:
    print("No significant moves: the agent is not called.")

def pct(value):
    """Format a percentage with a + or - sign, coloured green or red."""
    css_class = "up" if value >= 0 else "down"
    return f'<span class="{css_class}">{value:+.2f}%</span>'


def sources_html(urls):
    """Turn a list of URLs into short links. Only http(s) links are allowed."""
    if not isinstance(urls, list):
        return ""
    links = []
    seen = set()
    for url in urls:
        if not isinstance(url, str):
            continue
        parts = urlparse(url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            continue                                  # skip anything that is not a normal web link
        name = parts.netloc.removeprefix("www.")
        if name in seen:
            continue                                  # show each website only once
        seen.add(name)
        links.append(f'<a href="{escape(url, quote=True)}" target="_blank" '
                     f'rel="noopener noreferrer">{escape(name)}</a>')
    if not links:
        return ""
    return f'<p class="sources">Sources: {" ".join(links)}</p>'


def summary_html(agent_answer, significant):
    """The 'Today in brief' block at the top of the page."""
    if not significant:
        text = "No significant moves today. All funds moved within their normal range."
        label = ""
    else:
        summary = agent_answer.get("market_summary") if isinstance(agent_answer, dict) else None
        if isinstance(summary, str) and summary.strip():
            text = escape(summary)
            label = '<p class="ai-label">Written by an AI agent from news sources. Check the links below.</p>'
        else:
            text = "The AI explanation is not available today. The numbers and charts below are not affected."
            label = ""
    return f'<section class="summary"><h2>Today in brief</h2><p>{text}</p>{label}</section>'


def why_html(r, agent_answer):
    """The 'Why it moved' block of one significant fund."""
    explanations = agent_answer.get("explanations") if isinstance(agent_answer, dict) else None
    entry = None
    if isinstance(explanations, dict):
        # The agent sometimes drops the ^ or uses the name, so try all three
        for key in (r["symbol"], r["symbol"].lstrip("^"), r["name"]):
            if key in explanations:
                entry = explanations[key]
                break
    text = entry.get("text") if isinstance(entry, dict) else None
    if isinstance(text, str) and text.strip():
        body = f'<p>{escape(text)}</p>{sources_html(entry.get("sources"))}'
    elif agent_answer is None:
        body = "<p>The explanation is not available today.</p>"
    else:
        body = "<p>No explanation found.</p>"
    return f'<div class="why"><h3>Why it moved</h3>{body}</div>'


def stat(label, value, sub=""):
    """One small card with a label, a big value and an optional line below."""
    sub_html = f'<div class="stat-sub">{sub}</div>' if sub else ""
    return (f'<div class="stat"><div class="stat-label">{label}</div>'
            f'<div class="stat-value">{value}</div>{sub_html}</div>')


def vs_average(price, average):
    """'price +2.1%' relative to a moving average, or '' if the average does not exist."""
    if pd.isna(average):
        return ""
    return f"price {pct((price / average - 1) * 100)}"


def direction(r):
    """'pos' or 'neg': the colour of a fund follows its move on the last day."""
    return "pos" if r["change_1d"] >= 0 else "neg"


def fund_section(r, newest_date, agent_answer):
    """Build the HTML for one fund."""
    pe_text = f"{r['pe']:.1f}" if r["pe"] is not None else "n/a"

    stale_note = ""
    if r["date"].date() < newest_date:
        stale_note = (f'<p class="stale">This fund shows the close of {r["date"]:%d %b}. '
                      f'A newer close was not available yet.</p>')

    why = why_html(r, agent_answer) if r["significant"] else ""
    open_attr = " open" if r["significant"] else ""

    tag = ""
    if r["significant"]:
        tag = (f'<span class="alert" title="Significant move">!</span>'
               f'<span class="tag sigma">{r["z"]:+.1f}σ</span>')
    elif r["date"].date() < newest_date:
        tag = f'<span class="tag">{r["date"]:%d %b}</span>'

    performance = "".join([
        stat("1 week", pct(r["change_1w"])),
        stat("1 month", pct(r["change_1m"])),
        stat("3 months", pct(r["change_3m"])),
        stat("YTD", pct(r["change_ytd"])),
        stat("From 52-week high", pct(r["from_high"])),
    ])
    trend = "".join([
        stat("Trend", r["trend"]),
        stat("50-day average", f"{r['ma50']:,.2f}", vs_average(r["close"], r["ma50"])),
        stat("200-day average", f"{r['ma200']:,.2f}", vs_average(r["close"], r["ma200"])),
        stat("P/E", pe_text),
    ])

    return f"""
<details class="fund {direction(r)}" id="fund-{slug(r['symbol'])}"{open_attr}>
  <summary class="fund-head">
    <h2>{r['name']}{tag}</h2>
    <p class="price">{r['close']:,.2f} {pct(r['change_1d'])}</p>
  </summary>
  <div class="fund-body">
    {stale_note}
    {why}
    <div class="chart"><img src="charts/{r['chart'].name}" alt="Price of {r['name']} over the last year, with 50- and 200-day averages"></div>
    <p class="group">Performance</p>
    <div class="stats">{performance}</div>
    <p class="group">Trend and valuation</p>
    <div class="stats">{trend}</div>
    <p class="back"><a href="#watchlist">Back to watchlist</a></p>
  </div>
</details>"""


def overview_html(results):
    """The watchlist: one tile per fund, A to Z. Each tile links to its fund below."""
    tiles = []
    for r in sorted(results, key=lambda r: r["name"].lower()):
        mark = '<span class="alert" title="Significant move">!</span>' if r["significant"] else ""
        tiles.append(
            f'<a class="tile {direction(r)}" href="#fund-{slug(r["symbol"])}">'
            f'<div class="tile-top"><span class="tile-name">{r["name"]}</span>{mark}</div>'
            f'<div class="tile-price">{r["close"]:,.2f}</div>'
            f'<div class="tile-change">{pct(r["change_1d"])}</div></a>')
    n_significant = sum(1 for r in results if r["significant"])
    return (f'<section id="watchlist"><div class="watch-head"><h2>Watchlist</h2>'
            f'<span>{len(results)} funds · {n_significant} significant</span></div>'
            f'<div class="tiles">{"".join(tiles)}</div></section>')


def build_page(results, agent_answer):
    """Put all funds on one HTML page and save it."""
    newest_date = max(r["date"].date() for r in results)
    significant = [r for r in results if r["significant"]]
    others = [r for r in results if not r["significant"]]

    sections = "\n".join(fund_section(r, newest_date, agent_answer) for r in significant)
    if others:
        if significant:
            sections += '\n<p class="group-title">Other funds</p>'
        sections += "\n".join(fund_section(r, newest_date, agent_answer) for r in others)
    created = pd.Timestamp.now(tz="Europe/Amsterdam")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Market briefing {newest_date:%d %b %Y}</title>
  <style>{CSS}</style>
</head>
<body>
<main>
  <h1>Market briefing</h1>
  <p class="subtitle">Closing prices up to {newest_date:%A %d %B %Y}. Generated on {created:%d %B %Y at %H:%M}.</p>
  {summary_html(agent_answer, significant)}
  {overview_html(results)}
  {sections}
  <p class="footnote">
    A move is significant when it is at least {SIGMA_THRESHOLD} standard deviations (σ) away from the
    average daily move of the previous 60 trading days. YTD is the change since the last close of
    the previous year. Colours show the move on the last trading day: green is up, red is down.
    Data: Yahoo Finance. The explanations are written by an AI agent ({AGENT_MODEL}) that searches
    the web; they can contain mistakes, so check the sources. This page explains what happened
    and is not investment advice.
  </p>
</main>
<script>{SCRIPT}</script>
</body>
</html>"""

    PAGE_FILE.write_text(html, encoding="utf-8")
    return PAGE_FILE

page = build_page(results, agent_answer)
print(f"Briefing saved: {page}")
