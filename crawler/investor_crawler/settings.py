"""
Scrapy Settings - Investor Relations Crawler
=============================================

Loads configuration from .env and maps to Scrapy settings.
Includes: anti-ban middlewares, CAPTCHA avoidance, rotating user agents,
autothrottle, retry logic, and pipeline switches.
"""

import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Load .env from project root (crawler/)
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

# Helper
def _env_bool(key, default="false"):
    return os.getenv(key, default).strip().lower() == "true"

def _env_int(key, default="0"):
    return int(os.getenv(key, default))

def _env_float(key, default="0.0"):
    return float(os.getenv(key, default))

# ---------------------------------------------------------------------------
# Scrapy Core Settings
# ---------------------------------------------------------------------------
BOT_NAME = "investor_crawler"
SPIDER_MODULES = ["investor_crawler.spiders"]
NEWSPIDER_MODULE = "investor_crawler.spiders"

# Crawl responsibly
ROBOTSTXT_OBEY = _env_bool("RESPECT_ROBOTS_TXT", "false")

# ---------------------------------------------------------------------------
# Concurrency & Throttling
# ---------------------------------------------------------------------------
CONCURRENT_REQUESTS = _env_int("CONCURRENT_REQUESTS", "4")
CONCURRENT_REQUESTS_PER_DOMAIN = _env_int("CONCURRENT_REQUESTS_PER_DOMAIN", "2")
DOWNLOAD_DELAY = _env_float("DELAY_MIN", "1")
RANDOMIZE_DOWNLOAD_DELAY = True
DOWNLOAD_TIMEOUT = _env_int("REQUEST_TIMEOUT", "30")

# ---------------------------------------------------------------------------
# AutoThrottle (smart delay management)
# ---------------------------------------------------------------------------
AUTOTHROTTLE_ENABLED = _env_bool("AUTOTHROTTLE_ENABLED", "true")
AUTOTHROTTLE_START_DELAY = _env_float("AUTOTHROTTLE_START_DELAY", "2")
AUTOTHROTTLE_MAX_DELAY = _env_float("AUTOTHROTTLE_MAX_DELAY", "10")
AUTOTHROTTLE_TARGET_CONCURRENCY = _env_float("AUTOTHROTTLE_TARGET_CONCURRENCY", "1.0")
AUTOTHROTTLE_DEBUG = False

# ---------------------------------------------------------------------------
# Retry Settings
# ---------------------------------------------------------------------------
RETRY_ENABLED = True
RETRY_TIMES = _env_int("MAX_RETRIES", "3")
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

# ---------------------------------------------------------------------------
# Cookies & Redirects
# ---------------------------------------------------------------------------
COOKIES_ENABLED = True
REDIRECT_ENABLED = True
REDIRECT_MAX_TIMES = 5

# Allow non-200 responses to reach the spider (for CAPTCHA detection)
HTTPERROR_ALLOWED_CODES = [403, 429, 503]

# ---------------------------------------------------------------------------
# Downloader Middlewares (order matters!)
# ---------------------------------------------------------------------------
DOWNLOADER_MIDDLEWARES = {
    # Disable default UA middleware (we use our own rotating one)
    "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
    # Disable OffsiteMiddleware (we crawl external domains from DDG results)
    "scrapy.spidermiddlewares.offsite.OffsiteMiddleware": None,
    # Our custom middlewares
    "investor_crawler.middlewares.RotatingUserAgentMiddleware": 400,
    "investor_crawler.middlewares.CaptchaDetectionMiddleware": 450,
    "investor_crawler.middlewares.LongDelayMiddleware": 500,
    "investor_crawler.middlewares.RandomHeadersMiddleware": 550,
    # Keep retry & redirect
    "scrapy.downloadermiddlewares.retry.RetryMiddleware": 600,
}

# Disable OffsiteMiddleware via spider middlewares (it lives there in Scrapy)
SPIDER_MIDDLEWARES = {
    "scrapy.spidermiddlewares.offsite.OffsiteMiddleware": None,
}

# ---------------------------------------------------------------------------
# Item Pipelines (order matters!)
# ---------------------------------------------------------------------------
ITEM_PIPELINES = {}

# Enable pipelines based on .env switches
if _env_bool("SAVE_TO_JSON", "true"):
    ITEM_PIPELINES["investor_crawler.pipelines.JsonFilePipeline"] = 100

if _env_bool("SAVE_TO_CSV", "true"):
    ITEM_PIPELINES["investor_crawler.pipelines.CsvFilePipeline"] = 200

if _env_bool("SAVE_TO_MONGO", "true") and _env_bool("MONGO_ENABLED", "true"):
    ITEM_PIPELINES["investor_crawler.pipelines.MongoDBPipeline"] = 300

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_ENABLED = _env_bool("LOG_ENABLED", "true")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

_log_to_file = _env_bool("LOG_TO_FILE", "true")
if _log_to_file:
    _log_dir = PROJECT_ROOT / os.getenv("LOG_FILE_PATH", "logs/")
    _log_dir.mkdir(parents=True, exist_ok=True)
    _timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    LOG_FILE = str(_log_dir / f"scrapy_crawler_{_timestamp}.log")
    LOG_FILE_APPEND = False

LOG_STDOUT = _env_bool("LOG_TO_CONSOLE", "true")

# ---------------------------------------------------------------------------
# Custom Settings (accessible via spider.settings or self.settings)
# ---------------------------------------------------------------------------
# Search
SEARCH_ENGINE = os.getenv("SEARCH_ENGINE", "duckduckgo")
MAX_SEARCH_RESULTS = _env_int("MAX_SEARCH_RESULTS", "20")
TOP_URLS_TO_VISIT = _env_int("TOP_URLS_TO_VISIT", "3")

# Save switches
SAVE_TO_JSON = _env_bool("SAVE_TO_JSON", "true")
SAVE_TO_CSV = _env_bool("SAVE_TO_CSV", "true")
SAVE_TO_MONGO = _env_bool("SAVE_TO_MONGO", "true")

# MongoDB
MONGO_ENABLED = _env_bool("MONGO_ENABLED", "true")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DATABASE = os.getenv("MONGO_DATABASE", "WEB_CRAWLER")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "invester_relation_scrapy")

# Delay (for LongDelayMiddleware)
DELAY_MIN = _env_float("DELAY_MIN", "1")
DELAY_MAX = _env_float("DELAY_MAX", "3")
LONG_DELAY_MIN = _env_float("LONG_DELAY_MIN", "10.0")
LONG_DELAY_MAX = _env_float("LONG_DELAY_MAX", "15.0")
LONG_DELAY_AFTER_COUNT = _env_int("LONG_DELAY_AFTER_COUNT", "30")

# Data paths
DATA_CSV_PATH = os.getenv("DATA_CSV_PATH", "DATA/CSV/")
DATA_JSON_PATH = os.getenv("DATA_JSON_PATH", "DATA/JSON/")

# Anti-ban
ROTATING_USER_AGENT = _env_bool("ROTATING_USER_AGENT", "true")
CAPTCHA_DETECTION = _env_bool("CAPTCHA_DETECTION", "true")
RETRY_ON_CAPTCHA = _env_bool("RETRY_ON_CAPTCHA", "true")

# Request fingerprinting (Scrapy 2.7+)
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
FEED_EXPORT_ENCODING = "utf-8"
