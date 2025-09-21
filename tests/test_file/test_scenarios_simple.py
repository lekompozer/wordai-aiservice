#!/usr/bin/env python3
"""
Simple test for new Scenario structure without services
"""

import sys
import os
import json

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


def test_scenario_model():
    """Test just the model without services"""
    try:
        from src.models.company_context import (
            Scenario,
            ScenarioType,
            CompanyContext,
            BasicInfo,
        )

        print("🧪 Testing new Scenario model...")

        # Test creating scenarios with new structure
        scenario = Scenario(
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
        )

        print("✅ Scenario created successfully")
        print(f"   Type: {scenario.type.value}")
        print(f"   Name: {scenario.name}")
        print(f"   Description: {scenario.description}")
        print(f"   Reference Messages: {len(scenario.reference_messages)} messages")

        # Test formatted string
        formatted = scenario.to_formatted_string()
        print(f"\n📝 Formatted string ({len(formatted)} chars):")
        print(formatted)

        # Test JSON serialization
        scenario_dict = scenario.model_dump()
        json_str = json.dumps(scenario_dict, ensure_ascii=False, indent=2)
        print(f"\n📋 JSON export ({len(json_str)} chars):")
        print(json_str[:300] + "..." if len(json_str) > 300 else json_str)

        # Test all scenario types
        print(f"\n🎯 Testing all ScenarioType values:")
        for scenario_type in ScenarioType:
            print(f"   ✅ {scenario_type.name}: {scenario_type.value}")

        # Test legacy compatibility
        print(f"\n🔄 Testing legacy compatibility:")
        legacy_scenario = Scenario(
            type=ScenarioType.SUPPORT,
            name="Legacy test",
            description="Test legacy fields",
            reference_messages=["test"],
            # Legacy fields
            situation="Old situation field",
            solution="Old solution field",
            steps=["Step 1", "Step 2"],
        )

        print(f"   ✅ Legacy scenario created with steps: {len(legacy_scenario.steps)}")

        print(f"\n🎉 All model tests passed!")
        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_scenario_model()
    exit(0 if success else 1)
