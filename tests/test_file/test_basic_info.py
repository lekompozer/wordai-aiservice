#!/usr/bin/env python3
"""
Simple test for basic info retrieval
"""

import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from src.services.company_context_service import get_company_context_service
from src.models.company_context import BasicInfo, SocialLinks, Location
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


async def test_basic_info():
    """Test basic info creation and retrieval"""
    try:
        logger.info("🚀 Testing basic info functionality...")

        # Step 1: Set up test company context
        company_id = "test_company_simple"
        context_service = get_company_context_service()

        # Step 2: Create test basic info
        basic_info = BasicInfo(
            name="Công ty Test Simple",
            industry="banking",
            description="Công ty test đơn giản",
            location=Location(
                country="Việt Nam", city="Hà Nội", address="123 Phố Test"
            ),
            email="test@simple.com",
            phone="0987654321",
            website="https://simple.test",
        )

        # Step 3: Set basic info
        logger.info("📝 Setting basic info...")
        result = await context_service.set_basic_info(company_id, basic_info)
        logger.info(f"✅ Basic info set: {result.name}")

        # Step 4: Retrieve basic info
        logger.info("📖 Retrieving basic info...")
        retrieved_info = await context_service.get_basic_info(company_id)

        if retrieved_info:
            logger.info(f"✅ Retrieved info: {retrieved_info.name}")

            # Step 5: Test formatted string
            formatted_string = retrieved_info.to_formatted_string()
            logger.info(f"📄 Formatted string:\n{formatted_string}")
        else:
            logger.error("❌ Failed to retrieve basic info")

        logger.info("✅ Basic info test completed!")

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    # Run the test
    asyncio.run(test_basic_info())
