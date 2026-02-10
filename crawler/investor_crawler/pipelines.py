"""
Scrapy Pipelines - Save crawl results to JSON, CSV, and MongoDB.
=================================================================

Each pipeline respects the SAVE_TO_* switches from .env.
File naming: <query_name>_<datetime>.ext
Directory:   DATA/<format>/<query_folder>/

Pipelines:
  1. JsonFilePipeline  - Save to DATA/JSON/<query>/file.json
  2. CsvFilePipeline   - Save to DATA/CSV/<query>/file.csv
  3. MongoDBPipeline   - Save to MongoDB WEB_CRAWLER.invester_relation_scrapy
"""

import csv
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def _sanitize_name(name: str) -> str:
    """Convert query to a safe folder/file name."""
    safe = name.strip().lower().replace(" ", "_")
    safe = "".join(c for c in safe if c.isalnum() or c in ("_", "-"))
    return safe[:100]


def _item_to_dict(item) -> dict:
    """Convert a Scrapy Item to a plain dict (JSON-serializable)."""
    return {
        "query": item.get("query", ""),
        "timestamp": item.get("timestamp", ""),
        "search_results": item.get("search_results", []),
        "top_sites_crawled": item.get("top_sites_crawled", []),
        "stats": item.get("stats", {}),
    }


# =============================================================================
# JSON Pipeline
# =============================================================================

class JsonFilePipeline:
    """
    Saves each CrawlResultItem as a JSON file.

    Output: DATA/JSON/<query_folder>/<query>_<datetime>.json
    """

    def __init__(self, base_path):
        self.base_path = Path(base_path)

    @classmethod
    def from_crawler(cls, crawler):
        project_root = Path(crawler.settings.get("PROJECT_ROOT", "."))
        base_path = project_root / crawler.settings.get("DATA_JSON_PATH", "DATA/JSON/")
        return cls(base_path=str(base_path))

    def open_spider(self, spider):
        # Resolve path relative to project root
        project_root = Path(spider.settings.get("PROJECT_ROOT", "."))
        self.base_path = project_root / spider.settings.get("DATA_JSON_PATH", "DATA/JSON/")
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"JsonFilePipeline: output dir = {self.base_path}")

    def process_item(self, item, spider):
        query = item.get("query", "unknown")
        folder_name = _sanitize_name(query)
        query_dir = self.base_path / folder_name
        query_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{folder_name}_{timestamp}.json"
        filepath = query_dir / filename

        data = _item_to_dict(item)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            logger.info(f"JSON saved: {filepath}")
        except Exception as e:
            logger.error(f"Failed to save JSON for '{query}': {e}")

        return item

    def close_spider(self, spider):
        pass


# =============================================================================
# CSV Pipeline
# =============================================================================

class CsvFilePipeline:
    """
    Saves each CrawlResultItem as a CSV file.

    Columns: query, rank, visited_url, page_title, link_type, link_url
    Output:  DATA/CSV/<query_folder>/<query>_<datetime>.csv
    """

    def __init__(self):
        self.base_path = None

    @classmethod
    def from_crawler(cls, crawler):
        return cls()

    def open_spider(self, spider):
        project_root = Path(spider.settings.get("PROJECT_ROOT", "."))
        self.base_path = project_root / spider.settings.get("DATA_CSV_PATH", "DATA/CSV/")
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"CsvFilePipeline: output dir = {self.base_path}")

    def process_item(self, item, spider):
        query = item.get("query", "unknown")
        folder_name = _sanitize_name(query)
        query_dir = self.base_path / folder_name
        query_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{folder_name}_{timestamp}.csv"
        filepath = query_dir / filename

        try:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "query", "rank", "visited_url", "page_title",
                    "link_type", "link_url"
                ])

                # Write search results
                for sr in item.get("search_results", []):
                    writer.writerow([
                        query, "", sr.get("url", ""), sr.get("title", ""),
                        "search_result", sr.get("url", "")
                    ])

                # Write top sites crawled
                for site in item.get("top_sites_crawled", []):
                    rank = site.get("rank", "")
                    visited_url = site.get("url", "")
                    page_title = site.get("page_title", "")

                    for link in site.get("all_links", []):
                        writer.writerow([
                            query, rank, visited_url, page_title,
                            "page_link", link
                        ])

                    for doc_link in site.get("doc_links", []):
                        writer.writerow([
                            query, rank, visited_url, page_title,
                            "doc_link", doc_link
                        ])

            logger.info(f"CSV saved: {filepath}")
        except Exception as e:
            logger.error(f"Failed to save CSV for '{query}': {e}")

        return item

    def close_spider(self, spider):
        pass


# =============================================================================
# MongoDB Pipeline
# =============================================================================

class MongoDBPipeline:
    """
    Saves each CrawlResultItem as a document in MongoDB.

    Database:   WEB_CRAWLER (configurable)
    Collection: invester_relation_scrapy (configurable)
    """

    def __init__(self, mongo_uri, mongo_db, mongo_collection):
        self.mongo_uri = mongo_uri
        self.mongo_db = mongo_db
        self.mongo_collection_name = mongo_collection
        self.client = None
        self.db = None
        self.collection = None

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            mongo_uri=crawler.settings.get("MONGO_URI", "mongodb://localhost:27017"),
            mongo_db=crawler.settings.get("MONGO_DATABASE", "WEB_CRAWLER"),
            mongo_collection=crawler.settings.get(
                "MONGO_COLLECTION", "invester_relation_scrapy"
            ),
        )

    def open_spider(self, spider):
        try:
            from pymongo import MongoClient

            self.client = MongoClient(
                self.mongo_uri,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
            )
            # Test connection
            self.client.admin.command("ping")
            self.db = self.client[self.mongo_db]
            self.collection = self.db[self.mongo_collection_name]
            logger.info(
                f"MongoDB connected: {self.mongo_db}.{self.mongo_collection_name}"
            )
        except Exception as e:
            logger.error(f"MongoDB connection failed: {e}")
            self.collection = None

    def process_item(self, item, spider):
        if self.collection is None:
            logger.warning("MongoDB not connected, skipping save")
            return item

        try:
            doc = _item_to_dict(item)
            doc["created_at"] = datetime.utcnow()
            doc["query_normalized"] = item.get("query", "").strip().lower()

            result = self.collection.insert_one(doc)
            logger.info(
                f"MongoDB saved: query='{item.get('query')}', "
                f"doc_id={result.inserted_id}"
            )
        except Exception as e:
            logger.error(
                f"Failed to save to MongoDB for '{item.get('query')}': {e}"
            )

        return item

    def close_spider(self, spider):
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")
