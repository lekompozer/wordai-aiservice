#!/usr/bin/env python3
"""
Test Encrypted Library Images API
Phase 1: Upload & List Operations
"""

import requests
import base64
import json
from pathlib import Path

# Configuration
BASE_URL = "http://localhost:8000"
# You need to get a valid Firebase token from your frontend
FIREBASE_TOKEN = "YOUR_FIREBASE_TOKEN_HERE"

HEADERS = {"Authorization": f"Bearer {FIREBASE_TOKEN}"}


def test_initialize_indexes():
    """Test: Initialize library_images collection indexes"""
    print("\n🧪 Test 1: Initialize Indexes")
    print("=" * 60)

    response = requests.post(
        f"{BASE_URL}/api/library/encrypted-images/initialize", headers=HEADERS
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")

    assert response.status_code == 200
    print("✅ Test passed!")


def test_upload_encrypted_image():
    """Test: Upload encrypted image with thumbnail"""
    print("\n🧪 Test 2: Upload Encrypted Image")
    print("=" * 60)

    # Mock encrypted data (in real app, this comes from frontend encryption)
    encrypted_image = b"ENCRYPTED_IMAGE_DATA_HERE" * 100  # Simulate encrypted binary
    encrypted_thumbnail = b"ENCRYPTED_THUMB_DATA" * 10

    # Mock encryption metadata
    encrypted_file_key = base64.b64encode(b"RSA_ENCRYPTED_AES_KEY").decode()
    iv_original = base64.b64encode(b"123456789012").decode()  # 12 bytes
    iv_thumbnail = base64.b64encode(b"098765432109").decode()

    files = {
        "encryptedImage": ("test.jpg.enc", encrypted_image, "application/octet-stream"),
        "encryptedThumbnail": (
            "test_thumb.jpg.enc",
            encrypted_thumbnail,
            "application/octet-stream",
        ),
    }

    data = {
        "encryptedFileKey": encrypted_file_key,
        "ivOriginal": iv_original,
        "ivThumbnail": iv_thumbnail,
        "filename": "test-image.jpg",
        "imageWidth": 1920,
        "imageHeight": 1080,
        "thumbnailWidth": 300,
        "thumbnailHeight": 200,
        "description": "Test encrypted image",
        "tags": "test,encrypted,secret",
    }

    response = requests.post(
        f"{BASE_URL}/api/library/encrypted-images/upload",
        headers=HEADERS,
        files=files,
        data=data,
    )

    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        print(f"Image ID: {result['image_id']}")
        print(f"Owner: {result['owner_id']}")
        print(f"Filename: {result['filename']}")
        print(f"Encrypted: {result['is_encrypted']}")
        print(f"Tags: {result['tags']}")
        print("✅ Test passed!")
        return result["image_id"]
    else:
        print(f"Error: {response.text}")
        return None


def test_list_encrypted_images():
    """Test: List encrypted images"""
    print("\n🧪 Test 3: List Encrypted Images")
    print("=" * 60)

    response = requests.get(
        f"{BASE_URL}/api/library/encrypted-images",
        headers=HEADERS,
        params={"limit": 10, "offset": 0},
    )

    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        images = response.json()
        print(f"Found {len(images)} encrypted images")

        for img in images:
            print(f"  - {img['filename']} ({img['image_id']})")
            print(f"    Encrypted: {img['is_encrypted']}")
            print(f"    Owner: {img['owner_id']}")
            if "image_download_url" in img:
                print(f"    Download URL: {img['image_download_url'][:50]}...")

        print("✅ Test passed!")
    else:
        print(f"Error: {response.text}")


def test_get_encrypted_image(image_id):
    """Test: Get single encrypted image"""
    print(f"\n🧪 Test 4: Get Encrypted Image {image_id}")
    print("=" * 60)

    response = requests.get(
        f"{BASE_URL}/api/library/encrypted-images/{image_id}", headers=HEADERS
    )

    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        img = response.json()
        print(f"Image ID: {img['image_id']}")
        print(f"Filename: {img['filename']}")
        print(f"Description: {img['description']}")
        print(f"File Size: {img['file_size']} bytes")
        print(f"Dimensions: {img['image_width']}x{img['image_height']}")
        print(f"Encrypted File Keys: {len(img['encrypted_file_keys'])} user(s)")
        print(f"Shared With: {img['shared_with']}")
        print("✅ Test passed!")
    else:
        print(f"Error: {response.text}")


def test_share_image(image_id):
    """Test: Share encrypted image with another user"""
    print(f"\n🧪 Test 5: Share Image {image_id}")
    print("=" * 60)

    # Mock: Encrypt file key for recipient
    recipient_encrypted_key = base64.b64encode(b"RSA_ENCRYPTED_FOR_RECIPIENT").decode()

    payload = {
        "recipient_user_id": "firebase_uid_recipient_123",
        "encrypted_file_key_for_recipient": recipient_encrypted_key,
    }

    response = requests.post(
        f"{BASE_URL}/api/library/encrypted-images/{image_id}/share",
        headers=HEADERS,
        json=payload,
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")

    if response.status_code == 200:
        print("✅ Test passed!")
    else:
        print(f"❌ Test failed!")


def test_soft_delete_image(image_id):
    """Test: Soft delete image"""
    print(f"\n🧪 Test 6: Soft Delete Image {image_id}")
    print("=" * 60)

    response = requests.delete(
        f"{BASE_URL}/api/library/encrypted-images/{image_id}", headers=HEADERS
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")

    if response.status_code == 200:
        print("✅ Test passed!")
    else:
        print(f"❌ Test failed!")


def test_restore_image(image_id):
    """Test: Restore deleted image"""
    print(f"\n🧪 Test 7: Restore Image {image_id}")
    print("=" * 60)

    response = requests.post(
        f"{BASE_URL}/api/library/encrypted-images/{image_id}/restore", headers=HEADERS
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")

    if response.status_code == 200:
        print("✅ Test passed!")
    else:
        print(f"❌ Test failed!")


def main():
    """Run all tests"""
    print("🚀 Testing Encrypted Library Images API - Phase 1")
    print("=" * 60)
    print("⚠️  NOTE: You need to set FIREBASE_TOKEN in this script")
    print("=" * 60)

    # Test 1: Initialize indexes
    try:
        test_initialize_indexes()
    except Exception as e:
        print(f"❌ Test 1 failed: {e}")

    # Test 2: Upload
    image_id = None
    try:
        image_id = test_upload_encrypted_image()
    except Exception as e:
        print(f"❌ Test 2 failed: {e}")

    # Test 3: List
    try:
        test_list_encrypted_images()
    except Exception as e:
        print(f"❌ Test 3 failed: {e}")

    # Test 4: Get single
    if image_id:
        try:
            test_get_encrypted_image(image_id)
        except Exception as e:
            print(f"❌ Test 4 failed: {e}")

    # Test 5: Share
    if image_id:
        try:
            test_share_image(image_id)
        except Exception as e:
            print(f"❌ Test 5 failed: {e}")

    # Test 6: Soft delete
    if image_id:
        try:
            test_soft_delete_image(image_id)
        except Exception as e:
            print(f"❌ Test 6 failed: {e}")

    # Test 7: Restore
    if image_id:
        try:
            test_restore_image(image_id)
        except Exception as e:
            print(f"❌ Test 7 failed: {e}")

    print("\n" + "=" * 60)
    print("✅ All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
