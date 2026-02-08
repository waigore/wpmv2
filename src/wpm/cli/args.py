"""Command-line argument parsing for CLI."""

import argparse
from datetime import date
from typing import Callable, List, Optional, TypeVar

from wpm.utils import normalize_date

T = TypeVar("T")


def _parse_flag_value(
    args: List[str],
    flag: str,
    parse_value: Callable[[str], T],
) -> tuple[Optional[T], List[str]]:
    """Parse a single --flag value from args; return (parsed value or None, remaining args).

    If the flag is found and the next token parses successfully, consume both and return
    the parsed value. On parse error (ValueError), keep the flag in remaining args.
    """
    value: Optional[T] = None
    remaining: List[str] = []
    i = 0
    while i < len(args):
        if args[i] == flag and i + 1 < len(args):
            try:
                value = parse_value(args[i + 1])
                i += 2
            except ValueError:
                remaining.append(args[i])
                i += 1
        else:
            remaining.append(args[i])
            i += 1
    return value, remaining


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
        choices=["import", "import-sheets"],
        help="Command to execute ('import' for CSV files, 'import-sheets' for Google Sheets)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="End date (YYYY-MM-DD) for historical portfolio import. "
             "Only trades on or before this date will be included.",
    )
    parser.add_argument(
        "--profile",
        action="store_true",
        help="Enable cProfile and print performance stats at exit. "
             "Useful for identifying bottlenecks in import and show asset flows.",
    )

    return parser.parse_args()


def _parse_brokers_value(s: str) -> Optional[List[str]]:
    """Parse --brokers value: strip outer quotes, split by comma, strip each; return None if empty."""
    if s.startswith('"') and s.endswith('"'):
        s = s[1:-1]
    elif s.startswith("'") and s.endswith("'"):
        s = s[1:-1]
    brokers = [broker.strip() for broker in s.split(",") if broker.strip()]
    return brokers if brokers else None


def parse_up_to_date(args: List[str]) -> tuple[Optional[date], List[str]]:
    """Parse --up-to date argument from command args.

    Args:
        args: Command arguments list

    Returns:
        Tuple of (up_to_date or None, remaining args without --up-to flag and date)
    """
    return _parse_flag_value(args, "--up-to", normalize_date)


def parse_from_date(args: List[str]) -> tuple[Optional[date], List[str]]:
    """Parse --from date argument from command args.

    Args:
        args: Command arguments list

    Returns:
        Tuple of (from_date or None, remaining args without --from flag and date)
    """
    return _parse_flag_value(args, "--from", normalize_date)


def parse_brokers(args: List[str]) -> tuple[Optional[List[str]], List[str]]:
    """Parse --brokers argument from command args.

    Args:
        args: Command arguments list

    Returns:
        Tuple of (brokers list or None, remaining args without --brokers flag and value)
    """
    return _parse_flag_value(args, "--brokers", _parse_brokers_value)
