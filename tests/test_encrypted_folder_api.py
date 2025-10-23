"""
Test Encrypted Library Folders API
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
def mock_folder_manager():
    """Mock EncryptedFolderManager"""
    with patch("src.api.encrypted_folder_routes.get_folder_manager") as mock_get:
        mock_manager = MagicMock()
        mock_get.return_value = mock_manager
        yield mock_manager


def test_create_folder(mock_firebase_auth, mock_folder_manager):
    """Test create folder"""
    # Mock response
    mock_folder_manager.create_folder.return_value = {
        "folder_id": "folder_abc123",
        "owner_id": MOCK_USER_ID,
        "name": "My Secret Photos",
        "description": "Personal photos",
        "parent_folder_id": None,
        "path": [],
        "created_at": "2025-10-23T10:00:00Z",
        "updated_at": "2025-10-23T10:00:00Z",
        "deleted_at": None,
        "is_deleted": False,
    }
    
    response = client.post(
        "/api/library/encrypted-folders/",
        headers={"Authorization": f"Bearer {MOCK_TOKEN}"},
        json={
            "name": "My Secret Photos",
            "description": "Personal photos",
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["folder_id"] == "folder_abc123"
    assert data["name"] == "My Secret Photos"
    assert data["owner_id"] == MOCK_USER_ID


def test_create_subfolder(mock_firebase_auth, mock_folder_manager):
    """Test create subfolder"""
    mock_folder_manager.create_folder.return_value = {
        "folder_id": "folder_xyz456",
        "owner_id": MOCK_USER_ID,
        "name": "Vacation 2025",
        "description": None,
        "parent_folder_id": "folder_abc123",
        "path": ["folder_abc123"],
        "created_at": "2025-10-23T10:05:00Z",
        "updated_at": "2025-10-23T10:05:00Z",
        "deleted_at": None,
        "is_deleted": False,
    }
    
    response = client.post(
        "/api/library/encrypted-folders/",
        headers={"Authorization": f"Bearer {MOCK_TOKEN}"},
        json={
            "name": "Vacation 2025",
            "parent_folder_id": "folder_abc123",
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["folder_id"] == "folder_xyz456"
    assert data["parent_folder_id"] == "folder_abc123"
    assert data["path"] == ["folder_abc123"]


def test_list_folders(mock_firebase_auth, mock_folder_manager):
    """Test list folders"""
    mock_folder_manager.list_folders.return_value = [
        {
            "folder_id": "folder_abc123",
            "owner_id": MOCK_USER_ID,
            "name": "My Secret Photos",
            "description": "Personal photos",
            "parent_folder_id": None,
            "path": [],
            "created_at": "2025-10-23T10:00:00Z",
            "updated_at": "2025-10-23T10:00:00Z",
            "deleted_at": None,
            "is_deleted": False,
        },
        {
            "folder_id": "folder_def789",
            "owner_id": MOCK_USER_ID,
            "name": "Work Documents",
            "description": None,
            "parent_folder_id": None,
            "path": [],
            "created_at": "2025-10-23T11:00:00Z",
            "updated_at": "2025-10-23T11:00:00Z",
            "deleted_at": None,
            "is_deleted": False,
        }
    ]
    
    response = client.get(
        "/api/library/encrypted-folders/",
        headers={"Authorization": f"Bearer {MOCK_TOKEN}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["folder_id"] == "folder_abc123"
    assert data[1]["folder_id"] == "folder_def789"


def test_get_folder(mock_firebase_auth, mock_folder_manager):
    """Test get folder by ID"""
    mock_folder_manager.get_folder.return_value = {
        "folder_id": "folder_abc123",
        "owner_id": MOCK_USER_ID,
        "name": "My Secret Photos",
        "description": "Personal photos",
        "parent_folder_id": None,
        "path": [],
        "created_at": "2025-10-23T10:00:00Z",
        "updated_at": "2025-10-23T10:00:00Z",
        "deleted_at": None,
        "is_deleted": False,
    }
    
    response = client.get(
        "/api/library/encrypted-folders/folder_abc123",
        headers={"Authorization": f"Bearer {MOCK_TOKEN}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["folder_id"] == "folder_abc123"
    assert data["name"] == "My Secret Photos"


def test_update_folder(mock_firebase_auth, mock_folder_manager):
    """Test update folder metadata"""
    mock_folder_manager.update_folder.return_value = {
        "folder_id": "folder_abc123",
        "owner_id": MOCK_USER_ID,
        "name": "Updated Folder Name",
        "description": "Updated description",
        "parent_folder_id": None,
        "path": [],
        "created_at": "2025-10-23T10:00:00Z",
        "updated_at": "2025-10-23T12:00:00Z",
        "deleted_at": None,
        "is_deleted": False,
    }
    
    response = client.put(
        "/api/library/encrypted-folders/folder_abc123",
        headers={"Authorization": f"Bearer {MOCK_TOKEN}"},
        json={
            "name": "Updated Folder Name",
            "description": "Updated description",
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Folder Name"
    assert data["description"] == "Updated description"


def test_move_folder(mock_firebase_auth, mock_folder_manager):
    """Test move folder to different parent"""
    mock_folder_manager.update_folder.return_value = {
        "folder_id": "folder_xyz456",
        "owner_id": MOCK_USER_ID,
        "name": "Vacation 2025",
        "description": None,
        "parent_folder_id": "folder_new_parent",
        "path": ["folder_new_parent"],
        "created_at": "2025-10-23T10:05:00Z",
        "updated_at": "2025-10-23T12:30:00Z",
        "deleted_at": None,
        "is_deleted": False,
    }
    
    response = client.put(
        "/api/library/encrypted-folders/folder_xyz456",
        headers={"Authorization": f"Bearer {MOCK_TOKEN}"},
        json={
            "parent_folder_id": "folder_new_parent",
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["parent_folder_id"] == "folder_new_parent"
    assert data["path"] == ["folder_new_parent"]


def test_soft_delete_folder(mock_firebase_auth, mock_folder_manager):
    """Test soft delete folder"""
    mock_folder_manager.soft_delete_folder.return_value = True
    
    response = client.delete(
        "/api/library/encrypted-folders/folder_abc123",
        headers={"Authorization": f"Bearer {MOCK_TOKEN}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["message"] == "Folder moved to trash"


def test_permanent_delete_folder(mock_firebase_auth, mock_folder_manager):
    """Test permanent delete folder"""
    mock_folder_manager.delete_folder_permanent.return_value = True
    
    response = client.delete(
        "/api/library/encrypted-folders/folder_abc123?permanent=true",
        headers={"Authorization": f"Bearer {MOCK_TOKEN}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["message"] == "Folder permanently deleted"


def test_restore_folder(mock_firebase_auth, mock_folder_manager):
    """Test restore folder from trash"""
    mock_folder_manager.restore_folder.return_value = True
    
    response = client.post(
        "/api/library/encrypted-folders/folder_abc123/restore",
        headers={"Authorization": f"Bearer {MOCK_TOKEN}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["message"] == "Folder restored from trash"


def test_folder_not_found(mock_firebase_auth, mock_folder_manager):
    """Test folder not found error"""
    mock_folder_manager.get_folder.return_value = None
    
    response = client.get(
        "/api/library/encrypted-folders/nonexistent",
        headers={"Authorization": f"Bearer {MOCK_TOKEN}"}
    )
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_create_folder_without_name(mock_firebase_auth, mock_folder_manager):
    """Test create folder without name (validation error)"""
    response = client.post(
        "/api/library/encrypted-folders/",
        headers={"Authorization": f"Bearer {MOCK_TOKEN}"},
        json={}
    )
    
    assert response.status_code == 422  # Validation error
