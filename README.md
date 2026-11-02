# BTC Swing HUD

Mobile-first, dark trader-style BTC dashboard on GitHub Pages: https://aikeluargalee-tech.github.io/btc-swing-hud/

- **Live in browser:** BTC price every 5 s (Binance `data-api.binance.vision`, Coinbase fallback) and 1H candles every 60 s; triggers recompute live.
- **Snapshot every 15 min:** `.github/workflows/refresh.yml` runs `scripts/refresh.py` and commits `data/hud.json` when it changes (funding, OI, liquidations, L/S, CVD estimates, macro, Fear & Greed, Coinbase premium, Coinalyze aggregates).
- **Edit levels, triggers, events, verdict and bot verdicts in `config/levels.json`** — no build step.

Setup: repo secret `COINALYZE_API_KEY` (optional). Run locally: `COINALYZE_API_KEY=... python3 scripts/refresh.py`, then `python3 -m http.server`.

Notes: GitHub cron can lag by several minutes. Spot data falls back api.binance.com → data-api.binance.vision → api.binance.us → OKX. ETF flows and FRED real yields are not fetched. Not financial advice.
