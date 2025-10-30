import os
import sys
import pytest

# Avoid model_factory initializing real LLMs during test import
os.environ.setdefault('DEEPSEEK_KEY', 'test')

# Ensure repo root is on sys.path for tests run by pytest in CI or local
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from exchange.upstox_rest_client import UpstoxRestClient


def test_paper_place_order_and_get_status():
    client = UpstoxRestClient(paper_mode=True)
    # Place a paper buy order
    order = client.place_order('RELIANCE', quantity=10, side='buy', order_type='market', price=2500.0)
    assert order['status'] == 'placed'
    assert order['filled_quantity'] == 10

    # Fetch by id
    fetched = client.get_order_status(order['order_id'])
    assert fetched['order_id'] == order['order_id']
    assert fetched['status'] == 'placed'

    # Cancel and ensure status updated
    cancelled = client.cancel_order(order['order_id'])
    assert cancelled['status'] == 'cancelled'


def test_lot_size_and_normalization():
    client = UpstoxRestClient(paper_mode=True, default_lot_sizes={'RELIANCE': 1, 'NIFTY': 50})
    assert client.get_lot_size('NIFTY') == 50
    assert client.get_lot_size('RELIANCE') == 1

    # Normalize quantity to lots
    assert client.normalize_quantity_to_lots(120, lot_size=50) == 100
    assert client.normalize_quantity_to_lots(3, lot_size=1) == 3


def test_margin_and_expiry_validation():
    client = UpstoxRestClient(paper_mode=True)
    margin = client.calculate_margin(100000.0, leverage=10)
    assert pytest.approx(margin, rel=1e-6) == 10000.0

    # Expiry validation
    today = __import__('datetime').date.today()
    future = (today.replace(day=min(today.day+1,28))).strftime('%Y-%m-%d')
    assert client.validate_expiry(future) is True

    assert client.validate_expiry('invalid-date') is False
