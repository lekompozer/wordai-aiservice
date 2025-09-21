#!/usr/bin/env python3
"""
Simple test để gửi CSV text trực tiếp cho DeepSeek
"""
import asyncio
import httpx
import json
import os
from dotenv import load_dotenv


async def test_deepseek_simple():
    """Test đơn giản với DeepSeek"""

    # Load environment
    load_dotenv("development.env")
    deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")

    print("🔍 TESTING DEEPSEEK WITH SIMPLE CSV TEXT")
    print("=" * 50)

    # Simple CSV text for testing
    csv_text = """CSV Data:
product_id,product_name,category,price
FW001,Áo blazer nữ cao cấp,Áo khoác,1580000
FW002,Váy midi hoa nhí,Váy,890000
FW003,Quần jean skinny,Quần,650000"""

    system_prompt = """You are an AI that extracts product data from CSV text.
Return ONLY valid JSON in this format:
{
  "raw_content": "original text here",
  "structured_data": {
    "products": [
      {"name": "product name", "category": "category", "price": number}
    ]
  }
}"""

    user_prompt = f"""Extract products from this CSV text:

{csv_text}

Return ONLY JSON, no other text."""

    print(f"📝 Sending text ({len(csv_text)} chars):")
    print(csv_text)
    print("\n🚀 Calling DeepSeek...")

    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {deepseek_api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 2000,
        "stream": False,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=payload)

            print(f"📊 Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                if "choices" in data and data["choices"]:
                    content = data["choices"][0]["message"]["content"]
                    print(f"✅ Response ({len(content)} chars):")
                    print(content)

                    # Try parsing JSON
                    try:
                        json_data = json.loads(content)
                        print("✅ Valid JSON!")
                        print(f"Keys: {list(json_data.keys())}")
                        if "structured_data" in json_data:
                            products = json_data["structured_data"].get("products", [])
                            print(f"🛍️ Found {len(products)} products")
                    except json.JSONDecodeError as e:
                        print(f"❌ JSON parse error: {e}")
                else:
                    print("❌ No choices in response")
            else:
                print(f"❌ HTTP error: {response.status_code}")
                print(response.text)

    except Exception as e:
        print(f"❌ Exception: {e}")


if __name__ == "__main__":
    asyncio.run(test_deepseek_simple())
