#!/usr/bin/env python3
"""
Test AI template generation with multiple models
"""

import asyncio
import requests
import json
from pathlib import Path

# Firebase token for authentication
FIREBASE_TOKEN = "eyJhbGciOiJSUzI1NiIsImtpZCI6IjJkNzU5MjUzMjFkZTczNGY1ZGNlOTc2ZmY4MDEyMzc0YjZmZjE3ODciLCJ0eXAiOiJKV1QifQ.eyJuYW1lIjoiTWljaGFlbCBMZSIsInBpY3R1cmUiOiJodHRwczovL2xoMy5nb29nbGV1c2VyY29udGVudC5jb20vYS9BQ2c4b2NKWGp5RTVoeWQ4Wk9ib0hmTVBRLTJNVjlSTnhHNmczYU9uNzA5UWdGRXpmdWRDPXM5Ni1jIiwiaXNzIjoiaHR0cHM6Ly9zZWN1cmV0b2tlbi5nb29nbGUuY29tL2FpdnVuZ3RhdS1wcm9qZWN0IiwiYXVkIjoiYWl2dW5ndGF1LXByb2plY3QiLCJhdXRoX3RpbWUiOjE3MzQ4OTc1NDMsInVzZXJfaWQiOiJ4UXNPRGMxVGNxZGJNYVV1TVBDbWc0cUlSdjIyIiwic3ViIjoieFFzT0RjMVRjcWRiTWFVdU1QQ21nNHFJUnYyMiIsImlhdCI6MTczNDg5NzU0MywiZXhwIjoxNzM0OTAxMTQzLCJlbWFpbCI6InRpZW5ob2kubGhAZ21haWwuY29tIiwiZW1haWxfdmVyaWZpZWQiOnRydWUsImZpcmViYXNlIjp7ImlkZW50aXRpZXMiOnsiZ29vZ2xlLmNvbSI6WyIxMDg5MTkxNzU4NDU4MjgwNTk1MDIiXSwiZW1haWwiOlsidGllbmhvaS5saEBnbWFpbC5jb20iXX0sInNpZ25faW5fcHJvdmlkZXIiOiJnb29nbGUuY29tIn19.NL4wnWe9HnbLHcBSuNu8CjwwcFJMPBKWP2OKCjqIiuvvF5c4E7wdRzGOPLNHBa2vFRfQq9AjUnGC5jWCwMFBxbMBXnWQFDgFDSN9LVr6GvpDdMnr7v_fCWUhp6J9xPEKReCzE-V7XbmNO-sSFSqkz4PVHe1gHUcHFe0dQ5tAhxmSSGp8kQh_vA0LfAwKV3c2A3WKwSUpLZ0_MsqhKPqmQQHtNFgfWQzFmeTGP9xvxPuiZABUKcJm1Vz7PTdp9h9B1n4AqZKXcGI4iIbZJ0jO_ADFX8nHPJe6d-bNLZNfbK9xmFe8K-VJXkrECjSb5F5SJaWZMXGUJbWXVZq5Sg"

BASE_URL = "http://localhost:8000"


async def test_ai_models():
    """Test getting available AI models"""
    print("🤖 Getting available AI models...")

    response = requests.get(
        f"{BASE_URL}/api/documents/ai-models",
        headers={"Authorization": f"Bearer {FIREBASE_TOKEN}"},
    )

    if response.status_code == 200:
        models = response.json()
        print(f"✅ Available models:")
        for model in models["models"]:
            default_text = " (DEFAULT)" if model.get("default") else ""
            print(f"  🔹 {model['name']}{default_text}")
            print(f"     ID: {model['id']}")
            print(f"     Provider: {model['provider']}")
            print(f"     Description: {model['description']}")
            print()

        return models["models"]
    else:
        print(f"❌ Failed to get models: {response.status_code}")
        return []


async def test_ai_template_generation(model_id: str = "deepseek"):
    """Test AI template generation with specific model"""
    print(f"\n🚀 Testing AI template generation with model: {model_id}")

    # Prepare AI template request
    ai_request = {
        "document_type": "quote",
        "template_option": "create_new",
        "ai_model": model_id,
        "language": "vi",
        "style": "professional",
        "custom_requirements": "Tạo báo giá cho công ty công nghệ, có phần VAT và chữ ký điện tử",
        "company_info": {
            "name": "CÔNG TY TNHH CÔNG NGHỆ AI VŨNG TÀU",
            "address": "123 Đường Lê Lợi, Phường 7, TP. Vũng Tàu",
            "phone": "0254.123.4567",
            "email": "info@aivungtau.com",
        },
        "customer_info": {
            "name": "CÔNG TY ABC TECHNOLOGY",
            "contact_person": "Nguyễn Văn A",
        },
    }

    response = requests.post(
        f"{BASE_URL}/api/documents/ai-template/generate",
        headers={
            "Authorization": f"Bearer {FIREBASE_TOKEN}",
            "Content-Type": "application/json",
        },
        json=ai_request,
    )

    if response.status_code == 200:
        result = response.json()
        print(f"✅ AI template generated successfully!")
        print(
            f"📄 Template structure: {json.dumps(result['template_structure'], indent=2, ensure_ascii=False)}"
        )
        print(f"🔧 Placeholders count: {len(result.get('placeholders', {}))}")
        print(f"📋 Sections count: {len(result.get('sections', []))}")
        print(f"🎨 Styling: {result.get('styling', {}).get('font_family', 'Default')}")
        print(
            f"📊 Metadata: AI Model = {result.get('metadata', {}).get('ai_model', 'Unknown')}"
        )

        return result
    else:
        print(f"❌ Failed to generate AI template: {response.status_code}")
        print(response.text)
        return None


async def test_ai_document_creation():
    """Test creating document using AI-generated template"""
    print(f"\n📝 Testing AI document creation...")

    # Prepare full document request
    doc_request = {
        "document_type": "quote",
        "template_option": "create_new",
        "ai_model": "deepseek",  # Test with default model
        "language": "vi",
        "style": "professional",
        "custom_requirements": "Báo giá chuyên nghiệp cho dịch vụ IT, có logo và chữ ký",
        "company_info": {
            "name": "CÔNG TY TNHH AI VŨNG TÀU",
            "address": "123 Đường Lê Lợi, Phường 7, TP. Vũng Tàu, Bà Rịa - Vũng Tàu",
            "phone": "0254.123.4567",
            "email": "info@aivungtau.com",
            "tax_code": "0123456789",
            "representative": "Nguyễn Văn B",
            "position": "Giám đốc",
        },
        "customer_info": {
            "name": "CÔNG TY TNHH ABC TRADING",
            "contact_person": "Nguyễn Văn A",
            "address": "456 Đường Nguyễn Huệ, Quận 1, TP. Hồ Chí Minh",
            "phone": "028.123.4567",
            "email": "contact@abctrading.com",
        },
        "products": [
            {
                "name": "Dịch vụ phát triển website",
                "description": "Thiết kế và phát triển website responsive với CMS",
                "quantity": 1,
                "unit": "dự án",
                "unit_price": 50000000,
                "total_price": 50000000,
                "specifications": {
                    "Technology": "React + Node.js",
                    "Timeline": "3 tháng",
                    "Features": "Admin panel, SEO optimization",
                },
            }
        ],
        "total_amount": 50000000,
        "total_quantity": 1,
        "payment_terms": {
            "payment_method": "Chuyển khoản ngân hàng",
            "payment_schedule": "50% đặt cọc, 50% nghiệm thu",
        },
        "vat_rate": 10.0,
        "notes": "Báo giá có hiệu lực 30 ngày",
    }

    response = requests.post(
        f"{BASE_URL}/api/documents/ai-documents/create",
        headers={
            "Authorization": f"Bearer {FIREBASE_TOKEN}",
            "Content-Type": "application/json",
        },
        json=doc_request,
    )

    if response.status_code == 200:
        result = response.json()
        print(f"✅ AI document created successfully!")
        print(f"📄 Document ID: {result['document_id']}")
        print(f"📝 File path: {result['file_path']}")
        print(f"⏱️  Processing time: {result['processing_time']:.3f}s")

        # Save file if available
        if result.get("file_content"):
            output_path = Path(f"ai_generated_quote_{result['document_id']}.docx")

            import base64

            file_content = base64.b64decode(result["file_content"])

            with open(output_path, "wb") as f:
                f.write(file_content)

            print(f"💾 File saved to: {output_path}")
            print(f"📊 File size: {len(file_content):,} bytes")

        return result
    else:
        print(f"❌ Failed to create AI document: {response.status_code}")
        print(response.text)
        return None


async def main():
    """Main test function"""
    print("🧪 Starting AI Document Generation Tests")
    print("=" * 50)

    # Test 1: Get available models
    models = await test_ai_models()

    if models:
        # Test 2: Test AI template generation with each model
        for model in models[:2]:  # Test first 2 models
            await test_ai_template_generation(model["id"])

        # Test 3: Test full document creation
        await test_ai_document_creation()

    print("\n🎉 All tests completed!")


if __name__ == "__main__":
    asyncio.run(main())
