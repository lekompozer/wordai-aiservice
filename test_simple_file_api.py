#!/usr/bin/env python3
"""
Test Simple File Upload API
"""

import requests
import os
from dotenv import load_dotenv

load_dotenv()

# Get Firebase token (you need to get this from your browser or app)
FIREBASE_TOKEN = "YOUR_FIREBASE_TOKEN_HERE"  # Replace with actual token

BASE_URL = "https://ai.wordai.pro"
# For local testing: BASE_URL = "http://localhost:8000"


def test_create_folder():
    """Test creating a folder"""
    url = f"{BASE_URL}/api/simple-files/folders"
    headers = {
        "Authorization": f"Bearer {FIREBASE_TOKEN}",
        "Content-Type": "application/json",
    }
    data = {"name": "Test Documents", "description": "Folder for testing file uploads"}

    response = requests.post(url, json=data, headers=headers)
    print(f"✅ Create Folder Response: {response.status_code}")
    if response.status_code == 200:
        folder_data = response.json()
        print(f"   Folder ID: {folder_data['id']}")
        return folder_data["id"]
    else:
        print(f"   Error: {response.text}")
        return None


def test_upload_file(folder_id=None):
    """Test uploading a file"""
    # Create a test file
    test_content = "This is a test document for file upload API testing."
    with open("/tmp/test_document.txt", "w") as f:
        f.write(test_content)

    url = f"{BASE_URL}/api/simple-files/upload"
    headers = {
        "Authorization": f"Bearer {FIREBASE_TOKEN}",
    }

    with open("/tmp/test_document.txt", "rb") as f:
        files = {"file": ("test_document.txt", f, "text/plain")}
        data = {}
        if folder_id:
            data["folder_id"] = folder_id

        response = requests.post(url, files=files, data=data, headers=headers)

    print(f"✅ Upload File Response: {response.status_code}")
    if response.status_code == 200:
        file_data = response.json()
        print(f"   File ID: {file_data['id']}")
        print(f"   Original Name: {file_data['original_name']}")
        print(f"   File Size: {file_data['file_size']} bytes")
        print(f"   Folder ID: {file_data['folder_id']}")
        print(f"   R2 URL: {file_data['r2_url']}")
        return file_data
    else:
        print(f"   Error: {response.text}")
        return None


def test_list_files_in_folder(folder_id=None):
    """Test listing files in specific folder"""
    url = f"{BASE_URL}/api/simple-files/files"
    headers = {
        "Authorization": f"Bearer {FIREBASE_TOKEN}",
    }

    params = {}
    if folder_id:
        params["folder_id"] = folder_id

    response = requests.get(url, headers=headers, params=params)
    print(f"✅ List Files in Folder Response: {response.status_code}")
    if response.status_code == 200:
        files = response.json()
        folder_name = f"folder {folder_id}" if folder_id else "root folder"
        print(f"   Found {len(files)} files in {folder_name}")
        for file in files:
            print(
                f"   - {file['original_name']} (ID: {file['id']}, Size: {file['file_size']} bytes)"
            )
        return files
    else:
        print(f"   Error: {response.text}")
        return []


def test_list_all_files():
    """Test listing all files for user"""
    url = f"{BASE_URL}/api/simple-files/files/all"
    headers = {
        "Authorization": f"Bearer {FIREBASE_TOKEN}",
    }

    response = requests.get(url, headers=headers)
    print(f"✅ List All Files Response: {response.status_code}")
    if response.status_code == 200:
        files = response.json()
        print(f"   Found {len(files)} total files")
        for file in files:
            folder_info = (
                f"in folder {file['folder_id']}" if file["folder_id"] else "in root"
            )
            print(f"   - {file['original_name']} (ID: {file['id']}) {folder_info}")
        return files
    else:
        print(f"   Error: {response.text}")
        return []


def test_get_file(file_id):
    """Test getting specific file details"""
    url = f"{BASE_URL}/api/simple-files/files/{file_id}"
    headers = {
        "Authorization": f"Bearer {FIREBASE_TOKEN}",
    }

    response = requests.get(url, headers=headers)
    print(f"✅ Get File Details Response: {response.status_code}")
    if response.status_code == 200:
        file = response.json()
        print(f"   File: {file['original_name']}")
        print(f"   Type: {file['file_type']}")
        print(f"   Size: {file['file_size']} bytes")
        print(f"   Public URL: {file['public_url']}")
        return file
    else:
        print(f"   Error: {response.text}")
        return None


def test_delete_file(file_id):
    """Test deleting a file"""
    url = f"{BASE_URL}/api/simple-files/files/{file_id}"
    headers = {
        "Authorization": f"Bearer {FIREBASE_TOKEN}",
    }

    response = requests.delete(url, headers=headers)
    print(f"✅ Delete File Response: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"   Success: {result['success']}")
        print(f"   Message: {result['message']}")
        print(f"   Deleted: {result.get('filename', 'Unknown')}")
        return True
    else:
        print(f"   Error: {response.text}")
        return False


def test_list_folders():
    """Test listing folders"""
    url = f"{BASE_URL}/api/simple-files/folders"
    headers = {
        "Authorization": f"Bearer {FIREBASE_TOKEN}",
    }

    response = requests.get(url, headers=headers)
    print(f"✅ List Folders Response: {response.status_code}")
    if response.status_code == 200:
        folders = response.json()
        print(f"   Found {len(folders)} folders")
        for folder in folders:
            print(f"   - {folder['name']} (ID: {folder['id']})")
    else:
        print(f"   Error: {response.text}")


def test_health_check():
    """Test health check endpoint"""
    url = f"{BASE_URL}/api/simple-files/health"
    response = requests.get(url)
    print(f"✅ Health Check Response: {response.status_code}")
    if response.status_code == 200:
        health = response.json()
        print(f"   Status: {health['status']}")
        print(f"   Service: {health['service']}")
    else:
        print(f"   Error: {response.text}")


if __name__ == "__main__":
    print("🧪 Testing Simple File Upload API")
    print("=" * 50)

    # Test health check first (no auth required)
    test_health_check()
    print()

    if FIREBASE_TOKEN == "YOUR_FIREBASE_TOKEN_HERE":
        print(
            "⚠️  Please set FIREBASE_TOKEN in this script to test authenticated endpoints"
        )
    else:
        # Test authenticated endpoints
        print("📁 Testing Folder Operations:")
        test_list_folders()
        print()

        folder_id = test_create_folder()
        print()

        print("📄 Testing File Operations:")

        # Upload file to specific folder
        file_data = test_upload_file(folder_id)
        file_id = file_data["id"] if file_data else None
        print()

        # Upload file to root folder
        root_file_data = test_upload_file(None)
        root_file_id = root_file_data["id"] if root_file_data else None
        print()

        # List files in specific folder
        test_list_files_in_folder(folder_id)
        print()

        # List files in root folder
        test_list_files_in_folder(None)
        print()

        # List all files
        test_list_all_files()
        print()

        # Get specific file details
        if file_id:
            test_get_file(file_id)
            print()

        # Test delete file
        if root_file_id:
            print("🗑️ Testing File Deletion:")
            test_delete_file(root_file_id)
            print()

        # Verify deletion by listing files again
        print("📋 Verifying deletion:")
        test_list_all_files()

    print("🎉 Testing completed!")
