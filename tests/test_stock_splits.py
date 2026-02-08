"""Tests for stock split support functionality."""

import os
import pytest
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, patch
import pandas as pd

from wpm.models import Asset, Trade, ValidationError
from wpm.pricing.splits import SplitService, compute_cumulative_split_factor_from_splits
from wpm.importer import adjust_trade_for_splits
from wpm.cost_basis import calculate_lots_from_trades, calculate_fifo_cost_basis
from wpm.portfolio import SimplePortfolio, get_historical_performance


@contextmanager
def _patch_tickers(splits_by_ticker):
    """Patch yf.Tickers so .tickers.get(t) returns an object with .splits = splits_by_ticker[t]."""
    ticker_dict = {t: Mock(splits=s) for t, s in splits_by_ticker.items()}
    mock_tickers_obj = Mock()
    mock_tickers_obj.tickers = ticker_dict
    with patch('wpm.pricing.splits.yf.Tickers') as mock_tickers_class:
        mock_tickers_class.return_value = mock_tickers_obj
        yield mock_tickers_class


class TestComputeCumulativeSplitFactorFromSplits:
    """Tests for compute_cumulative_split_factor_from_splits (pure function, no I/O)."""

    def test_empty_series_returns_one(self):
        """Empty or None splits returns 1.0."""
        assert compute_cumulative_split_factor_from_splits(
            pd.Series(dtype=float), date(2020, 1, 1)
        ) == Decimal('1.0')
        assert compute_cumulative_split_factor_from_splits(
            pd.Series(dtype=float), date(2020, 1, 1), current_date=date(2020, 12, 31)
        ) == Decimal('1.0')

    def test_single_forward_split(self):
        """Single 2:1 split after trade_date returns 2.0."""
        splits = pd.Series(
            [2.0],
            index=[pd.Timestamp('2020-06-15')],
        )
        assert compute_cumulative_split_factor_from_splits(
            splits, date(2020, 1, 1)
        ) == Decimal('2.0')
        assert compute_cumulative_split_factor_from_splits(
            splits, date(2020, 7, 1)
        ) == Decimal('1.0')

    def test_multiple_splits(self):
        """Multiple splits: product of ratios."""
        splits = pd.Series(
            [2.0, 3.0],
            index=[pd.Timestamp('2020-06-15'), pd.Timestamp('2021-01-01')],
        )
        assert compute_cumulative_split_factor_from_splits(
            splits, date(2020, 1, 1)
        ) == Decimal('6.0')
        assert compute_cumulative_split_factor_from_splits(
            splits, date(2020, 7, 1)
        ) == Decimal('3.0')
        assert compute_cumulative_split_factor_from_splits(
            splits, date(2021, 2, 1)
        ) == Decimal('1.0')

    def test_reverse_split(self):
        """Reverse split 1:2 returns 0.5."""
        splits = pd.Series(
            [0.5],
            index=[pd.Timestamp('2020-06-15')],
        )
        assert compute_cumulative_split_factor_from_splits(
            splits, date(2020, 1, 1)
        ) == Decimal('0.5')
        assert compute_cumulative_split_factor_from_splits(
            splits, date(2020, 7, 1)
        ) == Decimal('1.0')

    def test_with_current_date(self):
        """current_date limits which splits are included."""
        splits = pd.Series(
            [2.0, 3.0],
            index=[pd.Timestamp('2020-06-15'), pd.Timestamp('2021-01-01')],
        )
        # Only first split within current_date
        assert compute_cumulative_split_factor_from_splits(
            splits, date(2020, 1, 1), current_date=date(2020, 12, 31)
        ) == Decimal('2.0')
        # Both splits
        assert compute_cumulative_split_factor_from_splits(
            splits, date(2020, 1, 1), current_date=date(2021, 6, 1)
        ) == Decimal('6.0')

    def test_split_on_trade_date_excluded(self):
        """Splits on trade_date are excluded (strictly after)."""
        splits = pd.Series(
            [2.0],
            index=[pd.Timestamp('2020-06-15')],
        )
        assert compute_cumulative_split_factor_from_splits(
            splits, date(2020, 6, 15)
        ) == Decimal('1.0')


class TestSplitService:
    """Tests for SplitService."""

    def test_get_splits_no_splits(self, tmp_path):
        """Test getting splits when no splits exist."""
        service = SplitService(cache_file=tmp_path / "splits.parquet")
        with _patch_tickers({"GOOG": pd.Series(dtype=float)}):
            result = service.get_splits(["GOOG"])
        assert "GOOG" in result
        assert result["GOOG"].empty

    def test_get_splits_with_splits(self, tmp_path):
        """Test getting splits when splits exist."""
        service = SplitService(cache_file=tmp_path / "splits.parquet")
        split_data = pd.Series(
            [2.0],
            index=[pd.Timestamp('2020-06-15')],
        )
        with _patch_tickers({"GOOG": split_data}):
            result = service.get_splits(["GOOG"])
        assert "GOOG" in result
        assert not result["GOOG"].empty
        assert len(result["GOOG"]) == 1
        assert result["GOOG"].iloc[0] == 2.0

    def test_get_splits_batch_multiple_tickers(self, tmp_path):
        """Test get_splits returns one dict for multiple tickers (batch)."""
        service = SplitService(cache_file=tmp_path / "splits.parquet")
        goog_splits = pd.Series([2.0], index=[pd.Timestamp('2020-06-15')])
        aapl_splits = pd.Series(dtype=float)
        with _patch_tickers({"GOOG": goog_splits, "AAPL": aapl_splits}) as mock_tickers:
            result = service.get_splits(["GOOG", "AAPL"])
        assert mock_tickers.call_count == 1
        assert set(result.keys()) == {"GOOG", "AAPL"}
        assert len(result["GOOG"]) == 1
        assert result["AAPL"].empty

    def test_get_cumulative_split_factor_no_splits(self, tmp_path):
        """Test cumulative factor when no splits occurred."""
        service = SplitService(cache_file=tmp_path / "splits.parquet")
        with _patch_tickers({"GOOG": pd.Series(dtype=float)}):
            factor = service.get_cumulative_split_factor("GOOG", date(2020, 1, 1))
        assert factor == Decimal('1.0')

    def test_get_cumulative_split_factor_single_forward_split(self, tmp_path):
        """Test cumulative factor with single forward split."""
        service = SplitService(cache_file=tmp_path / "splits.parquet")
        split_data = pd.Series(
            [2.0],
            index=[pd.Timestamp('2020-06-15')],
        )
        with _patch_tickers({"GOOG": split_data}):
            factor = service.get_cumulative_split_factor("GOOG", date(2020, 1, 1))
            assert factor == Decimal('2.0')
            factor = service.get_cumulative_split_factor("GOOG", date(2020, 7, 1))
            assert factor == Decimal('1.0')

    def test_get_cumulative_split_factor_multiple_splits(self, tmp_path):
        """Test cumulative factor with multiple splits."""
        service = SplitService(cache_file=tmp_path / "splits.parquet")
        split_data = pd.Series(
            [2.0, 3.0],
            index=[pd.Timestamp('2020-06-15'), pd.Timestamp('2021-01-01')],
        )
        with _patch_tickers({"GOOG": split_data}):
            factor = service.get_cumulative_split_factor("GOOG", date(2020, 1, 1))
            assert factor == Decimal('6.0')
            factor = service.get_cumulative_split_factor("GOOG", date(2020, 7, 1))
            assert factor == Decimal('3.0')
            factor = service.get_cumulative_split_factor("GOOG", date(2021, 2, 1))
            assert factor == Decimal('1.0')

    def test_get_cumulative_split_factor_reverse_split(self, tmp_path):
        """Test cumulative factor with reverse split."""
        service = SplitService(cache_file=tmp_path / "splits.parquet")
        split_data = pd.Series(
            [0.5],
            index=[pd.Timestamp('2020-06-15')],
        )
        with _patch_tickers({"GOOG": split_data}):
            factor = service.get_cumulative_split_factor("GOOG", date(2020, 1, 1))
            assert factor == Decimal('0.5')
            factor = service.get_cumulative_split_factor("GOOG", date(2020, 7, 1))
            assert factor == Decimal('1.0')

    def test_get_cumulative_split_factor_mixed_splits(self, tmp_path):
        """Test cumulative factor with forward and reverse splits."""
        service = SplitService(cache_file=tmp_path / "splits.parquet")
        split_data = pd.Series(
            [2.0, 0.5],
            index=[pd.Timestamp('2020-06-15'), pd.Timestamp('2021-01-01')],
        )
        with _patch_tickers({"GOOG": split_data}):
            factor = service.get_cumulative_split_factor("GOOG", date(2020, 1, 1))
            assert factor == Decimal('1.0')

    def test_get_cumulative_split_factor_with_current_date(self, tmp_path):
        """Test cumulative factor with current_date parameter."""
        service = SplitService(cache_file=tmp_path / "splits.parquet")
        split_data = pd.Series(
            [2.0, 3.0],
            index=[pd.Timestamp('2020-06-15'), pd.Timestamp('2021-01-01')],
        )
        with _patch_tickers({"GOOG": split_data}):
            factor = service.get_cumulative_split_factor(
                "GOOG", date(2020, 1, 1), current_date=date(2020, 12, 31)
            )
            assert factor == Decimal('2.0')

    def test_get_cumulative_split_factor_error_handling(self, tmp_path):
        """Test error handling when batch fetch fails."""
        service = SplitService(cache_file=tmp_path / "splits.parquet")
        with patch('wpm.pricing.splits.yf.Tickers') as mock_tickers_class:
            mock_tickers_class.side_effect = Exception("API Error")
            factor = service.get_cumulative_split_factor("GOOG", date(2020, 1, 1))
        assert factor == Decimal('1.0')

    def test_split_cache(self, tmp_path):
        """Test that splits are cached (one batch fetch, then cache)."""
        service = SplitService(cache_file=tmp_path / "splits.parquet")
        split_data = pd.Series(
            [2.0],
            index=[pd.Timestamp('2020-06-15')],
        )
        with _patch_tickers({"GOOG": split_data}) as mock_tickers_class:
            result1 = service.get_splits(["GOOG"])
            result2 = service.get_splits(["GOOG"])
        assert mock_tickers_class.call_count == 1
        assert result1["GOOG"].equals(result2["GOOG"])

    def test_ensure_splits_loaded_then_get_splits_uses_memory_only(self, tmp_path):
        """ensure_splits_loaded populates cache; subsequent get_splits use memory only."""
        cache_file = tmp_path / "split_cache.parquet"
        service = SplitService(cache_file=cache_file)
        split_data = pd.Series(
            [2.0],
            index=[pd.Timestamp('2020-06-15')],
        )
        with _patch_tickers({"GOOG": split_data}) as mock_tickers_class:
            service.ensure_splits_loaded(["GOOG"])
            result1 = service.get_splits(["GOOG"])
            result2 = service.get_splits(["GOOG"])
        # One yfinance call for ensure_splits_loaded; get_splits use in-memory cache
        assert mock_tickers_class.call_count == 1
        assert result1["GOOG"].equals(result2["GOOG"])
        assert len(result1["GOOG"]) == 1

    def test_file_cache_validity_same_day_mtime(self, tmp_path):
        """File cache is valid when mtime is on same calendar day."""
        cache_file = tmp_path / "split_cache.parquet"
        service = SplitService(cache_file=cache_file)
        split_data = pd.Series([2.0], index=[pd.Timestamp('2020-06-15')])
        with _patch_tickers({"GOOG": split_data}) as mock_tickers_class:
            service.ensure_splits_loaded(["GOOG"])
        assert mock_tickers_class.call_count == 1
        assert cache_file.exists()

        # New service instance, same-day cache should be valid -> load from file
        service2 = SplitService(cache_file=cache_file)
        with _patch_tickers({"GOOG": split_data}) as mock_tickers_class2:
            service2.ensure_splits_loaded(["GOOG"])
        # Should load from file, not fetch from yfinance
        assert mock_tickers_class2.call_count == 0

    def test_file_cache_invalid_prior_day_mtime(self, tmp_path):
        """File cache is invalid when mtime is from a prior day; triggers refresh."""
        cache_file = tmp_path / "split_cache.parquet"
        service = SplitService(cache_file=cache_file)
        split_data = pd.Series([2.0], index=[pd.Timestamp('2020-06-15')])
        with _patch_tickers({"GOOG": split_data}) as mock_tickers_class:
            service.ensure_splits_loaded(["GOOG"])
        assert mock_tickers_class.call_count == 1
        assert cache_file.exists()

        # Set mtime to yesterday
        yesterday = datetime.now() - timedelta(days=1)
        os.utime(cache_file, (yesterday.timestamp(), yesterday.timestamp()))

        # New service instance; prior-day cache invalid -> fetch from yfinance
        service2 = SplitService(cache_file=cache_file)
        with _patch_tickers({"GOOG": split_data}) as mock_tickers_class2:
            service2.ensure_splits_loaded(["GOOG"])
        assert mock_tickers_class2.call_count == 1

    def test_missing_ticker_triggers_refresh(self, tmp_path):
        """When requested ticker is not in cache, triggers fetch."""
        cache_file = tmp_path / "split_cache.parquet"
        service = SplitService(cache_file=cache_file)
        goog_splits = pd.Series([2.0], index=[pd.Timestamp('2020-06-15')])
        aapl_splits = pd.Series(dtype=float)
        with _patch_tickers({"GOOG": goog_splits}) as mock_tickers_class:
            service.ensure_splits_loaded(["GOOG"])
        assert mock_tickers_class.call_count == 1

        # Request AAPL which is not in cache -> triggers refresh
        with _patch_tickers({"GOOG": goog_splits, "AAPL": aapl_splits}) as mock_tickers_class2:
            result = service.get_splits(["GOOG", "AAPL"])
        assert mock_tickers_class2.call_count == 1
        assert "GOOG" in result
        assert "AAPL" in result

    def test_timezone_aware_splits(self, tmp_path):
        """Test that timezone-aware timestamps from yfinance are handled correctly."""
        service = SplitService(cache_file=tmp_path / "splits.parquet")
        split_data = pd.Series(
            [0.05],
            index=[pd.Timestamp('2026-02-06 00:00:00-05:00')],
        )
        with _patch_tickers({"ASST": split_data}):
            factor = service.get_cumulative_split_factor("ASST", date(2026, 2, 5))
            assert factor == Decimal('0.05')
            factor2 = service.get_cumulative_split_factor("ASST", date(2026, 2, 6))
            assert factor2 == Decimal('1.0')
            factor3 = service.get_cumulative_split_factor("ASST", date(2026, 2, 7))
            assert factor3 == Decimal('1.0')


class TestTradeSplitAdjustment:
    """Tests for Trade split adjustment properties."""

    def test_trade_default_split_factor(self):
        """Test that Trade defaults to split_factor of 1.0."""
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trade = Trade(
            date=date(2024, 1, 15),
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=150.0,
            price_native=150.0,
            quantity=Decimal('10.0'),
        )
        
        assert trade.split_adjustment_factor == Decimal('1.0')
        assert trade.adjusted_quantity == Decimal('10.0')
        assert trade.adjusted_price == 150.0
        assert trade.adjusted_price_native == 150.0

    def test_trade_with_split_factor(self):
        """Test Trade with split adjustment factor."""
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trade = Trade(
            date=date(2024, 1, 15),
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=150.0,
            price_native=150.0,
            quantity=Decimal('10.0'),
            split_adjustment_factor=Decimal('2.0'),  # 2:1 split
        )
        
        assert trade.split_adjustment_factor == Decimal('2.0')
        assert trade.adjusted_quantity == Decimal('20.0')  # 10 * 2
        assert trade.adjusted_price == 75.0  # 150 / 2
        assert trade.adjusted_price_native == 75.0

    def test_trade_with_reverse_split(self):
        """Test Trade with reverse split factor."""
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trade = Trade(
            date=date(2024, 1, 15),
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=50.0,
            price_native=50.0,
            quantity=Decimal('100.0'),
            split_adjustment_factor=Decimal('0.5'),  # 1:2 reverse split
        )
        
        assert trade.split_adjustment_factor == Decimal('0.5')
        assert trade.adjusted_quantity == Decimal('50.0')  # 100 * 0.5
        assert trade.adjusted_price == 100.0  # 50 / 0.5
        assert trade.adjusted_price_native == 100.0

    def test_trade_total_value_unchanged(self):
        """Test that total_value remains unchanged with split adjustment."""
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trade = Trade(
            date=date(2024, 1, 15),
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=150.0,
            price_native=150.0,
            quantity=Decimal('10.0'),
            split_adjustment_factor=Decimal('2.0'),
        )
        
        # Original total value
        original_total = float(trade.quantity) * trade.price  # 10 * 150 = 1500
        # Adjusted total value
        adjusted_total = float(trade.adjusted_quantity) * trade.adjusted_price  # 20 * 75 = 1500
        
        assert trade.total_value == original_total
        assert adjusted_total == original_total  # Cost basis unchanged


class TestAdjustTradeForSplits:
    """Tests for adjust_trade_for_splits function."""

    def test_adjust_trade_crypto(self):
        """Test that crypto trades are not adjusted."""
        asset = Asset(ticker="BTC-USD", asset_type="Crypto")
        trade = Trade(
            date=date(2024, 1, 15),
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=50000.0,
            price_native=50000.0,
            quantity=Decimal('0.1'),
        )
        ticker_splits = {"BTC-USD": pd.Series(dtype=float)}
        adjusted_trade = adjust_trade_for_splits(trade, ticker_splits)
        assert adjusted_trade.split_adjustment_factor == Decimal('1.0')
        assert adjusted_trade.adjusted_quantity == trade.quantity
        assert adjusted_trade.adjusted_price == trade.price

    def test_adjust_trade_stock_with_split(self):
        """Test adjusting stock trade with split."""
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trade = Trade(
            date=date(2020, 1, 1),
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=150.0,
            price_native=150.0,
            quantity=Decimal('10.0'),
        )
        split_series = pd.Series(
            [2.0],
            index=[pd.Timestamp('2020-07-01')],
        )
        ticker_splits = {"GOOG": split_series}
        adjusted_trade = adjust_trade_for_splits(trade, ticker_splits)
        assert adjusted_trade.split_adjustment_factor == Decimal('2.0')
        assert adjusted_trade.adjusted_quantity == Decimal('20.0')
        assert adjusted_trade.adjusted_price == 75.0

    def test_adjust_trade_with_current_date(self):
        """Test adjusting trade with current_date parameter."""
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trade = Trade(
            date=date(2020, 1, 1),
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=150.0,
            price_native=150.0,
            quantity=Decimal('10.0'),
        )
        split_series = pd.Series(
            [2.0],
            index=[pd.Timestamp('2020-07-01')],
        )
        ticker_splits = {"GOOG": split_series}
        with patch('wpm.importer.compute_cumulative_split_factor_from_splits') as mock_fn:
            mock_fn.return_value = Decimal('2.0')
            adjust_trade_for_splits(trade, ticker_splits, current_date=date(2020, 12, 31))
            mock_fn.assert_called_once_with(
                split_series, trade.date, date(2020, 12, 31)
            )

    def test_adjust_trade_raises_if_ticker_splits_none(self):
        """Test that None ticker_splits raises ValidationError."""
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trade = Trade(
            date=date(2020, 1, 1),
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=150.0,
            price_native=150.0,
            quantity=Decimal('10.0'),
        )
        with pytest.raises(ValidationError, match="ticker_splits is required"):
            adjust_trade_for_splits(trade, None)

    def test_adjust_trade_raises_if_ticker_missing_from_ticker_splits(self):
        """Test that missing ticker in ticker_splits raises ValidationError."""
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trade = Trade(
            date=date(2020, 1, 1),
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=150.0,
            price_native=150.0,
            quantity=Decimal('10.0'),
        )
        ticker_splits = {"AAPL": pd.Series(dtype=float)}
        with pytest.raises(ValidationError, match="ticker_splits must contain an entry for ticker GOOG"):
            adjust_trade_for_splits(trade, ticker_splits)


class TestLotCalculationWithSplits:
    """Tests for lot calculation with split-adjusted trades."""

    def test_lot_uses_adjusted_values(self):
        """Test that lots use adjusted quantity and price."""
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trade = Trade(
            date=date(2024, 1, 15),
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=150.0,
            price_native=150.0,
            quantity=Decimal('10.0'),
            split_adjustment_factor=Decimal('2.0'),  # 2:1 split
        )
        
        lots_by_asset = calculate_lots_from_trades([trade])
        assert asset in lots_by_asset
        lot = lots_by_asset[asset][0]
        
        # Lot should use adjusted values
        assert lot.original_quantity == Decimal('20.0')  # Adjusted
        assert lot.remaining_quantity == Decimal('20.0')  # Adjusted
        assert lot.purchase_price == 75.0  # Adjusted
        assert lot.cost_basis == 1500.0  # 20 * 75 = 1500 (same as original)

    def test_fifo_with_split_adjusted_trades(self):
        """Test FIFO matching with split-adjusted trades."""
        asset = Asset(ticker="GOOG", asset_type="Stock")
        
        # Buy before split (will be adjusted)
        buy_trade = Trade(
            date=date(2020, 1, 1),
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=150.0,
            price_native=150.0,
            quantity=Decimal('10.0'),
            split_adjustment_factor=Decimal('2.0'),  # 2:1 split
        )
        
        # Sell after split (will be adjusted)
        sell_trade = Trade(
            date=date(2021, 1, 1),
            asset=asset,
            action="Sell",
            broker="IBKR",
            currency="USD",
            price=100.0,
            price_native=100.0,
            quantity=Decimal('5.0'),
            split_adjustment_factor=Decimal('2.0'),  # Same split applies
        )
        
        lots_by_asset = calculate_lots_from_trades([buy_trade, sell_trade])
        assert asset in lots_by_asset
        lot = lots_by_asset[asset][0]
        
        # Buy: 10 * 2 = 20 shares @ $75
        # Sell: 5 * 2 = 10 shares
        # Remaining: 20 - 10 = 10 shares
        assert lot.remaining_quantity == Decimal('10.0')
        assert len(lot.matched_sells) == 1
        assert lot.matched_sells[0][1] == Decimal('10.0')  # Adjusted quantity sold

    def test_position_with_split_adjusted_lots(self):
        """Test position calculation with split-adjusted lots."""
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trade = Trade(
            date=date(2024, 1, 15),
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=150.0,
            price_native=150.0,
            quantity=Decimal('10.0'),
            split_adjustment_factor=Decimal('2.0'),
        )
        
        positions = calculate_fifo_cost_basis([trade])
        position = positions[asset]
        
        # Position should reflect adjusted quantity
        assert position.quantity == Decimal('20.0')  # Adjusted
        assert position.cost_basis == 1500.0  # 20 * 75 = 1500 (unchanged)


class TestHistoricalPerformanceWithSplits:
    """Tests for historical performance with split-adjusted trades."""

    def test_historical_performance_uses_adjusted_values(self):
        """Test that historical performance uses adjusted values."""
        asset = Asset(ticker="GOOG", asset_type="Stock")
        
        # Trade before split
        # Note: split_adjustment_factor will be recalculated for historical date
        trade = Trade(
            date=date(2020, 1, 1),
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=150.0,
            price_native=150.0,
            quantity=Decimal('10.0'),
            split_adjustment_factor=Decimal('1.0'),  # Will be recalculated
        )
        
        portfolio = SimplePortfolio("Test")
        portfolio.add_trade(trade)
        
        # Mock price service
        price_service = Mock()
        
        # Historical price after split: $100 (post-split price)
        price_service.get_historical_prices.return_value = {
            "GOOG": {
                date(2021, 1, 1): 100.0
            }
        }
        
        # Mock SplitService: prefetch returns 2:1 split data; pure function yields factor 2.0 for trade date, 1.0 for price scale (no splits after history date)
        split_service = Mock(spec=SplitService)
        goog_splits = pd.Series([2.0], index=[pd.Timestamp("2020-06-15")])
        split_service.get_splits.return_value = {"GOOG": goog_splits}

        # Calculate historical performance
        history = get_historical_performance(
            portfolio, price_service, date(2021, 1, 1), date(2021, 1, 1),
            split_service=split_service
        )
        
        assert len(history) == 1
        point = history[0]
        
        # Position should be 20 shares (adjusted)
        # Market value = 20 * 100 = 2000
        assert point.quantities["GOOG"] == 20.0
        assert point.asset_positions["GOOG"] == 2000.0
        
        # Cost basis = 20 * 75 = 1500
        # Unrealized P/L = 2000 - 1500 = 500
        # Percentage return = (500 / 1500) * 100 = 33.33%
        assert point.percentage_return == pytest.approx(33.33, abs=0.1)


class TestMultipleSplits:
    """Tests for multiple splits over time."""

    def test_multiple_forward_splits(self):
        """Test trade with multiple forward splits."""
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trade = Trade(
            date=date(2020, 1, 1),
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=150.0,
            price_native=150.0,
            quantity=Decimal('10.0'),
            split_adjustment_factor=Decimal('6.0'),  # 2:1 then 3:1 = 6.0
        )
        
        assert trade.adjusted_quantity == Decimal('60.0')  # 10 * 6
        assert trade.adjusted_price == 25.0  # 150 / 6
        assert trade.total_value == 1500.0  # Unchanged

    def test_forward_then_reverse_split(self):
        """Test trade with forward split followed by reverse split."""
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trade = Trade(
            date=date(2020, 1, 1),
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=100.0,
            price_native=100.0,
            quantity=Decimal('10.0'),
            split_adjustment_factor=Decimal('1.0'),  # 2:1 then 1:2 = 1.0 (net no change)
        )
        
        assert trade.adjusted_quantity == Decimal('10.0')  # No net change
        assert trade.adjusted_price == 100.0  # No net change
