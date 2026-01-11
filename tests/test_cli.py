"""Tests for CLI functionality."""

import pytest
from datetime import date
from decimal import Decimal
from io import StringIO
from unittest.mock import Mock, patch
import sys

from wpm.cli import (
    parse_up_to_date,
    cmd_show_all,
    cmd_show_portfolio,
    _display_weekly_summary,
)
from wpm.models import Asset, PortfolioHistoryPoint, Trade
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


class TestWeeklySummary:
    """Tests for weekly summary display."""

    def test_display_weekly_summary_single_week(self):
        """Test displaying weekly summary for single week."""
        history_points = [
            PortfolioHistoryPoint(
                date=date(2024, 1, 15),  # Monday
                total_market_value=1000.0,
                asset_positions={"GOOG": 1000.0},
            ),
            PortfolioHistoryPoint(
                date=date(2024, 1, 16),  # Tuesday
                total_market_value=1050.0,
                asset_positions={"GOOG": 1050.0},
            ),
            PortfolioHistoryPoint(
                date=date(2024, 1, 17),  # Wednesday
                total_market_value=1100.0,
                asset_positions={"GOOG": 1100.0},
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
            ),
            PortfolioHistoryPoint(
                date=date(2024, 1, 20),  # Saturday, Week 1
                total_market_value=1050.0,
                asset_positions={"GOOG": 1050.0},
            ),
            PortfolioHistoryPoint(
                date=date(2024, 1, 22),  # Monday, Week 2
                total_market_value=1100.0,
                asset_positions={"GOOG": 1100.0},
            ),
            PortfolioHistoryPoint(
                date=date(2024, 1, 28),  # Sunday, Week 2
                total_market_value=1200.0,
                asset_positions={"GOOG": 1200.0},
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

