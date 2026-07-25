# NIFTY Positioning Dashboard (free stack)

Replicates the option-chain / participant-positioning style dashboard using
100% free data and hosting.

## What it uses
- **Data**: NSE India public option-chain API (live) + Participant-wise Open
  Interest CSV reports (EOD, free, ~1 day lag by design of the source)
- **Storage**: SQLite (`data/nifty.db`), grows a new snapshot each run
- **Automation**: GitHub Actions free cron, runs the fetch daily after market close
- **Dashboard**: Streamlit + Plotly, hosted free on Streamlit Community Cloud

## Local setup
```bash
pip install -r requirements.txt
python fetch_nse.py        # pulls today's snapshot into data/nifty.db
streamlit run dashboard.py # opens dashboard at localhost:8501
```

## Put it on GitHub
```bash
cd nifty-dashboard
git init
git add .
git commit -m "Initial dashboard"
gh repo create nifty-dashboard --public --source=. --push
# or manually create a repo on github.com and push
```

## Automate the daily fetch (free)
Already set up in `.github/workflows/fetch.yml` — once pushed to GitHub, it
runs on its own schedule and commits the updated database back to the repo.
No server needed for this part.

## Deploy the dashboard (free, no sleep issues)
1. Go to https://share.streamlit.io
2. Sign in with GitHub, pick this repo, set main file to `dashboard.py`
3. Deploy — you get a public URL instantly, and it auto-redeploys on every push

**Why Streamlit Cloud instead of Render for this piece:** Render's free web
services spin down after 15 minutes idle (30-60s cold start on next visit).
Streamlit Community Cloud doesn't have that limitation for this kind of app.
If you'd rather run everything on Render instead (e.g. to also expose an API),
that works too — add a `render.yaml` and set the start command to
`streamlit run dashboard.py --server.port $PORT --server.address 0.0.0.0`.

## Extending toward the exact panels in your screenshots
- **Conviction (traded vs retained)**: compare `call_oi`/`put_oi` day-over-day
  per participant from the participant_oi table
- **Build-up classification** (long build-up / short covering / etc.): compare
  sign of price change vs sign of OI change, bucket into the 4 standard cases
- **PCR trend, volatility, futures basis**: pull NSE's futures & index bhavcopy
  (also free, `nsearchives.nseindia.com/content/historical/...`) and join by date

Everything here is for personal/educational analysis — not investment advice.
NSE's terms restrict heavy automated scraping; keep fetch frequency to a few
times a day max to stay within reasonable/fair use.
