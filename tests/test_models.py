"""Tests for core data models."""

import pytest
from datetime import date, timedelta
from decimal import Decimal

from wpm.models import Asset, Position, Trade, ValidationError


class TestAsset:
    """Tests for Asset model."""

    def test_asset_creation_valid(self):
        """Test creating valid asset."""
        asset = Asset(ticker="GOOG", asset_type="Stock")
        assert asset.ticker == "GOOG"
        assert asset.asset_type == "Stock"

    def test_asset_type_normalization(self):
        """Test asset type normalization."""
        asset = Asset(ticker="GOOG", asset_type="stock")
        assert asset.asset_type == "Stock"

        asset = Asset(ticker="GOOG", asset_type="EQUITY")
        assert asset.asset_type == "Stock"

    def test_asset_equality(self):
        """Test asset equality comparison."""
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        asset2 = Asset(ticker="GOOG", asset_type="Stock")
        asset3 = Asset(ticker="GOOG", asset_type="ETF")

        assert asset1 == asset2
        assert asset1 != asset3

    def test_asset_hashable(self):
        """Test asset is hashable."""
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        asset2 = Asset(ticker="GOOG", asset_type="Stock")

        asset_set = {asset1, asset2}
        assert len(asset_set) == 1

    def test_asset_invalid_ticker(self):
        """Test asset with invalid ticker."""
        with pytest.raises(ValidationError):
            Asset(ticker="", asset_type="Stock")

        with pytest.raises(ValidationError):
            Asset(ticker="GOO G", asset_type="Stock")

    def test_asset_invalid_type(self):
        """Test asset with invalid type."""
        with pytest.raises(ValidationError):
            Asset(ticker="GOOG", asset_type="Invalid")


class TestTrade:
    """Tests for Trade model."""

    def test_trade_creation_valid(self):
        """Test creating valid trade."""
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trade = Trade(
            date=date(2024, 1, 15),
            asset=asset,
            action="Buy",
            broker="IBKR",
            price=150.0,
            quantity=10.0,
        )

        assert trade.date == date(2024, 1, 15)
        assert trade.action == "Buy"
        assert trade.price == 150.0
        assert trade.quantity == Decimal('10.0')

    def test_trade_action_normalization(self):
        """Test trade action normalization."""
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trade1 = Trade(
            date=date(2024, 1, 15),
            asset=asset,
            action="buy",
            broker="IBKR",
            price=150.0,
            quantity=10.0,
        )
        assert trade1.action == "Buy"

        trade2 = Trade(
            date=date(2024, 1, 15),
            asset=asset,
            action="SELL",
            broker="IBKR",
            price=160.0,
            quantity=5.0,
        )
        assert trade2.action == "Sell"

    def test_trade_total_value(self):
        """Test trade total value calculation."""
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trade = Trade(
            date=date(2024, 1, 15),
            asset=asset,
            action="Buy",
            broker="IBKR",
            price=150.0,
            quantity=10.0,
        )

        assert trade.total_value == 1500.0

    def test_trade_is_buy_sell(self):
        """Test trade is_buy and is_sell methods."""
        asset = Asset(ticker="GOOG", asset_type="Stock")
        buy_trade = Trade(
            date=date(2024, 1, 15),
            asset=asset,
            action="Buy",
            broker="IBKR",
            price=150.0,
            quantity=10.0,
        )
        sell_trade = Trade(
            date=date(2024, 2, 15),
            asset=asset,
            action="Sell",
            broker="IBKR",
            price=160.0,
            quantity=5.0,
        )

        assert buy_trade.is_buy()
        assert not buy_trade.is_sell()
        assert sell_trade.is_sell()
        assert not sell_trade.is_buy()

    def test_trade_future_date(self):
        """Test trade with future date raises error."""
        asset = Asset(ticker="GOOG", asset_type="Stock")
        future_date = date.today() + timedelta(days=1)

        with pytest.raises(ValidationError):
            Trade(
                date=future_date,
                asset=asset,
                action="Buy",
                broker="IBKR",
                price=150.0,
                quantity=10.0,
            )

    def test_trade_invalid_price(self):
        """Test trade with invalid price."""
        asset = Asset(ticker="GOOG", asset_type="Stock")

        with pytest.raises(ValidationError):
            Trade(
                date=date(2024, 1, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                price=-10.0,
                quantity=10.0,
            )

        with pytest.raises(ValidationError):
            Trade(
                date=date(2024, 1, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                price=0.0,
                quantity=10.0,
            )

    def test_trade_invalid_quantity(self):
        """Test trade with invalid quantity."""
        asset = Asset(ticker="GOOG", asset_type="Stock")

        with pytest.raises(ValidationError):
            Trade(
                date=date(2024, 1, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                price=150.0,
                quantity=-10.0,
            )

    def test_trade_optional_order_type(self):
        """Test trade with optional order_type."""
        asset = Asset(ticker="GOOG", asset_type="Stock")

        trade_with_type = Trade(
            date=date(2024, 1, 15),
            asset=asset,
            action="Buy",
            broker="IBKR",
            order_type="Limit",
            price=150.0,
            quantity=10.0,
        )
        assert trade_with_type.order_type == "Limit"

        trade_without_type = Trade(
            date=date(2024, 1, 15),
            asset=asset,
            action="Buy",
            broker="IBKR",
            price=150.0,
            quantity=10.0,
        )
        assert trade_without_type.order_type is None


class TestPosition:
    """Tests for Position model."""

    def test_position_creation_valid(self):
        """Test creating valid position."""
        asset = Asset(ticker="GOOG", asset_type="Stock")
        position = Position(
            asset=asset,
            quantity=10.0,
            cost_basis=1500.0,
            cost_basis_method="fifo",
        )

        assert position.quantity == Decimal('10.0')
        assert position.cost_basis == 1500.0
        assert position.cost_basis_method == "fifo"

    def test_position_average_cost(self):
        """Test position average cost calculation."""
        asset = Asset(ticker="GOOG", asset_type="Stock")
        position = Position(
            asset=asset,
            quantity=10.0,
            cost_basis=1500.0,
            cost_basis_method="fifo",
        )

        assert position.get_average_cost() == 150.0
        assert position.average_cost == 150.0

    def test_position_average_cost_zero_quantity(self):
        """Test position average cost with zero quantity."""
        asset = Asset(ticker="GOOG", asset_type="Stock")
        position = Position(
            asset=asset,
            quantity=0.0,
            cost_basis=0.0,
            cost_basis_method="fifo",
        )

        assert position.get_average_cost() == 0.0

    def test_position_invalid_method(self):
        """Test position with invalid cost basis method."""
        asset = Asset(ticker="GOOG", asset_type="Stock")

        with pytest.raises(ValidationError):
            Position(
                asset=asset,
                quantity=10.0,
                cost_basis=1500.0,
                cost_basis_method="invalid",
            )

    def test_position_negative_quantity(self):
        """Test position with negative quantity."""
        asset = Asset(ticker="GOOG", asset_type="Stock")

        with pytest.raises(ValidationError):
            Position(
                asset=asset,
                quantity=-10.0,
                cost_basis=1500.0,
                cost_basis_method="fifo",
            )

