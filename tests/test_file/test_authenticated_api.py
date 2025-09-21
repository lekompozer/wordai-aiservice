"""
Test document generation API with Firebase token
"""

import requests
import json

# User token provided
user_token = "eyJhbGciOiJSUzI1NiIsImtpZCI6ImVmMjQ4ZjQyZjc0YWUwZjk0OTIwYWY5YTlhMDEzMTdlZjJkMzVmZTEiLCJ0eXAiOiJKV1QifQ.eyJuYW1lIjoiTWljaGFlbCBMZSIsInBpY3R1cmUiOiJodHRwczovL2xoMy5nb29nbGV1c2VyY29udGVudC5jb20vYS9BQ2c4b2NLWUZtc01DeTRZMnkzd2U1MmFNMDFNbXB2MkJCd005SHg2QUlNOEViR09HeVR6MkE9czk2LWMiLCJpc3MiOiJodHRwczovL3NlY3VyZXRva2VuLmdvb2dsZS5jb20vYWl2dW5ndGF1LTM0NzI0IiwiYXVkIjoiYWl2dW5ndGF1LTM0NzI0IiwiYXV0aF90aW1lIjoxNzU3MDA1OTkwLCJ1c2VyX2lkIjoiQWNXU043a0VXUWZCNnp2Yjl2cnpQV05ZeXFUMiIsInN1YiI6IkFjV1NON2tFV1FmQjZ6dmI5dnJ6UFdOWXlxVDIiLCJpYXQiOjE3NTcwMDU5OTAsImV4cCI6MTc1NzAwOTU5MCwiZW1haWwiOiJ0aWVuaG9pLmxoQGdtYWlsLmNvbSIsImVtYWlsX3ZlcmlmaWVkIjp0cnVlLCJmaXJlYmFzZSI6eyJpZGVudGl0aWVzIjp7Imdvb2dsZS5jb20iOlsiMTE1MjI3ODQ5NzU4MjQyOTYyMDUzIl0sImVtYWlsIjpbInRpZW5ob2kubGhAZ21haWwuY29tIl19LCJzaWduX2luX3Byb3ZpZGVyIjoiZ29vZ2xlLmNvbSJ9fQ.agNYf78zyTkuzf05gKNsmdQCX93HtfX6wYWKj6bUFg3Zq38OdgmslNhf_sVAaa7RWMo0_Fd5gB65Mp0ciqukfOteICDRU0-MRzo1SzVQICOatqNXfxeRKaHByNf8KdiwylPh_PFNyhNAuoQ2gY2W2eEwt_wv2-gdjGMnZJjGDXf41yQNDe_Z9QcstZ-GwpwxOyBEIqOhB0ZXU-xSkWVTU6jcVP9rTfuMeh7jv9ol__AVoNlsfPnW7bERXjnZvuozTwnJW-zmLNDj1cJnYiGpxP9rpDAMwO2iHYQ9fqRWuRpQH3XH62neYrHbU8CQRuF3LPTDy00lMPi3YF5uVGpSlA"


def test_authenticated_api():
    """Test API with authentication"""
    base_url = "http://localhost:8000"
    headers = {
        "Authorization": f"Bearer {user_token}",
        "Content-Type": "application/json",
    }

    print("🔐 Testing Authenticated Document Generation API...")
    print(f"🆔 User: tienhoi.lh@gmail.com (Michael Le)")

    # Test templates list with auth
    print("\n1. Testing templates list with authentication...")
    try:
        response = requests.get(f"{base_url}/api/documents/templates", headers=headers)
        print(f"   Status: {response.status_code}")
        result = response.json()
        print(f"   Templates found: {result.get('total', 0)}")

        if result.get("templates"):
            for i, template in enumerate(result["templates"], 1):
                print(
                    f"   {i}. {template['name']} ({template['type']}) - ID: {template.get('id', 'No ID')}"
                )

        # Store template ID for testing
        template_id = None
        if result.get("templates"):
            template_id = result["templates"][0].get("id") or result["templates"][
                0
            ].get("_id")
            print(f"   Using template ID: {template_id}")

    except Exception as e:
        print(f"   Error: {e}")
        return

    # Test quote creation with authentication
    if template_id:
        print("\n2. Testing quote creation with authentication...")
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
                f"{base_url}/api/documents/quotes", json=quote_data, headers=headers
            )
            print(f"   Status: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                print(f"   ✅ Success: {result.get('message', 'Quote created')}")
                print(f"   📄 Request ID: {result.get('request_id', 'Unknown')}")
                print(f"   📁 File URL: {result.get('file_url', 'Not available')}")
                print(f"   ⏱️ Processing time: {result.get('processing_time', 0):.2f}s")

                # Test status check if we have request_id
                request_id = result.get("request_id")
                if request_id:
                    print(f"\n3. Testing status check for request: {request_id}")
                    status_response = requests.get(
                        f"{base_url}/api/documents/status/{request_id}", headers=headers
                    )
                    print(f"   Status: {status_response.status_code}")
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        print(
                            f"   📊 Document Status: {status_data.get('status', 'Unknown')}"
                        )
                        print(
                            f"   🗂️ Document Type: {status_data.get('type', 'Unknown')}"
                        )
                        print(
                            f"   📅 Created: {status_data.get('created_at', 'Unknown')}"
                        )

            else:
                print(f"   ❌ Error: {response.text}")

        except Exception as e:
            print(f"   Error: {e}")

    # Test health endpoint
    print("\n4. Testing health endpoint...")
    try:
        response = requests.get(f"{base_url}/api/documents/health")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            health_data = response.json()
            print(f"   💚 Service Status: {health_data.get('status', 'Unknown')}")
            print(f"   🗄️ Database: {health_data.get('database', 'Unknown')}")
        else:
            print(f"   ❌ Health check failed: {response.text}")
    except Exception as e:
        print(f"   Error: {e}")

    print("\n🎉 Authentication testing completed!")


if __name__ == "__main__":
    test_authenticated_api()
