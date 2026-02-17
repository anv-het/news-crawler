"""
Investor Spider - DuckDuckGo Search + Page Crawl Spider
=========================================================

FLOW (sequential, non-blocking):
  1. Read queries from queries.csv (or --query arg)
  2. For EACH query, one at a time:
     a. Search DuckDuckGo → get top 15-20 first-page URLs
     b. Pick top 3 URLs from search results
     c. Yield Scrapy requests to visit each top URL
     d. On each page response:
        - Extract ALL <a href> links
        - Identify document links (pdf, xlsx, csv, ppt, doc, etc.)
     e. After all 3 pages crawled, yield a CrawlResultItem
     f. Pipelines save to JSON / CSV / MongoDB
  3. Move to the next query only after current one finishes

CRITICAL DESIGN:
  - Queries are processed ONE AT A TIME to avoid overloading DDG
  - DDG search happens just before each query's crawl, not all upfront
  - No time.sleep() anywhere (Scrapy handles delays)
  - Skip-already-downloaded support via SKIP_ALREADY_DOWNLOADED setting
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


def _sanitize_name(name: str) -> str:
    """Convert query to a safe folder/file name."""
    safe = name.strip().lower().replace(" ", "_")
    safe = "".join(c for c in safe if c.isalnum() or c in ("_", "-"))
    return safe[:100]


class InvestorSpider(scrapy.Spider):
    """
    Spider that searches DuckDuckGo for investor-relations queries,
    then crawls the top N result pages to extract all links and
    document URLs.

    IMPORTANT: Processes ONE query at a time to avoid DDG rate-limiting
    and reactor blocking. Next query is triggered only after the
    current query's crawl is fully complete.
    """

    name = "investor_spider"

    # PROJECT_ROOT is set here so pipelines can resolve paths.
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

        # Query queue for sequential processing
        self._query_queue = []
        self._query_index = 0
        self._total_queries = 0

        # Skip-already-downloaded
        self._skip_downloaded = False
        self._completed_queries = set()

        # Stats
        self._stats_queries_completed = 0
        self._stats_queries_skipped = 0
        self._stats_total_links = 0
        self._stats_total_docs = 0
        self._start_time = None

    def start_requests(self):
        """
        Entry point: Load the query list, build the skip set, then
        yield a single dummy request that kicks off the query chain.
        
        IMPORTANT: We DON'T run searches here - they happen in callbacks.
        """
        self._start_time = datetime.now()

        self.max_search_results = self.settings.getint("MAX_SEARCH_RESULTS", 20)
        self.top_urls_to_visit = self.settings.getint("TOP_URLS_TO_VISIT", 3)
        self._skip_downloaded = self.settings.getbool(
            "SKIP_ALREADY_DOWNLOADED", False
        )

        # Load queries
        if self.single_query:
            self._query_queue = [self.single_query]
            logger.info(f"Single query mode: '{self.single_query}'")
        else:
            queries_path = self.project_root / self.queries_file
            if not queries_path.exists():
                logger.error(f"Queries file not found: {queries_path}")
                return
            self._query_queue = self._load_queries(str(queries_path))
            logger.info(
                f"Loaded {len(self._query_queue)} queries from {queries_path}"
            )

        self._total_queries = len(self._query_queue)
        self._query_index = 0

        # Build skip set if enabled
        if self._skip_downloaded:
            self._completed_queries = self._scan_completed_queries()
            logger.info(
                f"Skip-already-downloaded is ON. "
                f"Found {len(self._completed_queries)} previously completed queries."
            )

        # Yield a SINGLE dummy request to start the chain.
        # All subsequent queries are triggered from callbacks.
        yield scrapy.Request(
            url="https://www.google.com/favicon.ico",  # Tiny, fast, reliable
            callback=self._kickoff_first_query,
            errback=self._kickoff_first_query_error,
            dont_filter=True,
            priority=2000,
        )

    def _kickoff_first_query(self, response):
        """Kickoff callback - starts processing the first query."""
        logger.info("Query processing chain started")
        yield from self._process_next_query()

    def _kickoff_first_query_error(self, failure):
        """Kickoff error handler - starts processing anyway."""
        logger.warning(f"Kickoff request failed (non-critical): {failure.value}")
        yield from self._process_next_query()

    # ------------------------------------------------------------------
    # Query loading & skip logic
    # ------------------------------------------------------------------

    def _load_queries(self, filepath: str) -> list:
        """Load queries from CSV (one per row, first column)."""
        queries = []
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if row and row[0].strip():
                    queries.append(row[0].strip())
        return queries

    def _scan_completed_queries(self) -> set:
        """
        Scan DATA/JSON/ directory to find which queries already
        have saved output. Uses sanitized folder names as keys.
        """
        completed = set()
        json_dir = self.project_root / self.settings.get(
            "DATA_JSON_PATH", "DATA/JSON/"
        )
        if json_dir.exists():
            for folder in json_dir.iterdir():
                if folder.is_dir():
                    json_files = list(folder.glob("*.json"))
                    if json_files:
                        completed.add(folder.name)
        return completed

    def _is_already_downloaded(self, query: str) -> bool:
        """Check if a query has already been downloaded."""
        if not self._skip_downloaded:
            return False
        folder_name = _sanitize_name(query)
        return folder_name in self._completed_queries

    # ------------------------------------------------------------------
    # Sequential query driver
    # ------------------------------------------------------------------

    def _process_next_query(self):
        """
        Advance to the next un-skipped query and yield a dummy request
        to trigger the search in a non-blocking callback.
        Returns without yielding anything when all queries are done.
        """
        while self._query_index < self._total_queries:
            query = self._query_queue[self._query_index]
            self._query_index += 1

            if self._is_already_downloaded(query):
                self._stats_queries_skipped += 1
                logger.info(
                    f"[{self._query_index}/{self._total_queries}] "
                    f"SKIPPED (already downloaded): '{query}'"
                )
                continue

            # Found a query to process
            logger.info(
                f"[{self._query_index}/{self._total_queries}] "
                f"Starting query: '{query}' "
                f"(done={self._stats_queries_completed}, "
                f"skipped={self._stats_queries_skipped})"
            )
            
            # Yield a dummy request with the query in meta.
            # The actual DDG search happens in the callback (non-blocking).
            yield scrapy.Request(
                url="https://www.google.com/favicon.ico",  # Tiny, fast, reliable
                callback=self._do_search_and_crawl,
                errback=self._search_error,
                meta={"query": query},
                dont_filter=True,
                priority=1000,  # High priority to process immediately
            )
            return  # Stop here; next query triggered by callback chain

        # All queries exhausted
        self._log_final_summary()

    def _log_final_summary(self):
        """Print final summary when all queries are done."""
        elapsed = (datetime.now() - self._start_time).total_seconds()
        logger.info(
            f"\n{'='*60}\n"
            f"ALL QUERIES PROCESSED\n"
            f"  Total queries : {self._total_queries}\n"
            f"  Completed     : {self._stats_queries_completed}\n"
            f"  Skipped       : {self._stats_queries_skipped}\n"
            f"  Total links   : {self._stats_total_links}\n"
            f"  Total doc links: {self._stats_total_docs}\n"
            f"  Elapsed       : {elapsed:.0f}s ({elapsed/60:.1f} min)\n"
            f"{'='*60}"
        )

    # ------------------------------------------------------------------
    # Search & crawl
    # ------------------------------------------------------------------

    def _do_search_and_crawl(self, response):
        """
        Callback that performs the DDG search and yields crawl requests.
        This runs in Twisted's callback chain (non-blocking).
        """
        query = response.meta["query"]
        logger.info(f"SEARCHING: '{query}'")

        # DuckDuckGo search (now happens in callback, not blocking generator)
        search_results = self._ddg_search(query)

        if not search_results:
            logger.warning(f"No search results for '{query}'")
            item = self._build_empty_item(query)
            yield item
            self._stats_queries_completed += 1
            # Chain to next query
            yield from self._process_next_query()
            return

        logger.info(f"Found {len(search_results)} search results for '{query}'")

        # Pick top N URLs
        top_n = min(self.top_urls_to_visit, len(search_results))
        top_urls = search_results[:top_n]

        logger.info(f"Will crawl top {top_n} URLs:")
        for i, sr in enumerate(top_urls, 1):
            logger.info(f"  {i}. {sr['url']}")

        # Shared state for this query's crawl callbacks.
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

    def _search_error(self, failure):
        """Handle errors in the dummy search request."""
        query = failure.request.meta.get("query", "unknown")
        logger.error(f"Search initiation failed for '{query}': {failure.value}")
        # Skip this query and move to next
        self._stats_queries_completed += 1
        return self._process_next_query()

    def _ddg_search(self, query: str) -> list:
        """
        Perform DuckDuckGo search and return results.
        Returns list of dicts: {title, url, snippet}
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

    def _build_empty_item(self, query):
        """Build an item for a query with zero search results."""
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
        return item

    # ------------------------------------------------------------------
    # Page parsing callbacks
    # ------------------------------------------------------------------

    def parse_top_url(self, response):
        """
        Parse a top-URL page: extract all links and document links.
        When all top URLs for a query are done, yield the item and
        trigger the next query.
        """
        crawl_state = response.meta["crawl_state"]
        rank = response.meta["rank"]
        url = response.url

        logger.info(f"Parsing top URL #{rank}: {url} (status: {response.status})")

        # CAPTCHA blocked?
        if response.meta.get("captcha_blocked"):
            logger.warning(f"CAPTCHA blocked on #{rank}: {url}")
            site_data = self._build_site_data(
                rank, url, response.meta, "", "CAPTCHA_BLOCKED", [], []
            )
            yield from self._add_and_check_complete(crawl_state, site_data)
            return

        # Check if response is a binary/non-text file (e.g., PDF, XLSX)
        content_type = response.headers.get("Content-Type", b"").decode(
            "utf-8", errors="ignore"
        ).lower()
        is_text_response = hasattr(response, "text") and (
            "text/" in content_type
            or "html" in content_type
            or "xml" in content_type
            or "json" in content_type
            or not content_type  # default to text if no content type
        )

        if not is_text_response:
            # Binary file (PDF, XLSX, etc.) — record as a doc link itself
            logger.info(f"  URL #{rank}: Binary file ({content_type}), recorded as doc link")
            site_data = self._build_site_data(
                rank, url, response.meta, "", response.status, [url], [url]
            )
            yield from self._add_and_check_complete(crawl_state, site_data)
            return

        # Page title
        page_title = ""
        try:
            title_sel = response.css("title::text").get()
            if title_sel:
                page_title = title_sel.strip()
        except Exception:
            pass

        # Extract all links
        all_links = set()
        doc_links = set()

        try:
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
        except Exception as e:
            logger.warning(f"  URL #{rank}: Error extracting links: {e}")

        logger.info(
            f"  URL #{rank}: {len(all_links)} links, {len(doc_links)} doc links"
        )

        site_data = self._build_site_data(
            rank, url, response.meta, page_title,
            response.status, sorted(all_links), sorted(doc_links)
        )

        yield from self._add_and_check_complete(crawl_state, site_data)

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

        yield from self._add_and_check_complete(crawl_state, site_data)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_site_data(self, rank, url, meta, page_title, status,
                         all_links, doc_links):
        """Build the site data dictionary for one crawled page."""
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
        Record one crawled page. When all pages for a query are done,
        yield the CrawlResultItem and chain to the next query.
        """
        crawl_state["crawled_sites"].append(site_data)
        crawl_state["pending_count"] -= 1

        if crawl_state["pending_count"] > 0:
            return  # Still waiting for more pages

        # ---- All top URLs crawled for this query ----
        query = crawl_state["query"]
        crawled_sites = sorted(
            crawl_state["crawled_sites"], key=lambda x: x["rank"]
        )

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

        # Update running stats
        self._stats_queries_completed += 1
        self._stats_total_links += total_links
        self._stats_total_docs += total_docs

        # Progress report every 10 queries
        if self._stats_queries_completed % 10 == 0:
            elapsed = (datetime.now() - self._start_time).total_seconds()
            rate = (
                self._stats_queries_completed / (elapsed / 60)
                if elapsed > 0 else 0
            )
            remaining = self._total_queries - self._query_index
            eta_min = remaining / rate if rate > 0 else 0
            logger.info(
                f">>> PROGRESS: {self._stats_queries_completed}/"
                f"{self._total_queries} completed, "
                f"{self._stats_queries_skipped} skipped, "
                f"{rate:.1f} queries/min, "
                f"ETA: {eta_min:.0f} min <<<"
            )

        yield item

        # ---- Chain to the next query ----
        yield from self._process_next_query()
