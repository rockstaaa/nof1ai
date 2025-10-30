"""
Upstox adapter (minimal, safe wrapper)

This module provides a lightweight Upstox client abstraction used by agents.
It supports a paper trading fallback if credentials are not provided or if
environment variable UPSTOX_PAPER_MODE is set to '1' / 'true'.

The implementation intentionally keeps network calls optional and resilient
so the repository can be tested without live API keys.
"""

from __future__ import annotations

import os
import time
import math
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import pandas as pd

# Environment keys
_API_KEY = os.getenv('UPSTOX_API_KEY')
_API_SECRET = os.getenv('UPSTOX_API_SECRET')
_ACCESS_TOKEN = os.getenv('UPSTOX_ACCESS_TOKEN')
_PAPER_MODE = os.getenv('UPSTOX_PAPER_MODE', '1').lower() in ('1', 'true', 'yes')


# Default F&O lot sizes (will be used when API doesn't return values)
DEFAULT_LOT_SIZES = {
    'NIFTY': 50,
    'BANKNIFTY': 15
}


class UpstoxMarketData:
    """Minimal Upstox wrapper with paper mode fallback.

    Public methods exposed (module-level wrappers provided below):
    - get_data(symbol, timeframe, bars)
    - get_current_price(symbol)
    - market_buy(symbol, quantity, price=None)
    - market_sell(symbol, quantity, price=None)
    - get_all_positions()
    - get_account_balance()
    - get_lot_size(symbol)
    """

    def __init__(self):
        self.api_key = _API_KEY
        self.api_secret = _API_SECRET
        self.access_token = _ACCESS_TOKEN
        self.paper_mode = _PAPER_MODE or (self.access_token is None)
        self.base_url = 'https://api.upstox.com'  # kept for reference

        # Paper state
        self.paper_capital_inr = float(os.getenv('STARTING_CAPITAL_INR', 100000.0))
        self.paper_positions: Dict[str, Dict] = {}

    # ------------------ Market data ------------------
    def get_data(self, symbol: str, timeframe: str = '3m', bars: int = 100) -> pd.DataFrame:
        """Return OHLCV DataFrame indexed by timestamp (oldest→newest).

        In paper mode or without credentials, this returns a synthetic timeseries.
        """
        try:
            # If we had a real client, we'd call the Upstox OHLC endpoint here.
            # For now, produce a synthetic series that resembles intraday bars.
            now = datetime.utcnow()
            minutes = 3 if timeframe.endswith('m') else 60
            # simple resolution: parse '3m' -> 3
            try:
                if timeframe.endswith('m'):
                    minutes = int(timeframe[:-1])
                elif timeframe.endswith('h'):
                    minutes = int(timeframe[:-1]) * 60
            except Exception:
                minutes = 3

            timestamps = [now - timedelta(minutes=minutes * (bars - i)) for i in range(bars)]
            base = 1000.0 + (hash(symbol) % 500)
            close = [base + math.sin(i / 5.0) * 5 + (i * 0.01) for i in range(bars)]
            openp = [close[i] - (0.1 + (i % 3) * 0.05) for i in range(bars)]
            high = [max(openp[i], close[i]) + 0.5 for i in range(bars)]
            low = [min(openp[i], close[i]) - 0.5 for i in range(bars)]
            volume = [1000 + (i % 50) * 10 for i in range(bars)]

            df = pd.DataFrame({
                'timestamp': timestamps,
                'open': openp,
                'high': high,
                'low': low,
                'close': close,
                'volume': volume
            })
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            return df
        except Exception:
            return pd.DataFrame()

    def get_current_price(self, symbol: str) -> float:
        """Return last traded price (ltp) for the symbol."""
        # If we can call a real API, do so. Otherwise, use last value from synthetic data.
        try:
            df = self.get_data(symbol, timeframe='1m', bars=5)
            if not df.empty:
                return float(df['close'].iloc[-1])
        except Exception:
            pass
        # Fallback
        return 1000.0 + (hash(symbol) % 500)

    # ------------------ Orders ------------------
    def market_buy(self, symbol: str, quantity: int, price: Optional[float] = None) -> Dict:
        """Place a buy order. In paper mode this simulates execution."""
        if self.paper_mode:
            return self._place_paper_trade(symbol, 'BUY', quantity, price)
        # TODO: Implement live order via Upstox REST API when credentials available
        return {'error': 'live-upstox-not-implemented', 'status': 'failed'}

    def market_sell(self, symbol: str, quantity: int, price: Optional[float] = None) -> Dict:
        """Place a sell order. In paper mode this simulates execution."""
        if self.paper_mode:
            return self._place_paper_trade(symbol, 'SELL', quantity, price)
        return {'error': 'live-upstox-not-implemented', 'status': 'failed'}

    def _place_paper_trade(self, symbol: str, side: str, quantity: int, price: Optional[float] = None) -> Dict:
        """Simulate trade execution and update paper positions & capital."""
        ltp = price or self.get_current_price(symbol)
        notional = float(quantity) * float(ltp)
        trade_id = f'PAPER_{int(time.time())}'

        # Update paper positions (very simple mark-to-market aggregation)
        pos = self.paper_positions.get(symbol, {'quantity': 0, 'avg_price': 0.0})
        if side == 'BUY':
            total_qty = pos['quantity'] + quantity
            if total_qty == 0:
                avg = 0
            else:
                avg = (pos['avg_price'] * pos['quantity'] + ltp * quantity) / max(1, total_qty)
            pos['quantity'] = total_qty
            pos['avg_price'] = avg
        else:
            # SELL reduces position
            pos['quantity'] = pos.get('quantity', 0) - quantity
            # avg_price remains for simplicity

        self.paper_positions[symbol] = pos

        # Update capital (very basic)
        if side == 'BUY':
            self.paper_capital_inr -= notional
        else:
            self.paper_capital_inr += notional

        return {'status': 'success', 'trade_id': trade_id, 'symbol': symbol, 'side': side, 'quantity': quantity, 'price': ltp}

    # ------------------ Account & Positions ------------------
    def get_all_positions(self) -> Dict[str, Dict]:
        """Return paper/live positions in a common format."""
        if self.paper_mode:
            out = {}
            for sym, p in self.paper_positions.items():
                out[sym] = {
                    'symbol': sym,
                    'quantity': p.get('quantity', 0),
                    'avg_price': p.get('avg_price', 0.0),
                    'current_price': self.get_current_price(sym),
                    'unrealized_pnl': (self.get_current_price(sym) - p.get('avg_price', 0.0)) * p.get('quantity', 0)
                }
            return out
        # Live mode placeholder
        return {}

    def get_account_balance(self) -> Dict:
        """Return account balances in INR."""
        if self.paper_mode:
            return {
                'account_value_inr': round(self.paper_capital_inr + sum((self.get_current_price(s) * p.get('quantity', 0)) for s, p in self.paper_positions.items()), 2),
                'available_cash_inr': round(self.paper_capital_inr, 2)
            }
        # Live mode placeholder
        return {'account_value_inr': 0.0, 'available_cash_inr': 0.0}

    def get_lot_size(self, symbol: str) -> int:
        """Return lot size for F&O underlyings. Defaults to DEFAULT_LOT_SIZES."""
        key = symbol.upper()
        return DEFAULT_LOT_SIZES.get(key, 1)


# ------------------ Module-level singleton + convenience wrappers ------------------
_client: Optional[UpstoxMarketData] = None


def get_upstox_client() -> UpstoxMarketData:
    global _client
    if _client is None:
        _client = UpstoxMarketData()
    return _client


def get_data(symbol: str, timeframe: str = '3m', bars: int = 100) -> pd.DataFrame:
    return get_upstox_client().get_data(symbol, timeframe=timeframe, bars=bars)


def get_current_price(symbol: str) -> float:
    return get_upstox_client().get_current_price(symbol)


def market_buy(symbol: str, quantity: int, price: Optional[float] = None) -> Dict:
    return get_upstox_client().market_buy(symbol, quantity, price=price)


def market_sell(symbol: str, quantity: int, price: Optional[float] = None) -> Dict:
    return get_upstox_client().market_sell(symbol, quantity, price=price)


def get_all_positions() -> Dict:
    return get_upstox_client().get_all_positions()


def get_account_balance() -> Dict:
    return get_upstox_client().get_account_balance()


def get_lot_size(symbol: str) -> int:
    return get_upstox_client().get_lot_size(symbol)

