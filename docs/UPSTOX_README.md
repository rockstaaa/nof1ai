# 🇮🇳 Upstox / NSE Integration (Experimental)

This repository includes experimental Upstox support for Indian equities and F&O. The adapter is intentionally conservative and defaults to paper trading.

Quick start for NSE support

1. Copy environment template and fill Upstox creds:

```bash
cp env.example .env
# Edit .env and set UPSTOX_API_KEY, UPSTOX_API_SECRET, UPSTOX_ACCESS_TOKEN
```

2. Configure exchange and capital:

- In `agents/agent_configs.py` set `'EXCHANGE': 'upstox'` (the default in this branch).
- Set `'STARTING_CAPITAL_INR'` to your desired paper capital (e.g., `100000`).

3. Run in paper mode (default):

```bash
python run.py
```

Supported instruments and features

- NIFTY, BANKNIFTY (F&O underlyings)
- Top liquid F&O stocks can be added to `CONFIG['SYMBOLS']`
- Lot sizes configurable via `CONFIG['FO_LOT_SIZES']`
- Market hours enforcement (09:15–15:30 IST) and simple holiday list

Notes & next steps

- The current Upstox adapter provides synthetic OHLCV and paper execution when credentials are not available. Live-order execution needs Upstox REST implementation and careful margin handling before going live.
- I can implement live REST calls, add a holiday calendar fetch, and add unit tests for lot-size and expiry handling upon request.
