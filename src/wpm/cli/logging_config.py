"""CLI-specific logging configuration."""

import logging
from pathlib import Path


def setup_cli_logging() -> None:
    """Configure CLI-specific logging to write to logs/wpmcli.log.
    
    This function configures logging for the CLI only, directing all logs
    to logs/wpmcli.log and suppressing stdout/stderr output. This ensures
    a clean CLI interface while preserving logs for debugging.
    
    Library users are not affected and can still configure their own logging
    using wpm.utils.setup_logging().
    """
    # Create logs directory if it doesn't exist
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Get the root "wpm" logger to capture all module logs
    wpm_logger = logging.getLogger("wpm")
    wpm_logger.setLevel(logging.INFO)
    
    # Remove any existing StreamHandlers to suppress stdout/stderr output
    # This ensures no logs appear in the console
    for handler in wpm_logger.handlers[:]:
        if isinstance(handler, logging.StreamHandler):
            wpm_logger.removeHandler(handler)
    
    # Add FileHandler for logs/wpmcli.log
    log_file = logs_dir / "wpmcli.log"
    file_handler = logging.FileHandler(log_file, mode="a")
    file_handler.setLevel(logging.INFO)
    
    # Use the same formatter as setup_logging() for consistency
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(formatter)
    
    # Only add handler if it doesn't already exist (avoid duplicates on reload)
    if not any(isinstance(h, logging.FileHandler) and h.baseFilename == str(log_file.absolute()) 
               for h in wpm_logger.handlers):
        wpm_logger.addHandler(file_handler)
