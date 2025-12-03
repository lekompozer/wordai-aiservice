#!/usr/bin/env python3
"""
Test the exact endpoint that frontend is calling
"""
import requests
import json

book_id = "guide_f1fa41574c92"
url = f"http://localhost:8000/books/{book_id}/preview"

print(f"🔍 Testing: GET {url}")
print("=" * 80)

try:
    response = requests.get(url, timeout=5)
    print(f"Status Code: {response.status_code}\n")

    if response.status_code == 200:
        data = response.json()

        print("📦 Full Response:")
        print(json.dumps(data, indent=2, default=str))
        print("\n" + "=" * 80)

        # Focus on access_config
        print("\n🔍 ACCESS CONFIG ANALYSIS:")
        if "access_config" in data:
            if data["access_config"] is None:
                print("  ⚠️ access_config is null (free book)")
            else:
                ac = data["access_config"]
                print(f"  Type: {type(ac)}")
                print(f"  Keys: {list(ac.keys())}")
                print("\n  Fields:")
                for key, value in ac.items():
                    print(f"    • {key}: {value} (type: {type(value).__name__})")

                # Check for the problematic fields
                print("\n  🔎 Specific Field Check:")
                print(
                    f"    ✓ 'download_pdf_points' exists: {('download_pdf_points' in ac)}"
                )
                print(
                    f"    ✗ 'pdf_download_points' exists: {('pdf_download_points' in ac)}"
                )
                print(f"    ✗ 'access_type' exists: {('access_type' in ac)}")

                if "download_pdf_points" in ac:
                    print(
                        f"\n    ✅ download_pdf_points value: {ac['download_pdf_points']}"
                    )
        else:
            print("  ❌ No 'access_config' key in response!")

        # Check user_access (this has access_type)
        print("\n🔍 USER ACCESS ANALYSIS:")
        if "user_access" in data:
            ua = data["user_access"]
            if ua is None:
                print("  user_access: null (anonymous user)")
            else:
                print(f"  Type: {type(ua)}")
                print(f"  Keys: {list(ua.keys())}")
                print("\n  Fields:")
                for key, value in ua.items():
                    print(f"    • {key}: {value}")
        else:
            print("  ❌ No 'user_access' key in response!")

    else:
        print(f"❌ Error Response:")
        print(response.text)

except Exception as e:
    print(f"❌ Exception: {e}")
    import traceback

    traceback.print_exc()
