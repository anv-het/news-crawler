"""
=============================================================================
WEB CRAWLER - Main Entry Point
=============================================================================

FLOW:
  1. Read queries from queries.csv
  2. For each query:
     a. Search DuckDuckGo → get top 15-20 first-page URLs
     b. Pick top 3 URLs from search results
     c. Visit each of the top 3 URLs:
        - Collect ALL href links on the page
        - Collect document links (pdf, xlsx, csv, ppt, doc, etc.)
     d. Save results to JSON, CSV, and MongoDB (based on switches)

DATA STRUCTURE:
  {
    "query": "reliance investor relations",
    "timestamp": "2026-02-10T12:00:00",
    "search_results": [
      {"title": "...", "url": "...", "snippet": "..."}
    ],
    "top_sites_crawled": [
      {
        "rank": 1,
        "url": "...",
        "page_title": "...",
        "all_links": ["...", "..."],
        "doc_links": ["...", "..."]
      }
    ]
  }

Usage:
  python main.py                    # Process all queries from queries.csv
  python main.py --query "reliance" # Process a single query
  python main.py --file custom.csv  # Use a custom queries file
=============================================================================
"""

import sys
import os
import csv
import argparse
from datetime import datetime
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import Settings
from utils.logger import setup_logger, get_logger
from utils.delay import DelayManager
from core.searcher import DuckDuckGoSearcher
from core.crawler import PageCrawler
from pipeline.json_saver import JsonSaver
from pipeline.csv_saver import CsvSaver
from pipeline.mongo_saver import MongoSaver


def load_queries(filepath: str) -> list[str]:
    """
    Load queries from a CSV file (one query per row, first column).

    Args:
        filepath: Path to the queries CSV file.

    Returns:
        List of query strings.
    """
    queries = []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if row and row[0].strip():
                queries.append(row[0].strip())
    return queries


def process_query(
    query: str,
    searcher: DuckDuckGoSearcher,
    crawler: PageCrawler,
    settings: Settings,
    logger,
) -> dict:
    """
    Process a single query through the full pipeline.

    Steps:
      1. Search DuckDuckGo for the query
      2. Get top N URLs
      3. Visit each top URL and collect links + doc links
      4. Return structured data

    Args:
        query: Search query string.
        searcher: DuckDuckGoSearcher instance.
        crawler: PageCrawler instance.
        settings: Settings instance.
        logger: Logger instance.

    Returns:
        Dict with full crawl results.
    """
    logger.info(f"{'='*60}")
    logger.info(f"PROCESSING QUERY: '{query}'")
    logger.info(f"{'='*60}")

    # Step 1: Search DuckDuckGo
    search_results = searcher.search(query)

    if not search_results:
        logger.warning(f"No search results found for '{query}'")
        return {
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "search_results": [],
            "top_sites_crawled": [],
            "stats": {
                "total_search_results": 0,
                "sites_crawled": 0,
                "total_links_found": 0,
                "total_doc_links_found": 0,
            },
        }

    logger.info(
        f"Step 1 Complete: {len(search_results)} search results for '{query}'"
    )

    # Step 2: Pick top N URLs to visit
    top_n = min(settings.TOP_URLS_TO_VISIT, len(search_results))
    top_urls = search_results[:top_n]

    logger.info(f"Step 2: Will visit top {top_n} URLs:")
    for i, sr in enumerate(top_urls, 1):
        logger.info(f"  {i}. {sr['url']}")

    # Step 3: Visit each top URL and collect links
    top_sites_crawled = []
    total_links = 0
    total_docs = 0

    for rank, sr in enumerate(top_urls, 1):
        url = sr["url"]
        logger.info(f"Step 3.{rank}: Crawling URL #{rank}: {url}")

        crawl_result = crawler.crawl_page(url)

        site_data = {
            "rank": rank,
            "url": url,
            "search_title": sr.get("title", ""),
            "search_snippet": sr.get("snippet", ""),
            "page_title": crawl_result.get("page_title", ""),
            "status": crawl_result.get("status"),
            "all_links": crawl_result.get("all_links", []),
            "doc_links": crawl_result.get("doc_links", []),
            "total_links_count": len(crawl_result.get("all_links", [])),
            "doc_links_count": len(crawl_result.get("doc_links", [])),
        }

        total_links += site_data["total_links_count"]
        total_docs += site_data["doc_links_count"]

        top_sites_crawled.append(site_data)

        logger.info(
            f"  → Found {site_data['total_links_count']} links, "
            f"{site_data['doc_links_count']} doc links"
        )

    # Build final data structure
    data = {
        "query": query,
        "timestamp": datetime.now().isoformat(),
        "search_results": search_results,
        "top_sites_crawled": top_sites_crawled,
        "stats": {
            "total_search_results": len(search_results),
            "sites_crawled": len(top_sites_crawled),
            "total_links_found": total_links,
            "total_doc_links_found": total_docs,
        },
    }

    logger.info(
        f"Query '{query}' complete: "
        f"{len(search_results)} results, "
        f"{len(top_sites_crawled)} sites crawled, "
        f"{total_links} links, {total_docs} doc links"
    )

    return data


def main():
    """Main entry point - orchestrate the full crawling pipeline."""

    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Web Crawler - DuckDuckGo Search & Page Crawler"
    )
    parser.add_argument(
        "--query", "-q", type=str, help="Single query to process"
    )
    parser.add_argument(
        "--file", "-f", type=str, default="queries.csv",
        help="Path to queries CSV file (default: queries.csv)"
    )
    args = parser.parse_args()

    # Initialize settings
    settings = Settings()

    # Setup logger
    logger = setup_logger(settings)
    logger.info("=" * 70)
    logger.info("WEB CRAWLER STARTED")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info("=" * 70)
    logger.info(f"Configuration:\n{settings}")

    # Initialize delay manager
    delay_manager = DelayManager(settings)

    # Initialize core modules
    searcher = DuckDuckGoSearcher(settings, delay_manager)
    crawler = PageCrawler(settings, delay_manager)

    # Initialize pipeline savers
    json_saver = JsonSaver(settings)
    csv_saver = CsvSaver(settings)
    mongo_saver = MongoSaver(settings)

    # Connect to MongoDB if enabled
    if settings.SAVE_TO_MONGO:
        mongo_saver.connect()

    # Load queries
    if args.query:
        queries = [args.query]
        logger.info(f"Single query mode: '{args.query}'")
    else:
        queries_file = PROJECT_ROOT / args.file
        if not queries_file.exists():
            logger.error(f"Queries file not found: {queries_file}")
            sys.exit(1)
        queries = load_queries(str(queries_file))
        logger.info(f"Loaded {len(queries)} queries from {queries_file}")

    # Process each query
    total_queries = len(queries)
    successful = 0
    failed = 0

    for idx, query in enumerate(queries, 1):
        logger.info(f"\n[{idx}/{total_queries}] Processing query: '{query}'")

        try:
            # Process the query through the full pipeline
            data = process_query(query, searcher, crawler, settings, logger)

            # Save results via pipeline
            if data["search_results"]:  # Only save if we got results
                # Save to JSON
                json_path = json_saver.save(query, data)
                if json_path:
                    logger.info(f"  ✓ JSON saved: {json_path}")

                # Save to CSV
                csv_path = csv_saver.save(query, data)
                if csv_path:
                    logger.info(f"  ✓ CSV saved: {csv_path}")

                # Save to MongoDB
                mongo_id = mongo_saver.save(query, data)
                if mongo_id:
                    logger.info(f"  ✓ MongoDB saved: {mongo_id}")

                successful += 1
            else:
                logger.warning(f"  ⚠ No results for '{query}', skipping save")
                failed += 1

        except Exception as e:
            logger.error(f"  ✗ Failed to process '{query}': {e}")
            failed += 1

    # Cleanup
    crawler.close()
    mongo_saver.close()

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("CRAWL COMPLETE - SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Total queries: {total_queries}")
    logger.info(f"Successful:    {successful}")
    logger.info(f"Failed:        {failed}")
    logger.info(f"Timestamp:     {datetime.now().isoformat()}")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
