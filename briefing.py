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
body { margin: 0; background: #F2F4F5; color: #1A1E27;
       font-family: "Segoe UI", system-ui, sans-serif; line-height: 1.5; }
main { max-width: 860px; margin: 0 auto; padding: 2.5rem 1.25rem 4rem; }
h1 { font-size: 2.2rem; margin: 0; }
.subtitle { color: #5D6472; margin: 0.25rem 0 2rem; }
.fund { border-top: 1px solid #D3D8DE; }
.fund-head { display: flex; justify-content: space-between; align-items: baseline;
             flex-wrap: wrap; gap: 0.5rem; padding: 1.25rem 0; cursor: pointer; list-style: none; }
.fund-head::-webkit-details-marker { display: none; }
.fund-head h2::before { content: ""; display: inline-block; width: 0.4em; height: 0.4em;
                        margin-right: 0.7em; vertical-align: 0.2em;
                        border-right: 2px solid #5D6472; border-bottom: 2px solid #5D6472;
                        transform: rotate(-45deg); transition: transform 0.15s; }
.fund[open] .fund-head h2::before { transform: rotate(45deg); }
.fund-head:hover h2 { color: #4B2BD6; }
.fund-head:focus-visible { outline: 2px solid #4B2BD6; outline-offset: 4px; }
.tag { font-size: 0.8rem; font-weight: 600; color: #5D6472; margin-left: 0.5rem; }
.fund-body { padding-bottom: 1.75rem; }
.price { margin: 0; font-size: 1.4rem; font-weight: 700; }
.up { color: #0F7B4F; }
.down { color: #C2362F; }
table { width: 100%; table-layout: fixed; border-collapse: collapse; margin: 1rem 0;
        font-variant-numeric: tabular-nums; }
th, td { padding: 0.4rem 0.5rem 0.4rem 0; text-align: left; border-bottom: 1px solid #E3E6EA; }
th { color: #5D6472; font-weight: 600; font-size: 0.85rem; }
.note { padding: 0.6rem 1rem; border-radius: 6px; margin: 1rem 0; }
.significant { background: #EDE8FF; border-left: 4px solid #4B2BD6; }
.stale { background: #FFF4E0; border-left: 4px solid #C77700; font-size: 0.9rem; }
img { width: 100%; height: auto; }
.footnote { color: #5D6472; font-size: 0.85rem; border-top: 1px solid #D3D8DE; padding-top: 1rem; }
@media (max-width: 500px) { th, td { font-size: 0.8rem; } }
.alert { display: inline-flex; align-items: center; justify-content: center;
         width: 1.25em; height: 1.25em; margin-left: 0.6rem; border-radius: 50%;
         background: #FFC93C; color: #1A1E27; font-size: 0.85rem; font-weight: 800;
         vertical-align: 0.15em; }
"""

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

    # matplotlib handles dates without a time zone best, so we strip it for the chart
    dates = close.index.tz_localize(None)
    fig,ax=plt.subplots(figsize=(8,3.2))
    ax.plot(dates, close, color="#4B2BD6", linewidth=2, label="Closing price")
    ax.plot(dates, ma50, color="#C77700", linewidth=1.5, label="50-day average")
    ax.plot(dates,ma200,color="#00897B",linewidth=1.5,label="200-day average")

    ax.set_title(result["name"], loc="left", fontsize=13, fontweight="bold", pad=28)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=3, frameon=False, fontsize=9)
    ax.grid(axis="y", color="#E3E6EA", linewidth=0.8)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(length=0, labelsize=9, colors="#5D6472")
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))

    CHART_DIR.mkdir(exist_ok=True)
    safe_name = result["symbol"].replace("^", "").replace(".", "_")
    path = CHART_DIR / f"{safe_name}.svg"
    fig.savefig(path, bbox_inches="tight")
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
        if response.stop_reason != "pause_turn":
            break
        messages = [messages[0], {"role": "assistant", "content": response.content}]
        if response.stop_reason == "max_tokens":
            print("Warning: the agent's answer was cut off because it reached max_tokens.")

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


def fund_section(r, newest_date):
    """Build the HTML for one fund."""
    pe_text = f"{r['pe']:.1f}" if r["pe"] is not None else "n/a"

    stale_note = ""
    if r["date"].date() < newest_date:
        stale_note = (f'<p class="note stale">This fund shows the close of {r["date"]:%d %b}. '
                      f'A newer close was not available yet.</p>')

    significant_note = ""
    if r["significant"]:
        significant_note = (f'<p class="note significant"><strong>Significant move '
                            f'({r["z"]:+.1f}σ).</strong> The explanation will be added in step 2.</p>')

    open_attr = " open" if r["significant"] else ""

    tag = ""
    if r["significant"]:
            tag = (f'<span class="alert" title="Significant move">!</span>'
               f'<span class="tag">{r["z"]:+.1f}σ</span>')
    elif r["date"].date() < newest_date:
        tag = f'<span class="tag">{r["date"]:%d %b}</span>'

    return f"""
<details class="fund"{open_attr}>
  <summary class="fund-head">
    <h2>{r['name']}{tag}</h2>
    <p class="price">{r['close']:,.2f} {pct(r['change_1d'])}</p>
  </summary>
  <div class="fund-body">
    {stale_note}
    {significant_note}
    <table>
      <tr><th>1 week</th><th>1 month</th><th>3 months</th><th>YTD</th><th>From 52-week high</th></tr>
      <tr><td>{pct(r['change_1w'])}</td><td>{pct(r['change_1m'])}</td><td>{pct(r['change_3m'])}</td>
          <td>{pct(r['change_ytd'])}</td><td>{pct(r['from_high'])}</td></tr>
    </table>
    <table>
      <tr><th>Trend</th><th>50-day average</th><th>200-day average</th><th>P/E</th></tr>
      <tr><td>{r['trend']}</td><td>{r['ma50']:,.2f}</td><td>{r['ma200']:,.2f}</td><td>{pe_text}</td></tr>
    </table>
    <img src="charts/{r['chart'].name}" alt="Price of {r['name']} over the last year, with 50- and 200-day averages">
  </div>
</details>"""

def build_page(results):
    """Put all funds on one HTML page and save it."""
    newest_date = max(r["date"].date() for r in results)
    sections = "\n".join(fund_section(r, newest_date) for r in results)
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
  {sections}
  <p class="footnote">
    A move is significant when it is at least {SIGMA_THRESHOLD} standard deviations (σ) away from the
    average daily move of the previous 60 trading days. YTD is the change since the last close of
    the previous year. Data: Yahoo Finance.
  </p>
</main>
</body>
</html>"""

    PAGE_FILE.write_text(html, encoding="utf-8")
    return PAGE_FILE

page = build_page(results)
print(f"Briefing saved: {page}")