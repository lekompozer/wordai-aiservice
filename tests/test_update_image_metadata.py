"""
Test Update Image Metadata API
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from src.app import app

client = TestClient(app)

# Mock Firebase token
MOCK_USER_ID = "test_user_123"
MOCK_TOKEN = "mock_firebase_token"


@pytest.fixture
def mock_firebase_auth():
    """Mock Firebase authentication"""
    with patch("src.middleware.auth.verify_firebase_token") as mock_verify:
        mock_verify.return_value = {"uid": MOCK_USER_ID}
        yield mock_verify


@pytest.fixture
def mock_library_manager():
    """Mock EncryptedLibraryManager"""
    with patch("src.api.encrypted_library_routes.get_encrypted_library_manager") as mock_get:
        mock_manager = MagicMock()
        mock_get.return_value = mock_manager
        yield mock_manager


def test_update_image_filename(mock_firebase_auth, mock_library_manager):
    """Test update image filename"""
    mock_library_manager.update_image_metadata.return_value = {
        "image_id": "img_abc123",
        "owner_id": MOCK_USER_ID,
        "filename": "new_vacation_photo.jpg",
        "description": "Summer vacation",
        "file_size": 1234567,
        "tags": ["vacation", "beach"],
        "folder_id": None,
        "is_encrypted": True,
        "encrypted_file_keys": {MOCK_USER_ID: "encrypted_key"},
        "encryption_iv_original": "iv_12_bytes",
        "encryption_iv_thumbnail": "iv_thumb_12_bytes",
        "encryption_iv_exif": None,
        "encrypted_exif": None,
        "image_width": 1920,
        "image_height": 1080,
        "thumbnail_width": 300,
        "thumbnail_height": 200,
        "r2_image_path": "encrypted-library/test_user_123/abc123.jpg.enc",
        "r2_thumbnail_path": "encrypted-library/test_user_123/abc123_thumb.jpg.enc",
        "shared_with": [],
        "created_at": "2025-10-23T10:00:00Z",
        "updated_at": "2025-10-23T12:00:00Z",
        "deleted_at": None,
        "is_deleted": False,
    }
    
    response = client.put(
        "/api/library/encrypted-images/img_abc123/metadata",
        headers={"Authorization": f"Bearer {MOCK_TOKEN}"},
        json={
            "filename": "new_vacation_photo.jpg"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "new_vacation_photo.jpg"
    assert data["image_id"] == "img_abc123"


def test_update_image_description(mock_firebase_auth, mock_library_manager):
    """Test update image description"""
    mock_library_manager.update_image_metadata.return_value = {
        "image_id": "img_abc123",
        "owner_id": MOCK_USER_ID,
        "filename": "vacation.jpg",
        "description": "Updated: Beautiful sunset at the beach",
        "file_size": 1234567,
        "tags": ["vacation", "beach"],
        "folder_id": None,
        "is_encrypted": True,
        "encrypted_file_keys": {MOCK_USER_ID: "encrypted_key"},
        "encryption_iv_original": "iv_12_bytes",
        "encryption_iv_thumbnail": "iv_thumb_12_bytes",
        "encryption_iv_exif": None,
        "encrypted_exif": None,
        "image_width": 1920,
        "image_height": 1080,
        "thumbnail_width": 300,
        "thumbnail_height": 200,
        "r2_image_path": "encrypted-library/test_user_123/abc123.jpg.enc",
        "r2_thumbnail_path": "encrypted-library/test_user_123/abc123_thumb.jpg.enc",
        "shared_with": [],
        "created_at": "2025-10-23T10:00:00Z",
        "updated_at": "2025-10-23T12:05:00Z",
        "deleted_at": None,
        "is_deleted": False,
    }
    
    response = client.put(
        "/api/library/encrypted-images/img_abc123/metadata",
        headers={"Authorization": f"Bearer {MOCK_TOKEN}"},
        json={
            "description": "Updated: Beautiful sunset at the beach"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["description"] == "Updated: Beautiful sunset at the beach"


def test_update_image_tags(mock_firebase_auth, mock_library_manager):
    """Test update image tags"""
    mock_library_manager.update_image_metadata.return_value = {
        "image_id": "img_abc123",
        "owner_id": MOCK_USER_ID,
        "filename": "vacation.jpg",
        "description": "Summer vacation",
        "file_size": 1234567,
        "tags": ["vacation", "beach", "2025", "family"],
        "folder_id": None,
        "is_encrypted": True,
        "encrypted_file_keys": {MOCK_USER_ID: "encrypted_key"},
        "encryption_iv_original": "iv_12_bytes",
        "encryption_iv_thumbnail": "iv_thumb_12_bytes",
        "encryption_iv_exif": None,
        "encrypted_exif": None,
        "image_width": 1920,
        "image_height": 1080,
        "thumbnail_width": 300,
        "thumbnail_height": 200,
        "r2_image_path": "encrypted-library/test_user_123/abc123.jpg.enc",
        "r2_thumbnail_path": "encrypted-library/test_user_123/abc123_thumb.jpg.enc",
        "shared_with": [],
        "created_at": "2025-10-23T10:00:00Z",
        "updated_at": "2025-10-23T12:10:00Z",
        "deleted_at": None,
        "is_deleted": False,
    }
    
    response = client.put(
        "/api/library/encrypted-images/img_abc123/metadata",
        headers={"Authorization": f"Bearer {MOCK_TOKEN}"},
        json={
            "tags": ["vacation", "beach", "2025", "family"]
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["tags"]) == 4
    assert "family" in data["tags"]


def test_move_image_to_folder(mock_firebase_auth, mock_library_manager):
    """Test move image to folder"""
    mock_library_manager.update_image_metadata.return_value = {
        "image_id": "img_abc123",
        "owner_id": MOCK_USER_ID,
        "filename": "vacation.jpg",
        "description": "Summer vacation",
        "file_size": 1234567,
        "tags": ["vacation", "beach"],
        "folder_id": "folder_xyz456",
        "is_encrypted": True,
        "encrypted_file_keys": {MOCK_USER_ID: "encrypted_key"},
        "encryption_iv_original": "iv_12_bytes",
        "encryption_iv_thumbnail": "iv_thumb_12_bytes",
        "encryption_iv_exif": None,
        "encrypted_exif": None,
        "image_width": 1920,
        "image_height": 1080,
        "thumbnail_width": 300,
        "thumbnail_height": 200,
        "r2_image_path": "encrypted-library/test_user_123/abc123.jpg.enc",
        "r2_thumbnail_path": "encrypted-library/test_user_123/abc123_thumb.jpg.enc",
        "shared_with": [],
        "created_at": "2025-10-23T10:00:00Z",
        "updated_at": "2025-10-23T12:15:00Z",
        "deleted_at": None,
        "is_deleted": False,
    }
    
    response = client.put(
        "/api/library/encrypted-images/img_abc123/metadata",
        headers={"Authorization": f"Bearer {MOCK_TOKEN}"},
        json={
            "folder_id": "folder_xyz456"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["folder_id"] == "folder_xyz456"


def test_update_multiple_fields(mock_firebase_auth, mock_library_manager):
    """Test update multiple metadata fields at once"""
    mock_library_manager.update_image_metadata.return_value = {
        "image_id": "img_abc123",
        "owner_id": MOCK_USER_ID,
        "filename": "renamed_photo.jpg",
        "description": "New description",
        "file_size": 1234567,
        "tags": ["new", "tags"],
        "folder_id": "folder_new",
        "is_encrypted": True,
        "encrypted_file_keys": {MOCK_USER_ID: "encrypted_key"},
        "encryption_iv_original": "iv_12_bytes",
        "encryption_iv_thumbnail": "iv_thumb_12_bytes",
        "encryption_iv_exif": None,
        "encrypted_exif": None,
        "image_width": 1920,
        "image_height": 1080,
        "thumbnail_width": 300,
        "thumbnail_height": 200,
        "r2_image_path": "encrypted-library/test_user_123/abc123.jpg.enc",
        "r2_thumbnail_path": "encrypted-library/test_user_123/abc123_thumb.jpg.enc",
        "shared_with": [],
        "created_at": "2025-10-23T10:00:00Z",
        "updated_at": "2025-10-23T12:20:00Z",
        "deleted_at": None,
        "is_deleted": False,
    }
    
    response = client.put(
        "/api/library/encrypted-images/img_abc123/metadata",
        headers={"Authorization": f"Bearer {MOCK_TOKEN}"},
        json={
            "filename": "renamed_photo.jpg",
            "description": "New description",
            "tags": ["new", "tags"],
            "folder_id": "folder_new"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "renamed_photo.jpg"
    assert data["description"] == "New description"
    assert data["tags"] == ["new", "tags"]
    assert data["folder_id"] == "folder_new"


def test_update_no_fields(mock_firebase_auth, mock_library_manager):
    """Test update with no fields (should return 400)"""
    response = client.put(
        "/api/library/encrypted-images/img_abc123/metadata",
        headers={"Authorization": f"Bearer {MOCK_TOKEN}"},
        json={}
    )
    
    assert response.status_code == 400
    assert "No updates provided" in response.json()["detail"]


def test_update_image_not_found(mock_firebase_auth, mock_library_manager):
    """Test update non-existent image"""
    mock_library_manager.update_image_metadata.return_value = None
    
    response = client.put(
        "/api/library/encrypted-images/nonexistent/metadata",
        headers={"Authorization": f"Bearer {MOCK_TOKEN}"},
        json={
            "filename": "newname.jpg"
        }
    )
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_update_not_owner(mock_firebase_auth, mock_library_manager):
    """Test update image not owned by user"""
    mock_library_manager.update_image_metadata.return_value = None
    
    response = client.put(
        "/api/library/encrypted-images/img_abc123/metadata",
        headers={"Authorization": f"Bearer {MOCK_TOKEN}"},
        json={
            "filename": "newname.jpg"
        }
    )
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
