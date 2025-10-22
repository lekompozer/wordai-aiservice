#!/usr/bin/env python3
"""
Test Convert Regular Image to Secret API
Phase 2: Convert existing library images to encrypted
"""

import requests
import base64
import json
from pathlib import Path

# Configuration
BASE_URL = "http://localhost:8000"
# You need to get a valid Firebase token from your frontend
FIREBASE_TOKEN = "YOUR_FIREBASE_TOKEN_HERE"

HEADERS = {
    "Authorization": f"Bearer {FIREBASE_TOKEN}"
}


def test_upload_regular_image():
    """
    Step 1: Upload a regular (unencrypted) image to library first
    """
    print("\n🧪 Step 1: Upload Regular Image to Library")
    print("=" * 60)
    
    # Mock regular image data
    regular_image = b"REGULAR_IMAGE_JPEG_DATA" * 100
    
    files = {
        'file': ('regular-photo.jpg', regular_image, 'image/jpeg'),
    }
    
    data = {
        'description': 'Regular image to be converted',
        'tags': 'test,convert',
    }
    
    response = requests.post(
        f"{BASE_URL}/api/library/upload",
        headers=HEADERS,
        files=files,
        data=data
    )
    
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"Library ID: {result['library_id']}")
        print(f"Filename: {result['filename']}")
        print(f"Category: {result['category']}")
        print(f"Is Encrypted: {result.get('is_encrypted', False)}")
        print("✅ Regular image uploaded!")
        return result['library_id']
    else:
        print(f"❌ Error: {response.text}")
        return None


def test_convert_to_secret(library_id):
    """
    Step 2: Convert the regular image to encrypted secret
    
    In real app, frontend would:
    1. Download the regular image
    2. Encrypt it client-side
    3. Call this endpoint
    """
    print(f"\n🧪 Step 2: Convert Regular Image {library_id} to Secret")
    print("=" * 60)
    
    # Mock encrypted data (simulating client-side encryption)
    encrypted_image = b"ENCRYPTED_IMAGE_DATA_AES256GCM" * 100
    encrypted_thumbnail = b"ENCRYPTED_THUMB_DATA" * 10
    
    # Mock encryption metadata
    encrypted_file_key = base64.b64encode(b"RSA_OAEP_ENCRYPTED_AES_KEY").decode()
    iv_original = base64.b64encode(b"123456789012").decode()  # 12 bytes
    iv_thumbnail = base64.b64encode(b"098765432109").decode()
    
    # Optional EXIF encryption
    encrypted_exif = base64.b64encode(b'{"gps": "encrypted", "camera": "encrypted"}').decode()
    iv_exif = base64.b64encode(b"111111111111").decode()
    
    files = {
        'encryptedImage': ('encrypted.jpg.enc', encrypted_image, 'application/octet-stream'),
        'encryptedThumbnail': ('encrypted_thumb.jpg.enc', encrypted_thumbnail, 'application/octet-stream'),
    }
    
    data = {
        'encryptedFileKey': encrypted_file_key,
        'ivOriginal': iv_original,
        'ivThumbnail': iv_thumbnail,
        'encryptedExif': encrypted_exif,
        'ivExif': iv_exif,
        'imageWidth': 1920,
        'imageHeight': 1080,
        'thumbnailWidth': 300,
        'thumbnailHeight': 200,
    }
    
    response = requests.post(
        f"{BASE_URL}/api/library/files/{library_id}/convert-to-secret",
        headers=HEADERS,
        files=files,
        data=data
    )
    
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"Success: {result['success']}")
        print(f"Message: {result['message']}")
        print(f"Library ID: {result['library_id']}")
        print(f"R2 Image Path: {result['r2_image_path']}")
        print(f"R2 Thumbnail Path: {result['r2_thumbnail_path']}")
        print(f"Is Encrypted: {result['is_encrypted']}")
        print("✅ Image converted to secret!")
        return True
    else:
        print(f"❌ Error: {response.text}")
        return False


def test_verify_encryption(library_id):
    """
    Step 3: Verify the image is now encrypted in the library
    """
    print(f"\n🧪 Step 3: Verify Image {library_id} is Now Encrypted")
    print("=" * 60)
    
    response = requests.get(
        f"{BASE_URL}/api/library/files/{library_id}",
        headers=HEADERS
    )
    
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"Library ID: {result['library_id']}")
        print(f"Filename: {result['filename']}")
        print(f"Category: {result['category']}")
        print(f"Is Encrypted: {result.get('is_encrypted', False)}")
        
        # Check encryption fields
        if result.get('is_encrypted'):
            print(f"Encrypted File Keys: {len(result.get('encrypted_file_keys', {}))} user(s)")
            print(f"Has IV Original: {'encryption_iv_original' in result}")
            print(f"Has IV Thumbnail: {'encryption_iv_thumbnail' in result}")
            print(f"Has Encrypted EXIF: {'encrypted_exif' in result}")
            print(f"R2 Image Path: {result.get('r2_image_path', 'N/A')}")
            print(f"R2 Thumbnail Path: {result.get('r2_thumbnail_path', 'N/A')}")
            print("✅ Image is properly encrypted!")
        else:
            print("❌ Image is NOT encrypted!")
            return False
        
        return True
    else:
        print(f"❌ Error: {response.text}")
        return False


def test_double_encryption_prevention(library_id):
    """
    Step 4: Test that converting an already encrypted image fails
    """
    print(f"\n🧪 Step 4: Test Double Encryption Prevention")
    print("=" * 60)
    
    # Try to convert the same image again
    encrypted_image = b"FAKE_ENCRYPTED_DATA" * 10
    encrypted_thumbnail = b"FAKE_THUMB" * 5
    
    files = {
        'encryptedImage': ('fake.enc', encrypted_image, 'application/octet-stream'),
        'encryptedThumbnail': ('fake_thumb.enc', encrypted_thumbnail, 'application/octet-stream'),
    }
    
    data = {
        'encryptedFileKey': base64.b64encode(b"FAKE_KEY").decode(),
        'ivOriginal': base64.b64encode(b"123456789012").decode(),
        'ivThumbnail': base64.b64encode(b"098765432109").decode(),
    }
    
    response = requests.post(
        f"{BASE_URL}/api/library/files/{library_id}/convert-to-secret",
        headers=HEADERS,
        files=files,
        data=data
    )
    
    print(f"Status: {response.status_code}")
    
    if response.status_code == 400:
        error = response.json()
        print(f"Error Detail: {error['detail']}")
        print("✅ Double encryption properly prevented!")
        return True
    else:
        print(f"❌ Should have returned 400 Bad Request, got {response.status_code}")
        return False


def test_non_image_conversion():
    """
    Step 5: Test that converting a non-image file fails
    """
    print(f"\n🧪 Step 5: Test Non-Image File Conversion Prevention")
    print("=" * 60)
    
    # Upload a document first
    document_data = b"PDF DOCUMENT DATA" * 50
    
    files = {
        'file': ('document.pdf', document_data, 'application/pdf'),
    }
    
    upload_response = requests.post(
        f"{BASE_URL}/api/library/upload",
        headers=HEADERS,
        files=files
    )
    
    if upload_response.status_code != 200:
        print("❌ Failed to upload document")
        return False
    
    doc_library_id = upload_response.json()['library_id']
    print(f"Uploaded document: {doc_library_id}")
    
    # Try to convert the document to secret
    encrypted_image = b"FAKE_ENCRYPTED" * 10
    encrypted_thumbnail = b"FAKE_THUMB" * 5
    
    files = {
        'encryptedImage': ('fake.enc', encrypted_image, 'application/octet-stream'),
        'encryptedThumbnail': ('fake_thumb.enc', encrypted_thumbnail, 'application/octet-stream'),
    }
    
    data = {
        'encryptedFileKey': base64.b64encode(b"FAKE_KEY").decode(),
        'ivOriginal': base64.b64encode(b"123456789012").decode(),
        'ivThumbnail': base64.b64encode(b"098765432109").decode(),
    }
    
    response = requests.post(
        f"{BASE_URL}/api/library/files/{doc_library_id}/convert-to-secret",
        headers=HEADERS,
        files=files,
        data=data
    )
    
    print(f"Status: {response.status_code}")
    
    if response.status_code == 400:
        error = response.json()
        print(f"Error Detail: {error['detail']}")
        print("✅ Non-image conversion properly prevented!")
        return True
    else:
        print(f"❌ Should have returned 400 Bad Request, got {response.status_code}")
        return False


def main():
    """Run all Phase 2 tests"""
    print("🚀 Testing Convert Regular Image to Secret API - Phase 2")
    print("=" * 60)
    print("⚠️  NOTE: You need to set FIREBASE_TOKEN in this script")
    print("=" * 60)
    
    # Step 1: Upload regular image
    library_id = None
    try:
        library_id = test_upload_regular_image()
    except Exception as e:
        print(f"❌ Step 1 failed: {e}")
        return
    
    if not library_id:
        print("❌ Failed to upload regular image, aborting tests")
        return
    
    # Step 2: Convert to secret
    try:
        success = test_convert_to_secret(library_id)
        if not success:
            print("❌ Failed to convert image to secret")
            return
    except Exception as e:
        print(f"❌ Step 2 failed: {e}")
        return
    
    # Step 3: Verify encryption
    try:
        test_verify_encryption(library_id)
    except Exception as e:
        print(f"❌ Step 3 failed: {e}")
    
    # Step 4: Test double encryption prevention
    try:
        test_double_encryption_prevention(library_id)
    except Exception as e:
        print(f"❌ Step 4 failed: {e}")
    
    # Step 5: Test non-image conversion prevention
    try:
        test_non_image_conversion()
    except Exception as e:
        print(f"❌ Step 5 failed: {e}")
    
    print("\n" + "=" * 60)
    print("✅ Phase 2 tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
