#!/usr/bin/env python3
"""
Test với simple test để debug DeepSeek trong server
"""
import asyncio
import json
import re


def clean_json_response(response: str) -> str:
    """Clean AI response to extract valid JSON - copy từ ai_extraction_service.py"""
    cleaned = response.strip()

    # Remove markdown code blocks
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]

    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]

    cleaned = cleaned.strip()

    # Find JSON boundaries
    start_idx = cleaned.find("{")
    end_idx = cleaned.rfind("}")

    if start_idx != -1 and end_idx != -1:
        cleaned = cleaned[start_idx : end_idx + 1]

    return cleaned


def test_clean_response():
    """Test clean response function với output từ DeepSeek"""

    print("🧪 TESTING CLEAN JSON RESPONSE FUNCTION")
    print("=" * 50)

    # Sample response từ DeepSeek (với markdown)
    deepseek_response = """```json
{
  "raw_content": "product_id,product_name,category,price\\nFW001,Áo blazer nữ cao cấp,Áo khoác,1580000\\nFW002,Váy midi hoa nhí,Váy,890000\\nFW003,Quần jean skinny,Quần,650000",
  "structured_data": {
    "products": [
      {"name": "Áo blazer nữ cao cấp", "category": "Áo khoác", "price": 1580000},
      {"name": "Váy midi hoa nhí", "category": "Váy", "price": 890000},
      {"name": "Quần jean skinny", "category": "Quần", "price": 650000}
    ]
  }
}
```"""

    print("📄 Original DeepSeek response:")
    print(repr(deepseek_response))
    print()

    # Clean response
    cleaned = clean_json_response(deepseek_response)
    print("🧽 Cleaned response:")
    print(repr(cleaned))
    print()

    # Try parsing
    try:
        json_data = json.loads(cleaned)
        print("✅ JSON parsing successful!")
        print(f"📊 Keys: {list(json_data.keys())}")

        if "structured_data" in json_data:
            products = json_data["structured_data"].get("products", [])
            print(f"🛍️ Found {len(products)} products")
            for i, product in enumerate(products):
                print(f"  {i+1}. {product['name']} - {product['price']:,} VND")

    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing failed: {e}")
        print(f"📄 Cleaned content: {repr(cleaned)}")


if __name__ == "__main__":
    test_clean_response()
