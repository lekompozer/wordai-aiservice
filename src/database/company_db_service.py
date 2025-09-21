"""
Company Database Service for MongoDB persistence
Dịch vụ database công ty cho lưu trữ bền vững MongoDB
"""

import os
import pymongo
from datetime import datetime
from typing import Any, Dict, List, Optional
from bson import ObjectId

from src.models.unified_models import CompanyConfig, Industry, Language
from src.utils.logger import setup_logger

logger = setup_logger()


class CompanyDBService:
    def __init__(self):
        """
        Initialize MongoDB connection for company data
        Khởi tạo kết nối MongoDB cho dữ liệu công ty
        """
        # Check environment and use appropriate MongoDB URI
        environment = os.getenv("ENVIRONMENT", "development")

        if environment == "development":
            # Development: Use local MongoDB without authentication
            mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
            db_name = os.getenv("MONGODB_NAME", "ai_service_dev_db")
            logger.info(f"🏠 [DEV] Using local MongoDB: {mongo_uri}")
        else:
            # Production: Use authenticated MongoDB
            mongo_uri = os.getenv("MONGODB_URI_AUTH")
            if not mongo_uri:
                # Build authenticated URI from components
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

        try:
            self.client = pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=10000)
            self.db = self.client[db_name]
            self.companies = self.db["companies"]

            # Test connection first
            self.client.admin.command("ping")
            logger.info(f"✅ MongoDB connection successful using authenticated URI")

            # Create indexes for efficient queries
            self.companies.create_index("company_id", unique=True)
            self.companies.create_index("industry")
            self.companies.create_index("company_name")
            self.companies.create_index("created_at")

            logger.info(f"✅ Connected to MongoDB for companies: {db_name}")

        except Exception as e:
            logger.error(f"❌ Failed to connect to MongoDB: {e}")
            raise e

    def save_company(self, company_config: CompanyConfig) -> bool:
        """
        Save or update company configuration in MongoDB
        Lưu hoặc cập nhật cấu hình công ty trong MongoDB
        """
        try:
            # Convert CompanyConfig to dict for MongoDB
            company_data = {
                "company_id": company_config.company_id,
                "company_name": company_config.company_name,
                "industry": company_config.industry.value,
                "languages": [lang.value for lang in company_config.languages],
                "qdrant_collection": company_config.qdrant_collection,
                "data_sources": company_config.data_sources,
                "ai_config": company_config.ai_config,
                "industry_config": company_config.industry_config,
                "business_hours": company_config.business_hours,
                "contact_info": company_config.contact_info,
                "created_at": company_config.created_at,
                "updated_at": datetime.now(),
            }

            # Use upsert to save or update
            result = self.companies.update_one(
                {"company_id": company_config.company_id},
                {"$set": company_data},
                upsert=True,
            )

            if result.upserted_id or result.modified_count > 0:
                logger.info(f"✅ Saved company to MongoDB: {company_config.company_id}")
                return True
            else:
                logger.warning(
                    f"⚠️ No changes made to company: {company_config.company_id}"
                )
                return True

        except Exception as e:
            logger.error(f"❌ Failed to save company {company_config.company_id}: {e}")
            return False

    def get_company(self, company_id: str) -> Optional[CompanyConfig]:
        """
        Get company configuration from MongoDB
        Lấy cấu hình công ty từ MongoDB
        """
        try:
            company_data = self.companies.find_one({"company_id": company_id})

            if not company_data:
                logger.warning(f"⚠️ Company not found in MongoDB: {company_id}")
                return None

            # Convert MongoDB document back to CompanyConfig
            company_config = CompanyConfig(
                company_id=company_data["company_id"],
                company_name=company_data["company_name"],
                industry=Industry(company_data["industry"]),
                languages=[
                    Language(lang) for lang in company_data.get("languages", ["vi"])
                ],
                qdrant_collection=company_data["qdrant_collection"],
                data_sources=company_data.get("data_sources", {}),
                ai_config=company_data.get("ai_config", {}),
                industry_config=company_data.get("industry_config", {}),
                business_hours=company_data.get("business_hours"),
                contact_info=company_data.get("contact_info"),
                created_at=company_data.get("created_at", datetime.now()),
                updated_at=company_data.get("updated_at", datetime.now()),
            )

            logger.info(f"✅ Retrieved company from MongoDB: {company_id}")
            return company_config

        except Exception as e:
            logger.error(f"❌ Failed to get company {company_id}: {e}")
            return None

    def list_companies(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """
        List all companies with basic info
        Liệt kê tất cả công ty với thông tin cơ bản
        """
        try:
            companies = (
                self.companies.find(
                    {},
                    {
                        "company_id": 1,
                        "company_name": 1,
                        "industry": 1,
                        "created_at": 1,
                        "updated_at": 1,
                        "_id": 0,
                    },
                )
                .skip(offset)
                .limit(limit)
                .sort("created_at", -1)
            )

            companies_list = list(companies)
            logger.info(f"✅ Retrieved {len(companies_list)} companies from MongoDB")
            return companies_list

        except Exception as e:
            logger.error(f"❌ Failed to list companies: {e}")
            return []

    def search_companies(
        self, company_name: str = None, industry: str = None, limit: int = 50
    ) -> List[Dict]:
        """
        Search companies by name or industry
        Tìm kiếm công ty theo tên hoặc ngành
        """
        try:
            query = {}

            if company_name:
                query["company_name"] = {"$regex": company_name, "$options": "i"}

            if industry:
                query["industry"] = industry

            companies = (
                self.companies.find(
                    query,
                    {
                        "company_id": 1,
                        "company_name": 1,
                        "industry": 1,
                        "contact_info": 1,
                        "created_at": 1,
                        "_id": 0,
                    },
                )
                .limit(limit)
                .sort("company_name", 1)
            )

            companies_list = list(companies)
            logger.info(f"✅ Found {len(companies_list)} companies matching search")
            return companies_list

        except Exception as e:
            logger.error(f"❌ Failed to search companies: {e}")
            return []

    def delete_company(self, company_id: str) -> bool:
        """
        Delete company from MongoDB
        Xóa công ty khỏi MongoDB
        """
        try:
            result = self.companies.delete_one({"company_id": company_id})

            if result.deleted_count > 0:
                logger.info(f"✅ Deleted company from MongoDB: {company_id}")
                return True
            else:
                logger.warning(f"⚠️ Company not found for deletion: {company_id}")
                return False

        except Exception as e:
            logger.error(f"❌ Failed to delete company {company_id}: {e}")
            return False

    def get_companies_by_industry(self, industry: str) -> List[Dict]:
        """
        Get all companies in a specific industry
        Lấy tất cả công ty trong một ngành cụ thể
        """
        try:
            companies = self.companies.find(
                {"industry": industry},
                {
                    "company_id": 1,
                    "company_name": 1,
                    "industry": 1,
                    "qdrant_collection": 1,
                    "created_at": 1,
                    "_id": 0,
                },
            ).sort("company_name", 1)

            companies_list = list(companies)
            logger.info(
                f"✅ Found {len(companies_list)} companies in {industry} industry"
            )
            return companies_list

        except Exception as e:
            logger.error(f"❌ Failed to get companies by industry {industry}: {e}")
            return []

    def get_company_count(self) -> int:
        """
        Get total number of registered companies
        Lấy tổng số công ty đã đăng ký
        """
        try:
            count = self.companies.count_documents({})
            logger.info(f"✅ Total companies in MongoDB: {count}")
            return count

        except Exception as e:
            logger.error(f"❌ Failed to get company count: {e}")
            return 0

    def update_company_metadata(self, company_id: str, metadata: Dict) -> bool:
        """
        Update specific metadata fields for a company
        Cập nhật các trường metadata cụ thể cho công ty
        """
        try:
            update_data = {"updated_at": datetime.now()}
            update_data.update(metadata)

            result = self.companies.update_one(
                {"company_id": company_id}, {"$set": update_data}
            )

            if result.modified_count > 0:
                logger.info(f"✅ Updated company metadata: {company_id}")
                return True
            else:
                logger.warning(f"⚠️ No changes made to company metadata: {company_id}")
                return True

        except Exception as e:
            logger.error(f"❌ Failed to update company metadata {company_id}: {e}")
            return False

    async def update_company_basic_info(
        self, company_id: str, info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update company basic info and return the updated document
        Cập nhật thông tin cơ bản công ty và trả về document đã cập nhật
        """
        try:
            update_data = {"updated_at": datetime.now()}
            update_data.update(info)

            # Update the document and return the updated version
            result = self.companies.find_one_and_update(
                {"company_id": company_id},
                {"$set": update_data},
                return_document=pymongo.ReturnDocument.AFTER,
            )

            if result:
                # Convert ObjectId to string for JSON serialization
                if "_id" in result:
                    result["_id"] = str(result["_id"])

                logger.info(f"✅ Updated company basic info: {company_id}")
                return result
            else:
                logger.error(f"❌ Company not found for update: {company_id}")
                raise Exception(f"Company {company_id} not found")

        except Exception as e:
            logger.error(f"❌ Failed to update company basic info {company_id}: {e}")
            raise e


# Global service instance
company_db_service = None


def get_company_db_service() -> CompanyDBService:
    """Get Company DB service instance / Lấy instance service Company DB"""
    global company_db_service
    if company_db_service is None:
        company_db_service = CompanyDBService()
    return company_db_service
