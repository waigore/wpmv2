"""Pytest fixtures for common test data."""

import pytest
from datetime import date
from decimal import Decimal
from pathlib import Path

from wpm.models import Asset, Trade
from wpm.config import Config


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
        order_instruction="Limit",
        currency="USD",
        price=150.0,
        price_native=150.0,
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
        order_instruction="Market",
        currency="USD",
        price=160.0,
        price_native=160.0,
        quantity=5.0,
    )


@pytest.fixture(scope="session", autouse=True)
def test_cache_isolation(tmp_path_factory):
    """Automatically redirect all cache files to a test-specific directory.
    
    This fixture ensures that tests never write to or read from production cache files.
    It overrides Config class variables to point to a temporary test directory that is
    automatically cleaned up after all tests complete.
    """
    # Create a temporary directory for test cache files
    test_cache_dir = tmp_path_factory.mktemp("test_cache")
    
    # Store original Config values for restoration after tests
    original_cache_dir = Config.CACHE_DIR
    original_cache_file = Config.CACHE_FILE
    original_currency_cache_file = Config.CURRENCY_CACHE_FILE
    original_historical_cache_file = Config.HISTORICAL_CACHE_FILE
    original_asset_metadata_cache_file = Config.ASSET_METADATA_CACHE_FILE
    
    # Override Config class variables to use test cache directory
    Config.CACHE_DIR = test_cache_dir
    Config.CACHE_FILE = test_cache_dir / "price_cache.parquet"
    Config.CURRENCY_CACHE_FILE = test_cache_dir / "currency_cache.parquet"
    Config.HISTORICAL_CACHE_FILE = test_cache_dir / "historical_price_cache.parquet"
    Config.ASSET_METADATA_CACHE_FILE = test_cache_dir / "asset_metadata_cache.parquet"
    
    # Yield control to tests - cleanup happens automatically via tmp_path_factory
    yield
    
    # Restore original Config values (though not strictly necessary since tests are done)
    Config.CACHE_DIR = original_cache_dir
    Config.CACHE_FILE = original_cache_file
    Config.CURRENCY_CACHE_FILE = original_currency_cache_file
    Config.HISTORICAL_CACHE_FILE = original_historical_cache_file
    Config.ASSET_METADATA_CACHE_FILE = original_asset_metadata_cache_file
    
    # Note: tmp_path_factory automatically cleans up the temporary directory
    # after all tests in the session complete

