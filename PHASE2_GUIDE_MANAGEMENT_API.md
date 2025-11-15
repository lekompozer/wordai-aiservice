# Phase 2: Guide Management API

**Status:** In Progress
**Phase:** 2/6
**Target:** Create REST API endpoints for User Guide CRUD operations

---

## 📋 Overview

Phase 2 implements the core API endpoints for managing User Guides. These endpoints allow users to:
- Create new guides with customizable settings
- List their guides with pagination and filtering
- Retrieve detailed guide information
- Update guide metadata (title, description, visibility, etc.)
- Delete guides (with cascade deletion of chapters and permissions)

---

## 🎯 API Endpoints

### 1. Create Guide
**Endpoint:** `POST /api/v1/guides`
**Authentication:** Required (Firebase JWT)
**Purpose:** Create a new User Guide

**Request Body:**
```json
{
  "title": "Getting Started Guide",
  "slug": "getting-started",
  "description": "Learn how to use our platform",
  "visibility": "public",
  "icon": "📘",
  "color": "#3B82F6",
  "enable_toc": true,
  "enable_search": true,
  "enable_feedback": true
}
```

**Response:** `201 Created`
```json
{
  "guide_id": "guide_abc123def456",
  "user_id": "user_xyz789",
  "title": "Getting Started Guide",
  "slug": "getting-started",
  "visibility": "public",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

**Validation:**
- `slug`: Must be unique per user, alphanumeric with hyphens only
- `title`: 1-200 characters
- `description`: Optional, max 1000 characters
- `visibility`: Must be one of ["public", "private", "unlisted"]
- `color`: Must be valid hex color format

---

### 2. List User's Guides
**Endpoint:** `GET /api/v1/guides`
**Authentication:** Required
**Purpose:** Retrieve paginated list of user's guides

**Query Parameters:**
- `skip`: Pagination offset (default: 0)
- `limit`: Results per page (default: 20, max: 100)
- `visibility`: Filter by visibility type (optional)

**Request:**
```
GET /api/v1/guides?skip=0&limit=10&visibility=public
```

**Response:** `200 OK`
```json
{
  "guides": [
    {
      "guide_id": "guide_abc123",
      "title": "Getting Started Guide",
      "slug": "getting-started",
      "visibility": "public",
      "chapter_count": 5,
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 1,
  "skip": 0,
  "limit": 10
}
```

---

### 3. Get Guide Details
**Endpoint:** `GET /api/v1/guides/{guide_id}`
**Authentication:** Required
**Purpose:** Retrieve detailed information about a specific guide

**Request:**
```
GET /api/v1/guides/guide_abc123def456
```

**Response:** `200 OK`
```json
{
  "guide_id": "guide_abc123def456",
  "user_id": "user_xyz789",
  "title": "Getting Started Guide",
  "slug": "getting-started",
  "description": "Learn how to use our platform",
  "visibility": "public",
  "icon": "📘",
  "color": "#3B82F6",
  "enable_toc": true,
  "enable_search": true,
  "enable_feedback": true,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

**Error Handling:**
- `404 Not Found`: Guide doesn't exist or user doesn't have access
- `403 Forbidden`: User is not the guide owner

---

### 4. Update Guide
**Endpoint:** `PATCH /api/v1/guides/{guide_id}`
**Authentication:** Required
**Purpose:** Update guide metadata (partial update supported)

**Request Body:**
```json
{
  "title": "Updated Guide Title",
  "description": "New description",
  "visibility": "private",
  "color": "#10B981"
}
```

**Response:** `200 OK`
```json
{
  "guide_id": "guide_abc123def456",
  "title": "Updated Guide Title",
  "description": "New description",
  "visibility": "private",
  "updated_at": "2024-01-15T11:00:00Z"
}
```

**Validation:**
- Only guide owner can update
- Cannot update `guide_id`, `user_id`, or `created_at`
- Slug changes must maintain uniqueness

---

### 5. Delete Guide
**Endpoint:** `DELETE /api/v1/guides/{guide_id}`
**Authentication:** Required
**Purpose:** Delete guide and all associated chapters and permissions

**Request:**
```
DELETE /api/v1/guides/guide_abc123def456
```

**Response:** `204 No Content`

**Cascade Deletion:**
1. Delete all chapters in `guide_chapters` collection
2. Delete all permissions in `guide_permissions` collection
3. Delete guide document from `user_guides` collection

**Error Handling:**
- `404 Not Found`: Guide doesn't exist
- `403 Forbidden`: User is not the guide owner

---

## 🔒 Authorization Rules

| Endpoint | Rule |
|----------|------|
| Create Guide | Any authenticated user |
| List Guides | Only user's own guides |
| Get Guide | Owner OR has viewer/editor permission |
| Update Guide | Owner only |
| Delete Guide | Owner only |

---

## 🛠️ Implementation Details

### File Structure
```
src/api/user_guide_routes.py
```

### Dependencies
- **FastAPI:** Router, HTTPException, Depends
- **Services:** UserGuideManager, GuideChapterManager, GuidePermissionManager
- **Models:** GuideCreate, GuideUpdate, GuideResponse
- **Auth:** get_current_user (Firebase JWT verification)

### Example Route Implementation
```python
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

router = APIRouter(prefix="/api/v1/guides", tags=["User Guides"])

@router.post("", response_model=GuideResponse, status_code=status.HTTP_201_CREATED)
async def create_guide(
    guide_data: GuideCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new User Guide"""
    user_id = current_user["uid"]

    # Check slug uniqueness
    if await guide_manager.slug_exists(user_id, guide_data.slug):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Slug '{guide_data.slug}' already exists"
        )

    # Create guide
    guide = await guide_manager.create_guide(user_id, guide_data)
    return guide
```

---

## ✅ Acceptance Criteria

- [ ] All 5 endpoints implemented with correct HTTP methods
- [ ] Request/response models use Pydantic validation
- [ ] Authentication required for all endpoints
- [ ] Authorization checks enforce ownership rules
- [ ] Slug uniqueness validated on create/update
- [ ] Cascade deletion removes chapters and permissions
- [ ] Pagination works correctly for list endpoint
- [ ] Error responses follow standard format
- [ ] API integrated into serve.py main router

---

## 🧪 Testing Checklist

**Create Guide:**
- [ ] Successfully creates guide with valid data
- [ ] Rejects duplicate slug for same user
- [ ] Validates required fields
- [ ] Rejects invalid color format
- [ ] Returns 401 without authentication

**List Guides:**
- [ ] Returns only user's guides
- [ ] Pagination works correctly
- [ ] Visibility filter works
- [ ] Returns empty list for new user

**Get Guide:**
- [ ] Returns guide details for owner
- [ ] Returns 404 for non-existent guide
- [ ] Returns 403 for unauthorized user

**Update Guide:**
- [ ] Updates allowed fields successfully
- [ ] Maintains slug uniqueness on update
- [ ] Returns 403 for non-owner
- [ ] Updates `updated_at` timestamp

**Delete Guide:**
- [ ] Deletes guide successfully
- [ ] Cascade deletes all chapters
- [ ] Cascade deletes all permissions
- [ ] Returns 404 for non-existent guide
- [ ] Returns 403 for non-owner

---

## 📊 Success Metrics

| Metric | Target |
|--------|--------|
| Endpoints Implemented | 5/5 |
| Test Coverage | >95% |
| Response Time | <100ms (p95) |
| Error Handling | All edge cases covered |

---

**Next Phase:** [Phase 3 - Chapter Management API](PHASE3_CHAPTER_MANAGEMENT_API.md)
