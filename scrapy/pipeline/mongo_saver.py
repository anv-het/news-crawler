"""
MongoDB Saver - Saves crawl results to MongoDB.

Database: WEB_CRAWLER (configurable)
Collection: invester_relation_scrapy (configurable)

Each document follows the same hierarchical structure as the JSON output.
"""

from datetime import datetime
from utils.logger import get_logger


class MongoSaver:
    """Save crawl results to MongoDB."""

    def __init__(self, settings):
        self.enabled = settings.SAVE_TO_MONGO and settings.MONGO_ENABLED
        self.uri = settings.MONGO_URI
        self.database_name = settings.MONGO_DATABASE
        self.collection_name = settings.MONGO_COLLECTION
        self.logger = get_logger()
        self.client = None
        self.db = None
        self.collection = None

    def connect(self):
        """Establish MongoDB connection."""
        if not self.enabled:
            self.logger.info("MongoDB saving is disabled")
            return False

        try:
            from pymongo import MongoClient

            self.client = MongoClient(
                self.uri,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
            )
            # Test connection
            self.client.admin.command("ping")
            self.db = self.client[self.database_name]
            self.collection = self.db[self.collection_name]
            self.logger.info(
                f"Connected to MongoDB: {self.database_name}.{self.collection_name}"
            )
            return True

        except Exception as e:
            self.logger.error(f"MongoDB connection failed: {e}")
            self.enabled = False
            return False

    def save(self, query: str, data: dict) -> str | None:
        """
        Save crawl data to MongoDB.

        Args:
            query: The search query.
            data: The full crawl result dictionary.

        Returns:
            Inserted document ID as string, or None.
        """
        if not self.enabled:
            self.logger.info("MongoDB saving is disabled (SAVE_TO_MONGO=false)")
            return None

        if self.collection is None:
            if not self.connect():
                return None

        try:
            # Add metadata
            doc = {
                **data,
                "created_at": datetime.utcnow(),
                "query_normalized": query.strip().lower(),
            }

            result = self.collection.insert_one(doc)
            doc_id = str(result.inserted_id)
            self.logger.info(
                f"MongoDB saved: query='{query}', doc_id={doc_id}"
            )
            return doc_id

        except Exception as e:
            self.logger.error(f"Failed to save to MongoDB for '{query}': {e}")
            return None

    def close(self):
        """Close the MongoDB connection."""
        if self.client:
            self.client.close()
            self.logger.info("MongoDB connection closed")
