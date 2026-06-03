# TradingView Screenshotter

## Setup (Windows)

```bash
pip install playwright
playwright install chromium
```

## Usage

### Step 1 — Save your session (run once)
```bash
python setup_session.py
```
A browser window will open. Log in to TradingView manually, then press ENTER in the terminal.
Your session is saved to `cookies.json`.

### Step 2 — Start the screenshot loop
```bash
python screenshotter.py
```
Screenshots save to `./screenshots/` as `xauusd_m1_YYYYMMDD_HHMMSS.png`.
Press `Ctrl+C` to stop.

## Config (in screenshotter.py)
| Variable | Default | Description |
|---|---|---|
| `INTERVAL_SEC` | `60` | seconds between screenshots |
| `headless` | `True` | set `False` to see the browser |
| `TV_CHART_URL` | XAUUSD M1 | change symbol/interval here |

## Troubleshooting
- **Blank screenshots**: set `headless=False` to inspect what the browser sees
- **Login required popup**: re-run `setup_session.py` to refresh cookies
- **Wrong chart area**: open browser DevTools on TradingView, inspect the chart div, update `CHART_SELECTOR` in screenshotter.py