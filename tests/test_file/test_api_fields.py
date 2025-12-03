#!/usr/bin/env python3
"""
Test API response from inside container
"""
import requests
import json

book_id = "7ec4b4"
url = f"http://localhost:8000/books/{book_id}/preview"

print(f"Testing: {url}")
response = requests.get(url)
print(f"Status: {response.status_code}")

if response.status_code == 200:
    data = response.json()

    # Check access_config
    if "access_config" in data and data["access_config"]:
        ac = data["access_config"]
        print("\n✅ access_config fields:")
        for key in ac.keys():
            print(f"  - {key}: {ac[key]}")

        print(f"\n🔍 Field check:")
        print(f"  download_pdf_points exists: {'download_pdf_points' in ac}")
        print(f"  pdf_download_points exists: {'pdf_download_points' in ac}")
        print(f"  access_type exists: {'access_type' in ac}")
    else:
        print("access_config is null or missing")
else:
    print(f"Error: {response.text}")
