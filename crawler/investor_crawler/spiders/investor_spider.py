"""
Investor Spider - DuckDuckGo Search + Page Crawl Spider
=========================================================

FLOW:
  1. Read queries from queries.csv (or --query arg)
  2. For each query:
     a. Search DuckDuckGo → get top 15-20 first-page URLs
     b. Pick top 3 URLs from search results
     c. Yield Scrapy requests to visit each top URL
     d. On each page response:
        - Extract ALL <a href> links
        - Identify document links (pdf, xlsx, csv, ppt, doc, etc.)
     e. After all 3 pages crawled, yield a CrawlResultItem
     f. Pipelines save to JSON / CSV / MongoDB

This spider uses Scrapy's request/callback model for proper
async handling and middleware integration (CAPTCHA, UA rotation, etc.)
"""

import csv
import logging
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import scrapy
from ddgs import DDGS

from investor_crawler.items import CrawlResultItem

logger = logging.getLogger(__name__)

# Document file extensions to detect
DOC_EXTENSIONS = {
    ".pdf", ".xlsx", ".xls", ".csv", ".ppt", ".pptx",
    ".doc", ".docx", ".zip", ".rar", ".txt",
}


class InvestorSpider(scrapy.Spider):
    """
    Spider that searches DuckDuckGo for investor-relations queries,
    then crawls the top N result pages to extract all links and
    document URLs.
    """

    name = "investor_spider"

    # PROJECT_ROOT is set here so pipelines can resolve paths.
    # It points to the crawler/ directory (2 levels up from this file).
    _project_root = str(Path(__file__).resolve().parent.parent.parent)

    custom_settings = {
        "FEEDS": {},
        "PROJECT_ROOT": _project_root,
    }

    def __init__(self, query=None, file=None, *args, **kwargs):
        """
        Args:
            query: Single query string (optional, overrides file).
            file:  Path to queries CSV file (default: queries.csv).
        """
        super().__init__(*args, **kwargs)
        self.single_query = query
        self.queries_file = file or "queries.csv"
        self.project_root = Path(self._project_root)

        # Will be populated from settings in start_requests
        self.max_search_results = 20
        self.top_urls_to_visit = 3

    def start_requests(self):
        """
        Entry point: Load queries and start the DDG search → crawl flow.
        """
        self.max_search_results = self.settings.getint("MAX_SEARCH_RESULTS", 20)
        self.top_urls_to_visit = self.settings.getint("TOP_URLS_TO_VISIT", 3)

        # Load queries
        if self.single_query:
            queries = [self.single_query]
            logger.info(f"Single query mode: '{self.single_query}'")
        else:
            queries_path = self.project_root / self.queries_file
            if not queries_path.exists():
                logger.error(f"Queries file not found: {queries_path}")
                return
            queries = self._load_queries(str(queries_path))
            logger.info(f"Loaded {len(queries)} queries from {queries_path}")

        # Process each query
        for idx, query in enumerate(queries, 1):
            logger.info(f"[{idx}/{len(queries)}] Starting query: '{query}'")
            yield from self._search_and_crawl(query)

    def _load_queries(self, filepath: str) -> list:
        """Load queries from CSV (one per row, first column)."""
        queries = []
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if row and row[0].strip():
                    queries.append(row[0].strip())
        return queries

    def _search_and_crawl(self, query: str):
        """
        Step 1: Search DuckDuckGo for the query.
        Step 2: Pick top N URLs.
        Step 3: Yield Scrapy requests for each top URL.
        """
        logger.info(f"{'='*60}")
        logger.info(f"SEARCHING: '{query}'")
        logger.info(f"{'='*60}")

        # Step 1: DuckDuckGo search
        search_results = self._ddg_search(query)

        if not search_results:
            logger.warning(f"No search results for '{query}'")
            # Yield empty item
            item = CrawlResultItem()
            item["query"] = query
            item["timestamp"] = datetime.now().isoformat()
            item["search_results"] = []
            item["top_sites_crawled"] = []
            item["stats"] = {
                "total_search_results": 0,
                "sites_crawled": 0,
                "total_links_found": 0,
                "total_doc_links_found": 0,
            }
            yield item
            return

        logger.info(f"Found {len(search_results)} search results for '{query}'")

        # Step 2: Pick top N URLs
        top_n = min(self.top_urls_to_visit, len(search_results))
        top_urls = search_results[:top_n]

        logger.info(f"Will crawl top {top_n} URLs:")
        for i, sr in enumerate(top_urls, 1):
            logger.info(f"  {i}. {sr['url']}")

        # Step 3: Yield requests for top URLs
        # We need to collect all results before yielding the item,
        # so we use meta to pass state through callbacks.
        crawl_state = {
            "query": query,
            "search_results": search_results,
            "top_urls": top_urls,
            "crawled_sites": [],
            "pending_count": top_n,
        }

        for rank, sr in enumerate(top_urls, 1):
            yield scrapy.Request(
                url=sr["url"],
                callback=self.parse_top_url,
                errback=self.handle_error,
                meta={
                    "crawl_state": crawl_state,
                    "rank": rank,
                    "search_title": sr.get("title", ""),
                    "search_snippet": sr.get("snippet", ""),
                },
                dont_filter=True,
            )

    def _ddg_search(self, query: str) -> list:
        """
        Perform DuckDuckGo search and return results.

        Returns:
            List of dicts with keys: title, url, snippet
        """
        results = []
        try:
            ddgs = DDGS()
            raw_results = ddgs.text(query, max_results=self.max_search_results)

            for r in raw_results:
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                })
        except Exception as e:
            logger.error(f"DuckDuckGo search failed for '{query}': {e}")

        return results

    def parse_top_url(self, response):
        """
        Step 3 callback: Parse a top URL page.
        Extract all links and document links.
        When all top URLs are parsed, yield the final CrawlResultItem.
        """
        crawl_state = response.meta["crawl_state"]
        rank = response.meta["rank"]
        url = response.url

        logger.info(f"Parsing top URL #{rank}: {url} (status: {response.status})")

        # Check if CAPTCHA blocked
        if response.meta.get("captcha_blocked"):
            logger.warning(f"CAPTCHA blocked on #{rank}: {url}")
            site_data = self._build_site_data(
                rank, url, response.meta, "", "CAPTCHA_BLOCKED", [], []
            )
            self._add_and_check_complete(crawl_state, site_data)
            return

        # Extract page title
        page_title = ""
        title_sel = response.css("title::text").get()
        if title_sel:
            page_title = title_sel.strip()

        # Extract all links
        all_links = set()
        doc_links = set()

        for href in response.css("a::attr(href)").getall():
            href = href.strip()
            if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
                continue

            absolute_url = urljoin(response.url, href)
            parsed = urlparse(absolute_url)

            if parsed.scheme in ("http", "https"):
                all_links.add(absolute_url)

                path_lower = parsed.path.lower()
                for ext in DOC_EXTENSIONS:
                    if path_lower.endswith(ext):
                        doc_links.add(absolute_url)
                        break

        logger.info(
            f"  URL #{rank}: {len(all_links)} links, {len(doc_links)} doc links"
        )

        site_data = self._build_site_data(
            rank, url, response.meta, page_title,
            response.status, sorted(all_links), sorted(doc_links)
        )

        # Check if all top URLs have been crawled
        results = self._add_and_check_complete(crawl_state, site_data)
        if results is not None:
            yield results

    def handle_error(self, failure):
        """Handle request errors (timeout, DNS, connection, etc.)."""
        request = failure.request
        crawl_state = request.meta["crawl_state"]
        rank = request.meta["rank"]
        url = request.url

        error_msg = str(failure.value)
        logger.error(f"Error crawling #{rank} {url}: {error_msg}")

        site_data = self._build_site_data(
            rank, url, request.meta, "", f"ERROR: {error_msg}", [], []
        )

        results = self._add_and_check_complete(crawl_state, site_data)
        if results is not None:
            yield results

    def _build_site_data(self, rank, url, meta, page_title, status,
                         all_links, doc_links):
        """Build the site data dictionary."""
        return {
            "rank": rank,
            "url": url,
            "search_title": meta.get("search_title", ""),
            "search_snippet": meta.get("search_snippet", ""),
            "page_title": page_title,
            "status": status,
            "all_links": all_links,
            "doc_links": doc_links,
            "total_links_count": len(all_links),
            "doc_links_count": len(doc_links),
        }

    def _add_and_check_complete(self, crawl_state, site_data):
        """
        Add crawled site data and check if all top URLs are done.
        If complete, build and return the final CrawlResultItem.
        """
        crawl_state["crawled_sites"].append(site_data)
        crawl_state["pending_count"] -= 1

        if crawl_state["pending_count"] > 0:
            return None

        # All top URLs crawled — build the final item
        query = crawl_state["query"]
        crawled_sites = sorted(crawl_state["crawled_sites"], key=lambda x: x["rank"])

        total_links = sum(s["total_links_count"] for s in crawled_sites)
        total_docs = sum(s["doc_links_count"] for s in crawled_sites)

        item = CrawlResultItem()
        item["query"] = query
        item["timestamp"] = datetime.now().isoformat()
        item["search_results"] = crawl_state["search_results"]
        item["top_sites_crawled"] = crawled_sites
        item["stats"] = {
            "total_search_results": len(crawl_state["search_results"]),
            "sites_crawled": len(crawled_sites),
            "total_links_found": total_links,
            "total_doc_links_found": total_docs,
        }

        logger.info(
            f"Query '{query}' COMPLETE: "
            f"{item['stats']['total_search_results']} results, "
            f"{item['stats']['sites_crawled']} sites crawled, "
            f"{total_links} links, {total_docs} doc links"
        )

        return item
