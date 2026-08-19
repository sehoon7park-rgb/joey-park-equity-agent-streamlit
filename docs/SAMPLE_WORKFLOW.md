# Sample Workflow

A realistic single-session walk-through, assuming `.env` is filled in
(`ANTHROPIC_API_KEY`, `SEC_EDGAR_CONTACT_EMAIL`; `FRED_API_KEY` optional).

```bash
# 1. First look at a name you're curious about, and keep it on your list.
python -m joey_park.cli analyze MSFT --watchlist

# 2. Same for a couple of comparables.
python -m joey_park.cli analyze GOOGL --watchlist
python -m joey_park.cli analyze ORCL --watchlist

# 3. See everything you're tracking and how it currently scores.
python -m joey_park.cli watchlist

# 4. Open the dashboard for a side-by-side view and to drill into one name.
streamlit run ui/app.py
#   -> Compare tab: paste "MSFT, GOOGL, ORCL", Run/Refresh All
#   -> Stock Research tab: MSFT, read Bull/Base/Bear, Critic findings,
#      "What Would Change My Mind"

# 5. A few weeks later, re-run the same ticker.
python -m joey_park.cli analyze MSFT
#   -> report now includes "Thesis change vs. prior run: <classification>"
#      e.g. "STRENGTHENED — Score improved 0.61 -> 0.79 (view: Neutral -> Bullish)."
#   -> if classified BROKEN, a CRITICAL alert is written to the `alerts` table
#      and shows up on the dashboard's Alerts tab.
```

What actually happens under the hood on each `analyze` call, in order,
is documented in [`docs/DECISION_LOG.md`](DECISION_LOG.md) and diagrammed in
the README — Data -> Validation -> deterministic analysis agents ->
Research/Critic/Decision (LLM) -> thesis comparison -> persistence -> report.

See [`docs/SAMPLE_REPORT.md`](SAMPLE_REPORT.md) for a real (non-fabricated)
output from step 1, run against live data with the LLM intentionally
disabled to show the failure-mode behavior.
