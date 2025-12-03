#!/usr/bin/env python3
"""
Test the book preview endpoint to see actual API response
"""
import requests
import json

# Test with the known book ID
book_id = "7ec4b4"

url = f"http://104.248.147.155/books/{book_id}/preview"

print(f"🔍 Testing GET {url}")
print("=" * 80)

response = requests.get(url)

print(f"Status Code: {response.status_code}")
print("\n📄 Response Headers:")
print(f"Content-Type: {response.headers.get('content-type')}")

if response.status_code == 200:
    data = response.json()

    print("\n✅ Success! API Response Structure:")
    print(json.dumps(data, indent=2, default=str))

    print("\n🔍 Checking access_config field:")
    if "access_config" in data:
        access_config = data["access_config"]
        print(f"access_config type: {type(access_config)}")
        print(f"access_config content: {json.dumps(access_config, indent=2)}")

        # Check specific fields
        print("\n🔎 Field check:")
        print(
            f"  - download_pdf_points: {access_config.get('download_pdf_points', 'NOT FOUND')}"
        )
        print(
            f"  - pdf_download_points: {access_config.get('pdf_download_points', 'NOT FOUND')}"
        )
        print(f"  - access_type in access_config: {'access_type' in access_config}")
    else:
        print("⚠️ No access_config in response!")

    print("\n🔍 Checking user_access field:")
    if "user_access" in data:
        user_access = data["user_access"]
        print(f"user_access: {json.dumps(user_access, indent=2)}")
        if user_access and "access_type" in user_access:
            print(f"  - access_type in user_access: {user_access['access_type']}")
    else:
        print("user_access: null (not authenticated)")

else:
    print(f"\n❌ Error: {response.text}")
