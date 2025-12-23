"""Pytest fixtures for common test data."""

import pytest
from datetime import date
from decimal import Decimal

from wpm.models import Asset, Trade


@pytest.fixture
def sample_asset_stock():
    """Sample stock asset."""
    return Asset(ticker="GOOG", asset_type="Stock")


@pytest.fixture
def sample_asset_etf():
    """Sample ETF asset."""
    return Asset(ticker="IAU", asset_type="ETF")


@pytest.fixture
def sample_asset_crypto():
    """Sample crypto asset."""
    return Asset(ticker="BTC-USD", asset_type="Crypto")


@pytest.fixture
def sample_buy_trade(sample_asset_stock):
    """Sample buy trade."""
    return Trade(
        date=date(2024, 1, 15),
        asset=sample_asset_stock,
        action="Buy",
        broker="IBKR",
        order_type="Limit",
        price=150.0,
        quantity=10.0,
    )


@pytest.fixture
def sample_sell_trade(sample_asset_stock):
    """Sample sell trade."""
    return Trade(
        date=date(2024, 2, 15),
        asset=sample_asset_stock,
        action="Sell",
        broker="IBKR",
        order_type="Market",
        price=160.0,
        quantity=5.0,
    )

