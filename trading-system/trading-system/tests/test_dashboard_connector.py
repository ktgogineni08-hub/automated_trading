from dataclasses import dataclass

import pytest

from utilities import dashboard


@dataclass
class FakeResponse:
    status_code: int

    def json(self):
        return {}


class FakeSession:
    default_get_responses = []
    default_post_responses = []
    instances = []

    def __init__(self):
        self.timeout = None
        self.headers = {}
        self.verify = True
        self.get_responses = list(FakeSession.default_get_responses)
        self.post_responses = list(FakeSession.default_post_responses)
        self.get_calls = []
        self.post_calls = []
        FakeSession.instances.append(self)

    def update(self, d):
        """Support headers.update() calls"""
        self.headers.update(d)

    def get(self, url, timeout=None):
        self.get_calls.append((url, timeout))
        if not self.get_responses:
            raise AssertionError('No fake GET response configured')
        resp = self.get_responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp

    def post(self, url, json=None, timeout=None, headers=None):
        """Accept headers parameter to match real requests.Session"""
        self.post_calls.append((url, json, timeout))
        if not self.post_responses:
            raise AssertionError('No fake POST response configured')
        resp = self.post_responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp


@pytest.fixture(autouse=True)
def reset_fake_session(monkeypatch):
    FakeSession.instances.clear()
    FakeSession.default_get_responses = [FakeResponse(200)] * 5
    FakeSession.default_post_responses = []
    monkeypatch.setattr(dashboard.requests, 'Session', FakeSession)
    monkeypatch.setattr(dashboard.time, 'sleep', lambda _: None)
    yield
    FakeSession.default_get_responses = []
    FakeSession.default_post_responses = []
    FakeSession.instances.clear()


def test_send_signal_success():
    FakeSession.default_post_responses = [FakeResponse(200)]
    connector = dashboard.DashboardConnector(base_url='http://fake', api_key='secret')
    assert connector.send_signal('NIFTY', 'buy', 0.8, 100.0)
    session = FakeSession.instances[-1]
    assert session.post_calls
    assert session.headers.get('X-API-Key') == 'secret'
    url, payload, _ = session.post_calls[0]
    assert url == 'http://fake/api/signals'
    assert payload['symbol'] == 'NIFTY'


def test_send_trade_retries_then_success():
    FakeSession.default_post_responses = [Exception('boom'), FakeResponse(200)]
    connector = dashboard.DashboardConnector(base_url='http://fake', api_key='secret')
    assert connector.send_trade('BANKNIFTY', 'sell', 2, 350.0)
    session = FakeSession.instances[-1]
    assert len(session.post_calls) == 2


def test_circuit_breaker_trips_after_failures():
    FakeSession.default_post_responses = [Exception('boom')] * 5
    connector = dashboard.DashboardConnector(base_url='http://fake', api_key='secret')
    success = connector.send_portfolio_update(1000.0, 500.0, 1, 50.0)
    assert not success
    assert connector.circuit_breaker_failures >= connector.circuit_breaker_threshold
    # Next attempt short-circuits because breaker is open
    FakeSession.default_post_responses = [FakeResponse(200)]
    assert not connector.send_portfolio_update(1000.0, 500.0, 1, 50.0)
