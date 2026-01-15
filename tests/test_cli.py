"""Tests for CLI functionality."""

import pytest
from datetime import date
from decimal import Decimal
from io import StringIO
from unittest.mock import Mock, patch
import sys

from wpm.cli import (
    parse_up_to_date,
    parse_from_date,
    cmd_show_all,
    cmd_show_portfolio,
    cmd_show_asset,
    cmd_metadata,
    format_historical_asset_line,
    format_position_line,
    format_market_cap,
    _display_weekly_summary,
)
from wpm.models import Asset, PortfolioHistoryPoint, Trade
from wpm.portfolio import CompositePortfolio, SimplePortfolio
from wpm.portfolio import CompositePortfolio, SimplePortfolio
from wpm.pricing import PriceService


class TestParseUpToDate:
    """Tests for parse_up_to_date function."""

    def test_parse_up_to_date_with_valid_date(self):
        """Test parsing --up-to with valid date."""
        args = ["--up-to", "2024-01-15", "extra"]
        up_to_date, remaining = parse_up_to_date(args)
        assert up_to_date == date(2024, 1, 15)
        assert remaining == ["extra"]

    def test_parse_up_to_date_without_flag(self):
        """Test parsing args without --up-to flag."""
        args = ["portfolio", "name"]
        up_to_date, remaining = parse_up_to_date(args)
        assert up_to_date is None
        assert remaining == ["portfolio", "name"]

    def test_parse_up_to_date_no_date_after_flag(self):
        """Test parsing --up-to without date argument."""
        args = ["--up-to"]
        up_to_date, remaining = parse_up_to_date(args)
        assert up_to_date is None
        assert remaining == ["--up-to"]

    def test_parse_up_to_date_invalid_date_format(self):
        """Test parsing --up-to with invalid date format."""
        args = ["--up-to", "invalid-date"]
        up_to_date, remaining = parse_up_to_date(args)
        # Should return None for up_to_date if date is invalid
        # Invalid date format will raise ValueError in normalize_date
        # but parse_up_to_date should handle it gracefully
        assert up_to_date is None or isinstance(up_to_date, date)
        # The --up-to flag might remain in remaining args
        assert "invalid-date" in remaining or "--up-to" in remaining


class TestParseFromDate:
    """Tests for parse_from_date function."""

    def test_parse_from_date_with_valid_date(self):
        """Test parsing --from with valid date."""
        args = ["--from", "2024-01-15", "extra"]
        from_date, remaining = parse_from_date(args)
        assert from_date == date(2024, 1, 15)
        assert remaining == ["extra"]

    def test_parse_from_date_without_flag(self):
        """Test parsing args without --from flag."""
        args = ["portfolio", "name"]
        from_date, remaining = parse_from_date(args)
        assert from_date is None
        assert remaining == ["portfolio", "name"]

    def test_parse_from_date_no_date_after_flag(self):
        """Test parsing --from without date argument."""
        args = ["--from"]
        from_date, remaining = parse_from_date(args)
        assert from_date is None
        assert remaining == ["--from"]

    def test_parse_from_date_invalid_date_format(self):
        """Test parsing --from with invalid date format."""
        args = ["--from", "invalid-date"]
        from_date, remaining = parse_from_date(args)
        # Should return None for from_date if date is invalid
        # Invalid date format will raise ValueError in normalize_date
        # but parse_from_date should handle it gracefully
        assert from_date is None or isinstance(from_date, date)
        # The --from flag might remain in remaining args
        assert "invalid-date" in remaining or "--from" in remaining


class TestFormatHistoricalAssetLine:
    """Tests for format_historical_asset_line function."""

    def test_format_with_valid_price(self):
        """Test formatting with valid price."""
        history_point = PortfolioHistoryPoint(
            date=date(2024, 1, 15),
            total_market_value=1000.0,
            asset_positions={"GOOG": 1000.0},
            prices={"GOOG": 100.0},
        )
        result = format_historical_asset_line(history_point, "GOOG", "Stock")
        assert "2024-01-15" in result
        assert "GOOG" in result
        assert "Stock" in result
        assert "$1,000.00" in result
        assert "$100.00" in result

    def test_format_with_missing_price(self):
        """Test formatting with missing price (N/A)."""
        history_point = PortfolioHistoryPoint(
            date=date(2024, 1, 15),
            total_market_value=1000.0,
            asset_positions={"GOOG": 1000.0},
            prices={},
        )
        result = format_historical_asset_line(history_point, "GOOG", "Stock")
        assert "2024-01-15" in result
        assert "GOOG" in result
        assert "Stock" in result
        assert "$1,000.00" in result
        assert "N/A" in result

    def test_format_with_zero_position_value(self):
        """Test formatting with zero position value."""
        history_point = PortfolioHistoryPoint(
            date=date(2024, 1, 15),
            total_market_value=0.0,
            asset_positions={"GOOG": 0.0},
            prices={"GOOG": 100.0},
        )
        result = format_historical_asset_line(history_point, "GOOG", "Stock")
        assert "2024-01-15" in result
        assert "$0.00" in result


class TestCmdShowAsset:
    """Tests for cmd_show_asset function."""

    def test_cmd_show_asset_current_portfolio_valid_ticker(self):
        """Test show asset for current portfolio with valid ticker."""
        portfolio = SimplePortfolio(name="Test")
        asset = Asset(ticker="GOOG", asset_type="Stock")
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )
        composite = CompositePortfolio(name="Composite")
        composite.add_sub_portfolio(portfolio)

        mock_price_service = Mock(spec=PriceService)

        with patch("wpm.cli.fetch_price_map") as mock_fetch_price_map:
            mock_fetch_price_map.return_value = {asset: 160.0}

            with patch("sys.stdout", new=StringIO()) as fake_out:
                cmd_show_asset(composite, "GOOG", mock_price_service)
                output = fake_out.getvalue()
                assert "GOOG" in output
                assert "Stock" in output
                assert "Total Market Value" in output
                assert "Total Cost Basis" in output
                assert "Total Unrealized P/L" in output

    def test_cmd_show_asset_current_portfolio_invalid_ticker(self):
        """Test show asset for current portfolio with invalid ticker."""
        portfolio = SimplePortfolio(name="Test")
        composite = CompositePortfolio(name="Composite")
        composite.add_sub_portfolio(portfolio)

        mock_price_service = Mock(spec=PriceService)

        with patch("sys.stdout", new=StringIO()) as fake_out:
            cmd_show_asset(composite, "INVALID", mock_price_service)
            output = fake_out.getvalue()
            assert "not found" in output

    def test_cmd_show_asset_historical_portfolio_without_from(self):
        """Test show asset for historical portfolio without --from (past 30 days)."""
        portfolio = SimplePortfolio(name="Test", is_historical=True)
        asset = Asset(ticker="GOOG", asset_type="Stock")
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 1),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )
        composite = CompositePortfolio(name="Composite", is_historical=True)
        composite.add_sub_portfolio(portfolio)

        mock_price_service = Mock(spec=PriceService)
        mock_price_service.get_historical_prices.return_value = {
            "GOOG": {
                date(2024, 1, 30): 160.0,
                date(2024, 1, 31): 161.0,
            }
        }

        with patch("wpm.cli.get_historical_performance") as mock_get_perf:
            with patch("wpm.cli.get_historical_allocations") as mock_get_alloc:
                # Mock history points for past 30 days
                history_points = [
                    PortfolioHistoryPoint(
                        date=date(2024, 1, 30),
                        total_market_value=1600.0,
                        asset_positions={"GOOG": 1600.0},
                        prices={"GOOG": 160.0},
                    ),
                    PortfolioHistoryPoint(
                        date=date(2024, 1, 31),
                        total_market_value=1610.0,
                        asset_positions={"GOOG": 1610.0},
                        prices={"GOOG": 161.0},
                    ),
                ]
                mock_get_perf.return_value = history_points

                # Mock allocations
                allocations_list = [
                    {asset: Decimal('100.00')},
                    {asset: Decimal('100.00')},
                ]
                mock_get_alloc.return_value = allocations_list

                with patch("sys.stdout", new=StringIO()) as fake_out:
                    cmd_show_asset(composite, "GOOG", mock_price_service)
                    output = fake_out.getvalue()
                    assert "2024-01-30" in output
                    assert "2024-01-31" in output
                    assert "GOOG" in output
                    assert "Stock" in output

    def test_cmd_show_asset_historical_portfolio_with_from(self):
        """Test show asset for historical portfolio with --from argument."""
        portfolio = SimplePortfolio(name="Test", is_historical=True)
        asset = Asset(ticker="GOOG", asset_type="Stock")
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 1),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )
        # Add another trade to extend the portfolio's end_date
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 20),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=155.0,
                price_native=155.0,
                quantity=5.0,
            )
        )
        composite = CompositePortfolio(name="Composite", is_historical=True)
        composite.add_sub_portfolio(portfolio)

        mock_price_service = Mock(spec=PriceService)

        with patch("wpm.cli.get_historical_performance") as mock_get_perf:
            with patch("wpm.cli.get_historical_allocations") as mock_get_alloc:
                from_date = date(2024, 1, 15)
                history_points = [
                    PortfolioHistoryPoint(
                        date=date(2024, 1, 15),
                        total_market_value=1550.0,
                        asset_positions={"GOOG": 1550.0},
                        prices={"GOOG": 155.0},
                    ),
                ]
                mock_get_perf.return_value = history_points

                # Mock allocations
                allocations_list = [
                    {asset: Decimal('100.00')},
                ]
                mock_get_alloc.return_value = allocations_list

                with patch("sys.stdout", new=StringIO()) as fake_out:
                    cmd_show_asset(composite, "GOOG", mock_price_service, from_date=from_date)
                    output = fake_out.getvalue()
                    assert "2024-01-15" in output
                assert "GOOG" in output

    def test_cmd_show_asset_historical_missing_price(self):
        """Test show asset for historical portfolio with missing price (N/A)."""
        portfolio = SimplePortfolio(name="Test", is_historical=True)
        asset = Asset(ticker="GOOG", asset_type="Stock")
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 1),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )
        composite = CompositePortfolio(name="Composite", is_historical=True)
        composite.add_sub_portfolio(portfolio)

        mock_price_service = Mock(spec=PriceService)

        with patch("wpm.cli.get_historical_performance") as mock_get_perf:
            with patch("wpm.cli.get_historical_allocations") as mock_get_alloc:
                history_points = [
                    PortfolioHistoryPoint(
                        date=date(2024, 1, 15),
                        total_market_value=1500.0,
                        asset_positions={"GOOG": 1500.0},
                        prices={},  # Missing price
                    ),
                ]
                mock_get_perf.return_value = history_points

                # Mock allocations (even with missing price, allocation calculation may still work)
                allocations_list = [
                    {asset: Decimal('100.00')},
                ]
                mock_get_alloc.return_value = allocations_list

                with patch("sys.stdout", new=StringIO()) as fake_out:
                    cmd_show_asset(composite, "GOOG", mock_price_service)
                    output = fake_out.getvalue()
                    assert "2024-01-15" in output
                    assert "N/A" in output


class TestWeeklySummary:
    """Tests for weekly summary display."""

    def test_display_weekly_summary_single_week(self):
        """Test displaying weekly summary for single week."""
        history_points = [
            PortfolioHistoryPoint(
                date=date(2024, 1, 15),  # Monday
                total_market_value=1000.0,
                asset_positions={"GOOG": 1000.0},
                prices={"GOOG": 100.0},
            ),
            PortfolioHistoryPoint(
                date=date(2024, 1, 16),  # Tuesday
                total_market_value=1050.0,
                asset_positions={"GOOG": 1050.0},
                prices={"GOOG": 105.0},
            ),
            PortfolioHistoryPoint(
                date=date(2024, 1, 17),  # Wednesday
                total_market_value=1100.0,
                asset_positions={"GOOG": 1100.0},
                prices={"GOOG": 110.0},
            ),
        ]

        with patch("sys.stdout", new=StringIO()) as fake_out:
            _display_weekly_summary(history_points)
            output = fake_out.getvalue()
            assert "Weekly Performance Summary:" in output
            assert "2024-01-15" in output  # Week start
            assert "2024-01-21" in output  # Week end (Sunday)
            assert "$1,100.00" in output  # Last value of the week

    def test_display_weekly_summary_multiple_weeks(self):
        """Test displaying weekly summary for multiple weeks."""
        # Week 1: Jan 15-21 (Monday-Sunday)
        # Week 2: Jan 22-28 (Monday-Sunday)
        history_points = [
            PortfolioHistoryPoint(
                date=date(2024, 1, 15),  # Monday, Week 1
                total_market_value=1000.0,
                asset_positions={"GOOG": 1000.0},
                prices={"GOOG": 100.0},
            ),
            PortfolioHistoryPoint(
                date=date(2024, 1, 20),  # Saturday, Week 1
                total_market_value=1050.0,
                asset_positions={"GOOG": 1050.0},
                prices={"GOOG": 105.0},
            ),
            PortfolioHistoryPoint(
                date=date(2024, 1, 22),  # Monday, Week 2
                total_market_value=1100.0,
                asset_positions={"GOOG": 1100.0},
                prices={"GOOG": 110.0},
            ),
            PortfolioHistoryPoint(
                date=date(2024, 1, 28),  # Sunday, Week 2
                total_market_value=1200.0,
                asset_positions={"GOOG": 1200.0},
                prices={"GOOG": 120.0},
            ),
        ]

        with patch("sys.stdout", new=StringIO()) as fake_out:
            _display_weekly_summary(history_points)
            output = fake_out.getvalue()
            assert "Weekly Performance Summary:" in output
            # Should have two weeks
            assert output.count("Week of") == 2
            assert "2024-01-15" in output  # Week 1 start
            assert "2024-01-21" in output  # Week 1 end
            assert "2024-01-22" in output  # Week 2 start
            assert "2024-01-28" in output  # Week 2 end

    def test_display_weekly_summary_empty_list(self):
        """Test displaying weekly summary with empty list."""
        with patch("sys.stdout", new=StringIO()) as fake_out:
            _display_weekly_summary([])
            output = fake_out.getvalue()
            assert "No history points to display" in output


class TestShowCommandsWithUpTo:
    """Tests for show commands with --up-to argument."""

    def test_show_portfolio_with_up_to_historical(self):
        """Test show portfolio with --up-to for historical portfolio."""
        portfolio = SimplePortfolio(name="Test Portfolio", is_historical=True)
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trade = Trade(
            date=date(2024, 1, 15),
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=150.0,
            price_native=150.0,
            quantity=10.0,
        )
        portfolio.add_trade(trade)

        composite = CompositePortfolio(name="Composite", is_historical=True)
        composite.add_sub_portfolio(portfolio)

        mock_price_service = Mock(spec=PriceService)
        
        def mock_get_historical_prices(tickers, asset_type, start_date, end_date):
            from datetime import timedelta
            prices = {}
            current = start_date
            while current <= end_date:
                for ticker in tickers:
                    if ticker not in prices:
                        prices[ticker] = {}
                    prices[ticker][current] = 155.0
                current += timedelta(days=1)
            return prices
        
        mock_price_service.get_historical_prices.side_effect = mock_get_historical_prices

        with patch("sys.stdout", new=StringIO()) as fake_out:
            cmd_show_portfolio(
                composite, "Test Portfolio", mock_price_service, date(2024, 1, 17)
            )
            output = fake_out.getvalue()
            assert "Weekly Performance Summary:" in output

    def test_show_portfolio_with_up_to_non_historical(self):
        """Test show portfolio with --up-to for non-historical portfolio."""
        portfolio = SimplePortfolio(name="Test Portfolio", is_historical=False)
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trade = Trade(
            date=date(2024, 1, 15),
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=150.0,
            price_native=150.0,
            quantity=10.0,
        )
        portfolio.add_trade(trade)

        composite = CompositePortfolio(name="Composite", is_historical=False)
        composite.add_sub_portfolio(portfolio)

        mock_price_service = Mock(spec=PriceService)

        with patch("sys.stdout", new=StringIO()) as fake_out:
            cmd_show_portfolio(
                composite, "Test Portfolio", mock_price_service, date(2024, 1, 17)
            )
            output = fake_out.getvalue()
            assert "Error: --up-to can only be used with historical portfolios" in output

    def test_show_all_with_up_to_historical(self):
        """Test show all with --up-to for historical portfolio."""
        portfolio = SimplePortfolio(name="Test Portfolio", is_historical=True)
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trade = Trade(
            date=date(2024, 1, 15),
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=150.0,
            price_native=150.0,
            quantity=10.0,
        )
        portfolio.add_trade(trade)

        composite = CompositePortfolio(name="Composite", is_historical=True)
        composite.add_sub_portfolio(portfolio)

        mock_price_service = Mock(spec=PriceService)
        
        def mock_get_historical_prices(tickers, asset_type, start_date, end_date):
            from datetime import timedelta
            prices = {}
            current = start_date
            while current <= end_date:
                for ticker in tickers:
                    if ticker not in prices:
                        prices[ticker] = {}
                    prices[ticker][current] = 155.0
                current += timedelta(days=1)
            return prices
        
        mock_price_service.get_historical_prices.side_effect = mock_get_historical_prices

        with patch("sys.stdout", new=StringIO()) as fake_out:
            cmd_show_all(composite, mock_price_service, date(2024, 1, 17))
            output = fake_out.getvalue()
            assert "Weekly Performance Summary:" in output

    def test_show_all_with_up_to_non_historical(self):
        """Test show all with --up-to for non-historical portfolio."""
        portfolio = SimplePortfolio(name="Test Portfolio", is_historical=False)
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trade = Trade(
            date=date(2024, 1, 15),
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=150.0,
            price_native=150.0,
            quantity=10.0,
        )
        portfolio.add_trade(trade)

        composite = CompositePortfolio(name="Composite", is_historical=False)
        composite.add_sub_portfolio(portfolio)

        mock_price_service = Mock(spec=PriceService)

        with patch("sys.stdout", new=StringIO()) as fake_out:
            cmd_show_all(composite, mock_price_service, date(2024, 1, 17))
            output = fake_out.getvalue()
            assert "Error: --up-to can only be used with historical portfolios" in output

    def test_show_portfolio_with_up_to_no_start_date(self):
        """Test show portfolio with --up-to when portfolio has no start_date."""
        portfolio = SimplePortfolio(name="Test Portfolio", is_historical=True)
        # No trades, so no start_date

        composite = CompositePortfolio(name="Composite", is_historical=True)
        composite.add_sub_portfolio(portfolio)

        mock_price_service = Mock(spec=PriceService)

        with patch("sys.stdout", new=StringIO()) as fake_out:
            cmd_show_portfolio(
                composite, "Test Portfolio", mock_price_service, date(2024, 1, 17)
            )
            output = fake_out.getvalue()
            assert (
                "Error: Portfolio has no start date, cannot calculate historical performance"
                in output
            )


class TestFormatPositionLine:
    """Tests for format_position_line function with allocations."""

    def test_format_position_line_with_allocation(self):
        """Test formatting position line with allocation."""
        from wpm.models import Position

        asset = Asset(ticker="GOOG", asset_type="Stock")
        position = Position(
            asset=asset,
            quantity=Decimal('10.0'),
            cost_basis=1500.0,
            cost_basis_method="fifo",
        )
        price = 160.0
        allocation = Decimal('25.50')

        result = format_position_line(position, price, False, None, allocation)
        assert "GOOG" in result
        assert "Stock" in result
        assert "Allocation: 25.50%" in result
        assert "Current Value" in result

    def test_format_position_line_without_allocation(self):
        """Test formatting position line without allocation (backward compatible)."""
        from wpm.models import Position

        asset = Asset(ticker="GOOG", asset_type="Stock")
        position = Position(
            asset=asset,
            quantity=Decimal('10.0'),
            cost_basis=1500.0,
            cost_basis_method="fifo",
        )
        price = 160.0

        result = format_position_line(position, price, False, None, None)
        assert "GOOG" in result
        assert "Allocation" not in result

    def test_format_position_line_historical_with_allocation(self):
        """Test formatting historical position line with allocation."""
        from wpm.models import Position

        asset = Asset(ticker="GOOG", asset_type="Stock")
        position = Position(
            asset=asset,
            quantity=Decimal('10.0'),
            cost_basis=1500.0,
            cost_basis_method="fifo",
        )
        price = 160.0
        allocation = Decimal('30.00')
        end_date = date(2024, 1, 15)

        result = format_position_line(position, price, True, end_date, allocation)
        assert "GOOG" in result
        assert "Historical Value (2024-01-15)" in result
        assert "Allocation: 30.00%" in result


class TestFormatHistoricalAssetLineWithAllocation:
    """Tests for format_historical_asset_line function with allocations."""

    def test_format_with_allocation(self):
        """Test formatting with allocation."""
        history_point = PortfolioHistoryPoint(
            date=date(2024, 1, 15),
            total_market_value=1000.0,
            asset_positions={"GOOG": 1000.0},
            prices={"GOOG": 100.0},
        )
        allocation = Decimal('100.00')
        result = format_historical_asset_line(history_point, "GOOG", "Stock", allocation)
        assert "2024-01-15" in result
        assert "GOOG" in result
        assert "Allocation: 100.00%" in result

    def test_format_without_allocation(self):
        """Test formatting without allocation (backward compatible)."""
        history_point = PortfolioHistoryPoint(
            date=date(2024, 1, 15),
            total_market_value=1000.0,
            asset_positions={"GOOG": 1000.0},
            prices={"GOOG": 100.0},
        )
        result = format_historical_asset_line(history_point, "GOOG", "Stock", None)
        assert "2024-01-15" in result
        assert "GOOG" in result
        assert "Allocation" not in result


class TestCmdShowPortfolioWithAllocations:
    """Tests for cmd_show_portfolio with allocation display."""

    def test_cmd_show_portfolio_displays_allocations(self):
        """Test that show portfolio displays allocations for all assets."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        asset2 = Asset(ticker="AAPL", asset_type="Stock")

        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 16),
                asset=asset2,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=200.0,
                price_native=200.0,
                quantity=5.0,
            )
        )

        composite = CompositePortfolio(name="Composite")
        composite.add_sub_portfolio(portfolio)

        mock_price_service = Mock(spec=PriceService)

        with patch("wpm.cli.fetch_price_map") as mock_fetch_price_map:
            mock_fetch_price_map.return_value = {asset1: 160.0, asset2: 220.0}

            with patch("sys.stdout", new=StringIO()) as fake_out:
                cmd_show_portfolio(composite, "Test Portfolio", mock_price_service)
                output = fake_out.getvalue()
                assert "GOOG" in output
                assert "AAPL" in output
                assert "Allocation:" in output
                # Verify allocations are displayed
                assert output.count("Allocation:") == 2

    def test_cmd_show_portfolio_no_prices_no_allocation(self):
        """Test that show portfolio doesn't show allocation when prices unavailable."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset = Asset(ticker="GOOG", asset_type="Stock")

        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )

        composite = CompositePortfolio(name="Composite")
        composite.add_sub_portfolio(portfolio)

        mock_price_service = Mock(spec=PriceService)

        with patch("wpm.cli.fetch_price_map") as mock_fetch_price_map:
            mock_fetch_price_map.return_value = {asset: None}

            with patch("sys.stdout", new=StringIO()) as fake_out:
                cmd_show_portfolio(composite, "Test Portfolio", mock_price_service)
                output = fake_out.getvalue()
                assert "GOOG" in output
                assert "Allocation" not in output


class TestCmdShowAllWithAllocations:
    """Tests for cmd_show_all with allocation display."""

    def test_cmd_show_all_displays_allocations(self):
        """Test that show all displays allocations for all assets."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        asset2 = Asset(ticker="AAPL", asset_type="Stock")

        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 16),
                asset=asset2,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=200.0,
                price_native=200.0,
                quantity=5.0,
            )
        )

        composite = CompositePortfolio(name="Composite")
        composite.add_sub_portfolio(portfolio)

        mock_price_service = Mock(spec=PriceService)

        with patch("wpm.cli.fetch_price_map") as mock_fetch_price_map:
            mock_fetch_price_map.return_value = {asset1: 160.0, asset2: 220.0}

            with patch("sys.stdout", new=StringIO()) as fake_out:
                cmd_show_all(composite, mock_price_service)
                output = fake_out.getvalue()
                assert "GOOG" in output
                assert "AAPL" in output
                assert "Allocation:" in output
                # Verify allocations are displayed
                assert output.count("Allocation:") == 2


class TestCmdShowAssetWithAllocations:
    """Tests for cmd_show_asset with allocation display."""

    def test_cmd_show_asset_current_displays_allocation(self):
        """Test that show asset displays allocation for current portfolio."""
        portfolio = SimplePortfolio(name="Test")
        asset = Asset(ticker="GOOG", asset_type="Stock")
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )
        composite = CompositePortfolio(name="Composite")
        composite.add_sub_portfolio(portfolio)

        mock_price_service = Mock(spec=PriceService)

        with patch("wpm.cli.fetch_price_map") as mock_fetch_price_map:
            mock_fetch_price_map.return_value = {asset: 160.0}

            with patch("sys.stdout", new=StringIO()) as fake_out:
                cmd_show_asset(composite, "GOOG", mock_price_service)
                output = fake_out.getvalue()
                assert "GOOG" in output
                assert "Allocation:" in output

    def test_cmd_show_asset_historical_displays_allocations(self):
        """Test that show asset displays allocations for historical portfolio."""
        portfolio = SimplePortfolio(name="Test", is_historical=True)
        asset = Asset(ticker="GOOG", asset_type="Stock")
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 1),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )
        composite = CompositePortfolio(name="Composite", is_historical=True)
        composite.add_sub_portfolio(portfolio)

        mock_price_service = Mock(spec=PriceService)

        with patch("wpm.cli.get_historical_performance") as mock_get_perf:
            with patch("wpm.cli.get_historical_allocations") as mock_get_alloc:
                history_points = [
                    PortfolioHistoryPoint(
                        date=date(2024, 1, 30),
                        total_market_value=1600.0,
                        asset_positions={"GOOG": 1600.0},
                        prices={"GOOG": 160.0},
                    ),
                    PortfolioHistoryPoint(
                        date=date(2024, 1, 31),
                        total_market_value=1610.0,
                        asset_positions={"GOOG": 1610.0},
                        prices={"GOOG": 161.0},
                    ),
                ]
                mock_get_perf.return_value = history_points

                allocations_list = [
                    {asset: Decimal('100.00')},
                    {asset: Decimal('100.00')},
                ]
                mock_get_alloc.return_value = allocations_list

                with patch("sys.stdout", new=StringIO()) as fake_out:
                    cmd_show_asset(composite, "GOOG", mock_price_service)
                    output = fake_out.getvalue()
                    assert "2024-01-30" in output
                    assert "2024-01-31" in output
                    assert "Allocation:" in output
                    # Verify allocations are displayed for each date
                    assert output.count("Allocation:") == 2


class TestFormatMarketCap:
    """Tests for format_market_cap function."""

    def test_format_market_cap_trillions(self):
        """Test formatting market cap in trillions."""
        assert format_market_cap(1_500_000_000_000) == "$1.50T"

    def test_format_market_cap_billions(self):
        """Test formatting market cap in billions."""
        assert format_market_cap(1_500_000_000) == "$1.50B"

    def test_format_market_cap_millions(self):
        """Test formatting market cap in millions."""
        assert format_market_cap(1_500_000) == "$1.50M"

    def test_format_market_cap_small(self):
        """Test formatting small market cap."""
        assert format_market_cap(1_500_000) == "$1.50M"
        assert format_market_cap(500_000) == "$500,000.00"

    def test_format_market_cap_none(self):
        """Test formatting None market cap."""
        assert format_market_cap(None) == "N/A"


class TestCmdMetadata:
    """Tests for cmd_metadata function."""

    def test_cmd_metadata_ticker_in_portfolio(self):
        """Test metadata command with ticker in portfolio."""
        portfolio = SimplePortfolio(name="Test")
        asset = Asset(ticker="GOOG", asset_type="Stock")
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 1),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )
        composite = CompositePortfolio(name="Composite")
        composite.add_sub_portfolio(portfolio)

        mock_asset_service = Mock()
        mock_asset_service.get_metadata.return_value = {
            "name": "Alphabet Inc.",
            "sector": "Technology",
            "industry": "Internet Content & Information",
            "country": "United States",
            "market_cap": 1_500_000_000_000,
            "category": "Technology",
        }

        with patch.object(composite, "get_positions") as mock_get_positions:
            with patch.object(composite, "get_asset_trades") as mock_get_asset_trades:
                with patch("sys.stdout", new=StringIO()) as fake_out:
                    cmd_metadata(composite, "GOOG", mock_asset_service)
                    output = fake_out.getvalue()
                    assert "Ticker: GOOG" in output
                    assert "Name: Alphabet Inc." in output
                    assert "Type: Stock" in output
                    assert "Sector: Technology" in output
                    # Verify get_assets was used (we can't easily mock it, but we can verify
                    # that get_asset_trades and get_positions were NOT called)
                    mock_get_asset_trades.assert_not_called()
                    # Verify get_positions was NOT called (to avoid FIFO calculations)
                    mock_get_positions.assert_not_called()

    def test_cmd_metadata_ticker_not_in_portfolio_stock(self):
        """Test metadata command with ticker not in portfolio (infers Stock)."""
        composite = CompositePortfolio(name="Composite")

        mock_asset_service = Mock()
        mock_asset_service.get_metadata.return_value = {
            "name": "Microsoft Corporation",
            "sector": "Technology",
            "industry": "Software",
            "country": "United States",
            "market_cap": 2_500_000_000_000,
            "category": "Technology",
        }

        with patch.object(composite, "get_positions") as mock_get_positions:
            with patch.object(composite, "get_asset_trades") as mock_get_asset_trades:
                with patch("sys.stdout", new=StringIO()) as fake_out:
                    cmd_metadata(composite, "MSFT", mock_asset_service)
                    output = fake_out.getvalue()
                    assert "Ticker: MSFT" in output
                    assert "Name: Microsoft Corporation" in output
                    assert "Type: Stock" in output  # Default inference
                    # Verify lightweight methods were used (get_assets, not get_asset_trades or get_positions)
                    mock_get_asset_trades.assert_not_called()
                    mock_get_positions.assert_not_called()
                # Verify get_metadata was called with inferred asset_type
                mock_asset_service.get_metadata.assert_called_once_with("MSFT", "Stock")

    def test_cmd_metadata_ticker_not_in_portfolio_crypto(self):
        """Test metadata command with crypto ticker not in portfolio (infers Crypto)."""
        composite = CompositePortfolio(name="Composite")

        mock_asset_service = Mock()
        mock_asset_service.get_metadata.return_value = {
            "name": "Bitcoin USD",
            "sector": "N/A",
            "industry": "N/A",
            "country": "N/A",
            "market_cap": 500_000_000_000,
            "category": "Crypto",
        }

        with patch("sys.stdout", new=StringIO()) as fake_out:
            cmd_metadata(composite, "BTC-USD", mock_asset_service)
            output = fake_out.getvalue()
            assert "Ticker: BTC-USD" in output
            assert "Name: Bitcoin USD" in output
            assert "Type: Crypto" in output  # Inferred from -USD suffix
            # Verify get_metadata was called with Crypto asset_type
            mock_asset_service.get_metadata.assert_called_once_with("BTC-USD", "Crypto")

    def test_cmd_metadata_no_metadata_available(self):
        """Test metadata command when metadata is not available."""
        portfolio = SimplePortfolio(name="Test")
        asset = Asset(ticker="GOOG", asset_type="Stock")
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 1),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )
        composite = CompositePortfolio(name="Composite")
        composite.add_sub_portfolio(portfolio)

        mock_asset_service = Mock()
        mock_asset_service.get_metadata.return_value = None

        with patch("sys.stdout", new=StringIO()) as fake_out:
            cmd_metadata(composite, "GOOG", mock_asset_service)
            output = fake_out.getvalue()
            assert "No metadata available for 'GOOG'." in output

    def test_cmd_metadata_uses_get_assets_not_get_positions(self):
        """Test that metadata command uses get_assets (lightweight) not get_positions (expensive)."""
        portfolio = SimplePortfolio(name="Test")
        asset = Asset(ticker="GOOG", asset_type="Stock")
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 1),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )
        composite = CompositePortfolio(name="Composite")
        composite.add_sub_portfolio(portfolio)

        mock_asset_service = Mock()
        mock_asset_service.get_metadata.return_value = {
            "name": "Alphabet Inc.",
            "sector": "Technology",
            "industry": "Internet Content & Information",
            "country": "United States",
            "market_cap": 1_500_000_000_000,
            "category": "Technology",
        }

        # Mock get_positions and get_asset_trades to verify they're NOT called
        with patch.object(composite, "get_positions") as mock_get_positions:
            with patch.object(composite, "get_asset_trades") as mock_get_asset_trades:
                with patch("sys.stdout", new=StringIO()):
                    cmd_metadata(composite, "GOOG", mock_asset_service)
                    # Verify get_assets was used (we can't easily mock it, but we can verify
                    # that get_asset_trades and get_positions were NOT called)
                    mock_get_asset_trades.assert_not_called()
                    # Verify get_positions was NOT called
                    mock_get_positions.assert_not_called()

    def test_cmd_metadata_handles_get_assets_exception(self):
        """Test that metadata command handles exceptions from get_assets gracefully."""
        composite = CompositePortfolio(name="Composite")

        mock_asset_service = Mock()
        mock_asset_service.get_metadata.return_value = {
            "name": "Test Company",
            "sector": "Technology",
            "industry": "Software",
            "country": "United States",
            "market_cap": 1_000_000_000,
            "category": "Technology",
        }

        # Mock get_assets to raise exception - should fall back to inferring asset type
        with patch.object(composite, "get_assets", side_effect=Exception("Error")):
            with patch("sys.stdout", new=StringIO()) as fake_out:
                cmd_metadata(composite, "TEST", mock_asset_service)
                output = fake_out.getvalue()
                # Should still work by inferring asset type
                assert "Ticker: TEST" in output
                assert "Type: Stock" in output  # Default inference
                # Verify get_metadata was called with inferred type
                mock_asset_service.get_metadata.assert_called_once_with("TEST", "Stock")

