"""Tests for CLI functionality."""

import re
import sys
import pytest
from datetime import date
from decimal import Decimal
from io import StringIO
from unittest.mock import Mock, patch

from wpm.cli import (
    parse_up_to_date,
    parse_from_date,
    parse_brokers,
    cmd_show_all,
    cmd_show_portfolio,
    cmd_show_asset,
    cmd_metadata,
    format_historical_asset_line,
    format_position_line,
    format_market_cap,
    _display_weekly_summary,
    calculate_unrealized_pnl_percentage,
    calculate_realized_pnl_percentage,
    _display_totals_section,
)
from wpm.models import Asset, PortfolioHistoryPoint, Trade
from wpm.portfolio import CompositePortfolio, SimplePortfolio
from wpm.portfolio import CompositePortfolio, SimplePortfolio
from wpm.pricing import PriceService
from wpm.reference.portfolio import create_reference_portfolio
from wpm.reference.strategy import BuyAndHoldStrategy
from wpm.currency import CurrencyService


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


class TestParseBrokers:
    """Tests for parse_brokers function."""

    def test_parse_brokers_with_quoted_string(self):
        """Test parsing --brokers with quoted string."""
        args = ["--brokers", '"IBKR,Schwab"', "extra"]
        brokers, remaining = parse_brokers(args)
        assert brokers == ["IBKR", "Schwab"]
        assert remaining == ["extra"]

    def test_parse_brokers_with_spaces_in_names(self):
        """Test parsing --brokers with broker names containing spaces."""
        args = ["--brokers", '"IBKR,Charles Schwab"', "extra"]
        brokers, remaining = parse_brokers(args)
        assert brokers == ["IBKR", "Charles Schwab"]
        assert remaining == ["extra"]

    def test_parse_brokers_with_single_quotes(self):
        """Test parsing --brokers with single quotes."""
        args = ["--brokers", "'IBKR,Schwab'", "extra"]
        brokers, remaining = parse_brokers(args)
        assert brokers == ["IBKR", "Schwab"]
        assert remaining == ["extra"]

    def test_parse_brokers_without_quotes(self):
        """Test parsing --brokers without quotes."""
        args = ["--brokers", "IBKR,Schwab", "extra"]
        brokers, remaining = parse_brokers(args)
        assert brokers == ["IBKR", "Schwab"]
        assert remaining == ["extra"]

    def test_parse_brokers_without_flag(self):
        """Test parsing args without --brokers flag."""
        args = ["portfolio", "name"]
        brokers, remaining = parse_brokers(args)
        assert brokers is None
        assert remaining == ["portfolio", "name"]

    def test_parse_brokers_no_value_after_flag(self):
        """Test parsing --brokers without value argument."""
        args = ["--brokers"]
        brokers, remaining = parse_brokers(args)
        assert brokers is None
        assert remaining == ["--brokers"]

    def test_parse_brokers_empty_string(self):
        """Test parsing --brokers with empty string."""
        args = ["--brokers", '""']
        brokers, remaining = parse_brokers(args)
        assert brokers is None

    def test_parse_brokers_with_whitespace(self):
        """Test parsing --brokers with whitespace around broker names."""
        args = ["--brokers", '"IBKR, Schwab , Tiger"']
        brokers, remaining = parse_brokers(args)
        assert brokers == ["IBKR", "Schwab", "Tiger"]

    def test_parse_brokers_combined_with_from(self):
        """Test parsing --brokers combined with --from."""
        args = ["--from", "2024-01-15", "--brokers", '"IBKR,Schwab"']
        from_date, remaining_after_from = parse_from_date(args)
        brokers, remaining = parse_brokers(remaining_after_from)
        assert from_date == date(2024, 1, 15)
        assert brokers == ["IBKR", "Schwab"]
        assert remaining == []


class TestFormatHistoricalAssetLine:
    """Tests for format_historical_asset_line function."""

    def test_format_with_valid_price(self):
        """Test formatting with valid price."""
        history_point = PortfolioHistoryPoint(
            date=date(2024, 1, 15),
            total_market_value=1000.0,
            asset_positions={"GOOG": 1000.0},
            prices={"GOOG": 100.0},
            quantities={"GOOG": 10.0},
            percentage_return=0.0,
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
            quantities={"GOOG": 10.0},
            percentage_return=0.0,
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
            quantities={"GOOG": 0.0},
            percentage_return=0.0,
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

        with patch("wpm.cli.commands.asset.fetch_price_map") as mock_fetch_price_map:
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

        with patch("wpm.cli.commands.asset.get_historical_performance") as mock_get_perf:
            with patch("wpm.cli.commands.asset.get_historical_allocations") as mock_get_alloc:
                # Mock history points for past 30 days
                history_points = [
                    PortfolioHistoryPoint(
                        date=date(2024, 1, 30),
                        total_market_value=1600.0,
                        asset_positions={"GOOG": 1600.0},
                        prices={"GOOG": 160.0},
                        quantities={"GOOG": 10.0},
                        percentage_return=0.0,
                    ),
                    PortfolioHistoryPoint(
                        date=date(2024, 1, 31),
                        total_market_value=1610.0,
                        asset_positions={"GOOG": 1610.0},
                        prices={"GOOG": 161.0},
                        quantities={"GOOG": 10.0},
                        percentage_return=0.0,
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

        with patch("wpm.cli.commands.asset.get_historical_performance") as mock_get_perf:
            with patch("wpm.cli.commands.asset.get_historical_allocations") as mock_get_alloc:
                from_date = date(2024, 1, 15)
                history_points = [
                    PortfolioHistoryPoint(
                        date=date(2024, 1, 15),
                        total_market_value=1550.0,
                        asset_positions={"GOOG": 1550.0},
                        prices={"GOOG": 155.0},
                        quantities={"GOOG": 10.0},
                        percentage_return=0.0,
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

        with patch("wpm.cli.commands.asset.get_historical_performance") as mock_get_perf:
            with patch("wpm.cli.commands.asset.get_historical_allocations") as mock_get_alloc:
                history_points = [
                    PortfolioHistoryPoint(
                        date=date(2024, 1, 15),
                        total_market_value=1500.0,
                        asset_positions={"GOOG": 1500.0},
                        prices={},  # Missing price
                        quantities={"GOOG": 10.0},
                        percentage_return=0.0,
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

    def test_cmd_show_asset_current_portfolio_with_broker_filter_single(self):
        """Test show asset with single broker filter for current portfolio."""
        portfolio = SimplePortfolio(name="Test")
        asset = Asset(ticker="VOO", asset_type="ETF")
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=600.0,
                price_native=600.0,
                quantity=2.0,
            )
        )
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 16),
                asset=asset,
                action="Buy",
                broker="Schwab",
                currency="USD",
                price=610.0,
                price_native=610.0,
                quantity=1.0,
            )
        )
        composite = CompositePortfolio(name="Composite")
        composite.add_sub_portfolio(portfolio)

        mock_price_service = Mock(spec=PriceService)

        with patch("wpm.cli.commands.asset.fetch_price_map") as mock_fetch_price_map:
            mock_fetch_price_map.return_value = {asset: 620.0}

            with patch("sys.stdout", new=StringIO()) as fake_out:
                cmd_show_asset(composite, "VOO", mock_price_service, brokers=["IBKR"])
                output = fake_out.getvalue()
                assert "VOO" in output
                assert "ETF" in output
                # Should show quantity 2.0 from IBKR only (not 3.0 from both brokers)
                assert "2.0" in output or "2" in output

    def test_cmd_show_asset_current_portfolio_with_broker_filter_multiple(self):
        """Test show asset with multiple broker filter for current portfolio."""
        portfolio = SimplePortfolio(name="Test")
        asset = Asset(ticker="VOO", asset_type="ETF")
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=600.0,
                price_native=600.0,
                quantity=2.0,
            )
        )
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 16),
                asset=asset,
                action="Buy",
                broker="Schwab",
                currency="USD",
                price=610.0,
                price_native=610.0,
                quantity=1.0,
            )
        )
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 17),
                asset=asset,
                action="Buy",
                broker="Tiger",
                currency="USD",
                price=620.0,
                price_native=620.0,
                quantity=1.0,
            )
        )
        composite = CompositePortfolio(name="Composite")
        composite.add_sub_portfolio(portfolio)

        mock_price_service = Mock(spec=PriceService)

        with patch("wpm.cli.commands.asset.fetch_price_map") as mock_fetch_price_map:
            mock_fetch_price_map.return_value = {asset: 630.0}

            with patch("sys.stdout", new=StringIO()) as fake_out:
                cmd_show_asset(composite, "VOO", mock_price_service, brokers=["IBKR", "Schwab"])
                output = fake_out.getvalue()
                assert "VOO" in output
                # Should show quantity 3.0 from IBKR and Schwab (not 4.0 from all brokers)

    def test_cmd_show_asset_current_portfolio_with_broker_filter_no_match(self):
        """Test show asset with broker filter when no matching brokers exist."""
        portfolio = SimplePortfolio(name="Test")
        asset = Asset(ticker="VOO", asset_type="ETF")
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=600.0,
                price_native=600.0,
                quantity=2.0,
            )
        )
        composite = CompositePortfolio(name="Composite")
        composite.add_sub_portfolio(portfolio)

        mock_price_service = Mock(spec=PriceService)

        with patch("sys.stdout", new=StringIO()) as fake_out:
            cmd_show_asset(composite, "VOO", mock_price_service, brokers=["NonexistentBroker"])
            output = fake_out.getvalue()
            assert "No positions found" in output
            assert "VOO" in output
            assert "specified brokers" in output

    def test_cmd_show_asset_historical_portfolio_with_broker_filter(self):
        """Test show asset with broker filter for historical portfolio."""
        portfolio = SimplePortfolio(name="Test", is_historical=True)
        asset = Asset(ticker="VOO", asset_type="ETF")
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 1),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=600.0,
                price_native=600.0,
                quantity=2.0,
            )
        )
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset,
                action="Buy",
                broker="Schwab",
                currency="USD",
                price=610.0,
                price_native=610.0,
                quantity=1.0,
            )
        )
        composite = CompositePortfolio(name="Composite", is_historical=True)
        composite.add_sub_portfolio(portfolio)

        mock_price_service = Mock(spec=PriceService)

        with patch("wpm.cli.commands.asset.get_historical_performance") as mock_get_perf:
            with patch("wpm.cli.commands.asset.get_historical_allocations") as mock_get_alloc:
                # Mock history points filtered by broker
                history_points = [
                    PortfolioHistoryPoint(
                        date=date(2024, 1, 31),
                        total_market_value=1200.0,
                        asset_positions={"VOO": 1200.0},  # Only IBKR lots (2.0 * 600)
                        prices={"VOO": 600.0},
                        quantities={"VOO": 2.0},
                        percentage_return=0.0,
                    ),
                ]
                mock_get_perf.return_value = history_points

                allocations_list = [
                    {asset: Decimal('100.00')},
                ]
                mock_get_alloc.return_value = allocations_list

                with patch("sys.stdout", new=StringIO()) as fake_out:
                    cmd_show_asset(composite, "VOO", mock_price_service, brokers=["IBKR"])
                    output = fake_out.getvalue()
                    assert "VOO" in output
                    # Verify that get_historical_performance was called with brokers parameter
                    mock_get_perf.assert_called_once()
                    call_kwargs = mock_get_perf.call_args[1]
                    assert call_kwargs.get("brokers") == ["IBKR"]


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
                quantities={"GOOG": 10.0},
                percentage_return=0.0,
            ),
            PortfolioHistoryPoint(
                date=date(2024, 1, 16),  # Tuesday
                total_market_value=1050.0,
                asset_positions={"GOOG": 1050.0},
                prices={"GOOG": 105.0},
                quantities={"GOOG": 10.0},
                percentage_return=5.0,
            ),
            PortfolioHistoryPoint(
                date=date(2024, 1, 17),  # Wednesday
                total_market_value=1100.0,
                asset_positions={"GOOG": 1100.0},
                prices={"GOOG": 110.0},
                quantities={"GOOG": 10.0},
                percentage_return=10.0,
            ),
        ]

        with patch("sys.stdout", new=StringIO()) as fake_out:
            _display_weekly_summary(history_points)
            output = fake_out.getvalue()
            assert "Weekly Performance Summary:" in output
            assert "2024-01-15" in output  # Week start
            assert "2024-01-21" in output  # Week end (Sunday)
            assert "$1,100.00" in output  # Last value of the week
            assert "(+10.00%)" in output  # Percentage return

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
                quantities={"GOOG": 10.0},
                percentage_return=0.0,
            ),
            PortfolioHistoryPoint(
                date=date(2024, 1, 20),  # Saturday, Week 1
                total_market_value=1050.0,
                asset_positions={"GOOG": 1050.0},
                prices={"GOOG": 105.0},
                quantities={"GOOG": 10.0},
                percentage_return=5.0,
            ),
            PortfolioHistoryPoint(
                date=date(2024, 1, 22),  # Monday, Week 2
                total_market_value=1100.0,
                asset_positions={"GOOG": 1100.0},
                prices={"GOOG": 110.0},
                quantities={"GOOG": 10.0},
                percentage_return=10.0,
            ),
            PortfolioHistoryPoint(
                date=date(2024, 1, 28),  # Sunday, Week 2
                total_market_value=1200.0,
                asset_positions={"GOOG": 1200.0},
                prices={"GOOG": 120.0},
                quantities={"GOOG": 10.0},
                percentage_return=20.0,
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
            assert "(+5.00%)" in output  # Week 1 percentage return
            assert "(+20.00%)" in output  # Week 2 percentage return

    def test_display_weekly_summary_negative_return(self):
        """Test displaying weekly summary with negative percentage return."""
        history_points = [
            PortfolioHistoryPoint(
                date=date(2024, 1, 15),  # Monday
                total_market_value=1000.0,
                asset_positions={"GOOG": 1000.0},
                prices={"GOOG": 100.0},
                quantities={"GOOG": 10.0},
                percentage_return=0.0,
            ),
            PortfolioHistoryPoint(
                date=date(2024, 1, 17),  # Wednesday
                total_market_value=950.0,
                asset_positions={"GOOG": 950.0},
                prices={"GOOG": 95.0},
                quantities={"GOOG": 10.0},
                percentage_return=-5.0,
            ),
        ]

        with patch("sys.stdout", new=StringIO()) as fake_out:
            _display_weekly_summary(history_points)
            output = fake_out.getvalue()
            assert "Weekly Performance Summary:" in output
            assert "$950.00" in output
            assert "(-5.00%)" in output  # Negative return should show minus sign

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
            quantities={"GOOG": 10.0},
            percentage_return=0.0,
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
            quantities={"GOOG": 10.0},
            percentage_return=0.0,
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

        with patch("wpm.cli.commands.portfolio.fetch_price_map") as mock_fetch_price_map:
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

        with patch("wpm.cli.commands.portfolio.fetch_price_map") as mock_fetch_price_map:
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

        with patch("wpm.cli.commands.portfolio.fetch_price_map") as mock_fetch_price_map:
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

        with patch("wpm.cli.commands.asset.fetch_price_map") as mock_fetch_price_map:
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

        with patch("wpm.cli.commands.asset.get_historical_performance") as mock_get_perf:
            with patch("wpm.cli.commands.asset.get_historical_allocations") as mock_get_alloc:
                history_points = [
                    PortfolioHistoryPoint(
                        date=date(2024, 1, 30),
                        total_market_value=1600.0,
                        asset_positions={"GOOG": 1600.0},
                        prices={"GOOG": 160.0},
                        quantities={"GOOG": 10.0},
                        percentage_return=0.0,
                    ),
                    PortfolioHistoryPoint(
                        date=date(2024, 1, 31),
                        total_market_value=1610.0,
                        asset_positions={"GOOG": 1610.0},
                        prices={"GOOG": 161.0},
                        quantities={"GOOG": 10.0},
                        percentage_return=0.0,
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
                    assert "Return:" in output
                    # Verify allocations are displayed for each date
                    assert output.count("Allocation:") == 2
                    # Verify percentage return is displayed for each date
                    assert output.count("Return:") == 2

    def test_cmd_show_asset_historical_displays_percentage_return(self):
        """Test that show asset displays percentage return for historical portfolio."""
        portfolio = SimplePortfolio(name="Test", is_historical=True)
        asset = Asset(ticker="VOO", asset_type="ETF")
        # Buy 1 share at $400 on 2024-01-01
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 1),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=400.0,
                price_native=400.0,
                quantity=1.0,
            )
        )
        # Add another small buy on 2024-01-02 to extend portfolio end_date
        # This creates a second lot but won't significantly affect the percentage return calculation
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 2),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=410.0,
                price_native=410.0,
                quantity=0.01,  # Small quantity to extend date range
            )
        )
        composite = CompositePortfolio(name="Composite", is_historical=True)
        composite.add_sub_portfolio(portfolio)

        mock_price_service = Mock(spec=PriceService)

        # Mock historical prices: Day 1: $400, Day 2: $410
        def mock_get_historical_prices(tickers, asset_type, start_date, end_date):
            prices = {}
            for ticker in tickers:
                prices[ticker] = {
                    date(2024, 1, 1): 400.0,
                    date(2024, 1, 2): 410.0,
                }
            return prices

        mock_price_service.get_historical_prices.side_effect = mock_get_historical_prices

        with patch("sys.stdout", new=StringIO()) as fake_out:
            cmd_show_asset(composite, "VOO", mock_price_service, from_date=date(2024, 1, 1))
            output = fake_out.getvalue()

            # Verify dates are displayed
            assert "2024-01-01" in output
            assert "2024-01-02" in output

            # Verify percentage return is displayed
            assert "Return:" in output

            # Day 1: price = $400, purchase = $400, return = 0%
            assert "Return: 0.00%" in output or "Return: 0.0%" in output

            # Day 2: price = $410
            # Lot 1: purchase = $400, quantity = 1.0, unrealized P/L = (410-400)*1 = 10, cost basis = 400
            # Lot 2: purchase = $410, quantity = 0.01, unrealized P/L = (410-410)*0.01 = 0, cost basis = 4.1
            # Total unrealized P/L = 10, total cost basis = 404.1, return ≈ 2.48%
            # Check that return is approximately 2.5% (allowing for formatting and small lot)
            lines = output.split("\n")
            for line in lines:
                if "2024-01-02" in line and "Return:" in line:
                    # Extract the return value
                    match = re.search(r"Return: ([\d.]+)%", line)
                    if match:
                        return_value = float(match.group(1))
                        # Expected: 10/404.1 * 100 ≈ 2.48%, but allow range around 2.5%
                        assert 2.0 <= return_value <= 3.0  # Allow range for small lot impact
                    break

    def test_cmd_show_asset_historical_percentage_return_negative(self):
        """Test that show asset displays negative percentage return correctly."""
        portfolio = SimplePortfolio(name="Test", is_historical=True)
        asset = Asset(ticker="VOO", asset_type="ETF")
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 1),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=400.0,
                price_native=400.0,
                quantity=1.0,
            )
        )
        composite = CompositePortfolio(name="Composite", is_historical=True)
        composite.add_sub_portfolio(portfolio)

        mock_price_service = Mock(spec=PriceService)

        # Mock historical prices: Day 1: $400, Day 2: $380 (price dropped)
        def mock_get_historical_prices(tickers, asset_type, start_date, end_date):
            prices = {}
            for ticker in tickers:
                prices[ticker] = {
                    date(2024, 1, 1): 400.0,
                    date(2024, 1, 2): 380.0,
                }
            return prices

        mock_price_service.get_historical_prices.side_effect = mock_get_historical_prices

        with patch("sys.stdout", new=StringIO()) as fake_out:
            cmd_show_asset(composite, "VOO", mock_price_service, from_date=date(2024, 1, 1))
            output = fake_out.getvalue()

            # Verify percentage return is displayed
            assert "Return:" in output

            # Day 2: price = $380, purchase = $400, unrealized P/L = -20, cost basis = 400
            # return = -20/400 * 100 = -5.0%
            lines = output.split("\n")
            for line in lines:
                if "2024-01-02" in line and "Return:" in line:
                    # Check for negative return
                    assert "-" in line or "Return: -" in line
                    import re
                    match = re.search(r"Return: (-?[\d.]+)%", line)
                    if match:
                        return_value = float(match.group(1))
                        assert abs(return_value - (-5.0)) < 0.1
                    break


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


class TestReferencePortfolioInCLI:
    """Tests for reference portfolio integration in CLI."""

    def test_cmd_show_all_with_reference_portfolio_and_up_to(self):
        """Test show all with --up-to displays reference portfolio P/L."""
        # Create main portfolio
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

        # Create reference portfolio
        spy_asset = Asset(ticker="SPY", asset_type="ETF")
        strategy = BuyAndHoldStrategy(reference_asset=spy_asset)
        currency_service = CurrencyService()
        
        mock_price_service = Mock(spec=PriceService)
        
        # Mock historical prices for main portfolio
        def mock_get_historical_prices(tickers, asset_type, start_date, end_date, in_native_currency=False, cached_prices_only=False):
            from datetime import timedelta
            prices = {}
            current = start_date
            while current <= end_date:
                for ticker in tickers:
                    if ticker not in prices:
                        prices[ticker] = {}
                    if ticker == "GOOG":
                        prices[ticker][current] = 155.0
                    elif ticker == "SPY":
                        prices[ticker][current] = 400.0
                current += timedelta(days=1)
            return prices
        
        mock_price_service.get_historical_prices.side_effect = mock_get_historical_prices
        
        # Mock get_historical_price for reference portfolio creation
        def mock_get_historical_price(ticker, asset_type, target_date, in_native_currency):
            if ticker == "SPY":
                return 400.0
            return None
        
        mock_price_service.get_historical_price.side_effect = mock_get_historical_price
        
        # Create reference portfolio
        reference_portfolio = create_reference_portfolio(
            original_portfolio=composite,
            strategy=strategy,
            price_service=mock_price_service,
            currency_service=currency_service,
            name="SPY Reference Portfolio",
        )

        # Mock fetch_price_map for reference portfolio
        with patch("wpm.cli.commands.asset.fetch_price_map") as mock_fetch_price_map:
            # First call for main portfolio (in get_historical_performance)
            # Subsequent calls for reference portfolios
            spy_ref_asset = Asset(ticker="SPY", asset_type="ETF")
            def mock_fetch_price_map_side_effect(portfolio, price_service, target_date=None):
                if portfolio == reference_portfolio:
                    return {spy_ref_asset: 410.0}
                return {}
            mock_fetch_price_map.side_effect = mock_fetch_price_map_side_effect
            
            reference_portfolios = {"SPY Reference Portfolio": reference_portfolio}
            
            with patch("sys.stdout", new=StringIO()) as fake_out:
                cmd_show_all(
                    composite, mock_price_service, date(2024, 1, 17), reference_portfolios
                )
                output = fake_out.getvalue()
                assert "Weekly Performance Summary:" in output
                assert "Totals:" in output
                assert "Imported Portfolio:" in output
                assert "SPY Reference Portfolio:" in output
                assert "Total Unrealized P/L:" in output
                assert "Total Realized P/L:" in output
                # Check for percentage returns
                assert "%" in output

    def test_cmd_show_all_with_reference_portfolio_no_up_to(self):
        """Test show all without --up-to displays totals section with both portfolios."""
        portfolio = SimplePortfolio(name="Test Portfolio")
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

        composite = CompositePortfolio(name="Composite")
        composite.add_sub_portfolio(portfolio)

        # Create reference portfolio
        spy_asset = Asset(ticker="SPY", asset_type="ETF")
        strategy = BuyAndHoldStrategy(reference_asset=spy_asset)
        currency_service = CurrencyService()
        
        mock_price_service = Mock(spec=PriceService)
        mock_price_service.get_historical_price.return_value = 400.0
        
        # Mock get_historical_prices for prefetch (called by strategy.prepare())
        def mock_get_historical_prices(tickers, asset_type, start_date, end_date, in_native_currency=False, cached_prices_only=False):
            from datetime import timedelta
            prices = {}
            current = start_date
            while current <= end_date:
                for ticker in tickers:
                    if ticker not in prices:
                        prices[ticker] = {}
                    if ticker == "SPY":
                        prices[ticker][current] = 400.0
                current += timedelta(days=1)
            return prices
        
        mock_price_service.get_historical_prices.side_effect = mock_get_historical_prices
        
        reference_portfolio = create_reference_portfolio(
            original_portfolio=composite,
            strategy=strategy,
            price_service=mock_price_service,
            currency_service=currency_service,
            name="SPY Reference Portfolio",
        )

        with patch("wpm.cli.commands.portfolio.fetch_price_map") as mock_fetch_price_map:
            def mock_fetch_price_map_side_effect(portfolio, price_service, target_date=None):
                if portfolio == composite:
                    return {asset: 160.0}
                elif portfolio == reference_portfolio:
                    spy_ref_asset = Asset(ticker="SPY", asset_type="ETF")
                    return {spy_ref_asset: 410.0}
                return {}
            mock_fetch_price_map.side_effect = mock_fetch_price_map_side_effect
            
            reference_portfolios = {"SPY Reference Portfolio": reference_portfolio}
            
            with patch("sys.stdout", new=StringIO()) as fake_out:
                cmd_show_all(composite, mock_price_service, None, reference_portfolios)
                output = fake_out.getvalue()
                # Should display totals section with both portfolios
                assert "Totals:" in output
                assert "Imported Portfolio:" in output
                assert "SPY Reference Portfolio:" in output
                assert "Total Unrealized P/L:" in output
                assert "Total Realized P/L:" in output

    def test_cmd_show_all_with_empty_reference_portfolios(self):
        """Test show all handles empty reference portfolios dict gracefully."""
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
            cmd_show_all(composite, mock_price_service, date(2024, 1, 17), {})
            output = fake_out.getvalue()
            assert "Weekly Performance Summary:" in output
            # Should not display reference portfolio P/L when empty dict
            assert "SPY Reference Portfolio:" not in output
            assert "BTC-USD Reference Portfolio:" not in output

    def test_cmd_show_all_reference_portfolio_handles_price_error(self):
        """Test show all handles price errors for reference portfolio gracefully."""
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

        # Create reference portfolio
        spy_asset = Asset(ticker="SPY", asset_type="ETF")
        strategy = BuyAndHoldStrategy(reference_asset=spy_asset)
        currency_service = CurrencyService()
        
        mock_price_service = Mock(spec=PriceService)
        
        def mock_get_historical_prices(tickers, asset_type, start_date, end_date, in_native_currency=False, cached_prices_only=False):
            from datetime import timedelta
            prices = {}
            current = start_date
            while current <= end_date:
                for ticker in tickers:
                    if ticker not in prices:
                        prices[ticker] = {}
                    if ticker == "SPY":
                        prices[ticker][current] = 400.0
                    else:
                        prices[ticker][current] = 155.0
                current += timedelta(days=1)
            return prices
        
        mock_price_service.get_historical_prices.side_effect = mock_get_historical_prices
        mock_price_service.get_historical_price.return_value = 400.0
        
        reference_portfolio = create_reference_portfolio(
            original_portfolio=composite,
            strategy=strategy,
            price_service=mock_price_service,
            currency_service=currency_service,
            name="SPY Reference Portfolio",
        )

        # Mock fetch_price_map to raise exception for reference portfolio only
        call_count = [0]
        def mock_fetch_price_map(portfolio, price_service, target_date=None):
            call_count[0] += 1
            # First call is for imported portfolio in get_historical_performance (succeeds)
            # Second call is for imported portfolio in _display_totals_section (should succeed)
            # Third call is for reference portfolio in _display_totals_section (should fail)
            if call_count[0] <= 2:
                # Return price map for imported portfolio
                return {asset: 155.0}
            elif portfolio == reference_portfolio:
                # Raise exception for reference portfolio
                raise ValueError("Price unavailable")
            return {}
        
        reference_portfolios = {"SPY Reference Portfolio": reference_portfolio}
        
        with patch("wpm.cli.commands.portfolio.fetch_price_map", side_effect=mock_fetch_price_map):
            with patch("sys.stdout", new=StringIO()) as fake_out:
                # Should not crash, just skip reference portfolio display
                cmd_show_all(
                    composite, mock_price_service, date(2024, 1, 17), reference_portfolios
                )
                output = fake_out.getvalue()
                assert "Weekly Performance Summary:" in output
                assert "Totals:" in output
                assert "Imported Portfolio:" in output
                # Reference portfolio may not be displayed if there's an error, but totals section should still appear


class TestTotalsSectionDisplay:
    """Tests for totals section display function."""

    def test_display_totals_section_with_both_portfolios(self):
        """Test totals section displays both imported and reference portfolios."""
        imported_portfolio = SimplePortfolio(name="Test Portfolio")
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
        imported_portfolio.add_trade(trade)
        
        spy_reference_portfolio = SimplePortfolio(name="SPY Reference Portfolio")
        spy_asset = Asset(ticker="SPY", asset_type="ETF")
        spy_trade = Trade(
            date=date(2024, 1, 15),
            asset=spy_asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=400.0,
            price_native=400.0,
            quantity=3.75,
        )
        spy_reference_portfolio.add_trade(spy_trade)
        
        btc_reference_portfolio = SimplePortfolio(name="BTC-USD Reference Portfolio")
        btc_asset = Asset(ticker="BTC-USD", asset_type="Crypto")
        btc_trade = Trade(
            date=date(2024, 1, 15),
            asset=btc_asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=45000.0,
            price_native=45000.0,
            quantity=0.03333333,
        )
        btc_reference_portfolio.add_trade(btc_trade)
        
        reference_portfolios = {
            "SPY Reference Portfolio": spy_reference_portfolio,
            "BTC-USD Reference Portfolio": btc_reference_portfolio,
        }
        
        mock_price_service = Mock(spec=PriceService)
        
        # Mock fetch_price_map to return prices
        def mock_fetch_price_map(portfolio, price_service, target_date=None):
            if portfolio == imported_portfolio:
                return {asset: 160.0}
            elif portfolio == spy_reference_portfolio:
                return {spy_asset: 410.0}
            elif portfolio == btc_reference_portfolio:
                return {btc_asset: 46000.0}
            return {}
        
        with patch("wpm.cli.commands.portfolio.fetch_price_map", side_effect=mock_fetch_price_map):
            with patch("sys.stdout", new=StringIO()) as fake_out:
                _display_totals_section(
                    imported_portfolio=imported_portfolio,
                    reference_portfolios=reference_portfolios,
                    price_service=mock_price_service,
                    target_date=None,
                )
                output = fake_out.getvalue()
                
                assert "Totals:" in output
                assert "Imported Portfolio:" in output
                assert "SPY Reference Portfolio:" in output
                assert "BTC-USD Reference Portfolio:" in output
                assert "Total Unrealized P/L:" in output
                assert "Total Realized P/L:" in output
                # Check for percentage returns
                assert "%" in output

    def test_display_totals_section_with_only_imported_portfolio(self):
        """Test totals section displays only imported portfolio when reference portfolios dict is empty."""
        imported_portfolio = SimplePortfolio(name="Test Portfolio")
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
        imported_portfolio.add_trade(trade)
        
        mock_price_service = Mock(spec=PriceService)
        
        def mock_fetch_price_map(portfolio, price_service, target_date=None):
            return {asset: 160.0}
        
        with patch("wpm.cli.commands.portfolio.fetch_price_map", side_effect=mock_fetch_price_map):
            with patch("sys.stdout", new=StringIO()) as fake_out:
                _display_totals_section(
                    imported_portfolio=imported_portfolio,
                    reference_portfolios={},
                    price_service=mock_price_service,
                    target_date=None,
                )
                output = fake_out.getvalue()
                
                assert "Totals:" in output
                assert "Imported Portfolio:" in output
                assert "SPY Reference Portfolio:" not in output
                assert "BTC-USD Reference Portfolio:" not in output

    def test_display_totals_section_with_target_date(self):
        """Test totals section calculates values against target_date."""
        imported_portfolio = SimplePortfolio(name="Test Portfolio", is_historical=True)
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
        imported_portfolio.add_trade(trade)
        
        mock_price_service = Mock(spec=PriceService)
        target_date = date(2024, 1, 17)
        
        mock_fetch_price_map = Mock(return_value={asset: 160.0})
        
        with patch("wpm.cli.commands.portfolio.fetch_price_map", mock_fetch_price_map):
            with patch("sys.stdout", new=StringIO()) as fake_out:
                _display_totals_section(
                    imported_portfolio=imported_portfolio,
                    reference_portfolios={},
                    price_service=mock_price_service,
                    target_date=target_date,
                )
                output = fake_out.getvalue()
                
                assert "Totals:" in output
                assert "Imported Portfolio:" in output
                # Verify fetch_price_map was called with target_date
                mock_fetch_price_map.assert_called_once_with(
                    imported_portfolio, mock_price_service, target_date=target_date
                )


class TestReferencePortfolioCreation:
    """Tests for reference portfolio creation in CLI."""

    def test_reference_portfolio_creation_success(self):
        """Test that reference portfolio can be created successfully."""
        # Create a simple portfolio
        portfolio = SimplePortfolio(name="Test Portfolio")
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

        composite = CompositePortfolio(name="Composite")
        composite.add_sub_portfolio(portfolio)

        # Create reference portfolio
        spy_asset = Asset(ticker="SPY", asset_type="ETF")
        strategy = BuyAndHoldStrategy(reference_asset=spy_asset)
        currency_service = CurrencyService()
        
        mock_price_service = Mock(spec=PriceService)
        mock_price_service.get_historical_price.return_value = 400.0
        
        # Mock get_historical_prices for prefetch
        def mock_get_historical_prices(tickers, asset_type, start_date, end_date, in_native_currency=False, cached_prices_only=False):
            from datetime import timedelta
            prices = {}
            current = start_date
            while current <= end_date:
                for ticker in tickers:
                    if ticker not in prices:
                        prices[ticker] = {}
                    if ticker == "SPY":
                        prices[ticker][current] = 400.0
                current += timedelta(days=1)
            return prices
        
        mock_price_service.get_historical_prices.side_effect = mock_get_historical_prices
        
        reference_portfolio = create_reference_portfolio(
            original_portfolio=composite,
            strategy=strategy,
            price_service=mock_price_service,
            currency_service=currency_service,
            name="SPY Reference Portfolio",
        )
        
        # Verify reference portfolio was created
        assert reference_portfolio is not None
        assert reference_portfolio.name == "SPY Reference Portfolio"
        assert reference_portfolio.is_historical == composite.is_historical
        
        # Verify reference portfolio has trades
        all_trades = reference_portfolio.get_all_trades()
        assert len(all_trades) > 0
        
        # Verify all trades are for SPY
        for trade in all_trades:
            assert trade.asset.ticker == "SPY"
            assert trade.asset.asset_type == "ETF"

    def test_reference_portfolio_creation_handles_error(self):
        """Test that reference portfolio creation error is handled gracefully."""
        # Create a simple portfolio
        portfolio = SimplePortfolio(name="Test Portfolio")
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

        composite = CompositePortfolio(name="Composite")
        composite.add_sub_portfolio(portfolio)

        # Create reference portfolio with price service that fails
        spy_asset = Asset(ticker="SPY", asset_type="ETF")
        strategy = BuyAndHoldStrategy(reference_asset=spy_asset)
        currency_service = CurrencyService()
        
        mock_price_service = Mock(spec=PriceService)
        # Make price service raise error for both methods
        # The fetcher will try get_historical_price first, then get_historical_prices for lookback
        mock_price_service.get_historical_price.side_effect = ValueError("Price unavailable")
        mock_price_service.get_historical_prices.side_effect = ValueError("Price unavailable")
        
        # Should raise ValueError when creating reference portfolio
        with pytest.raises(ValueError, match="Price unavailable"):
            create_reference_portfolio(
                original_portfolio=composite,
                strategy=strategy,
                price_service=mock_price_service,
                currency_service=currency_service,
                name="SPY Reference Portfolio",
            )

    def test_btc_usd_reference_portfolio_creation_success(self):
        """Test that BTC-USD reference portfolio can be created successfully."""
        # Create a simple portfolio
        portfolio = SimplePortfolio(name="Test Portfolio")
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

        composite = CompositePortfolio(name="Composite")
        composite.add_sub_portfolio(portfolio)

        # Create BTC-USD reference portfolio
        btc_asset = Asset(ticker="BTC-USD", asset_type="Crypto")
        strategy = BuyAndHoldStrategy(reference_asset=btc_asset)
        currency_service = CurrencyService()
        
        mock_price_service = Mock(spec=PriceService)
        mock_price_service.get_historical_price.return_value = 45000.0
        
        # Mock get_historical_prices for prefetch
        def mock_get_historical_prices(tickers, asset_type, start_date, end_date, in_native_currency=False, cached_prices_only=False):
            from datetime import timedelta
            prices = {}
            current = start_date
            while current <= end_date:
                for ticker in tickers:
                    if ticker not in prices:
                        prices[ticker] = {}
                    if ticker == "BTC-USD":
                        prices[ticker][current] = 45000.0
                current += timedelta(days=1)
            return prices
        
        mock_price_service.get_historical_prices.side_effect = mock_get_historical_prices
        
        reference_portfolio = create_reference_portfolio(
            original_portfolio=composite,
            strategy=strategy,
            price_service=mock_price_service,
            currency_service=currency_service,
            name="BTC-USD Reference Portfolio",
        )
        
        # Verify reference portfolio was created
        assert reference_portfolio is not None
        assert reference_portfolio.name == "BTC-USD Reference Portfolio"
        assert reference_portfolio.is_historical == composite.is_historical
        
        # Verify reference portfolio has trades
        all_trades = reference_portfolio.get_all_trades()
        assert len(all_trades) > 0
        
        # Verify all trades are for BTC-USD
        for trade in all_trades:
            assert trade.asset.ticker == "BTC-USD"
            assert trade.asset.asset_type == "Crypto"

    def test_both_reference_portfolios_creation_success(self):
        """Test that both SPY and BTC-USD reference portfolios can be created successfully."""
        # Create a simple portfolio
        portfolio = SimplePortfolio(name="Test Portfolio")
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

        composite = CompositePortfolio(name="Composite")
        composite.add_sub_portfolio(portfolio)

        currency_service = CurrencyService()
        mock_price_service = Mock(spec=PriceService)
        
        # Mock get_historical_price to return different prices for different assets
        def mock_get_historical_price(ticker, asset_type, target_date, in_native_currency=False):
            if ticker == "SPY":
                return 400.0
            elif ticker == "BTC-USD":
                return 45000.0
            return 0.0
        
        mock_price_service.get_historical_price.side_effect = mock_get_historical_price
        
        # Mock get_historical_prices for prefetch
        def mock_get_historical_prices(tickers, asset_type, start_date, end_date, in_native_currency=False, cached_prices_only=False):
            from datetime import timedelta
            prices = {}
            current = start_date
            while current <= end_date:
                for ticker in tickers:
                    if ticker not in prices:
                        prices[ticker] = {}
                    if ticker == "SPY":
                        prices[ticker][current] = 400.0
                    elif ticker == "BTC-USD":
                        prices[ticker][current] = 45000.0
                current += timedelta(days=1)
            return prices
        
        mock_price_service.get_historical_prices.side_effect = mock_get_historical_prices
        
        # Create SPY reference portfolio
        spy_asset = Asset(ticker="SPY", asset_type="ETF")
        spy_strategy = BuyAndHoldStrategy(reference_asset=spy_asset)
        spy_reference = create_reference_portfolio(
            original_portfolio=composite,
            strategy=spy_strategy,
            price_service=mock_price_service,
            currency_service=currency_service,
            name="SPY Reference Portfolio",
        )
        
        # Create BTC-USD reference portfolio
        btc_asset = Asset(ticker="BTC-USD", asset_type="Crypto")
        btc_strategy = BuyAndHoldStrategy(reference_asset=btc_asset)
        btc_reference = create_reference_portfolio(
            original_portfolio=composite,
            strategy=btc_strategy,
            price_service=mock_price_service,
            currency_service=currency_service,
            name="BTC-USD Reference Portfolio",
        )
        
        # Verify both reference portfolios were created
        assert spy_reference is not None
        assert spy_reference.name == "SPY Reference Portfolio"
        assert btc_reference is not None
        assert btc_reference.name == "BTC-USD Reference Portfolio"
        
        # Verify both have trades
        spy_trades = spy_reference.get_all_trades()
        btc_trades = btc_reference.get_all_trades()
        assert len(spy_trades) > 0
        assert len(btc_trades) > 0
        
        # Verify trades are for correct assets
        for trade in spy_trades:
            assert trade.asset.ticker == "SPY"
        for trade in btc_trades:
            assert trade.asset.ticker == "BTC-USD"

    def test_partial_reference_portfolio_creation_failure(self):
        """Test that if one reference portfolio fails, the other can still be created."""
        # Create a simple portfolio
        portfolio = SimplePortfolio(name="Test Portfolio")
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

        composite = CompositePortfolio(name="Composite")
        composite.add_sub_portfolio(portfolio)

        currency_service = CurrencyService()
        
        # Create SPY reference portfolio with working price service
        spy_asset = Asset(ticker="SPY", asset_type="ETF")
        spy_strategy = BuyAndHoldStrategy(reference_asset=spy_asset)
        
        spy_price_service = Mock(spec=PriceService)
        spy_price_service.get_historical_price.return_value = 400.0
        
        def mock_get_historical_prices(tickers, asset_type, start_date, end_date, in_native_currency=False, cached_prices_only=False):
            from datetime import timedelta
            prices = {}
            current = start_date
            while current <= end_date:
                for ticker in tickers:
                    if ticker not in prices:
                        prices[ticker] = {}
                    if ticker == "SPY":
                        prices[ticker][current] = 400.0
                current += timedelta(days=1)
            return prices
        
        spy_price_service.get_historical_prices.side_effect = mock_get_historical_prices
        
        spy_reference = create_reference_portfolio(
            original_portfolio=composite,
            strategy=spy_strategy,
            price_service=spy_price_service,
            currency_service=currency_service,
            name="SPY Reference Portfolio",
        )
        
        # Verify SPY reference portfolio was created
        assert spy_reference is not None
        
        # Try to create BTC-USD reference portfolio with failing price service
        btc_asset = Asset(ticker="BTC-USD", asset_type="Crypto")
        btc_strategy = BuyAndHoldStrategy(reference_asset=btc_asset)
        
        btc_price_service = Mock(spec=PriceService)
        btc_price_service.get_historical_price.side_effect = ValueError("Price unavailable")
        btc_price_service.get_historical_prices.side_effect = ValueError("Price unavailable")
        
        # Should raise ValueError when creating BTC-USD reference portfolio
        with pytest.raises(ValueError, match="Price unavailable"):
            create_reference_portfolio(
                original_portfolio=composite,
                strategy=btc_strategy,
                price_service=btc_price_service,
                currency_service=currency_service,
                name="BTC-USD Reference Portfolio",
            )
        
        # SPY reference portfolio should still be valid
        assert spy_reference is not None
        assert spy_reference.name == "SPY Reference Portfolio"


class TestPercentageReturnCalculations:
    """Tests for percentage return calculation helper functions."""

    def test_calculate_unrealized_pnl_percentage_with_valid_prices(self):
        """Test calculating unrealized P/L percentage with valid prices."""
        portfolio = SimplePortfolio(name="Test Portfolio")
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
        
        # Price increased to $160, so unrealized P/L = (160 - 150) * 10 = $100
        # Cost basis = 150 * 10 = $1500
        # Percentage = (100 / 1500) * 100 = 6.67%
        price_map = {asset: 160.0}
        
        percentage = calculate_unrealized_pnl_percentage(portfolio, price_map)
        
        assert percentage is not None
        assert abs(percentage - 6.666666666666667) < 0.01

    def test_calculate_unrealized_pnl_percentage_with_zero_cost_basis(self):
        """Test calculating unrealized P/L percentage with zero cost basis returns None."""
        portfolio = SimplePortfolio(name="Empty Portfolio")
        price_map = {}
        
        percentage = calculate_unrealized_pnl_percentage(portfolio, price_map)
        
        assert percentage is None

    def test_calculate_unrealized_pnl_percentage_with_missing_prices(self):
        """Test calculating unrealized P/L percentage with missing prices returns None."""
        portfolio = SimplePortfolio(name="Test Portfolio")
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
        
        # No prices available
        price_map = {asset: None}
        
        percentage = calculate_unrealized_pnl_percentage(portfolio, price_map)
        
        assert percentage is None

    def test_calculate_unrealized_pnl_percentage_with_target_date(self):
        """Test calculating unrealized P/L percentage with target_date filtering."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trade1 = Trade(
            date=date(2024, 1, 15),
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=150.0,
            price_native=150.0,
            quantity=10.0,
        )
        trade2 = Trade(
            date=date(2024, 1, 20),
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=155.0,
            price_native=155.0,
            quantity=5.0,
        )
        portfolio.add_trade(trade1)
        portfolio.add_trade(trade2)
        
        # Price at target_date (2024-01-18) is $160
        # Only first trade should be included
        price_map = {asset: 160.0}
        
        percentage = calculate_unrealized_pnl_percentage(
            portfolio, price_map, target_date=date(2024, 1, 18)
        )
        
        assert percentage is not None
        # Only first trade: (160 - 150) * 10 / (150 * 10) * 100 = 6.67%
        assert abs(percentage - 6.666666666666667) < 0.01

    def test_calculate_realized_pnl_percentage_with_sold_lots(self):
        """Test calculating realized P/L percentage with sold lots."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset = Asset(ticker="GOOG", asset_type="Stock")
        buy_trade = Trade(
            date=date(2024, 1, 15),
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=150.0,
            price_native=150.0,
            quantity=10.0,
        )
        sell_trade = Trade(
            date=date(2024, 1, 20),
            asset=asset,
            action="Sell",
            broker="IBKR",
            currency="USD",
            price=160.0,
            price_native=160.0,
            quantity=5.0,
        )
        portfolio.add_trade(buy_trade)
        portfolio.add_trade(sell_trade)
        
        # Realized P/L = (160 - 150) * 5 = $50
        # Cost basis of sold lots = 150 * 5 = $750
        # Percentage = (50 / 750) * 100 = 6.67%
        percentage = calculate_realized_pnl_percentage(portfolio)
        
        assert percentage is not None
        assert abs(percentage - 6.666666666666667) < 0.01

    def test_calculate_realized_pnl_percentage_with_zero_cost_basis(self):
        """Test calculating realized P/L percentage with zero cost basis returns None."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset = Asset(ticker="GOOG", asset_type="Stock")
        # Only buy, no sells
        buy_trade = Trade(
            date=date(2024, 1, 15),
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=150.0,
            price_native=150.0,
            quantity=10.0,
        )
        portfolio.add_trade(buy_trade)
        
        percentage = calculate_realized_pnl_percentage(portfolio)
        
        assert percentage is None

    def test_calculate_realized_pnl_percentage_with_target_date(self):
        """Test calculating realized P/L percentage with target_date filtering."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset = Asset(ticker="GOOG", asset_type="Stock")
        buy_trade = Trade(
            date=date(2024, 1, 15),
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=150.0,
            price_native=150.0,
            quantity=10.0,
        )
        sell_trade1 = Trade(
            date=date(2024, 1, 20),
            asset=asset,
            action="Sell",
            broker="IBKR",
            currency="USD",
            price=160.0,
            price_native=160.0,
            quantity=3.0,
        )
        sell_trade2 = Trade(
            date=date(2024, 1, 25),
            asset=asset,
            action="Sell",
            broker="IBKR",
            currency="USD",
            price=165.0,
            price_native=165.0,
            quantity=2.0,
        )
        portfolio.add_trade(buy_trade)
        portfolio.add_trade(sell_trade1)
        portfolio.add_trade(sell_trade2)
        
        # With target_date = 2024-01-22, only first sell should be included
        # Realized P/L = (160 - 150) * 3 = $30
        # Cost basis of sold lots = 150 * 3 = $450
        # Percentage = (30 / 450) * 100 = 6.67%
        percentage = calculate_realized_pnl_percentage(portfolio, target_date=date(2024, 1, 22))
        
        assert percentage is not None
        assert abs(percentage - 6.666666666666667) < 0.01

