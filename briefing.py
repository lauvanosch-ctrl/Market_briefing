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
# === Settings

FUNDS = [
    {"name": "AEX", "symbol": "^AEX"},
    {"name": "S&P 500", "symbol": "^GSPC"},
    {"name": "VanEck Defense", "symbol": "DFEN.DE"},
    {"name": "Vanguard FTSE Dev. Europe", "symbol": "VEUR.AS"},
    {"name": "NVIDIA", "symbol": "NVDA"},
    {"name": "Avantium N.V.", "symbol": "AVTX.AS"},
    {"name": "Sif Holding N.V.","symbol": "SIFG.AS"},
]

SIGMA_THRESHOLD = 2

CHART_DIR = Path(__file__).parent / "charts"
# C:\Users\lauva\Documents\Market_briefing\charts   
PAGE_FILE = Path(__file__).parent / "briefing.html"        

# === Calculation of the change

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
    result["chart"] = make_charts(result)
    results.append(result)

# Print a summary table
for r in results:
    flag = "<-- SIGNIFICANT" if r["significant"] else ""
    print(f"{r['name']:<27} {r['date']:%d %b}  {r['close']:>10.2f}  {r['change_1d']:+6.2f}%   z = {r['z']:+.1f}  {flag}")
    pe_text = f"{r['pe']:.1f}" if r["pe"] is not None else "n/a"
    print(f"{r['name']:<27} {r['trend']:<10} P/E: {pe_text}")


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