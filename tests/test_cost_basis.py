"""Tests for cost basis calculation methods."""

import pytest
from datetime import date
from decimal import Decimal

from wpm.cost_basis import calculate_average_cost_basis, calculate_fifo_cost_basis
from wpm.models import Asset, Trade


class TestFIFOCostBasis:
    """Tests for FIFO cost basis calculation."""

    def test_simple_buy(self):
        """Test FIFO with a single buy."""
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trade = Trade(
            date=date(2024, 1, 15),
            asset=asset,
            action="Buy",
            broker="IBKR",
            price=150.0,
            quantity=10.0,
        )

        positions = calculate_fifo_cost_basis([trade])
        assert asset in positions
        position = positions[asset]

        assert position.quantity == Decimal('10.0')
        assert position.cost_basis == 1500.0
        assert position.cost_basis_method == "fifo"
        assert position.average_cost == 150.0

    def test_multiple_buys_same_asset(self):
        """Test FIFO with multiple buys of the same asset."""
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trades = [
            Trade(
                date=date(2024, 1, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                price=150.0,
                quantity=10.0,
            ),
            Trade(
                date=date(2024, 2, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                price=160.0,
                quantity=5.0,
            ),
        ]

        positions = calculate_fifo_cost_basis(trades)
        position = positions[asset]

        assert position.quantity == Decimal('15.0')
        assert position.cost_basis == 2300.0  # 10*150 + 5*160
        assert position.average_cost == pytest.approx(153.33, abs=0.01)

    def test_buy_and_sell_fifo(self):
        """Test FIFO with buy followed by sell."""
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trades = [
            Trade(
                date=date(2024, 1, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                price=150.0,
                quantity=10.0,
            ),
            Trade(
                date=date(2024, 2, 15),
                asset=asset,
                action="Sell",
                broker="IBKR",
                price=160.0,
                quantity=5.0,
            ),
        ]

        positions = calculate_fifo_cost_basis(trades)
        position = positions[asset]

        assert position.quantity == Decimal('5.0')
        assert position.cost_basis == 750.0  # Remaining 5 shares at $150 each
        assert position.average_cost == 150.0

    def test_multiple_buys_partial_sell_fifo(self):
        """Test FIFO with multiple buys and partial sell."""
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trades = [
            Trade(
                date=date(2024, 1, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                price=150.0,
                quantity=10.0,
            ),
            Trade(
                date=date(2024, 2, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                price=160.0,
                quantity=5.0,
            ),
            Trade(
                date=date(2024, 3, 15),
                asset=asset,
                action="Sell",
                broker="IBKR",
                price=170.0,
                quantity=8.0,
            ),
        ]

        positions = calculate_fifo_cost_basis(trades)
        position = positions[asset]

        assert position.quantity == Decimal('7.0')
        # Sold 8 shares: 10@150 + 5@160, so 8@150 were sold, remaining: 2@150 + 5@160
        assert position.cost_basis == pytest.approx(1100.0, abs=0.01)  # 2*150 + 5*160

    def test_multiple_assets(self):
        """Test FIFO with multiple different assets."""
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        asset2 = Asset(ticker="AAPL", asset_type="Stock")
        trades = [
            Trade(
                date=date(2024, 1, 15),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                price=150.0,
                quantity=10.0,
            ),
            Trade(
                date=date(2024, 1, 16),
                asset=asset2,
                action="Buy",
                broker="IBKR",
                price=200.0,
                quantity=5.0,
            ),
        ]

        positions = calculate_fifo_cost_basis(trades)
        assert len(positions) == 2

        assert positions[asset1].quantity == Decimal('10.0')
        assert positions[asset1].cost_basis == 1500.0

        assert positions[asset2].quantity == Decimal('5.0')
        assert positions[asset2].cost_basis == 1000.0

    def test_sell_more_than_owned(self):
        """Test FIFO when selling more than owned raises validation error."""
        # When selling more than owned, the calculation would result in
        # negative quantity, which Position validation disallows.
        from wpm.models import ValidationError
        
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trades = [
            Trade(
                date=date(2024, 1, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                price=150.0,
                quantity=10.0,
            ),
            Trade(
                date=date(2024, 2, 15),
                asset=asset,
                action="Sell",
                broker="IBKR",
                price=160.0,
                quantity=15.0,  # More than owned
            ),
        ]

        # This should raise ValidationError because position quantity would be negative
        with pytest.raises(ValidationError, match="Quantity must be a non-negative number"):
            calculate_fifo_cost_basis(trades)


class TestAverageCostBasis:
    """Tests for Average Cost basis calculation."""

    def test_simple_buy(self):
        """Test Average Cost with a single buy."""
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trade = Trade(
            date=date(2024, 1, 15),
            asset=asset,
            action="Buy",
            broker="IBKR",
            price=150.0,
            quantity=10.0,
        )

        positions = calculate_average_cost_basis([trade])
        assert asset in positions
        position = positions[asset]

        assert position.quantity == Decimal('10.0')
        assert position.cost_basis == 1500.0
        assert position.cost_basis_method == "average"
        assert position.average_cost == 150.0

    def test_multiple_buys_average_cost(self):
        """Test Average Cost with multiple buys."""
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trades = [
            Trade(
                date=date(2024, 1, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                price=150.0,
                quantity=10.0,
            ),
            Trade(
                date=date(2024, 2, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                price=160.0,
                quantity=5.0,
            ),
        ]

        positions = calculate_average_cost_basis(trades)
        position = positions[asset]

        assert position.quantity == Decimal('15.0')
        assert position.cost_basis == 2300.0  # 10*150 + 5*160
        assert position.average_cost == pytest.approx(153.33, abs=0.01)

    def test_buy_and_sell_average_cost(self):
        """Test Average Cost with buy followed by sell."""
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trades = [
            Trade(
                date=date(2024, 1, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                price=150.0,
                quantity=10.0,
            ),
            Trade(
                date=date(2024, 2, 15),
                asset=asset,
                action="Sell",
                broker="IBKR",
                price=160.0,
                quantity=5.0,
            ),
        ]

        positions = calculate_average_cost_basis(trades)
        position = positions[asset]

        assert position.quantity == Decimal('5.0')
        assert position.cost_basis == 750.0  # 5 shares * $150 average cost
        assert position.average_cost == 150.0  # Average cost maintained

    def test_multiple_buys_partial_sell_average_cost(self):
        """Test Average Cost with multiple buys and partial sell."""
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trades = [
            Trade(
                date=date(2024, 1, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                price=150.0,
                quantity=10.0,
            ),
            Trade(
                date=date(2024, 2, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                price=160.0,
                quantity=5.0,
            ),
            Trade(
                date=date(2024, 3, 15),
                asset=asset,
                action="Sell",
                broker="IBKR",
                price=170.0,
                quantity=8.0,
            ),
        ]

        positions = calculate_average_cost_basis(trades)
        position = positions[asset]

        assert position.quantity == Decimal('7.0')
        # Average cost was 153.33, sold 8 shares
        # Remaining cost basis: (15*153.33) - (8*153.33) = 7*153.33
        assert position.cost_basis == pytest.approx(1073.33, abs=0.01)
        assert position.average_cost == pytest.approx(153.33, abs=0.01)

    def test_sell_with_no_position(self):
        """Test Average Cost when selling with no position."""
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trades = [
            Trade(
                date=date(2024, 1, 15),
                asset=asset,
                action="Sell",
                broker="IBKR",
                price=160.0,
                quantity=5.0,
            ),
        ]

        positions = calculate_average_cost_basis(trades)
        assert asset not in positions or positions[asset].quantity == Decimal('0')

    def test_empty_trades(self):
        """Test cost basis calculation with empty trade list."""
        positions_fifo = calculate_fifo_cost_basis([])
        assert positions_fifo == {}

        positions_avg = calculate_average_cost_basis([])
        assert positions_avg == {}

