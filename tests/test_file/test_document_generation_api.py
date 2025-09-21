"""
Test script for Document Generation API endpoints
"""

import requests
import json

# Test data
test_company = {
    "name": "Công ty TNHH ABC Technology",
    "address": "123 Đường ABC, Quận 1, TP.HCM",
    "tax_code": "0123456789",
    "representative": "Nguyễn Văn A",
    "position": "Giám đốc",
    "phone": "0901234567",
    "email": "info@abc-tech.com",
    "website": "https://abc-tech.com",
}

test_customer = {
    "name": "Công ty TNHH XYZ Solutions",
    "address": "456 Đường XYZ, Quận 3, TP.HCM",
    "contact_person": "Trần Thị B",
    "position": "Trưởng phòng IT",
    "phone": "0912345678",
    "email": "b.tran@xyz-solutions.com",
    "tax_code": "0987654321",
}

test_products = [
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
]

test_payment_terms = {
    "payment_method": "Chuyển khoản ngân hàng",
    "payment_schedule": "50% tạm ứng, 50% sau khi nghiệm thu",
    "currency": "VND",
    "advance_payment_percent": 50.0,
}


def test_api_endpoints():
    base_url = "http://localhost:8000"

    print("🚀 Testing Document Generation API Endpoints...")

    # Test health endpoint
    print("\n1. Testing health endpoint...")
    try:
        response = requests.get(f"{base_url}/api/documents/health")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   Response: {response.json()}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Error: {e}")

    # Test templates list
    print("\n2. Testing templates list...")
    try:
        response = requests.get(f"{base_url}/api/documents/templates")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"   Error: {e}")

    # Test quote creation (this will likely fail due to database)
    print("\n3. Testing quote creation...")
    quote_data = {
        "template_id": "68bd5c41e0e2da2aefa28434",  # ID from our created template
        "company_info": test_company,
        "customer_info": test_customer,
        "products": test_products,
        "payment_terms": test_payment_terms,
        "additional_terms": "Báo giá có hiệu lực 30 ngày",
        "validity_period": "30 ngày",
    }

    try:
        response = requests.post(
            f"{base_url}/api/documents/quotes",
            json=quote_data,
            headers={"Content-Type": "application/json"},
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"   Success: {result['message']}")
            print(f"   Request ID: {result['request_id']}")
            print(f"   File URL: {result.get('file_url', 'Not available')}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Error: {e}")

    # Test OpenAPI docs
    print("\n4. Testing OpenAPI documentation...")
    try:
        response = requests.get(f"{base_url}/docs")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ Documentation accessible")
        else:
            print(f"   ❌ Documentation not accessible: {response.status_code}")
    except Exception as e:
        print(f"   Error: {e}")

    print("\n🎉 API endpoint testing completed!")
    print("\n📋 Available endpoints:")
    print("   GET  /api/documents/health - Health check")
    print("   GET  /api/documents/templates - List templates")
    print("   POST /api/documents/quotes - Create quote")
    print("   POST /api/documents/contracts - Create contract")
    print("   POST /api/documents/appendices - Create appendix")
    print("   GET  /api/documents/status/{id} - Check status")
    print("   GET  /api/documents/download/{id} - Download file")
    print("   GET  /docs - API documentation")


if __name__ == "__main__":
    test_api_endpoints()
