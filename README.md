This is a project to familiarise myself more with coding with AI.
This specfici project Market_briefing will consist of two parts.
1. the briefing.py, where a list of Indexs,Stocks and funds are listed with their tracker.
the script then extracts the last 2 years of data and plots the data up to the last finished market day.
If the change in the value of the stock is drastically biger than normal this stock gets flagged.

That is where part two comes in: After the briefing.py script has extracted and processed the data an Agentic AI will look at the results and explain the reason for the unusual large change for the flagged stock. (In progress)

## Automation
The briefing updates itself with GitHub Actions; no computer of mine needs to be on.
- Every Tuesday to Saturday at 11:05 UTC a workflow runs `briefing.py`, so each run covers the previous trading day.
  It commits the new page to `docs/`, and GitHub Pages publishes it:
  https://lauvanosch-ctrl.github.io/Market_briefing/briefing.html
- On every push, a second workflow runs the test suite (`pytest`, offline, no API calls).
- The Claude API key is stored as a GitHub secret, never in the code. If a run fails, nothing is published
  and the previous briefing stays online.