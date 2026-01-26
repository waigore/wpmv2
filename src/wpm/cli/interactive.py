"""Interactive command loop for CLI."""

import logging
import shlex
import sys
from typing import Dict, Optional

from wpm.asset import AssetService
from wpm.models import Portfolio
from wpm.portfolio import CompositePortfolio
from wpm.pricing import PriceService

from .args import parse_brokers, parse_from_date, parse_up_to_date
from .commands import asset, breakdown, help, portfolio

logger = logging.getLogger(__name__)

# Constants
PROMPT = "wpm> "


def run_interactive_mode(
    composite: CompositePortfolio,
    price_service: PriceService,
    reference_portfolios: Dict[str, Portfolio] = None,
) -> None:
    """Run interactive command loop.

    Args:
        composite: Composite portfolio
        price_service: Price service for retrieving prices
        reference_portfolios: Dictionary mapping reference portfolio names to Portfolio objects
    """
    if reference_portfolios is None:
        reference_portfolios = {}
    print("Entering interactive mode. Type 'Quit' to exit.")
    logger.info("Entering interactive mode")
    
    # Initialize asset service for metadata commands (with price_service for retriever access)
    asset_service = AssetService(price_service=price_service)

    while True:
        try:
            user_input = input(PROMPT).strip()

            if not user_input:
                continue

            # Parse command using shlex to properly handle quoted strings
            try:
                parts = shlex.split(user_input)
            except ValueError:
                # If shlex fails (e.g., unmatched quotes), fall back to simple split
                parts = user_input.split()
            command = parts[0].lower()
            args = parts[1:]

            # Handle quit/exit (case-insensitive)
            if command in ("quit", "exit"):
                print("Exiting...")
                logger.info("Exiting interactive mode")
                sys.exit(0)

            # Route to command handlers
            if command == "list" and len(args) == 1 and args[0] == "portfolios":
                portfolio.cmd_list_portfolios(composite)
            elif command == "show":
                if len(args) >= 1 and args[0] == "all":
                    # Parse --up-to argument if present
                    up_to_date, remaining_args = parse_up_to_date(args[1:])
                    if remaining_args:
                        print("Unknown arguments: 'show all' only accepts --up-to YYYY-MM-DD")
                    else:
                        portfolio.cmd_show_all(composite, price_service, up_to_date, reference_portfolios)
                elif len(args) >= 2 and args[0] == "portfolio":
                    # Parse --up-to argument if present
                    portfolio_name = args[1]
                    up_to_date, remaining_args = parse_up_to_date(args[2:])
                    if remaining_args:
                        print("Unknown arguments: 'show portfolio <name>' only accepts --up-to YYYY-MM-DD")
                    else:
                        portfolio.cmd_show_portfolio(composite, portfolio_name, price_service, up_to_date)
                elif len(args) >= 2 and args[0] == "asset":
                    # Parse --from and --brokers arguments if present
                    ticker = args[1]
                    # Parse --from first, then parse --brokers from remaining args
                    from_date, remaining_after_from = parse_from_date(args[2:])
                    brokers, remaining_args = parse_brokers(remaining_after_from)
                    if remaining_args:
                        print("Unknown arguments: 'show asset <ticker>' only accepts --from YYYY-MM-DD and --brokers \"broker1,broker2,...\"")
                    else:
                        if from_date is not None and not composite.is_historical:
                            print("Error: --from can only be used with historical portfolios.")
                        else:
                            asset.cmd_show_asset(composite, ticker, price_service, from_date, brokers)
                else:
                    print("Unknown command: 'show'. Usage: 'show portfolio <name> [--up-to YYYY-MM-DD]', 'show all [--up-to YYYY-MM-DD]', or 'show asset <ticker> [--from YYYY-MM-DD] [--brokers \"broker1,broker2,...\"]'")
            elif command == "breakdown":
                breakdown.cmd_breakdown(composite, args)
            elif command == "lots":
                if len(args) == 1:
                    asset.cmd_show_lots(composite, args[0], price_service)
                else:
                    print("Error: Ticker required. Usage: lots <ticker>")
            elif command == "metadata":
                if len(args) == 1:
                    asset.cmd_metadata(composite, args[0], asset_service)
                else:
                    print("Error: Ticker required. Usage: metadata <ticker>")
            elif command == "help":
                help.cmd_help()
            else:
                print(f"Unknown command: '{user_input}'. Type 'help' for available commands.")

        except EOFError:
            # Handle Ctrl+D
            print("\nExiting...")
            logger.info("Exiting interactive mode (EOF)")
            sys.exit(0)
        except KeyboardInterrupt:
            # Handle Ctrl+C
            print("\nExiting...")
            logger.info("Exiting interactive mode (interrupt)")
            sys.exit(0)
        except Exception as e:
            logger.error(f"Error in interactive mode: {e}", exc_info=True)
            print(f"Error: {str(e)}")
