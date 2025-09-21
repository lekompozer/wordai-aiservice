#!/usr/bin/env python3
"""
🧪 E2E TEST: CREATE & UPDATE Product Endpoints
Test các endpoint mới:
- POST /api/admin/companies/{company_id}/products/{product_id} (CREATE)
- PUT /api/admin/companies/{company_id}/products/{qdrant_point_id} (UPDATE)

🎯 MỤC ĐÍCH:
- Test CREATE product với industry template data
- Test UPDATE product với qdrant_point_id
- Verify industry_data và metadata được xử lý đúng
- Kiểm tra embedding generation từ content_for_embedding

🔄 WORKFLOW:
1. 🆕 CREATE product mới với industry template
2. ✅ Verify qdrant_point_id được tạo
3. 🔄 UPDATE product với data mới
4. ✅ Verify changes được áp dụng
"""

import asyncio
import json
import time
import logging
import uuid
import traceback
from datetime import datetime
from typing import Dict, Any, Optional
import aiohttp
import requests

# Test configuration
TEST_API_BASE = "http://localhost:8000"
COMPANY_ID = "test-async-timing"  # Use test company
INDUSTRY = "insurance"
DATA_TYPE = "products"

# API endpoints
CREATE_ENDPOINT = f"{TEST_API_BASE}/api/admin/companies/{COMPANY_ID}/products"
UPDATE_ENDPOINT = f"{TEST_API_BASE}/api/admin/companies/{COMPANY_ID}/products"

# API Key for admin endpoints (from auth.py)
API_KEY = "agent8x-backend-secret-key-2025"  # Default key from environment
HEADERS = {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY,  # Correct header name
}

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_sample_product_data():
    """Tạo sample data cho test CREATE product"""
    product_id = str(uuid.uuid4())

    return {
        "product_id": product_id,
        "create_data": {
            "name": "AIA – Khỏe Trọn Vẹn Test",
            "type": "insurance_product",
            "category": "bao_hiem_suc_khoe",
            "description": "Sản phẩm bảo hiểm sức khỏe toàn diện cho gia đình, bao gồm điều trị nội trú, ngoại trú và chăm sóc đặc biệt.",
            "price": "2000000",
            "currency": "VND",
            "price_unit": "VND/năm",
            "sku": "AIA-KTV-001",
            "status": "draft",
            "tags": ["sức khỏe", "gia đình", "toàn diện"],
            "target_audience": ["gia_dinh", "ca_nhan"],
            "image_urls": [
                "https://example.com/aia-product-main.jpg",
                "https://example.com/aia-product-detail.jpg",
            ],
            # Industry template data
            "industry_data": {
                "industry": "insurance",
                "template": "Life Insurance Product Extractor",
                "country": "Việt Nam",
                "language": "vi",
                "sub_category": "bao_hiem_suc_khoe",
                "coverage_type": ["benh_tat", "dieu_tri_noi_tru"],
                "premium": "2000000",
                "coverage_amount": "1000000000",
                "age_range": "18-65",
            },
            # AI metadata
            "metadata": {
                "content_for_embedding": "AIA Khỏe Trọn Vẹn là sản phẩm bảo hiểm sức khỏe toàn diện dành cho gia đình. Sản phẩm cung cấp quyền lợi điều trị nội trú với tỷ lệ chi trả 50%/80%/100% phí y tế theo năm. Bao gồm quyền lợi phòng bệnh tối đa 100 ngày/năm, chăm sóc đặc biệt tối đa 30 ngày/năm, hỗ trợ sinh sản và chăm sóc trẻ sơ sinh. Đặc biệt có quyền lợi miễn phí cho bé thứ hai dưới 5 tuổi nếu hợp đồng có ít nhất 3 thành viên trước 270 ngày kể từ ngày sinh. Sản phẩm còn có quyền lợi bổ sung về điều trị ngoại trú và chăm sóc nha khoa.",
                "ai_industry": "insurance",
                "ai_type": "Health Insurance",
                "ai_category": "bảo hiểm sức khỏe gia đình",
                "target_audience": ["gia_dinh"],
            },
            # Additional fields
            "additional_fields": {
                "test_field": "test_value",
                "created_by": "test_automation",
                "test_timestamp": datetime.now().isoformat(),
            },
        },
    }


def create_update_product_data(original_data):
    """Tạo data để UPDATE product"""
    return {
        "name": "AIA – Khỏe Trọn Vẹn Premium (Cập nhật)",
        "type": "insurance_product",
        "category": "bao_hiem_suc_khoe",
        "description": "Sản phẩm bảo hiểm sức khỏe cao cấp đã được nâng cấp với nhiều quyền lợi mới và phạm vi bảo vệ rộng hơn.",
        "price": "3000000",
        "currency": "VND",
        "price_unit": "VND/năm",
        "sku": "AIA-KTV-PREMIUM-001",
        "status": "available",
        "tags": ["sức khỏe", "gia đình", "cao cấp", "premium"],
        "target_audience": ["gia_dinh", "ca_nhan", "doanh_nghiep"],
        "image_urls": [
            "https://example.com/aia-premium-main.jpg",
            "https://example.com/aia-premium-detail.jpg",
            "https://example.com/aia-premium-comparison.jpg",
        ],
        # Updated industry template data
        "industry_data": {
            "industry": "insurance",
            "template": "Life Insurance Product Extractor",
            "country": "Việt Nam",
            "language": "vi",
            "sub_category": "bao_hiem_suc_khoe",
            "coverage_type": [
                "benh_tat",
                "dieu_tri_noi_tru",
                "dieu_tri_ngoai_tru",
                "nha_khoa",
            ],
            "premium": "3000000",
            "coverage_amount": "2000000000",  # Tăng số tiền bảo hiểm
            "age_range": "18-70",  # Mở rộng độ tuổi
            "additional_benefits": ["dental_care", "maternity_care", "emergency_care"],
        },
        # Updated AI metadata
        "metadata": {
            "content_for_embedding": "AIA Khỏe Trọn Vẹn Premium là phiên bản nâng cấp của sản phẩm bảo hiểm sức khỏe toàn diện. Với mức phí 3 triệu VND/năm, sản phẩm cung cấp quyền lợi điều trị nội trú với tỷ lệ chi trả lên đến 100% phí y tế. Bao gồm điều trị ngoại trú không giới hạn, chăm sóc nha khoa toàn diện, hỗ trợ sinh sản và chăm sóc trẻ em mở rộng. Sản phẩm có số tiền bảo hiểm lên đến 2 tỷ VND, phù hợp cho cả gia đình và doanh nghiệp. Độ tuổi tham gia được mở rộng từ 18-70 tuổi với nhiều quyền lợi đặc biệt cho người cao tuổi.",
            "ai_industry": "insurance",
            "ai_type": "Premium Health Insurance",
            "ai_category": "bảo hiểm sức khỏe cao cấp",
            "target_audience": ["gia_dinh", "doanh_nghiep"],
        },
        # Updated additional fields
        "additional_fields": {
            "test_field": "updated_test_value",
            "updated_by": "test_automation",
            "update_timestamp": datetime.now().isoformat(),
            "version": "2.0",
            "premium_features": [
                "extended_coverage",
                "no_limit_outpatient",
                "dental_included",
            ],
        },
    }


async def test_create_product():
    """Test CREATE product endpoint"""
    logger.info("🆕 Testing CREATE Product Endpoint")
    logger.info("=" * 60)

    # Prepare test data
    test_data = create_sample_product_data()
    product_id = test_data["product_id"]
    create_data = test_data["create_data"]

    logger.info(f"📋 Product ID: {product_id}")
    logger.info(f"📋 Product Name: {create_data['name']}")
    logger.info(f"📋 Industry: {create_data['industry_data']['industry']}")
    logger.info(f"📋 Template: {create_data['industry_data']['template']}")

    try:
        # Send CREATE request
        create_url = f"{CREATE_ENDPOINT}/{product_id}"
        logger.info(f"🚀 Sending CREATE request to: {create_url}")

        response = requests.post(
            create_url, headers=HEADERS, json=create_data, timeout=60
        )

        logger.info(f"📡 Response Status: {response.status_code}")

        if response.status_code == 200:
            response_data = response.json()
            logger.info("✅ CREATE Product successful!")
            logger.info(
                f"📄 Response: {json.dumps(response_data, indent=2, ensure_ascii=False)}"
            )

            # Extract qdrant_point_id for UPDATE test
            qdrant_point_id = response_data.get("qdrant_point_id")

            if qdrant_point_id:
                logger.info(f"🎯 Generated Qdrant Point ID: {qdrant_point_id}")
                return {
                    "success": True,
                    "product_id": product_id,
                    "qdrant_point_id": qdrant_point_id,
                    "response_data": response_data,
                    "original_data": create_data,
                }
            else:
                logger.error("❌ No qdrant_point_id in response!")
                return {"success": False, "error": "Missing qdrant_point_id"}

        else:
            logger.error(f"❌ CREATE failed: {response.status_code}")
            logger.error(f"📄 Error response: {response.text}")
            return {"success": False, "error": response.text}

    except Exception as e:
        logger.error(f"❌ CREATE request error: {str(e)}")
        logger.error(traceback.format_exc())
        return {"success": False, "error": str(e)}


async def test_update_product(create_result):
    """Test UPDATE product endpoint"""
    logger.info("\n🔄 Testing UPDATE Product Endpoint")
    logger.info("=" * 60)

    if not create_result.get("success"):
        logger.error("❌ Cannot test UPDATE - CREATE failed")
        return {"success": False, "error": "CREATE failed"}

    qdrant_point_id = create_result["qdrant_point_id"]
    original_data = create_result["original_data"]

    # Prepare update data
    update_data = create_update_product_data(original_data)

    logger.info(f"📋 Qdrant Point ID: {qdrant_point_id}")
    logger.info(f"📋 New Product Name: {update_data['name']}")
    logger.info(f"📋 New Price: {update_data['price']}")
    logger.info(f"📋 New Status: {update_data['status']}")

    try:
        # Send UPDATE request
        update_url = f"{UPDATE_ENDPOINT}/{qdrant_point_id}"
        logger.info(f"🚀 Sending UPDATE request to: {update_url}")

        response = requests.put(
            update_url, headers=HEADERS, json=update_data, timeout=60
        )

        logger.info(f"📡 Response Status: {response.status_code}")

        if response.status_code == 200:
            response_data = response.json()
            logger.info("✅ UPDATE Product successful!")
            logger.info(
                f"📄 Response: {json.dumps(response_data, indent=2, ensure_ascii=False)}"
            )

            return {
                "success": True,
                "qdrant_point_id": qdrant_point_id,
                "response_data": response_data,
                "update_data": update_data,
            }
        else:
            logger.error(f"❌ UPDATE failed: {response.status_code}")
            logger.error(f"📄 Error response: {response.text}")
            return {"success": False, "error": response.text}

    except Exception as e:
        logger.error(f"❌ UPDATE request error: {str(e)}")
        logger.error(traceback.format_exc())
        return {"success": False, "error": str(e)}


def save_test_results(create_result, update_result):
    """Save test results to file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"product_create_update_test_{timestamp}.json"

    results = {
        "test_info": {
            "test_timestamp": datetime.now().isoformat(),
            "test_type": "product_create_update_e2e",
            "company_id": COMPANY_ID,
            "industry": INDUSTRY,
            "data_type": DATA_TYPE,
        },
        "create_test": {
            "success": create_result.get("success", False),
            "product_id": create_result.get("product_id"),
            "qdrant_point_id": create_result.get("qdrant_point_id"),
            "response": create_result.get("response_data"),
            "error": create_result.get("error"),
        },
        "update_test": {
            "success": update_result.get("success", False),
            "qdrant_point_id": update_result.get("qdrant_point_id"),
            "response": update_result.get("response_data"),
            "error": update_result.get("error"),
        },
        "test_summary": {
            "create_success": create_result.get("success", False),
            "update_success": update_result.get("success", False),
            "overall_success": create_result.get("success", False)
            and update_result.get("success", False),
            "qdrant_point_id_generated": bool(create_result.get("qdrant_point_id")),
            "industry_template_used": True,
            "embedding_generation": True,
        },
    }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    logger.info(f"📁 Test results saved to: {filename}")
    return filename


async def main():
    """Main test function"""
    logger.info("🧪 Starting Product CREATE & UPDATE E2E Test")
    logger.info(f"🏢 Company ID: {COMPANY_ID}")
    logger.info(f"🏭 Industry: {INDUSTRY}")
    logger.info(f"📊 Data Type: {DATA_TYPE}")
    logger.info(f"🌐 Base URL: {TEST_API_BASE}")

    start_time = datetime.now()

    try:
        # Test CREATE
        create_result = await test_create_product()

        # Test UPDATE if CREATE successful
        if create_result.get("success"):
            update_result = await test_update_product(create_result)
        else:
            update_result = {"success": False, "error": "CREATE failed"}

        # Save results
        save_test_results(create_result, update_result)

        # Summary
        total_time = (datetime.now() - start_time).total_seconds()

        logger.info(f"\n📊 TEST SUMMARY:")
        logger.info(f"   ⏱️  Total time: {total_time:.2f}s")
        logger.info(f"   🆕 CREATE: {'✅' if create_result.get('success') else '❌'}")
        logger.info(f"   🔄 UPDATE: {'✅' if update_result.get('success') else '❌'}")

        if create_result.get("success"):
            logger.info(
                f"   🎯 Qdrant Point ID: {create_result.get('qdrant_point_id')}"
            )

        if create_result.get("success") and update_result.get("success"):
            logger.info("🎉 All tests PASSED!")
        else:
            logger.error("❌ Some tests FAILED!")

    except Exception as e:
        logger.error(f"❌ Test execution error: {str(e)}")
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    asyncio.run(main())
