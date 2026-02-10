"""
Crawler module - Visits the top URLs and extracts all links from each page.

Step 2: Takes the top N URLs from search results, visits each one,
and collects all href links found on that page.
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from utils.logger import get_logger
from utils.delay import DelayManager


class PageCrawler:
    """Visit URLs and extract all hyperlinks from the page."""

    def __init__(self, settings, delay_manager: DelayManager):
        self.timeout = settings.REQUEST_TIMEOUT
        self.user_agent = settings.USER_AGENT
        self.delay_manager = delay_manager
        self.logger = get_logger()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
            }
        )

    def crawl_page(self, url: str) -> dict:
        """
        Visit a URL and extract all links from the page.

        Args:
            url: The URL to visit and crawl.

        Returns:
            Dict with keys:
                - url: The visited URL
                - page_title: Title of the page
                - all_links: List of all href URLs found
                - doc_links: List of document file URLs (pdf, xlsx, csv, etc.)
                - status: HTTP status code or error
        """
        self.logger.info(f"Crawling page: {url}")
        result = {
            "url": url,
            "page_title": "",
            "all_links": [],
            "doc_links": [],
            "status": None,
        }

        try:
            self.delay_manager.wait()
            response = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            result["status"] = response.status_code

            if response.status_code != 200:
                self.logger.warning(
                    f"Non-200 status ({response.status_code}) for: {url}"
                )
                return result

            soup = BeautifulSoup(response.text, "lxml")

            # Get page title
            title_tag = soup.find("title")
            result["page_title"] = title_tag.get_text(strip=True) if title_tag else ""

            # Extract all links
            all_links = set()
            doc_links = set()
            doc_extensions = {
                ".pdf", ".xlsx", ".xls", ".csv", ".ppt", ".pptx",
                ".doc", ".docx", ".zip", ".rar", ".txt",
            }

            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"].strip()

                # Skip empty, javascript, mailto, tel links
                if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
                    continue

                # Resolve relative URLs
                absolute_url = urljoin(url, href)

                # Validate URL
                parsed = urlparse(absolute_url)
                if parsed.scheme in ("http", "https"):
                    all_links.add(absolute_url)

                    # Check if it's a document link
                    path_lower = parsed.path.lower()
                    for ext in doc_extensions:
                        if path_lower.endswith(ext):
                            doc_links.add(absolute_url)
                            break

            result["all_links"] = sorted(all_links)
            result["doc_links"] = sorted(doc_links)

            self.logger.info(
                f"Crawled {url}: {len(all_links)} links, "
                f"{len(doc_links)} document links"
            )

        except requests.exceptions.Timeout:
            result["status"] = "TIMEOUT"
            self.logger.error(f"Timeout crawling: {url}")
        except requests.exceptions.ConnectionError:
            result["status"] = "CONNECTION_ERROR"
            self.logger.error(f"Connection error crawling: {url}")
        except Exception as e:
            result["status"] = f"ERROR: {str(e)}"
            self.logger.error(f"Error crawling {url}: {e}")

        return result

    def close(self):
        """Close the requests session."""
        self.session.close()
