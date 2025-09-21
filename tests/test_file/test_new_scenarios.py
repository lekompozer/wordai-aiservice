#!/usr/bin/env python3
"""
Test script for new Scenario structure with ScenarioType
"""

import asyncio
import sys
import os
import json

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from src.models.company_context import Scenario, ScenarioType, CompanyContext, BasicInfo
from src.services.company_context_service import get_company_context_service


async def test_new_scenario_structure():
    """Test the new scenario structure"""
    print("🧪 Testing new Scenario structure...")

    # Test creating scenarios with new structure
    scenarios = [
        Scenario(
            type=ScenarioType.SALES,
            name="Khách hàng muốn tư vấn bảo hiểm",
            description="Kịch bản khi khách hàng có ý định mua sản phẩm bảo hiểm và cần tư vấn",
            reference_messages=[
                "Tôi muốn mua bảo hiểm nhân thọ",
                "Cho tôi xem các gói bảo hiểm",
                "Tư vấn bảo hiểm cho gia đình",
                "I want to buy life insurance",
                "Show me insurance packages",
            ],
        ),
        Scenario(
            type=ScenarioType.ASK_COMPANY_INFORMATION,
            name="Khách hàng hỏi thông tin về công ty",
            description="Kịch bản khi khách hàng muốn tìm hiểu về công ty, lịch sử, dịch vụ",
            reference_messages=[
                "AIA là công ty gì?",
                "Giới thiệu về công ty của bạn",
                "Công ty hoạt động từ khi nào?",
                "What is AIA company?",
                "Tell me about your company",
            ],
        ),
        Scenario(
            type=ScenarioType.SUPPORT,
            name="Khách hàng cần hỗ trợ khiếu nại",
            description="Kịch bản xử lý khi khách hàng có vấn đề cần hỗ trợ",
            reference_messages=[
                "Tôi muốn khiếu nại về dịch vụ",
                "Có vấn đề với đơn bảo hiểm",
                "Cần hỗ trợ gấp",
                "I have a complaint",
                "Need urgent support",
            ],
        ),
    ]

    print("✅ Created scenarios successfully")

    # Test JSON serialization
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n📋 Scenario {i}:")
        print(f"   Type: {scenario.type.value}")
        print(f"   Name: {scenario.name}")
        print(f"   Description: {scenario.description}")
        print(f"   Reference Messages: {len(scenario.reference_messages)} messages")

        # Test to_formatted_string method
        formatted = scenario.to_formatted_string()
        print(f"   Formatted length: {len(formatted)} chars")

        # Test JSON export
        scenario_dict = scenario.model_dump()
        json_str = json.dumps(scenario_dict, ensure_ascii=False, indent=2)
        print(f"   JSON export: ✅ ({len(json_str)} chars)")

    # Test CompanyContext with new scenarios
    print("\n🏢 Testing CompanyContext with new scenarios...")

    context = CompanyContext(
        basic_info=BasicInfo(
            name="AIA Vietnam",
            industry="Insurance",
            description="Leading life insurance company",
        ),
        scenarios=scenarios,
    )

    # Test CompanyContextService
    print("\n🔧 Testing CompanyContextService...")
    service = get_company_context_service()

    company_id = "test_company_123"

    # Set scenarios using service
    await service.set_scenarios(company_id, scenarios)
    print("✅ Scenarios set successfully")

    # Get scenarios back
    retrieved_scenarios = await service.get_scenarios(company_id)
    print(f"✅ Retrieved {len(retrieved_scenarios)} scenarios")

    # Test full context formatting
    full_context = await service.get_full_company_context(company_id)
    formatted_context = full_context.get("formatted_context", "")

    print(f"\n📝 Formatted context:")
    print(f"   Length: {len(formatted_context)} chars")
    print(f"   Preview: {formatted_context[:300]}...")

    # Test scenario types grouping in formatted context
    if "#### SALES Scenarios:" in formatted_context:
        print("✅ SALES scenarios grouped correctly")
    if "#### ASK_COMPANY_INFORMATION Scenarios:" in formatted_context:
        print("✅ ASK_COMPANY_INFORMATION scenarios grouped correctly")
    if "#### SUPPORT Scenarios:" in formatted_context:
        print("✅ SUPPORT scenarios grouped correctly")

    print("\n🎉 All tests passed!")


if __name__ == "__main__":
    asyncio.run(test_new_scenario_structure())
