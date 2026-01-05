"""Tests for Lot model and lot calculations."""

import pytest
from datetime import date
from decimal import Decimal

from wpm.cost_basis import calculate_lots_from_trades
from wpm.models import Asset, Lot, Trade, ValidationError


class TestLotModel:
    """Tests for Lot dataclass."""

    def test_create_lot(self):
        """Test creating a lot."""
        asset = Asset(ticker="VOO", asset_type="ETF")
        lot = Lot(
            purchase_date=date(2025, 10, 1),
            purchase_price=600.0,
            original_quantity=Decimal('2'),
            remaining_quantity=Decimal('1'),
            cost_basis=1200.0,
            asset=asset,
            broker="IBKR",
            matched_sells=[],
        )

        assert lot.purchase_date == date(2025, 10, 1)
        assert lot.purchase_price == 600.0
        assert lot.original_quantity == Decimal('2')
        assert lot.remaining_quantity == Decimal('1')
        assert lot.cost_basis == 1200.0
        assert lot.asset == asset
        assert lot.broker == "IBKR"
        assert lot.matched_sells == []

    def test_lot_validation_negative_remaining_quantity(self):
        """Test lot validation rejects negative remaining quantity."""
        asset = Asset(ticker="VOO", asset_type="ETF")
        with pytest.raises(ValidationError, match="Remaining quantity must be a non-negative number"):
            Lot(
                purchase_date=date(2025, 10, 1),
                purchase_price=600.0,
                original_quantity=Decimal('2'),
                remaining_quantity=Decimal('-1'),
                cost_basis=1200.0,
                asset=asset,
                broker="IBKR",
            )

    def test_lot_validation_remaining_exceeds_original(self):
        """Test lot validation rejects remaining quantity exceeding original."""
        asset = Asset(ticker="VOO", asset_type="ETF")
        with pytest.raises(ValidationError, match="Remaining quantity cannot exceed original quantity"):
            Lot(
                purchase_date=date(2025, 10, 1),
                purchase_price=600.0,
                original_quantity=Decimal('2'),
                remaining_quantity=Decimal('3'),
                cost_basis=1200.0,
                asset=asset,
                broker="IBKR",
            )

    def test_lot_validation_invalid_broker_empty_string(self):
        """Test lot validation rejects empty broker string."""
        asset = Asset(ticker="VOO", asset_type="ETF")
        with pytest.raises(ValidationError, match="Broker must be a non-empty string"):
            Lot(
                purchase_date=date(2025, 10, 1),
                purchase_price=600.0,
                original_quantity=Decimal('2'),
                remaining_quantity=Decimal('2'),
                cost_basis=1200.0,
                asset=asset,
                broker="",
            )

    def test_lot_get_realized_pnl_no_sells(self):
        """Test realized P/L calculation with no matched sells."""
        asset = Asset(ticker="VOO", asset_type="ETF")
        lot = Lot(
            purchase_date=date(2025, 10, 1),
            purchase_price=600.0,
            original_quantity=Decimal('2'),
            remaining_quantity=Decimal('2'),
            cost_basis=1200.0,
            asset=asset,
            broker="IBKR",
            matched_sells=[],
        )

        assert lot.get_realized_pnl() == 0.0

    def test_lot_get_realized_pnl_with_sells(self):
        """Test realized P/L calculation with matched sells."""
        asset = Asset(ticker="VOO", asset_type="ETF")
        sell_trade = Trade(
            date=date(2025, 12, 1),
            asset=asset,
            action="Sell",
            broker="IBKR",
            currency="USD",
            price=620.0,
            price_native=620.0,
            quantity=Decimal('1'),
        )

        lot = Lot(
            purchase_date=date(2025, 10, 1),
            purchase_price=600.0,
            original_quantity=Decimal('2'),
            remaining_quantity=Decimal('1'),
            cost_basis=1200.0,
            asset=asset,
            broker="IBKR",
            matched_sells=[(sell_trade, Decimal('1'))],
        )

        # Realized P/L: 1 * (620 - 600) = 20
        assert lot.get_realized_pnl() == 20.0

    def test_lot_get_unrealized_pnl(self):
        """Test unrealized P/L calculation."""
        asset = Asset(ticker="VOO", asset_type="ETF")
        lot = Lot(
            purchase_date=date(2025, 10, 1),
            purchase_price=600.0,
            original_quantity=Decimal('2'),
            remaining_quantity=Decimal('1'),
            cost_basis=1200.0,
            asset=asset,
            broker="IBKR",
        )

        # Unrealized P/L: 1 * (630 - 600) = 30
        assert lot.get_unrealized_pnl(630.0) == 30.0

    def test_lot_get_total_pnl(self):
        """Test total P/L calculation (realized + unrealized)."""
        asset = Asset(ticker="VOO", asset_type="ETF")
        sell_trade = Trade(
            date=date(2025, 12, 1),
            asset=asset,
            action="Sell",
            broker="IBKR",
            currency="USD",
            price=620.0,
            price_native=620.0,
            quantity=Decimal('1'),
        )

        lot = Lot(
            purchase_date=date(2025, 10, 1),
            purchase_price=600.0,
            original_quantity=Decimal('2'),
            remaining_quantity=Decimal('1'),
            cost_basis=1200.0,
            asset=asset,
            broker="IBKR",
            matched_sells=[(sell_trade, Decimal('1'))],
        )

        # Realized: 20, Unrealized: 30, Total: 50
        assert lot.get_total_pnl(630.0) == 50.0


class TestLotCalculation:
    """Tests for lot calculation from trades."""

    def test_calculate_lots_single_buy(self):
        """Test calculating lots from a single buy trade."""
        asset = Asset(ticker="VOO", asset_type="ETF")
        trade = Trade(
            date=date(2025, 10, 1),
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=600.0,
            price_native=600.0,
            quantity=Decimal('2'),
        )

        lots_by_asset = calculate_lots_from_trades([trade])
        assert asset in lots_by_asset
        lots = lots_by_asset[asset]
        assert len(lots) == 1

        lot = lots[0]
        assert lot.purchase_date == date(2025, 10, 1)
        assert lot.purchase_price == 600.0
        assert lot.original_quantity == Decimal('2')
        assert lot.remaining_quantity == Decimal('2')
        assert lot.cost_basis == 1200.0
        assert lot.broker == "IBKR"
        assert len(lot.matched_sells) == 0

    def test_calculate_lots_buy_and_sell_fifo(self):
        """Test calculating lots with buy and sell using FIFO."""
        asset = Asset(ticker="VOO", asset_type="ETF")
        trades = [
            Trade(
                date=date(2025, 10, 1),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=600.0,
                price_native=600.0,
                quantity=Decimal('2'),
            ),
            Trade(
                date=date(2025, 11, 1),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=610.0,
                price_native=610.0,
                quantity=Decimal('1'),
            ),
            Trade(
                date=date(2025, 12, 1),
                asset=asset,
                action="Sell",
                broker="IBKR",
                currency="USD",
                price=620.0,
                price_native=620.0,
                quantity=Decimal('1'),
            ),
        ]

        lots_by_asset = calculate_lots_from_trades(trades)
        assert asset in lots_by_asset
        lots = lots_by_asset[asset]
        assert len(lots) == 2

        # First lot: 2 VOO @ $600, 1 sold, 1 remaining
        lot1 = lots[0]
        assert lot1.purchase_date == date(2025, 10, 1)
        assert lot1.purchase_price == 600.0
        assert lot1.original_quantity == Decimal('2')
        assert lot1.remaining_quantity == Decimal('1')
        assert lot1.broker == "IBKR"
        assert len(lot1.matched_sells) == 1
        assert lot1.matched_sells[0][1] == Decimal('1')  # quantity sold
        assert lot1.get_realized_pnl() == 20.0  # 1 * (620 - 600)

        # Second lot: 1 VOO @ $610, 0 sold, 1 remaining
        lot2 = lots[1]
        assert lot2.purchase_date == date(2025, 11, 1)
        assert lot2.purchase_price == 610.0
        assert lot2.original_quantity == Decimal('1')
        assert lot2.remaining_quantity == Decimal('1')
        assert lot2.broker == "IBKR"
        assert len(lot2.matched_sells) == 0
        assert lot2.get_realized_pnl() == 0.0

    def test_calculate_lots_multiple_sells_fifo(self):
        """Test calculating lots with multiple sells using FIFO."""
        asset = Asset(ticker="VOO", asset_type="ETF")
        trades = [
            Trade(
                date=date(2025, 10, 1),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=600.0,
                price_native=600.0,
                quantity=Decimal('3'),
            ),
            Trade(
                date=date(2025, 11, 1),
                asset=asset,
                action="Sell",
                broker="IBKR",
                currency="USD",
                price=620.0,
                price_native=620.0,
                quantity=Decimal('1'),
            ),
            Trade(
                date=date(2025, 12, 1),
                asset=asset,
                action="Sell",
                broker="IBKR",
                currency="USD",
                price=630.0,
                price_native=630.0,
                quantity=Decimal('1'),
            ),
        ]

        lots_by_asset = calculate_lots_from_trades(trades)
        assert asset in lots_by_asset
        lots = lots_by_asset[asset]
        assert len(lots) == 1

        lot = lots[0]
        assert lot.original_quantity == Decimal('3')
        assert lot.remaining_quantity == Decimal('1')
        assert lot.broker == "IBKR"
        assert len(lot.matched_sells) == 2
        # First sell: 1 @ 620
        assert lot.matched_sells[0][0].price == 620.0
        assert lot.matched_sells[0][1] == Decimal('1')
        # Second sell: 1 @ 630
        assert lot.matched_sells[1][0].price == 630.0
        assert lot.matched_sells[1][1] == Decimal('1')
        # Total realized: 1 * (620 - 600) + 1 * (630 - 600) = 20 + 30 = 50
        assert lot.get_realized_pnl() == 50.0

    def test_calculate_lots_empty_trades(self):
        """Test calculating lots from empty trade list."""
        lots_by_asset = calculate_lots_from_trades([])
        assert lots_by_asset == {}

    def test_calculate_lots_caching(self):
        """Test that lot calculation uses caching."""
        asset = Asset(ticker="VOO", asset_type="ETF")
        trades = [
            Trade(
                date=date(2025, 10, 1),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=600.0,
                price_native=600.0,
                quantity=Decimal('2'),
            ),
        ]

        # First call - cache miss
        lots1 = calculate_lots_from_trades(trades)
        # Second call with same trades - should use cache
        lots2 = calculate_lots_from_trades(trades)

        # Results should be the same
        assert len(lots1) == len(lots2)
        assert asset in lots1 and asset in lots2
        assert len(lots1[asset]) == len(lots2[asset])

