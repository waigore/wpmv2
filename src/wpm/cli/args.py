"""Command-line argument parsing for CLI."""

import argparse
from datetime import date
from typing import List, Optional

from wpm.utils import normalize_date


def parse_args() -> argparse.Namespace:
    """Parse and validate command-line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="WPM Command-Line Utility for Portfolio Management"
    )
    parser.add_argument(
        "command",
        choices=["import"],
        help="Command to execute (currently only 'import' is supported)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="End date (YYYY-MM-DD) for historical portfolio import. "
             "Only trades on or before this date will be included.",
    )

    return parser.parse_args()


def parse_up_to_date(args: List[str]) -> tuple[Optional[date], List[str]]:
    """Parse --up-to date argument from command args.

    Args:
        args: Command arguments list

    Returns:
        Tuple of (up_to_date or None, remaining args without --up-to flag and date)
    """
    up_to_date = None
    remaining_args = []
    i = 0
    while i < len(args):
        if args[i] == "--up-to" and i + 1 < len(args):
            try:
                up_to_date = normalize_date(args[i + 1])
                i += 2  # Skip both --up-to and the date
            except ValueError:
                # Invalid date format, keep the --up-to flag in remaining args
                remaining_args.append(args[i])
                i += 1
        else:
            remaining_args.append(args[i])
            i += 1
    return up_to_date, remaining_args


def parse_from_date(args: List[str]) -> tuple[Optional[date], List[str]]:
    """Parse --from date argument from command args.

    Args:
        args: Command arguments list

    Returns:
        Tuple of (from_date or None, remaining args without --from flag and date)
    """
    from_date = None
    remaining_args = []
    i = 0
    while i < len(args):
        if args[i] == "--from" and i + 1 < len(args):
            try:
                from_date = normalize_date(args[i + 1])
                i += 2  # Skip both --from and the date
            except ValueError:
                # Invalid date format, keep the --from flag in remaining args
                remaining_args.append(args[i])
                i += 1
        else:
            remaining_args.append(args[i])
            i += 1
    return from_date, remaining_args


def parse_brokers(args: List[str]) -> tuple[Optional[List[str]], List[str]]:
    """Parse --brokers argument from command args.

    Args:
        args: Command arguments list

    Returns:
        Tuple of (brokers list or None, remaining args without --brokers flag and value)
    """
    brokers = None
    remaining_args = []
    i = 0
    while i < len(args):
        if args[i] == "--brokers" and i + 1 < len(args):
            brokers_str = args[i + 1]
            # Strip outer quotes if present (handles "broker1,broker2" format)
            if brokers_str.startswith('"') and brokers_str.endswith('"'):
                brokers_str = brokers_str[1:-1]
            elif brokers_str.startswith("'") and brokers_str.endswith("'"):
                brokers_str = brokers_str[1:-1]
            # Split by comma and strip whitespace from each broker name
            brokers = [broker.strip() for broker in brokers_str.split(",") if broker.strip()]
            # If empty list after stripping, set to None
            if not brokers:
                brokers = None
            i += 2  # Skip both --brokers and the value
        else:
            remaining_args.append(args[i])
            i += 1
    return brokers, remaining_args
