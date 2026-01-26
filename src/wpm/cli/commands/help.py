"""Help command handler."""


def cmd_help() -> None:
    """Handle 'help' command.

    Displays a list of available commands and their usage.
    """
    print("Available commands:")
    print()
    print("  list portfolios")
    print("    List all sub-portfolios within the composite portfolio")
    print()
    print("  show portfolio <name> [--up-to YYYY-MM-DD]")
    print("    Show all assets in the specified sub-portfolio")
    print("    --up-to: Optional date for historical portfolios (shows weekly summary)")
    print()
    print("  show all [--up-to YYYY-MM-DD]")
    print("    Show all assets in the composite portfolio (aggregated)")
    print("    --up-to: Optional date for historical portfolios (shows weekly summary)")
    print()
    print("  show asset <ticker> [--from YYYY-MM-DD] [--brokers \"broker1,broker2,...\"]")
    print("    Show asset position for the specified ticker")
    print("    --from: Optional start date for historical portfolios")
    print("    --brokers: Optional comma-separated list of broker names to filter by")
    print()
    print("  metadata <ticker>")
    print("    Display metadata for the specified asset ticker")
    print()
    print("  lots <ticker>")
    print("    Display all lots (FIFO purchase records) for the specified ticker")
    print()
    print("  breakdown [<name>] <by>")
    print("    Show portfolio breakdown by dimension")
    print("    <by>: asset_type, ticker, purchase_period, or broker")
    print("    [<name>]: Optional sub-portfolio name")
    print()
    print("  help")
    print("    Display this help message")
    print()
    print("  quit, exit")
    print("    Exit the interactive mode")
