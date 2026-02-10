"""
Scrapy Items - Data containers for the crawler pipeline.
=========================================================

CrawlResultItem: The complete result for one query containing:
  - query name
  - search results (first page URLs)
  - top sites crawled (with all links + doc links)
  - stats
"""

import scrapy


class CrawlResultItem(scrapy.Item):
    """
    Complete crawl result for a single query.

    Structure mirrors the JSON output:
    {
        "query": "reliance investor relations",
        "timestamp": "2026-02-10T14:30:00",
        "search_results": [...],
        "top_sites_crawled": [
            {
                "rank": 1,
                "url": "...",
                "page_title": "...",
                "all_links": [...],
                "doc_links": [...]
            }
        ],
        "stats": {...}
    }
    """
    query = scrapy.Field()
    timestamp = scrapy.Field()
    search_results = scrapy.Field()
    top_sites_crawled = scrapy.Field()
    stats = scrapy.Field()
