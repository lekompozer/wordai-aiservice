"""
Test quote creation via API with Firebase authentication
"""

import requests
import json

# User token provided
user_token = "eyJhbGciOiJSUzI1NiIsImtpZCI6ImVmMjQ4ZjQyZjc0YWUwZjk0OTIwYWY5YTlhMDEzMTdlZjJkMzVmZTEiLCJ0eXAiOiJKV1QifQ.eyJuYW1lIjoiTWljaGFlbCBMZSIsInBpY3R1cmUiOiJodHRwczovL2xoMy5nb29nbGV1c2VyY29udGVudC5jb20vYS9BQ2c4b2NLWUZtc01DeTRZMnkzd2U1MmFNMDFNbXB2MkJCd005SHg2QUlNOEViR09HeVR6MkE9czk2LWMiLCJpc3MiOiJodHRwczovL3NlY3VyZXRva2VuLmdvb2dsZS5jb20vYWl2dW5ndGF1LTM0NzI0IiwiYXVkIjoiYWl2dW5ndGF1LTM0NzI0IiwiYXV0aF90aW1lIjoxNzU3MDA1OTkwLCJ1c2VyX2lkIjoiQWNXU043a0VXUWZCNnp2Yjl2cnpQV05ZeXFUMiIsInN1YiI6IkFjV1NON2tFV1FmQjZ6dmI5dnJ6UFdOWXlxVDIiLCJpYXQiOjE3NTcwMDU5OTAsImV4cCI6MTc1NzAwOTU5MCwiZW1haWwiOiJ0aWVuaG9pLmxoQGdtYWlsLmNvbSIsImVtYWlsX3ZlcmlmaWVkIjp0cnVlLCJmaXJlYmFzZSI6eyJpZGVudGl0aWVzIjp7Imdvb2dsZS5jb20iOlsiMTE1MjI3ODQ5NzU4MjQyOTYyMDUzIl0sImVtYWlsIjpbInRpZW5ob2kubGhAZ21haWwuY29tIl19LCJzaWduX2luX3Byb3ZpZGVyIjoiZ29vZ2xlLmNvbSJ9fQ.agNYf78zyTkuzf05gKNsmdQCX93HtfX6wYWKj6bUFg3Zq38OdgmslNhf_sVAaa7RWMo0_Fd5gB65Mp0ciqukfOteICDRU0-MRzo1SzVQICOatqNXfxeRKaHByNf8KdiwylPh_PFNyhNAuoQ2gY2W2eEwt_wv2-gdjGMnZJjGDXf41yQNDe_Z9QcstZ-GwpwxOyBEIqOhB0ZXU-xSkWVTU6jcVP9rTfuMeh7jv9ol__AVoNlsfPnW7bERXjnZvuozTwnJW-zmLNDj1cJnYiGpxP9rpDAMwO2iHYQ9fqRWuRpQH3XH62neYrHbU8CQRuF3LPTDy00lMPi3YF5uVGpSlA"


def test_quote_creation_api():
    """Test creating a quote via API with authentication"""
    base_url = "http://localhost:8000"
    headers = {
        "Authorization": f"Bearer {user_token}",
        "Content-Type": "application/json",
    }

    print("🔐 Testing Quote Creation via API...")
    print(f"🆔 User: tienhoi.lh@gmail.com (Michael Le)")

    # Step 1: Get templates first
    print("\n1. Getting available templates...")
    try:
        response = requests.get(f"{base_url}/api/documents/templates", headers=headers)
        print(f"   Status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            templates = result.get("templates", [])
            print(f"   Templates found: {len(templates)}")

            quote_template = None
            for template in templates:
                print(
                    f"   - {template['name']} ({template['type']}) - ID: {template.get('id', 'No ID')}"
                )
                if template["type"] == "quote":
                    quote_template = template

            if not quote_template:
                print("❌ No quote template found!")
                return

            template_id = quote_template.get("id") or quote_template.get("_id")
            print(f"✅ Using quote template ID: {template_id}")

        else:
            print(f"❌ Failed to get templates: {response.text}")
            return

    except Exception as e:
        print(f"❌ Error getting templates: {e}")
        return

    # Step 2: Create quote with the template
    print("\n2. Creating quote...")
    quote_data = {
        "template_id": str(template_id),
        "company_info": {
            "name": "Công ty TNHH ABC Technology",
            "address": "123 Đường ABC, Quận 1, TP.HCM",
            "tax_code": "0123456789",
            "representative": "Nguyễn Văn A",
            "position": "Giám đốc",
            "phone": "0901234567",
            "email": "info@abc-tech.com",
            "website": "https://abc-tech.com",
        },
        "customer_info": {
            "name": "Công ty TNHH XYZ Solutions",
            "address": "456 Đường XYZ, Quận 3, TP.HCM",
            "contact_person": "Trần Thị B",
            "position": "Trưởng phòng IT",
            "phone": "0912345678",
            "email": "b.tran@xyz-solutions.com",
            "tax_code": "0987654321",
        },
        "products": [
            {
                "name": "Phần mềm quản lý kho",
                "description": "Hệ thống quản lý kho hàng tự động với AI",
                "quantity": 1,
                "unit": "bộ",
                "unit_price": 50000000,
                "total_price": 50000000,
                "specifications": {"version": "2.0", "database": "MongoDB"},
                "warranty_period": "12 tháng",
                "delivery_time": "30 ngày",
            }
        ],
        "payment_terms": {
            "payment_method": "Chuyển khoản ngân hàng",
            "payment_schedule": "50% tạm ứng, 50% sau khi nghiệm thu",
            "currency": "VND",
            "advance_payment_percent": 50.0,
        },
        "additional_terms": "Báo giá có hiệu lực trong 30 ngày.",
        "validity_period": "30 ngày",
    }

    try:
        response = requests.post(
            f"{base_url}/api/documents/quotes",
            json=quote_data,
            headers=headers,
            timeout=30,  # 30 second timeout
        )
        print(f"   Status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print(f"🎉 SUCCESS: Quote created!")
            print(f"   📄 Request ID: {result.get('request_id', 'Unknown')}")
            print(f"   📊 Status: {result.get('status', 'Unknown')}")
            print(f"   💬 Message: {result.get('message', 'No message')}")
            print(f"   📁 File URL: {result.get('file_url', 'No URL')}")
            print(f"   ⏱️ Processing time: {result.get('processing_time', 0):.2f}s")

            # Test download if we have a request_id
            request_id = result.get("request_id")
            if request_id:
                print(f"\n3. Testing file download...")
                download_response = requests.get(
                    f"{base_url}/api/documents/download/{request_id}", headers=headers
                )
                print(f"   Download status: {download_response.status_code}")
                if download_response.status_code == 200:
                    print(f"   📁 File size: {len(download_response.content)} bytes")
                    print(f"   ✅ File download successful!")
                else:
                    print(f"   ❌ Download failed: {download_response.text}")

        else:
            print(f"❌ Quote creation failed:")
            print(f"   Status: {response.status_code}")
            print(f"   Error: {response.text}")

    except Exception as e:
        print(f"❌ Error creating quote: {e}")

    print("\n🎉 Quote creation test completed!")


if __name__ == "__main__":
    test_quote_creation_api()
