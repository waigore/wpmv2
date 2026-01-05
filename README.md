# WPM (Wealth Portfolio Manager)

Simple portfolio manager and planner (Python library + CLI)

## Installation

### Development Installation

For development, install the package in editable mode:

```bash
pip install -e ".[dev]"
```

This will install the package and all development dependencies (pytest, pytest-cov, pytest-mock).

### Production Installation

```bash
pip install .
```

## Usage

### CLI Tool

After installation, use the `wpm` command:

```bash
wpm import
```

This will:
1. Import CSV files from the `import/` directory
2. Fetch prices for all assets
3. Enter interactive mode for portfolio queries

### Python Library

Import and use the library in your Python code:

```python
from wpm import SimplePortfolio, Asset, Trade
from datetime import date

# Create a portfolio
portfolio = SimplePortfolio("My Portfolio")

# Create an asset and trade
asset = Asset(ticker="GOOG", asset_type="Stock")
trade = Trade(
    date=date(2024, 1, 15),
    asset=asset,
    action="Buy",
    broker="IBKR",
    price=150.0,
    quantity=10.0,
)

# Add trade to portfolio
portfolio.add_trade(trade)

# Get positions
positions = portfolio.get_positions()
```

## Development

### Running Tests

```bash
pytest
```

### Documentation

To generate markdown documentation from docstrings, ensure you have `pydoc-markdown` installed as a development dependency:

```bash
uv add --dev pydoc-markdown
```

Then generate the documentation:

```bash
pydoc-markdown -I src -p wpm --render-toc > src/wpm/docs/api.md
```

This will generate markdown documentation for all modules in `src/wpm/` and place it in the `src/wpm/docs/api.md` file. The generated documentation is included in version control and will be distributed with the package. After installation, the documentation will be available at `wpm/docs/api.md` in the installed package.

### Project Structure

The project uses the `src` layout:
- Package code: `src/wpm/`
- CLI entry point: `src/wpm/cli.py`
- Tests: `tests/`
- CSV imports: `import/`

### Version

The package version is automatically generated from the git commit SHA for bleeding-edge development. Format: `0.1.0.dev0+g{sha}` (or with `.dirty` suffix if working tree has uncommitted changes).

To generate/update the version before installation:

```bash
python scripts/generate_version.py
pip install -e ".[dev]"
```

The version script reads the current git commit SHA and updates `src/wpm/VERSION.txt`, which is used during package installation.

## License

Apache License 2.0
