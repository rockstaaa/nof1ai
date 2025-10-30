"""Upstox REST client (conservative, paper-mode-first)

This module implements a lightweight Upstox REST client wrapper suitable for
development and testing. It prioritizes PAPER_MODE safety: when PAPER_MODE is
enabled (default), no live HTTP requests will be made and orders are simulated
locally.

Features:
- Secure .env loading of credentials (via python-dotenv)
- OAuth2-style authentication flow (placeholder for live mode)
- place_order / get_order_status / cancel_order
- get_positions / close_position
- market_buy / market_sell wrappers
- Lot size normalization and helpers for NSE F&O
- Simple margin calculation and expiry validation helpers

NOTE: Live endpoints are left intentionally generic. Fill `base_url` and the
exact endpoint paths per Upstox's API if you switch PAPER_MODE off.

Extensive inline docs are provided to make future integration straightforward.
"""

from __future__ import annotations

import os
import uuid
import time
import json
from datetime import datetime, timezone
from typing import Dict, Optional, List, Any

import requests
from dotenv import load_dotenv

# Load .env automatically when the module is imported (safe; values may be None)
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', '.env')
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path)
else:
    # Also allow .env in workspace root
    load_dotenv()

# Default configuration keys
DEFAULT_BASE_URL = os.getenv('UPSTOX_BASE_URL', 'https://api.upstox.com')
DEFAULT_PAPER_MODE = os.getenv('UPSTOX_PAPER_MODE', os.getenv('PAPER_TRADING', '1'))


class UpstoxRestClient:
    """Conservative Upstox REST client.

    Safety-first behavior:
    - If paper_mode is True, the client will NOT perform any external HTTP
      requests for order placement. Instead it simulates orders locally.
    - If paper_mode is False (live), the client will attempt OAuth2 token
      retrieval and call the configured REST endpoints. Live mode must be used
      carefully.

    Usage:
        client = UpstoxRestClient()
        order = client.market_buy('RELIANCE', quantity=10)

    Important: This implementation aims to be a complete development scaffold
    and must be adjusted to match the actual Upstox REST API endpoints and
    authentication flow before enabling live trading.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        access_token: Optional[str] = None,
        paper_mode: Optional[bool] = None,
        base_url: Optional[str] = None,
        default_lot_sizes: Optional[Dict[str, int]] = None,
    ) -> None:
        # Load from env if not provided
        self.api_key = api_key or os.getenv('UPSTOX_API_KEY')
        self.api_secret = api_secret or os.getenv('UPSTOX_API_SECRET')
        self.access_token = access_token or os.getenv('UPSTOX_ACCESS_TOKEN')

        # Determine paper mode (env overrides)
        if paper_mode is None:
            pm = os.getenv('UPSTOX_PAPER_MODE', DEFAULT_PAPER_MODE)
            try:
                self.paper_mode = bool(int(str(pm)))
            except Exception:
                self.paper_mode = str(pm).lower() in ('1', 'true', 'yes')
        else:
            self.paper_mode = bool(paper_mode)

        self.base_url = base_url or DEFAULT_BASE_URL

        # Internal paper-mode stores (orders & positions) - used only when paper_mode=True
        self._paper_orders: Dict[str, Dict[str, Any]] = {}
        self._paper_positions: Dict[str, Dict[str, Any]] = {}

        # Default lot sizes (fallback). For accurate lot sizes, call exchange metadata
        self.default_lot_sizes = default_lot_sizes or {
            'NIFTY': 50,
            'BANKNIFTY': 15,
        }

        # Authentication state
        self._auth_token: Optional[str] = None
        self._auth_expires_at: Optional[float] = None

        # Initialize: perform auth if in live mode
        if not self.paper_mode:
            self._authenticate_live()
        else:
            # Paper-mode: set a fake token for internal tracing
            self._auth_token = self.access_token or f"paper-{uuid.uuid4()}"
            self._auth_expires_at = time.time() + 3600

    # -----------------------------
    # Authentication / HTTP helpers
    # -----------------------------
    def _authenticate_live(self) -> None:
        """Perform OAuth2 / token retrieval for live mode.

        This function is a placeholder that demonstrates how to perform a
        client-credentials or token exchange. Replace endpoints/field names
        with Upstox-specific values before switching to live mode.
        """
        if self.paper_mode:
            return

        if not (self.api_key and self.api_secret):
            raise RuntimeError("Missing UPSTOX_API_KEY / UPSTOX_API_SECRET for live mode")

        # Example: hypothetical token endpoint
        token_url = f"{self.base_url}/oauth2/token"
        payload = {
            'grant_type': 'client_credentials',
            'client_id': self.api_key,
            'client_secret': self.api_secret,
        }

        resp = requests.post(token_url, data=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        self._auth_token = data.get('access_token')
        expires_in = int(data.get('expires_in', 3600))
        self._auth_expires_at = time.time() + expires_in

    def _ensure_auth(self) -> None:
        """Ensure authentication is fresh for live requests."""
        if self.paper_mode:
            return
        if self._auth_token is None or (self._auth_expires_at and time.time() > self._auth_expires_at - 30):
            self._authenticate_live()

    def _headers(self) -> Dict[str, str]:
        """Return headers including Authorization when in live mode."""
        headers = {'Content-Type': 'application/json'}
        if not self.paper_mode and self._auth_token:
            headers['Authorization'] = f"Bearer {self._auth_token}"
        return headers

    # -----------------------------
    # Order management (high-level)
    # -----------------------------
    def place_order(
        self,
        symbol: str,
        quantity: int,
        side: str = 'buy',
        order_type: str = 'market',
        price: Optional[float] = None,
        product: str = 'MIS',
        validity: str = 'DAY',
        tag: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Place an order (paper-mode-safe).

        Returns a dict representing the order status. In paper mode this is a
        simulated order saved to an in-memory dict. In live mode this calls the
        exchange REST endpoint.
        """
        side = side.lower()
        if side not in ('buy', 'sell'):
            raise ValueError('side must be "buy" or "sell"')

        # Normalize quantity to integer shares
        quantity = int(quantity)
        if quantity <= 0:
            raise ValueError('quantity must be positive integer')

        if self.paper_mode:
            order_id = str(uuid.uuid4())
            order = {
                'order_id': order_id,
                'symbol': symbol,
                'quantity': quantity,
                'side': side,
                'order_type': order_type,
                'price': price,
                'status': 'placed',
                'filled_quantity': quantity,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'product': product,
                'validity': validity,
                'tag': tag,
            }
            # Save in paper store
            self._paper_orders[order_id] = order

            # Update paper positions (simplistic aggregation)
            pos = self._paper_positions.get(symbol, {'quantity': 0, 'avg_price': 0.0})
            existing_qty = int(pos.get('quantity', 0))
            existing_avg = float(pos.get('avg_price', 0.0) or 0.0)

            # For buy: increase; for sell: decrease
            if side == 'buy':
                total_cost = existing_avg * existing_qty + (price or 0.0) * quantity
                new_qty = existing_qty + quantity
                new_avg = (total_cost / new_qty) if new_qty > 0 else 0.0
                self._paper_positions[symbol] = {'quantity': new_qty, 'avg_price': new_avg, 'current_price': price or new_avg}
            else:  # sell
                new_qty = existing_qty - quantity
                # If position becomes zero or negative, remove or set to zero
                if new_qty <= 0:
                    self._paper_positions.pop(symbol, None)
                else:
                    self._paper_positions[symbol] = {'quantity': new_qty, 'avg_price': existing_avg, 'current_price': price or existing_avg}

            return order

        # Live mode: perform HTTP request
        self._ensure_auth()
        url = f"{self.base_url}/orders"
        payload = {
            'symbol': symbol,
            'quantity': quantity,
            'side': side,
            'order_type': order_type,
            'price': price,
            'product': product,
            'validity': validity,
            'tag': tag,
        }
        resp = requests.post(url, headers=self._headers(), json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Return order status. Paper-mode returns in-memory simulated order."""
        if self.paper_mode:
            return self._paper_orders.get(order_id, {'order_id': order_id, 'status': 'unknown'})
        self._ensure_auth()
        url = f"{self.base_url}/orders/{order_id}"
        resp = requests.get(url, headers=self._headers(), timeout=10)
        resp.raise_for_status()
        return resp.json()

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel an order. Paper-mode will mark simulated order as cancelled."""
        if self.paper_mode:
            order = self._paper_orders.get(order_id)
            if not order:
                return {'order_id': order_id, 'status': 'not_found'}
            order['status'] = 'cancelled'
            order['cancelled_at'] = datetime.now(timezone.utc).isoformat()
            self._paper_orders[order_id] = order
            return order

        self._ensure_auth()
        url = f"{self.base_url}/orders/{order_id}/cancel"
        resp = requests.post(url, headers=self._headers(), timeout=10)
        resp.raise_for_status()
        return resp.json()

    # -----------------------------
    # Position management
    # -----------------------------
    def get_positions(self) -> List[Dict[str, Any]]:
        """Return open positions.

        In paper-mode returns a list derived from the in-memory store. In live
        mode, calls the account/positions endpoint.
        """
        if self.paper_mode:
            res = []
            for sym, p in self._paper_positions.items():
                res.append({'symbol': sym, 'quantity': p.get('quantity', 0), 'avg_price': p.get('avg_price', 0.0), 'current_price': p.get('current_price', 0.0)})
            return res

        self._ensure_auth()
        url = f"{self.base_url}/positions"
        resp = requests.get(url, headers=self._headers(), timeout=10)
        resp.raise_for_status()
        return resp.json()

    def close_position(self, symbol: str) -> bool:
        """Close an existing position by sending opposite market order.

        Returns True on success. In paper mode this adjusts the simulated
        positions store.
        """
        if self.paper_mode:
            pos = self._paper_positions.get(symbol)
            if not pos:
                return True
            qty = int(pos.get('quantity', 0))
            if qty == 0:
                return True
            # Place opposite order to flatten
            side = 'sell' if qty > 0 else 'buy'
            self.place_order(symbol, abs(qty), side=side, order_type='market')
            # After placing, ensure position removed
            self._paper_positions.pop(symbol, None)
            return True

        # Live path: call close/exit endpoint or send reduce-only order
        self._ensure_auth()
        url = f"{self.base_url}/positions/{symbol}/close"
        resp = requests.post(url, headers=self._headers(), timeout=10)
        resp.raise_for_status()
        return bool(resp.json().get('success', True))

    # -----------------------------
    # Convenience market methods
    # -----------------------------
    def market_buy(self, symbol: str, quantity: int, price: Optional[float] = None) -> Dict[str, Any]:
        """Convenience wrapper to buy at market (paper-mode safe)."""
        return self.place_order(symbol, quantity, side='buy', order_type='market', price=price)

    def market_sell(self, symbol: str, quantity: int, price: Optional[float] = None) -> Dict[str, Any]:
        """Convenience wrapper to sell at market (paper-mode safe)."""
        return self.place_order(symbol, quantity, side='sell', order_type='market', price=price)

    # -----------------------------
    # Lot / margin / expiry helpers
    # -----------------------------
    def get_lot_size(self, symbol: str) -> int:
        """Return lot size for a symbol. First check provided defaults, then
        fallback to 1 (equities = 1 share per lot by convention here).
        """
        if not symbol:
            return 1
        sym = symbol.upper()
        return int(self.default_lot_sizes.get(sym, 1))

    def normalize_quantity_to_lots(self, quantity: int, lot_size: Optional[int] = None) -> int:
        """Round quantity down to a whole number of lots.

        Args:
            quantity: desired shares
            lot_size: if provided, the lot size to use; otherwise get_lot_size(symbol)

        Returns:
            int: normalized shares which are an integer multiple of lot_size
        """
        lot = int(lot_size or 1)
        if lot <= 1:
            return int(quantity)
        return int((int(quantity) // lot) * lot)

    def calculate_margin(self, notional_in_inr: float, leverage: float = 1.0) -> float:
        """Return a conservative margin estimate for a given notional amount.

        This is a simplified placeholder: for accurate margins, call exchange's
        margin API to get SPAN / exposure margin for F&O contracts.
        """
        if leverage <= 0:
            raise ValueError('leverage must be > 0')
        return float(abs(notional_in_inr) / float(leverage))

    def validate_expiry(self, expiry_date: str) -> bool:
        """Validate YYYY-MM-DD expiry is in the future.

        Returns True if expiry_date parses and is strictly after today (IST).
        """
        try:
            dt = datetime.strptime(expiry_date, '%Y-%m-%d').date()
            today = datetime.now().date()
            return dt > today
        except Exception:
            return False


# Module-level convenience singleton and wrappers
_default_client: Optional[UpstoxRestClient] = None


def get_upstox_client(paper_mode: Optional[bool] = None) -> UpstoxRestClient:
    """Return a shared UpstoxRestClient singleton (paper-mode by default)."""
    global _default_client
    if _default_client is None:
        _default_client = UpstoxRestClient(paper_mode=paper_mode)
    return _default_client


def place_order(*args, **kwargs):
    return get_upstox_client().place_order(*args, **kwargs)


def market_buy(*args, **kwargs):
    return get_upstox_client().market_buy(*args, **kwargs)


def market_sell(*args, **kwargs):
    return get_upstox_client().market_sell(*args, **kwargs)


def get_positions():
    return get_upstox_client().get_positions()


def get_lot_size(symbol: str):
    return get_upstox_client().get_lot_size(symbol)
