"""
JSON Saver - Saves crawl results to JSON files.

File structure:
  DATA/JSON/<query_folder>/<query_name>_<datetime>.json

The JSON structure follows the hierarchical format:
{
    "query": "reliance investor relations",
    "timestamp": "2026-02-10T12:00:00",
    "search_results": [ ... first page URLs ... ],
    "top_sites_crawled": [
        {
            "rank": 1,
            "url": "https://...",
            "page_title": "...",
            "all_links": [...],
            "doc_links": [...]
        },
        ...
    ]
}
"""

import json
import os
from datetime import datetime
from pathlib import Path
from utils.logger import get_logger


class JsonSaver:
    """Save crawl results to JSON files."""

    def __init__(self, settings):
        self.enabled = settings.SAVE_TO_JSON
        self.base_path = Path(settings.DATA_JSON_PATH)
        self.logger = get_logger()
        # Resolve relative to project root
        project_root = Path(__file__).resolve().parent.parent
        self.base_path = project_root / self.base_path

    def save(self, query: str, data: dict) -> str | None:
        """
        Save crawl data to a JSON file.

        Args:
            query: The search query (used for folder/file naming).
            data: The full crawl result dictionary.

        Returns:
            Path to the saved file, or None if saving is disabled.
        """
        if not self.enabled:
            self.logger.info("JSON saving is disabled (SAVE_TO_JSON=false)")
            return None

        try:
            # Create folder for this query
            folder_name = self._sanitize_name(query)
            query_dir = self.base_path / folder_name
            query_dir.mkdir(parents=True, exist_ok=True)

            # Create filename with datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{folder_name}_{timestamp}.json"
            filepath = query_dir / filename

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)

            self.logger.info(f"JSON saved: {filepath}")
            return str(filepath)

        except Exception as e:
            self.logger.error(f"Failed to save JSON for '{query}': {e}")
            return None

    @staticmethod
    def _sanitize_name(name: str) -> str:
        """Convert query to a safe folder/file name."""
        safe = name.strip().lower()
        safe = safe.replace(" ", "_")
        # Remove unsafe characters
        safe = "".join(c for c in safe if c.isalnum() or c in ("_", "-"))
        return safe[:100]  # Limit length
