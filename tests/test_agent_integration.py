import os
import sys
import pytest

# Avoid model_factory initializing real LLMs during test import
os.environ.setdefault('DEEPSEEK_KEY', 'test')

# Ensure repo root is on sys.path for tests run by pytest in CI or local
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from exchange.upstox_rest_client import get_upstox_client


def test_get_upstox_client_and_market_buy(monkeypatch):
    # Ensure PAPER_MODE prevents network calls
    os.environ['UPSTOX_PAPER_MODE'] = '1'
    client = get_upstox_client(paper_mode=True)

    # Place a paper market buy
    order = client.market_buy('RELIANCE', quantity=5, price=2500.0)
    assert order['status'] == 'placed'
    assert order['filled_quantity'] == 5

    # Positions should reflect the buy
    positions = client.get_positions()
    found = [p for p in positions if p['symbol'] == 'RELIANCE']
    assert len(found) == 1
    assert found[0]['quantity'] >= 5


def test_agent_collect_and_format_prompt(monkeypatch):
    # This test ensures the basic data collection flow works with the upstox client
    from agents.base_pure_agent import BaseNof1Agent
    from agents.agent_configs import CONFIG

    # Create a minimal concrete subclass for testing
    class DummyAgent(BaseNof1Agent):
        def get_llm_decision(self, prompt: str, system_prompt: str):
            return {'decision': 'DO_NOTHING', 'symbol': CONFIG['SYMBOLS'][0], 'confidence': 1.0}

    agent = DummyAgent(exchange='upstox', symbols=['RELIANCE'], check_interval_seconds=1, verbose=False)

    # Run a single iteration (should not raise)
    agent.run_single_iteration()
    # If we reach here without exception, integration smoke test passes
    assert True
