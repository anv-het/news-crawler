"""
Logger module - Configurable logging to file and console.
Creates log files with datetime stamp in the configured log directory.
"""

import logging
import os
from datetime import datetime
from pathlib import Path


_logger_instance = None


def setup_logger(settings) -> logging.Logger:
    """
    Set up and return a configured logger based on settings.

    Args:
        settings: Settings object with LOG_* attributes.

    Returns:
        logging.Logger: Configured logger instance.
    """
    global _logger_instance

    if _logger_instance is not None:
        return _logger_instance

    logger = logging.getLogger("web_crawler")
    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    # Prevent duplicate handlers
    logger.handlers.clear()

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if not settings.LOG_ENABLED:
        logger.addHandler(logging.NullHandler())
        _logger_instance = logger
        return logger

    # Console handler
    if settings.LOG_TO_CONSOLE:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # File handler
    if settings.LOG_TO_FILE:
        # Resolve path relative to project root (scrapy/)
        project_root = Path(__file__).resolve().parent.parent
        log_dir = project_root / settings.LOG_FILE_PATH
        log_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"scraper_{timestamp}.log"

        file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
        file_handler.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        logger.info(f"Log file created: {log_file}")

    _logger_instance = logger
    return logger


def get_logger() -> logging.Logger:
    """Get the existing logger instance, or a default one."""
    global _logger_instance
    if _logger_instance is None:
        return logging.getLogger("web_crawler")
    return _logger_instance
