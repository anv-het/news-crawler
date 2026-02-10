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
    from scrapy.crawler import CrawlerProcess
    from scrapy.utils.project import get_project_settings

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
