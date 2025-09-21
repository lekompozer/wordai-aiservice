#!/usr/bin/env python3
"""
Register Ivy Fashion Store company in the system
Đăng ký công ty Ivy Fashion Store trong hệ thống
"""

import asyncio
from datetime import datetime
from src.services.company_data_manager import get_company_data_manager
from src.models.unified_models import Industry, IndustryDataType


async def register_ivy_fashion_company():
    """Register Ivy Fashion Store company"""

    print("🏢 Registering Ivy Fashion Store...")

    # Get company data manager instance
    data_manager = get_company_data_manager()

    # Company information
    company_info = {
        "company_id": "ivy-fashion-store",
        "company_name": "IVY Fashion Store",
        "industry": Industry.FASHION,
        "description": "Thương hiệu thời trang cao cấp Việt Nam",
        "contact_info": {
            "email": "contact@ivyfashion.com",
            "phone": "1900 1234",
            "website": "https://ivyfashion.com",
            "address": "123 Nguyễn Huệ, Q1, TP.HCM",
        },
        "business_hours": {
            "weekdays": "8:00 AM - 9:00 PM",
            "weekend": "9:00 AM - 10:00 PM",
        },
        "qdrant_collection": "fashion_ivy_fashion_store",
        "created_at": datetime.now(),
    }

    # Register company
    try:
        result = await data_manager.register_company(company_info)
        success = True
        print("✅ Company registered successfully!")
        print(f"   Company Config: {result.company_name}")
    except Exception as e:
        success = False
        print(f"❌ Failed to register company: {e}")

    if success:
        # Verify registration
        companies = data_manager.list_companies()
        if company_info["company_id"] in companies:
            print(f"✅ Verified: Company found in system")
            print(f"   Total companies: {len(companies)}")
        else:
            print("❌ Warning: Company not found after registration")

        # Get company stats to verify
        stats = data_manager.get_company_stats(company_info["company_id"])
        if stats:
            print("\n📊 Company Stats:")
            print(f"   Company: {stats.get('company_name', 'N/A')}")
            print(f"   Industry: {stats.get('industry', 'N/A')}")
            print(
                f"   Qdrant Collection: {stats.get('qdrant_stats', {}).get('collection_name', 'N/A')}"
            )

    return success


if __name__ == "__main__":
    success = asyncio.run(register_ivy_fashion_company())
    exit(0 if success else 1)
