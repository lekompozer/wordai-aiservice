#!/usr/bin/env python3
"""
Test the FIXED preview endpoint to see exact API response structure
"""
import sys

sys.path.insert(0, "/app/src")

import requests
import json

book_id = "guide_f1fa41574c92"
url = f"http://localhost:8000/books/{book_id}/preview"

print(f"🔍 Testing FIXED endpoint: {url}")
print("=" * 80)

try:
    response = requests.get(url, timeout=10)
    print(f"✅ Status Code: {response.status_code}\n")

    if response.status_code == 200:
        data = response.json()

        # ==== MAIN ANALYSIS ====
        print("=" * 80)
        print("📋 COMPLETE API RESPONSE:")
        print("=" * 80)
        print(json.dumps(data, indent=2, default=str))
        print("\n" + "=" * 80)

        # ==== ACCESS_CONFIG DETAILED ANALYSIS ====
        print("\n🔍 ACCESS_CONFIG FIELD ANALYSIS:")
        print("=" * 80)

        if "access_config" not in data:
            print("❌ ERROR: 'access_config' key not found in response!")
        elif data["access_config"] is None:
            print("✅ access_config is null (This is a free book)")
        else:
            ac = data["access_config"]
            print(f"Type: {type(ac).__name__}")
            print(f"\n📦 All Fields in access_config:")
            for key, value in sorted(ac.items()):
                print(f"  • {key}: {value} (type: {type(value).__name__})")

            print(f"\n🔎 Critical Field Check:")
            print(f"  ✅ Has 'download_pdf_points': {'download_pdf_points' in ac}")
            if "download_pdf_points" in ac:
                print(f"     Value: {ac['download_pdf_points']}")

            print(f"  ❌ Has 'pdf_download_points': {'pdf_download_points' in ac}")
            if "pdf_download_points" in ac:
                print(f"     ⚠️  WRONG FIELD FOUND! Value: {ac['pdf_download_points']}")

            print(f"  ❌ Has 'access_type': {'access_type' in ac}")
            if "access_type" in ac:
                print(f"     ⚠️  UNEXPECTED FIELD! Value: {ac['access_type']}")

        print("\n" + "=" * 80)

        # ==== USER_ACCESS ANALYSIS ====
        print("\n🔍 USER_ACCESS FIELD ANALYSIS:")
        print("=" * 80)

        if "user_access" not in data:
            print("❌ ERROR: 'user_access' key not found!")
        elif data["user_access"] is None:
            print("✅ user_access is null (Anonymous/Not authenticated)")
        else:
            ua = data["user_access"]
            print(f"Type: {type(ua).__name__}")
            print(f"\n📦 Fields in user_access:")
            for key, value in sorted(ua.items()):
                print(f"  • {key}: {value}")

            # THIS is where access_type should be!
            if "access_type" in ua:
                print(
                    f"\n  ℹ️  Note: 'access_type' is in USER_ACCESS, not ACCESS_CONFIG!"
                )
                print(f"     This field indicates: {ua['access_type']}")

        print("\n" + "=" * 80)
        print("\n✅ CONCLUSION:")
        print(
            "If frontend is looking for 'pdf_download_points' or 'access_type' in access_config,"
        )
        print("it's using the WRONG field names. The correct names are:")
        print("  • access_config.download_pdf_points (NOT pdf_download_points)")
        print("  • user_access.access_type (NOT in access_config)")

    else:
        print(f"❌ Error Response (Status {response.status_code}):")
        print(response.text)

except Exception as e:
    print(f"❌ Exception occurred: {e}")
    import traceback

    traceback.print_exc()
