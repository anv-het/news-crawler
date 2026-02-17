"""
=============================================================================
INVESTOR CRAWLER - Scrapy Framework Entry Point
=============================================================================

Usage:
    python main.py                              # All queries from queries.csv
    python main.py --query "reliance investor"  # Single query
    python main.py --file custom.csv            # Custom queries file

Or using scrapy directly:
    scrapy crawl investor_spider
    scrapy crawl investor_spider -a query="reliance investor relations"
    scrapy crawl investor_spider -a file="custom.csv"
=============================================================================
"""

import sys
import argparse
from pathlib import Path

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))


def main():
    """Run the investor spider via CrawlerProcess."""
    import logging
    from scrapy.crawler import CrawlerProcess
    from scrapy.utils.project import get_project_settings
    from scrapy.utils.log import configure_logging

    # Parse args
    parser = argparse.ArgumentParser(
        description="Investor Relations Web Crawler (Scrapy Framework)"
    )
    parser.add_argument(
        "--query", "-q", type=str,
        help="Single query to process"
    )
    parser.add_argument(
        "--file", "-f", type=str, default="queries.csv",
        help="Path to queries CSV file (default: queries.csv)"
    )
    args = parser.parse_args()

    # Load Scrapy settings
    settings = get_project_settings()

    # Inject PROJECT_ROOT so pipelines can resolve paths
    settings.set("PROJECT_ROOT", str(PROJECT_ROOT), priority="cmdline")

    # Disable Scrapy's default logging to configure our own
    configure_logging(install_root_handler=False)
    
    # Set up logging to BOTH file and console
    log_level = settings.get("LOG_LEVEL", "INFO")
    log_format = '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
    log_dateformat = '%Y-%m-%d %H:%M:%S'
    
    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Console handler (always show in terminal)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(log_format, log_dateformat)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (if LOG_FILE is set)
    log_file = settings.get("LOG_FILE")
    if log_file:
        file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
        file_handler.setLevel(log_level)
        file_formatter = logging.Formatter(log_format, log_dateformat)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    # Create and run the spider
    process = CrawlerProcess(settings)

    spider_kwargs = {}
    if args.query:
        spider_kwargs["query"] = args.query
    if args.file != "queries.csv":
        spider_kwargs["file"] = args.file

    process.crawl("investor_spider", **spider_kwargs)
    process.start()


if __name__ == "__main__":
    main()
