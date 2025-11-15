# Phase 3: Chapter Management API

**Status:** In Progress
**Phase:** 3/6
**Target:** Create REST API endpoints for Guide Chapter CRUD operations with tree structure support

---

## 📋 Overview

Phase 3 implements the API endpoints for managing chapters within User Guides. These endpoints handle:
- Creating nested chapters with parent-child relationships
- Retrieving chapter tree structure (max 3 levels)
- Updating chapter content and metadata
- Deleting chapters (with recursive deletion of children)
- Bulk reordering chapters via drag-and-drop

---

## 🎯 API Endpoints

### 1. Create Chapter
**Endpoint:** `POST /api/v1/guides/{guide_id}/chapters`
**Authentication:** Required (Firebase JWT)
**Purpose:** Add a new chapter to a guide

**Request Body:**
```json
{
  "title": "Introduction",
  "slug": "introduction",
  "document_id": "doc_xyz123",
  "parent_id": null,
  "order_index": 0,
  "is_published": true
}
```

**Response:** `201 Created`
```json
{
  "chapter_id": "chapter_abc123",
  "guide_id": "guide_xyz789",
  "title": "Introduction",
  "slug": "introduction",
  "document_id": "doc_xyz123",
  "parent_id": null,
  "depth": 0,
  "order_index": 0,
  "is_published": true,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Validation:**
- `slug`: Must be unique within guide, alphanumeric with hyphens
- `parent_id`: Must exist in same guide if provided
- `depth`: Max 3 levels (0, 1, 2) - validated automatically
- `document_id`: Must exist in `documents` collection
- Only guide owner can create chapters

**Error Handling:**
- `403 Forbidden`: User is not guide owner
- `404 Not Found`: Guide or parent chapter doesn't exist
- `400 Bad Request`: Max depth exceeded (>2)
- `409 Conflict`: Duplicate slug within guide

---

### 2. Get Chapter Tree
**Endpoint:** `GET /api/v1/guides/{guide_id}/chapters`
**Authentication:** Required
**Purpose:** Retrieve hierarchical tree structure of all chapters

**Query Parameters:**
- `include_unpublished`: Include unpublished chapters (default: false, owner: true)

**Request:**
```
GET /api/v1/guides/guide_xyz789/chapters?include_unpublished=true
```

**Response:** `200 OK`
```json
{
  "guide_id": "guide_xyz789",
  "chapters": [
    {
      "chapter_id": "chapter_001",
      "title": "Getting Started",
      "slug": "getting-started",
      "document_id": "doc_001",
      "depth": 0,
      "order_index": 0,
      "is_published": true,
      "children": [
        {
          "chapter_id": "chapter_002",
          "title": "Installation",
          "slug": "installation",
          "document_id": "doc_002",
          "depth": 1,
          "order_index": 0,
          "is_published": true,
          "children": [
            {
              "chapter_id": "chapter_003",
              "title": "Prerequisites",
              "slug": "prerequisites",
              "document_id": "doc_003",
              "depth": 2,
              "order_index": 0,
              "is_published": true,
              "children": []
            }
          ]
        }
      ]
    }
  ],
  "total_chapters": 3
}
```

**Tree Structure Rules:**
- Max 3 levels: Level 0 (root), Level 1 (sub-chapter), Level 2 (sub-sub-chapter)
- Ordered by `order_index` at each level
- Unpublished chapters hidden for non-owners unless `include_unpublished=true`

---

### 3. Update Chapter
**Endpoint:** `PATCH /api/v1/guides/{guide_id}/chapters/{chapter_id}`
**Authentication:** Required
**Purpose:** Update chapter metadata or move to different parent

**Request Body:**
```json
{
  "title": "Updated Title",
  "parent_id": "chapter_new_parent",
  "order_index": 2,
  "is_published": false
}
```

**Response:** `200 OK`
```json
{
  "chapter_id": "chapter_abc123",
  "title": "Updated Title",
  "parent_id": "chapter_new_parent",
  "depth": 1,
  "order_index": 2,
  "is_published": false,
  "updated_at": "2024-01-15T11:00:00Z"
}
```

**Validation:**
- Moving chapter recalculates `depth` and validates max 3 levels
- Cannot move chapter to its own descendant (circular reference check)
- Slug changes must maintain uniqueness within guide
- Only guide owner can update chapters

**Error Handling:**
- `400 Bad Request`: Circular reference or max depth exceeded
- `403 Forbidden`: User is not guide owner
- `404 Not Found`: Chapter doesn't exist
- `409 Conflict`: Duplicate slug

---

### 4. Delete Chapter
**Endpoint:** `DELETE /api/v1/guides/{guide_id}/chapters/{chapter_id}`
**Authentication:** Required
**Purpose:** Delete chapter and all child chapters recursively

**Request:**
```
DELETE /api/v1/guides/guide_xyz789/chapters/chapter_abc123
```

**Response:** `200 OK`
```json
{
  "deleted_chapter_id": "chapter_abc123",
  "deleted_children_count": 3,
  "deleted_chapter_ids": [
    "chapter_abc123",
    "chapter_child1",
    "chapter_child2",
    "chapter_grandchild1"
  ]
}
```

**Cascade Deletion:**
1. Find all descendant chapters recursively
2. Delete all descendants from database
3. Delete the target chapter
4. Return list of deleted chapter IDs

**Error Handling:**
- `403 Forbidden`: User is not guide owner
- `404 Not Found`: Chapter doesn't exist

---

### 5. Bulk Reorder Chapters
**Endpoint:** `POST /api/v1/guides/{guide_id}/chapters/reorder`
**Authentication:** Required
**Purpose:** Update order_index and parent_id for multiple chapters (drag-and-drop support)

**Request Body:**
```json
{
  "updates": [
    {
      "chapter_id": "chapter_001",
      "parent_id": null,
      "order_index": 0
    },
    {
      "chapter_id": "chapter_002",
      "parent_id": "chapter_001",
      "order_index": 0
    },
    {
      "chapter_id": "chapter_003",
      "parent_id": null,
      "order_index": 1
    }
  ]
}
```

**Response:** `200 OK`
```json
{
  "updated_count": 3,
  "chapters": [
    {
      "chapter_id": "chapter_001",
      "parent_id": null,
      "depth": 0,
      "order_index": 0
    },
    {
      "chapter_id": "chapter_002",
      "parent_id": "chapter_001",
      "depth": 1,
      "order_index": 0
    },
    {
      "chapter_id": "chapter_003",
      "parent_id": null,
      "depth": 0,
      "order_index": 1
    }
  ]
}
```

**Validation:**
- All chapter_ids must exist in the guide
- Validates max depth for each chapter after reordering
- Prevents circular references
- Only guide owner can reorder

**Error Handling:**
- `400 Bad Request`: Invalid chapter IDs, circular reference, or max depth exceeded
- `403 Forbidden`: User is not guide owner

---

## 🔒 Authorization Rules

| Endpoint | Rule |
|----------|------|
| Create Chapter | Guide owner only |
| Get Chapter Tree | Owner OR has viewer/editor permission |
| Update Chapter | Guide owner only |
| Delete Chapter | Guide owner only |
| Reorder Chapters | Guide owner only |

---

## 🛠️ Implementation Details

### File Structure
```
src/api/user_guide_routes.py  (same file as Phase 2)
```

### Dependencies
- **FastAPI:** Router, HTTPException, Depends
- **Services:** GuideChapterManager, UserGuideManager
- **Models:** ChapterCreate, ChapterUpdate, ChapterResponse, ChapterTreeNode, ChapterReorderBulk
- **Auth:** get_current_user (Firebase JWT verification)

### Example Route Implementation
```python
@router.post("/{guide_id}/chapters", response_model=ChapterResponse, status_code=status.HTTP_201_CREATED)
async def create_chapter(
    guide_id: str,
    chapter_data: ChapterCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new chapter in a guide"""
    user_id = current_user["uid"]

    # Verify guide ownership
    guide = await guide_manager.get_guide(guide_id)
    if not guide or guide["user_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only guide owner can create chapters"
        )

    # Check slug uniqueness
    if await chapter_manager.slug_exists(guide_id, chapter_data.slug):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Slug '{chapter_data.slug}' already exists in this guide"
        )

    # Create chapter (depth is auto-calculated)
    chapter = await chapter_manager.create_chapter(guide_id, chapter_data)
    return chapter
```

---

## 📊 Tree Structure Example

```
📘 Getting Started Guide (guide_xyz789)
├─ 📄 Introduction (depth: 0, order: 0)
├─ 📄 Installation (depth: 0, order: 1)
│  ├─ 📄 Prerequisites (depth: 1, order: 0)
│  │  └─ 📄 System Requirements (depth: 2, order: 0)
│  └─ 📄 Setup Steps (depth: 1, order: 1)
└─ 📄 Configuration (depth: 0, order: 2)
   └─ 📄 Environment Variables (depth: 1, order: 0)
```

**Database Representation:**
```json
[
  {"chapter_id": "c1", "parent_id": null, "depth": 0, "order_index": 0, "title": "Introduction"},
  {"chapter_id": "c2", "parent_id": null, "depth": 0, "order_index": 1, "title": "Installation"},
  {"chapter_id": "c3", "parent_id": "c2", "depth": 1, "order_index": 0, "title": "Prerequisites"},
  {"chapter_id": "c4", "parent_id": "c3", "depth": 2, "order_index": 0, "title": "System Requirements"},
  {"chapter_id": "c5", "parent_id": "c2", "depth": 1, "order_index": 1, "title": "Setup Steps"},
  {"chapter_id": "c6", "parent_id": null, "depth": 0, "order_index": 2, "title": "Configuration"},
  {"chapter_id": "c7", "parent_id": "c6", "depth": 1, "order_index": 0, "title": "Environment Variables"}
]
```

---

## ✅ Acceptance Criteria

- [ ] All 5 endpoints implemented with correct HTTP methods
- [ ] Tree structure correctly builds from flat database records
- [ ] Max depth validation (3 levels) enforced
- [ ] Circular reference prevention implemented
- [ ] Cascade deletion removes all child chapters
- [ ] Bulk reorder updates multiple chapters atomically
- [ ] Unpublished chapters hidden from non-owners
- [ ] Authorization checks enforce ownership rules
- [ ] API integrated into serve.py main router

---

## 🧪 Testing Checklist

**Create Chapter:**
- [ ] Creates root chapter (depth 0)
- [ ] Creates nested chapter with parent (depth 1, 2)
- [ ] Rejects chapter exceeding max depth (depth 3)
- [ ] Validates slug uniqueness within guide
- [ ] Returns 403 for non-owner

**Get Chapter Tree:**
- [ ] Returns correctly nested tree structure
- [ ] Respects order_index at each level
- [ ] Hides unpublished chapters for non-owners
- [ ] Shows unpublished chapters for owner

**Update Chapter:**
- [ ] Updates title, slug, is_published
- [ ] Moves chapter to different parent
- [ ] Recalculates depth on parent change
- [ ] Prevents circular references
- [ ] Returns 400 if max depth exceeded

**Delete Chapter:**
- [ ] Deletes single chapter without children
- [ ] Recursively deletes all child chapters
- [ ] Returns correct deleted_count
- [ ] Returns 404 for non-existent chapter

**Bulk Reorder:**
- [ ] Updates multiple chapters simultaneously
- [ ] Recalculates depth for all affected chapters
- [ ] Prevents circular references
- [ ] Validates max depth for all chapters
- [ ] Returns updated chapter list

---

## 📊 Success Metrics

| Metric | Target |
|--------|--------|
| Endpoints Implemented | 5/5 |
| Test Coverage | >95% |
| Tree Build Performance | <50ms for 100 chapters |
| Cascade Delete | All children removed |

---

**Previous Phase:** [Phase 2 - Guide Management API](PHASE2_GUIDE_MANAGEMENT_API.md)
**Next Phase:** Phase 4 - User Permissions System
