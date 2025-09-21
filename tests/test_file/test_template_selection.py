#!/usr/bin/env python3
"""
Test template selection logic with enum handling
"""
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.services.extraction_templates.template_factory import ExtractionTemplateFactory


def test_template_selection():
    print("🧪 TESTING TEMPLATE SELECTION WITH ENUM HANDLING")
    print("=" * 60)

    test_cases = [
        # Frontend enum strings
        {"industry": "Industry.HOTEL", "expected": "hotel"},
        {"industry": "Industry.RESTAURANT", "expected": "restaurant"},
        {"industry": "Industry.BANKING", "expected": "banking"},
        {"industry": "Industry.INSURANCE", "expected": "insurance"},
        # Lowercase strings
        {"industry": "hotel", "expected": "hotel"},
        {"industry": "restaurant", "expected": "restaurant"},
        # Variations
        {"industry": "hotels", "expected": "hotel"},
        {"industry": "food", "expected": "restaurant"},
        {"industry": "finance", "expected": "banking"},
        # Unknown industry
        {"industry": "retail", "expected": "generic"},
        {"industry": "unknown", "expected": "generic"},
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🧪 Test {i}: {test_case['industry']} → {test_case['expected']}")

        metadata = {"industry": test_case["industry"], "company_info": {}}

        try:
            template = ExtractionTemplateFactory.get_template_with_metadata(metadata)
            actual_template = template.__class__.__name__.lower()

            if test_case["expected"] == "generic":
                expected_class = "genericextractiontemplate"
            else:
                expected_class = f"{test_case['expected']}extractiontemplate"

            if expected_class in actual_template:
                print(f"   ✅ SUCCESS: Got {template.__class__.__name__}")
            else:
                print(f"   ❌ FAILED: Expected {expected_class}, got {actual_template}")

        except Exception as e:
            print(f"   ❌ ERROR: {e}")

    print("\n" + "=" * 60)
    print("🎯 SPECIFIC TEST: Hotel data with Industry.HOTEL enum")

    # Test the specific case from your debug log
    hotel_metadata = {
        "industry": "Industry.HOTEL",  # This is what frontend sends
        "company_info": {},
        "original_name": "product_ks.md",
    }

    template = ExtractionTemplateFactory.get_template_with_metadata(hotel_metadata)
    print(f"📋 Template for hotel data: {template.__class__.__name__}")

    # Test pricing schema
    if hasattr(template, "get_extraction_schema"):
        schema = template.get_extraction_schema("products")
        has_pricing = "prices" in schema or "price" in schema
        print(f"💰 Has pricing structure: {has_pricing}")

        if "prices" in schema:
            print("   ✅ New pricing structure (prices.price_1, price_2, price_3)")
        elif "price" in schema:
            print("   ⚠️ Old pricing structure (single price field)")
        else:
            print("   ❌ No pricing structure found!")


if __name__ == "__main__":
    test_template_selection()
