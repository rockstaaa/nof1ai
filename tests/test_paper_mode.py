import os
import sys
import pytest

# Avoid model_factory initializing real LLMs during test import
os.environ.setdefault('DEEPSEEK_KEY', 'test')
import requests

# Ensure repo root is on sys.path for tests run by pytest in CI or local
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from exchange.upstox_rest_client import UpstoxRestClient


def test_no_live_requests_when_paper_mode(monkeypatch):
    # If paper_mode=True, client should not call requests.post for auth or orders
    called = {'post': False}

    def fake_post(*args, **kwargs):
        called['post'] = True
        raise RuntimeError('Should not be called in paper mode')

    monkeypatch.setattr(requests, 'post', fake_post)

    client = UpstoxRestClient(paper_mode=True)
    # Place a paper order; this should not call requests.post
    order = client.place_order('RELIANCE', quantity=2, side='buy')
    assert order['status'] == 'placed'
    assert called['post'] is False


def test_live_mode_requires_credentials(monkeypatch):
    # If paper_mode=False and no credentials, expect RuntimeError on auth
    monkeypatch.delenv('UPSTOX_API_KEY', raising=False)
    monkeypatch.delenv('UPSTOX_API_SECRET', raising=False)

    with pytest.raises(RuntimeError):
        UpstoxRestClient(paper_mode=False)
