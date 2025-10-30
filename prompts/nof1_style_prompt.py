"""
Clean Nof1-style prompt module for Indian equities (NSE) and F&O.

This module exposes:
- NOF1_SYSTEM_PROMPT: the system prompt (instructions + JSON schema)
- format_nof1_user_prompt(...): helper to create the user prompt text
"""

from typing import Dict
import json


NOF1_SYSTEM_PROMPT = """
You are an autonomous Indian equities and derivatives (F&O) trading assistant.

YOUR ROLE:
- Analyze live NSE market data (equities, Nifty, BankNifty, options/futures) and account state.
- Make one clear trading decision at a time: BUY (open long), SELL (open short/short-sell), CLOSE (close existing position), or DO_NOTHING.
- Use INR pricing, respect lot sizes for F&O, and prefer market-hours execution (09:15–15:30 IST).

OUTPUT CONTRACT (STRICT JSON):
Return exactly one JSON object with the following fields only.

{
  "decision": "BUY" | "SELL" | "CLOSE" | "DO_NOTHING",
  "symbol": "RELIANCE" | "NIFTY" | "BANKNIFTY" | "HDFCBANK" | etc.,
  "confidence": 0.0 to 1.0,
  "reasoning": "Concise step-by-step reasoning for this decision",
  "entry_price_inr": <float>,
  "quantity_lots": <int>,
  "lot_size": <int>,
  "stop_loss_inr": <float>,
  "take_profit_inr": <float>,
  "risk_in_inr": <float>,
  "invalidation_condition": "Clear condition where trade is invalidated",
  "time_horizon": "e.g., intraday / 1-3 days"
}

CRITICAL:
- Respect lot sizes (quantity_lots × lot_size is the tradable quantity). Round quantity_lots down to an integer.
- If trading equities (not F&O), prefer quantity in shares that match lot_size==1.
- If market is closed, respond with DO_NOTHING.
- Use INR values for all prices and risk calculations.
"""


def format_nof1_user_prompt(account_data: Dict, positions: Dict, market_data: Dict, timestamp: str, interaction_count: int = 0, start_time=None) -> str:
    """Compose a concise, structured user prompt for the LLM.

    This function returns a textual prompt that includes account summary, open positions,
    and succinct market-data snapshots for each symbol. The LLM should use the
    system prompt (NOF1_SYSTEM_PROMPT) to decide.
    """

    parts = []
    parts.append(f"Time: {timestamp} | Interaction: {interaction_count}")

    # Account summary
    parts.append("\n=== ACCOUNT SUMMARY ===")
    parts.append(f"Account Value (INR): {account_data.get('account_value', account_data.get('account_value_inr', 0))}")
    parts.append(f"Available Cash (INR): {account_data.get('available_cash', account_data.get('available_cash_inr', 0))}")
    parts.append(f"Total Return (%): {account_data.get('total_return_percent', 0):.2f}")

    # Positions
    parts.append("\n=== OPEN POSITIONS ===")
    if positions:
        for sym, p in positions.items():
            parts.append(json.dumps({
                'symbol': sym,
                'quantity': p.get('quantity', 0),
                'avg_price': p.get('avg_price', p.get('entry_price', 0)),
                'current_price': p.get('current_price', 0),
                'unrealized_pnl': p.get('unrealized_pnl', 0)
            }))
    else:
        parts.append('No open positions')

    # Market data
    parts.append('\n=== MARKET DATA ===')
    if isinstance(market_data, dict):
        for symbol, d in market_data.items():
            parts.append(f"{symbol}: price={d.get('price', d.get('close', 0))}, volume={d.get('volume', 0)}")
            ind = d.get('indicators', {}) if isinstance(d, dict) else {}
            if ind:
                parts.append(f"  indicators: {json.dumps(ind)}")

    parts.append('\nBased on the account state, open positions, and market data above, output exactly one JSON object in the schema described in the system prompt. Use INR and lot sizing when relevant. Be concise.')

    return '\n'.join(parts)


# Short helper quick prompt kept for backward compatibility with older modules
NOF1_QUICK_PROMPT = """You are an Indian equities trading assistant. Analyze the provided market snapshot and return a single JSON decision object as per the system prompt schema."""
