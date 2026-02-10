"""
CSV Saver - Saves crawl results to CSV files.

File structure:
  DATA/CSV/<query_folder>/<query_name>_<datetime>.csv

CSV columns:
  query, rank, visited_url, page_title, link_type, link_url
  
  link_type can be: "search_result", "page_link", "doc_link"
"""

import csv
import os
from datetime import datetime
from pathlib import Path
from utils.logger import get_logger


class CsvSaver:
    """Save crawl results to CSV files."""

    def __init__(self, settings):
        self.enabled = settings.SAVE_TO_CSV
        self.base_path = Path(settings.DATA_CSV_PATH)
        self.logger = get_logger()
        # Resolve relative to project root
        project_root = Path(__file__).resolve().parent.parent
        self.base_path = project_root / self.base_path

    def save(self, query: str, data: dict) -> str | None:
        """
        Save crawl data to a CSV file.

        Args:
            query: The search query (used for folder/file naming).
            data: The full crawl result dictionary.

        Returns:
            Path to the saved file, or None if saving is disabled.
        """
        if not self.enabled:
            self.logger.info("CSV saving is disabled (SAVE_TO_CSV=false)")
            return None

        try:
            # Create folder for this query
            folder_name = self._sanitize_name(query)
            query_dir = self.base_path / folder_name
            query_dir.mkdir(parents=True, exist_ok=True)

            # Create filename with datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{folder_name}_{timestamp}.csv"
            filepath = query_dir / filename

            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "query", "rank", "visited_url", "page_title",
                    "link_type", "link_url"
                ])

                # Write search results (first page URLs)
                for sr in data.get("search_results", []):
                    writer.writerow([
                        query, "", sr.get("url", ""), sr.get("title", ""),
                        "search_result", sr.get("url", "")
                    ])

                # Write top sites crawled data
                for site in data.get("top_sites_crawled", []):
                    rank = site.get("rank", "")
                    visited_url = site.get("url", "")
                    page_title = site.get("page_title", "")

                    # Write all page links
                    for link in site.get("all_links", []):
                        writer.writerow([
                            query, rank, visited_url, page_title,
                            "page_link", link
                        ])

                    # Write document links
                    for doc_link in site.get("doc_links", []):
                        writer.writerow([
                            query, rank, visited_url, page_title,
                            "doc_link", doc_link
                        ])

            self.logger.info(f"CSV saved: {filepath}")
            return str(filepath)

        except Exception as e:
            self.logger.error(f"Failed to save CSV for '{query}': {e}")
            return None

    @staticmethod
    def _sanitize_name(name: str) -> str:
        """Convert query to a safe folder/file name."""
        safe = name.strip().lower()
        safe = safe.replace(" ", "_")
        safe = "".join(c for c in safe if c.isalnum() or c in ("_", "-"))
        return safe[:100]
