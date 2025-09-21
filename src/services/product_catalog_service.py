"""
Product Catalog Service - Internal MongoDB Product Management
Service quản lý danh mục sản phẩm nội bộ trên MongoDB

🎯 PURPOSE:
- Generate unique, persistent product_id/service_id
- Store clean product data for AI prompts (4 key fields)
- Enable real inventory checking for check_quantity intent
- Sync product IDs with Backend via callback

🏗️ ARCHITECTURE:
- MongoDB Collection: "internal_products_catalog"
- Clean data for prompts: product_id, name, quantity, price
- Full raw data storage for future analysis
- Fast search with text indexes
"""

import os
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection
import pymongo

from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class ProductCatalogService:
    """
    🧠 Internal Product Catalog Management Service

    Manages the AI Service's own product/service catalog in MongoDB.
    This enables:
    - Unique ID generation and persistence
    - Clean data feeding into AI prompts
    - Real inventory checking capabilities
    - Backend synchronization via shared IDs
    """

    def __init__(self):
        """Initialize MongoDB connection and collection"""
        # Get MongoDB connection details from environment
        mongo_uri = os.getenv("MONGODB_URI_AUTH")
        if not mongo_uri:
            # Fallback: build authenticated URI from components
            mongo_user = os.getenv("MONGODB_APP_USERNAME")
            mongo_pass = os.getenv("MONGODB_APP_PASSWORD")
            mongo_host = (
                os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
                .replace("mongodb://", "")
                .rstrip("/")
            )
            db_name = os.getenv("MONGODB_NAME", "ai_service_db")

            if mongo_user and mongo_pass:
                mongo_uri = f"mongodb://{mongo_user}:{mongo_pass}@{mongo_host}/{db_name}?authSource=admin"
            else:
                mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")

        db_name = os.getenv("MONGODB_NAME", "ai_service_db")

        # Initialize async MongoDB client
        self.client = AsyncIOMotorClient(mongo_uri, serverSelectionTimeoutMS=10000)
        self.db = self.client[db_name]
        self.collection: AsyncIOMotorCollection = self.db["internal_products_catalog"]

        logger.info("✅ ProductCatalogService initialized")
        logger.info(f"   📊 Database: {db_name}")
        logger.info(f"   📁 Collection: internal_products_catalog")

    async def initialize_indexes(self):
        """Create MongoDB indexes for performance"""
        try:
            # Create indexes for fast searching
            await self.collection.create_index("company_id")
            await self.collection.create_index("item_type")
            await self.collection.create_index("product_id", unique=True, sparse=True)
            await self.collection.create_index("service_id", unique=True, sparse=True)
            await self.collection.create_index(
                "file_id", sparse=True
            )  # For file deletion cleanup

            # Text index for name searching (enables fuzzy search)
            await self.collection.create_index(
                [("name", "text"), ("description", "text")]
            )

            # Compound index for company + type queries
            await self.collection.create_index([("company_id", 1), ("item_type", 1)])

            # Compound index for file-based operations
            await self.collection.create_index([("file_id", 1), ("company_id", 1)])

            logger.info("✅ MongoDB indexes created successfully")

        except Exception as e:
            logger.warning(f"⚠️ Failed to create indexes (may already exist): {e}")

    async def register_item(
        self,
        item_data: Dict[str, Any],
        company_id: str,
        item_type: str,
        file_id: Optional[str] = None,
        file_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        🎯 CORE FUNCTION: Register new product/service with unique ID

        Args:
            item_data: Raw data from AI extraction
            company_id: Company identifier
            item_type: "product" or "service"
            file_id: File ID for deletion tracking
            file_name: File name for reference

        Returns:
            Dict with original data + new product_id/service_id
        """
        try:
            # 1. Generate unique ID
            item_id_field = "product_id" if item_type == "product" else "service_id"
            item_id = f"{'prod' if item_type == 'product' else 'serv'}_{uuid.uuid4()}"

            # 2. Extract clean data for prompt usage (4 key fields)
            name = item_data.get("name", "Unknown Item")
            price = self._extract_price(item_data)
            quantity = item_data.get(
                "quantity", -1
            )  # -1 = not tracked, 0 = out of stock

            # 3. Prepare full document for MongoDB storage
            document = {
                # === IDs and Classification ===
                item_id_field: item_id,
                "company_id": company_id,
                "item_type": item_type,
                # === File Information (for deletion tracking) ===
                "file_id": file_id,
                "file_name": file_name,
                # === Clean Data (for AI prompts) ===
                "name": name,
                "price": price,
                "quantity": quantity,
                "currency": item_data.get("currency", "VND"),
                # === Additional Fields ===
                "description": item_data.get("description", ""),
                "category": item_data.get("category", "uncategorized"),
                "sku": item_data.get("sku"),
                "tags": item_data.get("tags", []),
                # === Raw Data Preservation ===
                "raw_ai_data": item_data,  # Store complete AI extraction
                # === Metadata ===
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "status": "active",  # active, inactive, discontinued
            }

            # 4. Save to MongoDB
            result = await self.collection.insert_one(document)

            if result.inserted_id:
                logger.info(
                    f"💾 [CATALOG] Registered {item_type}: '{name}' with ID {item_id}"
                )
                logger.info(f"   🏢 Company: {company_id}")
                logger.info(f"   💰 Price: {price:,} VND")
                logger.info(f"   📦 Quantity: {quantity}")
                logger.info(f"   📁 File: {file_name} (ID: {file_id})")

                # 5. Return enriched data with new ID
                enriched_data = item_data.copy()

                # ✅ IMPORTANT: Remove old product_id/service_id from AI data to avoid confusion
                if item_type == "product" and "product_id" in enriched_data:
                    old_product_id = enriched_data.pop("product_id")
                    logger.info(f"   🔄 Removed old product_id: {old_product_id}")
                elif item_type == "service" and "service_id" in enriched_data:
                    old_service_id = enriched_data.pop("service_id")
                    logger.info(f"   🔄 Removed old service_id: {old_service_id}")

                # Add new catalog-generated ID
                enriched_data[item_id_field] = item_id
                enriched_data["catalog_price"] = price  # Normalized price
                enriched_data["catalog_quantity"] = quantity  # Normalized quantity

                return enriched_data
            else:
                logger.error(f"❌ [CATALOG] Failed to insert {item_type}: {name}")
                return item_data

        except Exception as e:
            logger.error(f"❌ [CATALOG] Error registering {item_type}: {e}")
            return item_data

    async def get_catalog_for_prompt(
        self, company_id: str, query: str = "", limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        🎯 GET CLEAN DATA FOR AI PROMPT (Only 4 key fields)

        Returns clean, prompt-ready data for AI to use in conversations.
        Only includes: product_id, name, quantity, price

        Args:
            company_id: Company to search in
            query: Search query (optional)
            limit: Max results to return

        Returns:
            List of clean product dictionaries for AI prompt
        """
        try:
            # Build MongoDB query
            mongo_query = {"company_id": company_id, "status": "active"}

            # Add text search if query provided
            if query and query.strip():
                mongo_query["$text"] = {"$search": query}
                # Sort by text score for relevance
                cursor = (
                    self.collection.find(mongo_query, {"score": {"$meta": "textScore"}})
                    .sort([("score", {"$meta": "textScore"})])
                    .limit(limit)
                )
            else:
                # No search query - get recent items
                cursor = (
                    self.collection.find(mongo_query)
                    .sort("created_at", -1)
                    .limit(limit)
                )

            # 📝 Extract ONLY 4 key fields for prompt efficiency
            clean_results = []
            async for doc in cursor:
                item_id = doc.get("product_id") or doc.get("service_id")
                item_type = doc.get("item_type", "unknown")

                # Format quantity for display
                quantity = doc.get("quantity", -1)
                if quantity == -1:
                    quantity_display = "Không theo dõi"
                elif quantity == 0:
                    quantity_display = "Hết hàng"
                else:
                    quantity_display = f"Còn {quantity}"

                # Format price for display
                price = doc.get("price", 0)
                price_display = f"{price:,} VND" if price > 0 else "Liên hệ"

                clean_item = {
                    "item_id": item_id,
                    "item_type": item_type,
                    "name": doc.get("name", "Unknown"),
                    "quantity_display": quantity_display,
                    "quantity_raw": quantity,  # For programmatic use
                    "price_display": price_display,
                    "price_raw": price,  # For programmatic use
                }

                clean_results.append(clean_item)

            logger.info(f"🔍 [CATALOG] Found {len(clean_results)} items for prompt")
            logger.info(f"   🏢 Company: {company_id}")
            logger.info(f"   🔍 Query: '{query}'" if query else "   📄 No search query")

            return clean_results

        except Exception as e:
            logger.error(f"❌ [CATALOG] Error getting catalog for prompt: {e}")
            return []

    async def find_by_name(
        self, company_id: str, item_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        🎯 FIND PRODUCT BY NAME (for check_quantity intent)

        Uses fuzzy text search to find products by name.
        Returns full document if found.
        """
        try:
            # Text search query
            result = await self.collection.find_one(
                {
                    "company_id": company_id,
                    "$text": {"$search": item_name},
                    "status": "active",
                }
            )

            if result:
                logger.info(
                    f"✅ [CATALOG] Found item by name: '{item_name}' → {result.get('product_id') or result.get('service_id')}"
                )
            else:
                logger.info(f"🔍 [CATALOG] No item found for name: '{item_name}'")

            return result

        except Exception as e:
            logger.error(f"❌ [CATALOG] Error finding by name '{item_name}': {e}")
            return None

    async def get_by_id(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Get item by product_id or service_id"""
        try:
            # Search by either product_id or service_id
            result = await self.collection.find_one(
                {
                    "$or": [{"product_id": item_id}, {"service_id": item_id}],
                    "status": "active",
                }
            )

            return result

        except Exception as e:
            logger.error(f"❌ [CATALOG] Error getting by ID '{item_id}': {e}")
            return None

    async def update_quantity(self, item_id: str, new_quantity: int) -> bool:
        """
        Update item quantity (for inventory management)
        """
        try:
            result = await self.collection.update_one(
                {"$or": [{"product_id": item_id}, {"service_id": item_id}]},
                {
                    "$set": {
                        "quantity": new_quantity,
                        "updated_at": datetime.now().isoformat(),
                    }
                },
            )

            if result.modified_count > 0:
                logger.info(
                    f"✅ [CATALOG] Updated quantity for {item_id}: {new_quantity}"
                )
                return True
            else:
                logger.warning(f"⚠️ [CATALOG] No item found to update: {item_id}")
                return False

        except Exception as e:
            logger.error(f"❌ [CATALOG] Error updating quantity for {item_id}: {e}")
            return False

    async def get_company_stats(self, company_id: str) -> Dict[str, int]:
        """Get catalog statistics for a company"""
        try:
            pipeline = [
                {"$match": {"company_id": company_id, "status": "active"}},
                {"$group": {"_id": "$item_type", "count": {"$sum": 1}}},
            ]

            results = await self.collection.aggregate(pipeline).to_list(length=None)

            stats = {"products": 0, "services": 0, "total": 0}
            for result in results:
                item_type = result["_id"]
                count = result["count"]
                if item_type == "product":
                    stats["products"] = count
                elif item_type == "service":
                    stats["services"] = count
                stats["total"] += count

            return stats

        except Exception as e:
            logger.error(f"❌ [CATALOG] Error getting company stats: {e}")
            return {"products": 0, "services": 0, "total": 0}

    def _extract_price(self, item_data: Dict[str, Any]) -> float:
        """Extract and normalize price from AI data - UNIVERSAL FORMAT SUPPORT"""

        # ✅ UNIVERSAL SUPPORT: Handle BOTH direct and nested pricing formats
        prices_obj = item_data.get("prices", {})

        # 🎯 Try DIRECT format first (new AI template): price_1, price_2, price_3
        price_1 = item_data.get("price_1") or prices_obj.get("price_1")
        if price_1:
            try:
                if isinstance(price_1, (int, float)) and price_1 > 0:
                    return float(price_1)
            except (ValueError, TypeError):
                pass

        # Try price_2 as fallback - both locations
        price_2 = item_data.get("price_2") or prices_obj.get("price_2")
        if price_2:
            try:
                if isinstance(price_2, (int, float)) and price_2 > 0:
                    return float(price_2)
            except (ValueError, TypeError):
                pass

        # Try price_3 as second fallback - both locations
        price_3 = item_data.get("price_3") or prices_obj.get("price_3")
        if price_3:
            try:
                if isinstance(price_3, (int, float)) and price_3 > 0:
                    return float(price_3)
            except (ValueError, TypeError):
                pass

        # 🔄 SERVICES: Handle service pricing format
        if "price_min" in item_data and item_data["price_min"]:
            try:
                price_min = item_data["price_min"]
                if isinstance(price_min, (int, float)) and price_min > 0:
                    return float(price_min)
            except (ValueError, TypeError):
                pass

        if "price_max" in item_data and item_data["price_max"]:
            try:
                price_max = item_data["price_max"]
                if isinstance(price_max, (int, float)) and price_max > 0:
                    return float(price_max)
            except (ValueError, TypeError):
                pass

        # 🔄 LEGACY: Try old format price fields
        legacy_price_fields = ["price", "cost", "amount", "value", "pricing"]

        for field in legacy_price_fields:
            if field in item_data:
                price_value = item_data[field]

                # Handle different price formats
                if isinstance(price_value, (int, float)) and price_value > 0:
                    return float(price_value)
                elif isinstance(price_value, str) and price_value.strip():
                    # Try to extract number from string
                    import re

                    numbers = re.findall(r"\d+(?:\.\d+)?", price_value.replace(",", ""))
                    if numbers:
                        try:
                            extracted_price = float(numbers[0])
                            if extracted_price > 0:
                                return extracted_price
                        except (ValueError, TypeError):
                            continue

        # 📋 LOGGING: Log when no price found for debugging
        logger.warning(
            f"⚠️ [CATALOG] No valid price found in item_data. Available fields: {list(item_data.keys())}"
        )
        if "price_1" in item_data:
            logger.warning(
                f"   price_1 = {item_data['price_1']} ({type(item_data['price_1'])})"
            )
        if "price_2" in item_data:
            logger.warning(
                f"   price_2 = {item_data['price_2']} ({type(item_data['price_2'])})"
            )
        if "price_min" in item_data:
            logger.warning(
                f"   price_min = {item_data['price_min']} ({type(item_data['price_min'])})"
            )

        return 0.0  # Default to 0 if no price found

    async def delete_items_by_file_id(self, file_id: str, company_id: str) -> int:
        """
        🗑️ Delete all items associated with a file_id for cleanup when files are deleted

        Args:
            file_id: File ID to delete items for
            company_id: Company ID for additional safety

        Returns:
            Number of items deleted
        """
        try:
            if not file_id:
                logger.warning("⚠️ [CATALOG] No file_id provided for deletion")
                return 0

            # Build query with both file_id and company_id for safety
            query = {"file_id": file_id, "company_id": company_id}  # Extra safety check

            # Get count before deletion for logging
            count_result = await self.collection.count_documents(query)

            if count_result == 0:
                logger.info(f"📋 [CATALOG] No items found for file_id: {file_id}")
                return 0

            # Perform deletion
            delete_result = await self.collection.delete_many(query)
            deleted_count = delete_result.deleted_count

            logger.info(
                f"🗑️ [CATALOG] Deleted {deleted_count} items for file_id: {file_id}"
            )
            logger.info(f"   🏢 Company: {company_id}")

            return deleted_count

        except Exception as e:
            logger.error(
                f"❌ [CATALOG] Error deleting items for file_id {file_id}: {e}"
            )
            return 0

    async def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            logger.info("✅ [CATALOG] MongoDB connection closed")


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_catalog_service: Optional[ProductCatalogService] = None


async def get_product_catalog_service() -> ProductCatalogService:
    """
    Get singleton instance of ProductCatalogService
    Initialize indexes on first access
    """
    global _catalog_service
    if _catalog_service is None:
        _catalog_service = ProductCatalogService()
        # Initialize indexes on first access
        await _catalog_service.initialize_indexes()
        logger.info("🚀 ProductCatalogService singleton initialized with indexes")
    return _catalog_service


def get_product_catalog_service_sync() -> ProductCatalogService:
    """
    Get singleton instance synchronously (for imports)
    Note: Indexes will be initialized on first async operation
    """
    global _catalog_service
    if _catalog_service is None:
        _catalog_service = ProductCatalogService()
        logger.info("🚀 ProductCatalogService singleton initialized (sync mode)")
    return _catalog_service
