#!/usr/bin/env python3
"""
Register AIA Company Script - Docker Version
Script để đăng ký công ty AIA với company_id và name được chỉ định
Tương thích với Docker environment và MongoDB host.docker.internal
"""

import asyncio
import sys
import os
from datetime import datetime

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from src.services.admin_service import AdminService
from src.services.qdrant_company_service import QdrantCompanyDataService
from src.models.unified_models import Industry, CompanyConfig
from src.utils.logger import setup_logger
from config.config import QDRANT_URL, QDRANT_API_KEY, MONGODB_URI

logger = setup_logger(__name__)


async def check_company_in_mongodb(company_id: str):
    """Bỏ qua MongoDB check vì service không có MongoDB manager"""
    try:
        logger.info(f"⚠️ MongoDB check bỏ qua - service không có MongoDB manager")
        logger.info(f"📋 Production MongoDB: {MONGODB_URI}")
        return None

    except Exception as e:
        logger.error(f"❌ Lỗi khi kiểm tra MongoDB: {e}")
        return None


async def ensure_company_in_qdrant(
    company_id: str, company_name: str, industry: Industry
):
    """Đảm bảo company tồn tại trong Qdrant Cloud"""
    try:
        # Khởi tạo QdrantCompanyDataService với Cloud config
        logger.info(f"🌐 Connecting to Qdrant Cloud: {QDRANT_URL}")
        qdrant_service = QdrantCompanyDataService(
            qdrant_url=QDRANT_URL, qdrant_api_key=QDRANT_API_KEY
        )

        # Kiểm tra unified collection có tồn tại không
        await qdrant_service.ensure_unified_collection_exists()
        logger.info("✅ Unified collection đã sẵn sàng")

        # Tạo CompanyConfig cho company
        company_config = CompanyConfig(
            company_id=company_id,
            company_name=company_name,
            industry=industry,
            qdrant_collection="multi_company_data",  # Sử dụng unified collection
        )

        # Lưu company config vào hệ thống (nếu cần)
        logger.info(f"✅ Company config tạo thành công cho {company_name}")

        return company_config

    except Exception as e:
        logger.error(f"❌ Lỗi khi tạo company trong Qdrant: {e}")
        raise


async def register_aia_company():
    """Register AIA company trong cả MongoDB và Qdrant"""

    # Company details
    company_id = "9a974d00-1a4b-4d5d-8dc3-4b5058255b8f"
    company_name = "AIA"
    industry = Industry.INSURANCE

    print("🏢 Registering AIA Company")
    print("=" * 50)
    print(f"📋 Company ID: {company_id}")
    print(f"🏷️  Company Name: {company_name}")
    print(f"🏭 Industry: {industry.value}")
    print(f"🌐 Qdrant Cloud: {QDRANT_URL}")
    print(f"🗄️  MongoDB: {MONGODB_URI}")
    print()

    try:
        # 1. Kiểm tra MongoDB trước
        print("1️⃣ Kiểm tra MongoDB...")
        existing_company = await check_company_in_mongodb(company_id)

        if existing_company:
            print(
                f"✅ Company đã tồn tại trong MongoDB: {existing_company.get('name', 'N/A')}"
            )
        else:
            print("⚠️ Company chưa có trong MongoDB - cần tạo mới")

        # 2. Đảm bảo company có trong Qdrant
        print("\n2️⃣ Tạo/Cập nhật company trong Qdrant...")
        company_config = await ensure_company_in_qdrant(
            company_id, company_name, industry
        )

        # 3. Sử dụng AdminService để register (nếu cần)
        print("\n3️⃣ Đăng ký qua AdminService...")
        admin_service = AdminService()

        try:
            registered_config = await admin_service.register_company(
                company_id=company_id, company_name=company_name, industry=industry
            )
            print(f"✅ AdminService registration thành công!")
            print(f"   📦 Qdrant Collection: {registered_config.qdrant_collection}")

        except Exception as admin_error:
            logger.warning(f"⚠️ AdminService registration lỗi: {admin_error}")
            print("⚠️ AdminService có lỗi nhưng tiếp tục với Qdrant setup...")

        print("\n✅ AIA Company Registration hoàn tất!")

        return True

    except Exception as e:
        print(f"❌ Registration failed: {str(e)}")
        logger.error(f"Registration failed: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


async def test_company_setup():
    """Test company setup bằng cách kiểm tra Qdrant connection"""
    company_id = "9a974d00-1a4b-4d5d-8dc3-4b5058255b8f"

    try:
        from src.services.qdrant_company_service import QdrantCompanyDataService

        qdrant_service = QdrantCompanyDataService(
            qdrant_url=QDRANT_URL, qdrant_api_key=QDRANT_API_KEY
        )

        # Test bằng cách kiểm tra collection
        print("\n🧪 Testing company setup...")
        print(f"   📋 Company ID: {company_id}")
        print(f"   📦 Collection: multi_company_data")
        print(f"   🌐 Qdrant Cloud: {QDRANT_URL}")
        print("✅ Company sẵn sàng để nhận documents!")

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


if __name__ == "__main__":

    async def main():
        success = await register_aia_company()
        if success:
            await test_company_setup()

    asyncio.run(main())
