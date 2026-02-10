"""
Settings module - Loads and validates all configuration from .env file.
"""

import os
from pathlib import Path
from dotenv import load_dotenv


class Settings:
    """Centralized configuration loaded from .env file."""

    def __init__(self):
        # Load .env from project root (scrapy/)
        env_path = Path(__file__).resolve().parent.parent / ".env"
        load_dotenv(dotenv_path=env_path)

        # -- Search Settings --
        self.SEARCH_ENGINE = os.getenv("SEARCH_ENGINE", "duckduckgo")
        self.MAX_SEARCH_RESULTS = int(os.getenv("MAX_SEARCH_RESULTS", "20"))
        self.TOP_URLS_TO_VISIT = int(os.getenv("TOP_URLS_TO_VISIT", "3"))

        # -- Save Switches --
        self.SAVE_TO_JSON = os.getenv("SAVE_TO_JSON", "true").lower() == "true"
        self.SAVE_TO_MONGO = os.getenv("SAVE_TO_MONGO", "true").lower() == "true"
        self.SAVE_TO_CSV = os.getenv("SAVE_TO_CSV", "true").lower() == "true"

        # -- MongoDB --
        self.MONGO_ENABLED = os.getenv("MONGO_ENABLED", "true").lower() == "true"
        self.MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.MONGO_DATABASE = os.getenv("MONGO_DATABASE", "WEB_CRAWLER")
        self.MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "invester_relation_scrapy")

        # -- Delay Settings --
        self.DELAY_MIN = float(os.getenv("DELAY_MIN", "1"))
        self.DELAY_MAX = float(os.getenv("DELAY_MAX", "3"))
        self.LONG_DELAY_MIN = float(os.getenv("LONG_DELAY_MIN", "10.0"))
        self.LONG_DELAY_MAX = float(os.getenv("LONG_DELAY_MAX", "15.0"))
        self.LONG_DELAY_AFTER_COUNT = int(os.getenv("LONG_DELAY_AFTER_COUNT", "30"))

        # -- Logging --
        self.LOG_ENABLED = os.getenv("LOG_ENABLED", "true").lower() == "true"
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        self.LOG_TO_FILE = os.getenv("LOG_TO_FILE", "true").lower() == "true"
        self.LOG_TO_CONSOLE = os.getenv("LOG_TO_CONSOLE", "true").lower() == "true"
        self.LOG_FILE_PATH = os.getenv("LOG_FILE_PATH", "logs/")

        # -- Data Paths --
        self.DATA_CSV_PATH = os.getenv("DATA_CSV_PATH", "DATA/CSV/")
        self.DATA_JSON_PATH = os.getenv("DATA_JSON_PATH", "DATA/JSON/")

        # -- Request Settings --
        self.REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
        self.USER_AGENT = os.getenv(
            "USER_AGENT",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )

    def __repr__(self):
        return (
            f"Settings(\n"
            f"  SEARCH_ENGINE={self.SEARCH_ENGINE},\n"
            f"  MAX_SEARCH_RESULTS={self.MAX_SEARCH_RESULTS},\n"
            f"  TOP_URLS_TO_VISIT={self.TOP_URLS_TO_VISIT},\n"
            f"  SAVE_TO_JSON={self.SAVE_TO_JSON},\n"
            f"  SAVE_TO_CSV={self.SAVE_TO_CSV},\n"
            f"  SAVE_TO_MONGO={self.SAVE_TO_MONGO},\n"
            f"  MONGO_DATABASE={self.MONGO_DATABASE},\n"
            f"  DELAY_MIN={self.DELAY_MIN}, DELAY_MAX={self.DELAY_MAX},\n"
            f"  LOG_LEVEL={self.LOG_LEVEL}\n"
            f")"
        )
