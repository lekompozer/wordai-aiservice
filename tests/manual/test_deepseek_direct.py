#!/usr/bin/env python3
"""
Test DeepSeek API directly with CSV text
"""
import asyncio
import httpx
import json
from typing import Dict, Any, List
import os
from datetime import datetime


async def test_deepseek_direct():
    """Test DeepSeek API call directly"""

    print("🔍 TESTING DEEPSEEK API DIRECTLY")
    print("=" * 60)
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Load environment variables
    from dotenv import load_dotenv

    load_dotenv("development.env")

    deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
    if not deepseek_api_key:
        print("❌ No DeepSeek API key found")
        return

    print(f"✅ DeepSeek API key found: {deepseek_api_key[:8]}...")

    # Read the CSV text we generated
    csv_text = ""
    try:
        with open("debug_csv_text.txt", "r", encoding="utf-8") as f:
            csv_text = f.read()
        print(f"📄 Loaded CSV text: {len(csv_text)} characters")
    except Exception as e:
        print(f"❌ Failed to load CSV text: {e}")
        return

    # Create fashion template system prompt
    system_prompt = """You are an AI expert specialized in extracting fashion product information from text data.

EXTRACTION REQUIREMENTS:
- Extract products information accurately from the provided document
- Return structured data in JSON format with proper categorization
- Ensure all prices are numeric values without currency symbols
- Process size variations (S|M|L|XL) and color options properly
- Maintain data integrity and completeness

RESPONSE FORMAT:
Return ONLY valid JSON without any additional text, explanations, or formatting.

JSON SCHEMA:
{
  "raw_content": "string - original document content",
  "structured_data": {
    "products": [
      {
        "name": "string",
        "category": "string",
        "price": number,
        "currency": "VND|USD",
        "description": "string",
        "brand": "string",
        "sizes": ["string"],
        "colors": ["string"],
        "material": "string",
        "stock_quantity": number
      }
    ],
    "extraction_summary": {
      "total_items": number,
      "data_quality": "high|medium|low",
      "extraction_notes": "string"
    }
  }
}"""

    user_prompt = f"""Extract all fashion products from this document. 

DOCUMENT CONTENT TO PROCESS:
{csv_text}

RAW DATA + JSON REQUIREMENT:
For DeepSeek text processing, you must return BOTH:
1. raw_content: The original text content as processed
2. structured_data: JSON formatted according to the schema

IMPORTANT INSTRUCTIONS:
1. Analyze the above text content carefully
2. Extract ALL text as raw_content (preserve original content)
3. Process and structure the data according to the JSON schema
4. Return BOTH raw content and structured data in the format specified
5. Return ONLY the JSON response, no additional text, explanations, or formatting

Expected response format:
{{
  "raw_content": "Complete original content of the file...",
  "structured_data": {{
    "products": [...extracted products...],
    "extraction_summary": {{
      "total_items": number,
      "data_quality": "high|medium|low",
      "extraction_notes": "Any relevant notes..."
    }}
  }}
}}"""

    print(f"📝 System prompt length: {len(system_prompt)} characters")
    print(f"📝 User prompt length: {len(user_prompt)} characters")

    # Prepare the API request
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
        "max_tokens": 4000,
        "stream": False,
    }

    print("🚀 Making DeepSeek API call...")
    print(f"📊 Request payload size: {len(json.dumps(payload))} characters")

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json=payload)

            print(f"📈 Response status: {response.status_code}")
            print(f"📄 Response headers: {dict(response.headers)}")

            if response.status_code == 200:
                response_data = response.json()
                print("✅ DeepSeek response received")

                # Parse the response
                if "choices" in response_data and response_data["choices"]:
                    content = response_data["choices"][0]["message"]["content"]
                    print(f"📝 Response content length: {len(content)} characters")
                    print(f"📄 First 500 chars: {content[:500]}...")

                    # Try to parse JSON
                    try:
                        json_data = json.loads(content)
                        print("✅ Valid JSON response")
                        print(f"📊 Keys: {list(json_data.keys())}")

                        if (
                            "structured_data" in json_data
                            and "products" in json_data["structured_data"]
                        ):
                            products = json_data["structured_data"]["products"]
                            print(f"🛍️ Products extracted: {len(products)}")
                            if products:
                                print(f"📦 First product: {products[0]}")

                    except json.JSONDecodeError as e:
                        print(f"❌ JSON parsing failed: {e}")
                        print(f"📄 Raw content: {content}")

                else:
                    print("❌ No choices in response")
                    print(f"📄 Full response: {response_data}")

            else:
                print(f"❌ API call failed: {response.status_code}")
                print(f"📄 Response text: {response.text}")

    except Exception as e:
        print(f"❌ Exception during API call: {e}")
        import traceback

        print(f"📄 Traceback: {traceback.format_exc()}")

    print(f"🕒 Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    asyncio.run(test_deepseek_direct())
