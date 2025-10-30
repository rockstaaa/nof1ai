"""
nof1-agents
Inspired by Nof1's Alpha Arena approach

Pure LLM decision-making with zero rules-based logic.
Technical data only. Reasoning traces logged.
Built for HyperLiquid perpetuals trading.

Quick Start:
    from src.nof1-agents import DeepSeekTrader
    
    trader = DeepSeekTrader(
        symbols=['BTC'],
        starting_capital_usd=500,
        check_interval_minutes=3
    )
    
    trader.run()

Or run directly:
    python src/nof1-agents/agents/deepseek_trader.py
"""

__version__ = "1.0.0"

from .agents.base_pure_agent import BaseNof1Agent
from .agents.deepseek_trader import DeepSeekTrader

__all__ = [
    'BaseNof1Agent',
    'DeepSeekTrader',
]
