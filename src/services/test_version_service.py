"""
Test Version Service
Handles test versioning for marketplace - snapshot test content when published/updated

Features:
- Create version snapshots (v1, v2, v3...)
- Track version history
- Auto-increment version numbers
- Store questions + configuration at publish time
- Mark latest version as current
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from bson import ObjectId
from pymongo import MongoClient

import config.config as config

logger = logging.getLogger("chatbot")


class TestVersionService:
    """Service for managing test versions in marketplace"""

    def __init__(self):
        """Initialize version service with MongoDB connection"""
        # Connect to MongoDB
        mongo_uri = getattr(config, "MONGODB_URI_AUTH", None) or getattr(
            config, "MONGODB_URI", "mongodb://localhost:27017"
        )
        self.client = MongoClient(mongo_uri)
        db_name = getattr(config, "MONGODB_NAME", "wordai_db")
        self.db = self.client[db_name]

        logger.info("✅ TestVersionService initialized")

    def create_version_snapshot(
        self, test_id: str, test_doc: Dict[str, Any], version_note: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Create a version snapshot of the test

        Args:
            test_id: Test MongoDB ObjectId
            test_doc: Full test document from online_tests
            version_note: Optional note about this version

        Returns:
            Tuple of (success, error_message, version_string)
        """
        try:
            # Get next version number
            latest_version = self._get_latest_version_number(test_id)
            new_version_number = latest_version + 1
            version_string = f"v{new_version_number}"

            # Mark all previous versions as not current
            self.db.test_versions.update_many(
                {"test_id": test_id, "is_current": True},
                {"$set": {"is_current": False}},
            )

            # Create version document
            version_doc = {
                "version_id": str(uuid.uuid4()),
                "test_id": test_id,
                "version": version_string,
                "version_number": new_version_number,
                "is_current": True,
                # Snapshot of test content
                "title": test_doc.get("title", ""),
                "questions": test_doc.get("questions", []),
                "time_limit_minutes": test_doc.get("time_limit_minutes", 30),
                "max_retries": test_doc.get("max_retries", 3),
                # Marketplace config at this version
                "marketplace_config_snapshot": test_doc.get("marketplace_config", {}),
                # Metadata
                "version_note": version_note or f"Version {version_string} created",
                "created_by": test_doc.get("creator_id"),
                "created_at": datetime.now(timezone.utc),
                # Stats (initialized to 0 for new version)
                "stats": {
                    "total_participants": 0,
                    "total_purchases": 0,
                    "average_rating": 0.0,
                    "rating_count": 0,
                },
            }

            # Insert version snapshot
            result = self.db.test_versions.insert_one(version_doc)

            # Update test document with current version
            self.db.online_tests.update_one(
                {"_id": ObjectId(test_id)},
                {
                    "$set": {
                        "marketplace_config.current_version": version_string,
                        "marketplace_config.last_updated": datetime.now(timezone.utc),
                    }
                },
            )

            logger.info(f"✅ Created version snapshot: {test_id} {version_string}")
            return True, None, version_string

        except Exception as e:
            logger.error(f"❌ Failed to create version snapshot: {e}")
            import traceback

            traceback.print_exc()
            return False, f"Version creation error: {str(e)}", None

    def _get_latest_version_number(self, test_id: str) -> int:
        """
        Get the latest version number for a test

        Args:
            test_id: Test MongoDB ObjectId

        Returns:
            Latest version number (0 if no versions exist)
        """
        try:
            latest_version = self.db.test_versions.find_one(
                {"test_id": test_id}, sort=[("version_number", -1)]
            )

            if latest_version:
                return latest_version.get("version_number", 0)
            return 0

        except Exception as e:
            logger.error(f"❌ Failed to get latest version number: {e}")
            return 0

    def get_version(self, test_id: str, version: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific version of a test

        Args:
            test_id: Test MongoDB ObjectId
            version: Version string (e.g., "v1")

        Returns:
            Version document or None if not found
        """
        try:
            version_doc = self.db.test_versions.find_one(
                {"test_id": test_id, "version": version}
            )

            if version_doc:
                # Convert ObjectId to string
                version_doc["_id"] = str(version_doc["_id"])
                logger.info(f"✅ Retrieved version: {test_id} {version}")
            else:
                logger.warning(f"⚠️  Version not found: {test_id} {version}")

            return version_doc

        except Exception as e:
            logger.error(f"❌ Failed to get version: {e}")
            return None

    def get_current_version(self, test_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current (latest) version of a test

        Args:
            test_id: Test MongoDB ObjectId

        Returns:
            Current version document or None if not found
        """
        try:
            version_doc = self.db.test_versions.find_one(
                {"test_id": test_id, "is_current": True}
            )

            if version_doc:
                # Convert ObjectId to string
                version_doc["_id"] = str(version_doc["_id"])
                logger.info(
                    f"✅ Retrieved current version: {test_id} {version_doc.get('version')}"
                )
            else:
                logger.warning(f"⚠️  No current version found: {test_id}")

            return version_doc

        except Exception as e:
            logger.error(f"❌ Failed to get current version: {e}")
            return None

    def list_versions(
        self, test_id: str, include_stats: bool = False
    ) -> List[Dict[str, Any]]:
        """
        List all versions of a test

        Args:
            test_id: Test MongoDB ObjectId
            include_stats: Include stats for each version

        Returns:
            List of version documents (newest first)
        """
        try:
            projection = {
                "version_id": 1,
                "version": 1,
                "version_number": 1,
                "is_current": 1,
                "version_note": 1,
                "created_at": 1,
                "created_by": 1,
            }

            if include_stats:
                projection["stats"] = 1

            versions = list(
                self.db.test_versions.find({"test_id": test_id}, projection).sort(
                    "version_number", -1
                )
            )

            # Convert ObjectIds to strings
            for version in versions:
                version["_id"] = str(version["_id"])

            logger.info(f"✅ Retrieved {len(versions)} versions for test {test_id}")
            return versions

        except Exception as e:
            logger.error(f"❌ Failed to list versions: {e}")
            return []

    def update_version_stats(
        self, test_id: str, version: str, stats_update: Dict[str, Any]
    ) -> bool:
        """
        Update statistics for a specific version

        Args:
            test_id: Test MongoDB ObjectId
            version: Version string (e.g., "v1")
            stats_update: Dictionary of stats to update

        Returns:
            True if update successful
        """
        try:
            # Build update document
            update_doc = {}
            for key, value in stats_update.items():
                update_doc[f"stats.{key}"] = value

            result = self.db.test_versions.update_one(
                {"test_id": test_id, "version": version}, {"$set": update_doc}
            )

            if result.modified_count > 0:
                logger.info(f"✅ Updated stats for version: {test_id} {version}")
                return True
            else:
                logger.warning(f"⚠️  No version updated: {test_id} {version}")
                return False

        except Exception as e:
            logger.error(f"❌ Failed to update version stats: {e}")
            return False

    def get_version_for_purchase(
        self, test_id: str, purchased_at: datetime
    ) -> Optional[str]:
        """
        Get the version that was current at the time of purchase

        Args:
            test_id: Test MongoDB ObjectId
            purchased_at: Purchase timestamp

        Returns:
            Version string (e.g., "v2") or None
        """
        try:
            # Find the version that was current at purchase time
            version_doc = self.db.test_versions.find_one(
                {"test_id": test_id, "created_at": {"$lte": purchased_at}},
                sort=[("created_at", -1)],
            )

            if version_doc:
                version = version_doc.get("version", "v1")
                logger.info(f"✅ Version at purchase time: {test_id} {version}")
                return version
            else:
                logger.warning(
                    f"⚠️  No version found at purchase time, defaulting to v1"
                )
                return "v1"

        except Exception as e:
            logger.error(f"❌ Failed to get version for purchase: {e}")
            return "v1"

    def compare_versions(
        self, test_id: str, version1: str, version2: str
    ) -> Optional[Dict[str, Any]]:
        """
        Compare two versions and return differences

        Args:
            test_id: Test MongoDB ObjectId
            version1: First version string
            version2: Second version string

        Returns:
            Dictionary with comparison results
        """
        try:
            v1_doc = self.get_version(test_id, version1)
            v2_doc = self.get_version(test_id, version2)

            if not v1_doc or not v2_doc:
                return None

            comparison = {
                "version1": version1,
                "version2": version2,
                "changes": {
                    "title_changed": v1_doc.get("title") != v2_doc.get("title"),
                    "questions_count_changed": len(v1_doc.get("questions", []))
                    != len(v2_doc.get("questions", [])),
                    "time_limit_changed": v1_doc.get("time_limit_minutes")
                    != v2_doc.get("time_limit_minutes"),
                    "max_retries_changed": v1_doc.get("max_retries")
                    != v2_doc.get("max_retries"),
                    "price_changed": v1_doc.get("marketplace_config_snapshot", {}).get(
                        "price_points"
                    )
                    != v2_doc.get("marketplace_config_snapshot", {}).get(
                        "price_points"
                    ),
                },
                "v1": {
                    "title": v1_doc.get("title"),
                    "questions_count": len(v1_doc.get("questions", [])),
                    "time_limit_minutes": v1_doc.get("time_limit_minutes"),
                    "price_points": v1_doc.get("marketplace_config_snapshot", {}).get(
                        "price_points"
                    ),
                },
                "v2": {
                    "title": v2_doc.get("title"),
                    "questions_count": len(v2_doc.get("questions", [])),
                    "time_limit_minutes": v2_doc.get("time_limit_minutes"),
                    "price_points": v2_doc.get("marketplace_config_snapshot", {}).get(
                        "price_points"
                    ),
                },
            }

            logger.info(f"✅ Compared versions: {test_id} {version1} vs {version2}")
            return comparison

        except Exception as e:
            logger.error(f"❌ Failed to compare versions: {e}")
            return None


# Singleton instance
_version_service: Optional[TestVersionService] = None


def get_version_service() -> TestVersionService:
    """Get singleton instance of TestVersionService"""
    global _version_service
    if _version_service is None:
        _version_service = TestVersionService()
    return _version_service
