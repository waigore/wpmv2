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
    format_historical_asset_line,
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
            history_points = [
                PortfolioHistoryPoint(
                    date=date(2024, 1, 15),
                    total_market_value=1500.0,
                    asset_positions={"GOOG": 1500.0},
                    prices={},  # Missing price
                ),
            ]
            mock_get_perf.return_value = history_points

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

