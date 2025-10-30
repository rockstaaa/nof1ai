# Quickstart: NSE / Upstox (Paper mode)

1. Create virtualenv and install requirements (same as primary quickstart):

```bash
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Configure `.env` (see `env.example`)

3. Run the agent (paper mode):

```bash
python run.py
```

Notes:
- Default exchange is `upstox` in `agents/agent_configs.py`.
- Paper trading is enabled by default (`UPSTOX_PAPER_MODE=1` in `.env`).
- To go live, implement live REST calls in `exchange/upstox_marketdata.py` and set `UPSTOX_PAPER_MODE=0`.
