#!/usr/bin/env python3
"""Test cover image download + upload to R2"""

import os
import sys
import requests
from datetime import datetime
import boto3
from botocore.client import Config

# Test cover URL from nhasachmienphi.com
TEST_COVER_URL = "https://nhasachmienphi.com/wp-content/uploads/the-emyth-de-xay-dung-doanh-nghiep-hieu-qua.jpg"
TEST_SLUG = "test-cover-download"


def test_cover_upload():
    print("=" * 60)
    print("🖼️  Test Cover Image Download + Upload to R2")
    print("=" * 60)

    # Init boto3 S3 client
    s3_client = boto3.client(
        "s3",
        endpoint_url=os.getenv("R2_ENDPOINT"),
        aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )
    bucket_name = os.getenv("R2_BUCKET_NAME", "wordai-documents")

    print(f"\n1️⃣  Downloading cover from:")
    print(f"   {TEST_COVER_URL}")

    try:
        # Download cover
        r = requests.get(TEST_COVER_URL, timeout=30)
        r.raise_for_status()

        content_type = r.headers.get("content-type", "image/jpeg")
        print(f"   ✅ Downloaded: {len(r.content)} bytes")
        print(f"   Content-Type: {content_type}")

        # Detect extension
        ext = "jpg"
        if "png" in content_type or TEST_COVER_URL.lower().endswith(".png"):
            ext = "png"
        elif "webp" in content_type or TEST_COVER_URL.lower().endswith(".webp"):
            ext = "webp"

        # Upload to R2
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        r2_key = f"books/covers/{ts}_{TEST_SLUG}.{ext}"

        print(f"\n2️⃣  Uploading to R2:")
        print(f"   Key: {r2_key}")

        s3_client.put_object(
            Bucket=bucket_name,
            Key=r2_key,
            Body=r.content,
            ContentType=content_type,
        )

        # Generate public URL
        public_url = f"https://static.wordai.pro/{r2_key}"

        print(f"   ✅ Uploaded successfully!")
        print(f"\n3️⃣  Public URL:")
        print(f"   {public_url}")

        # Verify URL accessible
        print(f"\n4️⃣  Verifying URL accessibility...")
        verify_r = requests.head(public_url, timeout=10)
        if verify_r.status_code == 200:
            print(f"   ✅ URL accessible (HTTP {verify_r.status_code})")
        else:
            print(f"   ⚠️  URL returned HTTP {verify_r.status_code}")

        print("\n" + "=" * 60)
        print("✅ Cover upload test PASSED!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    test_cover_upload()
