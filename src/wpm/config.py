"""Application-level configuration module.

This module handles all application configuration following these principles:
- Sensitive configuration (API keys, access tokens) loaded from .env file using python-dotenv
- Storage configuration (cache directories, file paths) defined as class variables
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file (if present)
load_dotenv()


class Config:
    """Application configuration class.
    
    Sensitive configuration values are loaded from environment variables (via .env file).
    Storage configuration values are defined as class variables.
    """
    
    # Storage configuration (class variables)
    CACHE_DIR = Path.home() / ".wpm"
    CACHE_FILE = CACHE_DIR / "price_cache.parquet"
    CACHE_VALIDITY_MINUTES = 10
    CURRENCY_CACHE_FILE = CACHE_DIR / "currency_cache.parquet"
    CURRENCY_CACHE_VALIDITY_MINUTES = 1440  # 24 hours
    HISTORICAL_CACHE_FILE = CACHE_DIR / "historical_price_cache.parquet"
    ASSET_METADATA_CACHE_FILE = CACHE_DIR / "asset_metadata_cache.parquet"
    SPLIT_CACHE_FILE = CACHE_DIR / "split_cache.parquet"
    
    # Sensitive configuration (loaded from .env file via os.getenv)
    COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")  # Optional - None if not set
    COINGECKO_API_IS_DEMO = os.getenv("COINGECKO_API_IS_DEMO", "false").lower() in ("true", "1", "yes")  # Optional - defaults to False
    
    # Google Sheets Configuration (loaded from .env)
    # These are optional - only validated when import-sheets command is used
    GOOGLE_SHEETS_CREDENTIALS_PATH = os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH")
    GOOGLE_SHEETS_DRIVE_PATH = os.getenv("GOOGLE_SHEETS_DRIVE_PATH")
    GOOGLE_SHEETS_SPREADSHEET_ID = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID")

