"""Application-level configuration module.

This module handles all application configuration following these principles:
- Sensitive configuration (API keys, access tokens) loaded from .env file using python-dotenv
- Storage configuration (cache directories, file paths) defined as class variables
"""

from pathlib import Path
import os

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
    
    # Sensitive configuration (loaded from .env file via os.getenv)
    COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")  # Optional - None if not set

