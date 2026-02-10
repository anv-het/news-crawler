"""
Searcher module - Performs DuckDuckGo searches for given queries.

Step 1: Takes a query (e.g., "reliance investor relations") and returns
the top N search result URLs from the first page.
"""

from ddgs import DDGS
from utils.logger import get_logger
from utils.delay import DelayManager


class DuckDuckGoSearcher:
    """Search DuckDuckGo and return first-page result URLs."""

    def __init__(self, settings, delay_manager: DelayManager):
        self.max_results = settings.MAX_SEARCH_RESULTS
        self.delay_manager = delay_manager
        self.logger = get_logger()

    def search(self, query: str) -> list[dict]:
        """
        Search DuckDuckGo for the given query.

        Args:
            query: The search query string.

        Returns:
            List of dicts with keys: title, url, snippet
        """
        self.logger.info(f"Searching DuckDuckGo for: '{query}'")
        results = []

        try:
            self.delay_manager.wait()

            ddgs = DDGS()
            search_results = ddgs.text(
                query,
                max_results=self.max_results,
            )

            for r in search_results:
                results.append(
                    {
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "snippet": r.get("body", ""),
                    }
                )

            self.logger.info(
                f"Found {len(results)} search results for '{query}'"
            )

        except Exception as e:
            self.logger.error(f"Search failed for '{query}': {e}")

        return results
