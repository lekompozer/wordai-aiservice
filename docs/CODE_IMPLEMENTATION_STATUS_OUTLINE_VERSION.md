# Code Implementation Status - Slide Outline & Version Management

## ✅ Đã có sẵn (Current State)

### 1. DocumentManager - Basic CRUD
**File:** `src/services/document_manager.py`

✅ **Có sẵn:**
- `create_document()` - Tạo document mới
- `get_document()` - Lấy document theo ID
- `update_document()` - Update content, title, slide_elements, slide_backgrounds, **slides_outline**
- `list_user_documents()` - List documents của user

✅ **Slides Outline đã được save:**
```python
# Line 215 trong document_manager.py
slides_outline: Optional[list] = None  # NEW: Save outline for retry

# Line 265-269
if slides_outline is not None:
    update_data["slides_outline"] = slides_outline
    logger.info(
        f"📝 [SLIDES_OUTLINE_SAVE] Preparing to save: document_id={document_id}, "
        f"user_id={user_id}, outline_count={len(slides_outline)}"
    )
```

✅ **Version tracking cơ bản:**
```python
# Line 136, 279 - Version counter (auto increment)
"version": 1,
# Mỗi lần update tăng version lên 1
```

---

## ❌ Chưa có (Need to Implement)

### 1. Version History Storage
❌ **Thiếu field `version_history`** trong document schema
❌ **Chưa save snapshot** của mỗi version khi update

**Cần thêm vào DocumentManager:**

```python
def save_version_snapshot(
    self,
    document_id: str,
    user_id: str,
    description: str = "Version snapshot"
) -> int:
    """
    Save current document state as a version in history
    Returns: new version number
    """
    # Get current document
    doc = self.documents.find_one({
        "document_id": document_id,
        "user_id": user_id,
        "is_deleted": False
    })

    if not doc:
        raise ValueError(f"Document {document_id} not found")

    # Create version snapshot
    version_snapshot = {
        "version": doc.get("version", 1),
        "created_at": datetime.utcnow(),
        "description": description,
        "content_html": doc.get("content_html", ""),
        "slides_outline": doc.get("slides_outline", []),
        "slide_backgrounds": doc.get("slide_backgrounds", []),
        "slide_elements": doc.get("slide_elements", []),
        "slide_count": len(doc.get("slides_outline", []))
    }

    # Increment version and save snapshot
    new_version = doc.get("version", 1) + 1

    self.documents.update_one(
        {"document_id": document_id},
        {
            "$set": {"version": new_version},
            "$push": {"version_history": version_snapshot}
        }
    )

    logger.info(
        f"📸 Saved version {version_snapshot['version']} snapshot "
        f"for {document_id} (new version: {new_version})"
    )

    return new_version
```

---

### 2. Version Restore
❌ **Chưa có method restore về version cũ**

**Cần thêm:**

```python
def restore_version(
    self,
    document_id: str,
    user_id: str,
    target_version: int
) -> bool:
    """
    Restore document to a specific version from history
    """
    doc = self.documents.find_one({
        "document_id": document_id,
        "user_id": user_id,
        "is_deleted": False
    })

    if not doc:
        raise ValueError(f"Document {document_id} not found")

    # Find target version in history
    target_snapshot = None
    for v in doc.get("version_history", []):
        if v["version"] == target_version:
            target_snapshot = v
            break

    if not target_snapshot:
        raise ValueError(f"Version {target_version} not found in history")

    # Restore to current
    self.documents.update_one(
        {"document_id": document_id},
        {
            "$set": {
                "version": target_snapshot["version"],
                "content_html": target_snapshot["content_html"],
                "slides_outline": target_snapshot["slides_outline"],
                "slide_backgrounds": target_snapshot["slide_backgrounds"],
                "slide_elements": target_snapshot["slide_elements"],
                "last_saved_at": datetime.utcnow()
            }
        }
    )

    logger.info(
        f"⏮️ Restored {document_id} to version {target_version} "
        f"({target_snapshot['slide_count']} slides)"
    )

    return True


def get_version_history(
    self,
    document_id: str,
    user_id: str
) -> list:
    """Get all version history for a document"""
    doc = self.documents.find_one({
        "document_id": document_id,
        "user_id": user_id,
        "is_deleted": False
    })

    if not doc:
        return []

    current_version = doc.get("version", 1)
    history = doc.get("version_history", [])

    # Mark current version
    for v in history:
        v["is_current"] = (v["version"] == current_version)

    # Sort by version descending (newest first)
    history.sort(key=lambda x: x["version"], reverse=True)

    return history
```

---

### 3. Outline Management API
❌ **Chưa có API routes cho outline CRUD**

**Cần tạo file:** `src/api/slide_outline_routes.py`

```python
"""
Slide Outline Management API
CRUD operations for slide outlines
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

router = APIRouter()

# ============ REQUEST MODELS ============

class OutlineSlideItem(BaseModel):
    """Single slide outline item"""
    slide_index: int
    slide_type: str = Field(..., description="title|agenda|content|thankyou")
    title: str
    subtitle: Optional[str] = None
    bullets: Optional[List[str]] = None
    notes: Optional[str] = None
    image_url: Optional[str] = None
    keywords: Optional[List[str]] = None


class UpdateOutlineRequest(BaseModel):
    """Request to update full outline"""
    document_id: str
    user_id: str
    slides_outline: List[OutlineSlideItem]
    change_description: Optional[str] = "Manual outline update"


class AddSlideRequest(BaseModel):
    """Request to add a new slide to outline"""
    document_id: str
    user_id: str
    insert_after_index: int
    new_slide: OutlineSlideItem


class DeleteSlideRequest(BaseModel):
    """Request to delete a slide from outline"""
    document_id: str
    user_id: str
    slide_index: int
    reason: Optional[str] = None


class RegenerateOptions(BaseModel):
    """Options for regenerating slides"""
    regenerate_all: bool = False
    slide_indices: Optional[List[int]] = None
    keep_backgrounds: bool = True
    keep_animations: bool = False
    description: Optional[str] = "Regenerated from edited outline"


class RegenerateRequest(BaseModel):
    """Request to regenerate slides from outline"""
    document_id: str
    user_id: str
    regenerate_options: RegenerateOptions


# ============ ENDPOINTS ============

@router.get("/slides/outline")
async def get_outline(document_id: str, user_id: str):
    """Get current outline for a slide document"""
    from src.services.document_manager import DocumentManager
    from src.services.online_test_utils import get_mongodb_service

    mongo = get_mongodb_service()
    doc_manager = DocumentManager(mongo.db)

    doc = doc_manager.get_document(document_id, user_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    slides_outline = doc.get("slides_outline", [])

    return {
        "success": True,
        "document_id": document_id,
        "version": doc.get("version", 1),
        "slide_count": len(slides_outline),
        "slides_outline": slides_outline
    }


@router.put("/slides/outline")
async def update_outline(request: UpdateOutlineRequest):
    """Update outline for a slide document"""
    from src.services.document_manager import DocumentManager
    from src.services.online_test_utils import get_mongodb_service

    mongo = get_mongodb_service()
    doc_manager = DocumentManager(mongo.db)

    # Save current version to history BEFORE updating
    try:
        new_version = doc_manager.save_version_snapshot(
            document_id=request.document_id,
            user_id=request.user_id,
            description=f"Before outline edit: {request.change_description}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

    # Update outline
    success = doc_manager.update_document(
        document_id=request.document_id,
        user_id=request.user_id,
        content_html="",  # Keep existing HTML for now
        slides_outline=[s.dict() for s in request.slides_outline],
        is_auto_save=False
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update outline"
        )

    return {
        "success": True,
        "message": "Outline updated successfully",
        "document_id": request.document_id,
        "updated_slides": len(request.slides_outline),
        "new_version": new_version,
        "can_regenerate": True
    }


@router.post("/slides/outline/add")
async def add_slide_to_outline(request: AddSlideRequest):
    """Add a new slide to outline"""
    from src.services.document_manager import DocumentManager
    from src.services.online_test_utils import get_mongodb_service

    mongo = get_mongodb_service()
    doc_manager = DocumentManager(mongo.db)

    # Get current outline
    doc = doc_manager.get_document(request.document_id, request.user_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    current_outline = doc.get("slides_outline", [])

    # Insert new slide
    insert_position = request.insert_after_index + 1
    new_slide_dict = request.new_slide.dict()
    new_slide_dict["slide_index"] = insert_position

    # Reindex slides
    updated_outline = []
    for slide in current_outline:
        if slide["slide_index"] <= request.insert_after_index:
            updated_outline.append(slide)
        else:
            slide["slide_index"] += 1
            updated_outline.append(slide)

    updated_outline.insert(insert_position, new_slide_dict)

    # Save version snapshot
    doc_manager.save_version_snapshot(
        document_id=request.document_id,
        user_id=request.user_id,
        description=f"Before adding slide at position {insert_position}"
    )

    # Update document
    doc_manager.update_document(
        document_id=request.document_id,
        user_id=request.user_id,
        content_html="",
        slides_outline=updated_outline,
        is_auto_save=False
    )

    return {
        "success": True,
        "message": "Slide added successfully",
        "new_slide_index": insert_position,
        "total_slides": len(updated_outline)
    }


@router.delete("/slides/outline/slide")
async def delete_slide_from_outline(request: DeleteSlideRequest):
    """Delete a slide from outline"""
    from src.services.document_manager import DocumentManager
    from src.services.online_test_utils import get_mongodb_service

    mongo = get_mongodb_service()
    doc_manager = DocumentManager(mongo.db)

    # Get current outline
    doc = doc_manager.get_document(request.document_id, request.user_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    current_outline = doc.get("slides_outline", [])

    # Remove slide and reindex
    updated_outline = []
    for slide in current_outline:
        if slide["slide_index"] < request.slide_index:
            updated_outline.append(slide)
        elif slide["slide_index"] > request.slide_index:
            slide["slide_index"] -= 1
            updated_outline.append(slide)
        # Skip slide_index == request.slide_index (delete it)

    # Save version snapshot
    doc_manager.save_version_snapshot(
        document_id=request.document_id,
        user_id=request.user_id,
        description=f"Before deleting slide {request.slide_index}: {request.reason or 'No reason'}"
    )

    # Update document
    doc_manager.update_document(
        document_id=request.document_id,
        user_id=request.user_id,
        content_html="",
        slides_outline=updated_outline,
        is_auto_save=False
    )

    return {
        "success": True,
        "message": f"Slide {request.slide_index} deleted from outline",
        "remaining_slides": len(updated_outline)
    }
```

---

### 4. Version Management API
❌ **Chưa có API routes cho version history**

**Cần thêm vào:** `src/api/slide_outline_routes.py`

```python
@router.get("/slides/versions")
async def get_version_history(document_id: str, user_id: str):
    """Get version history for a document"""
    from src.services.document_manager import DocumentManager
    from src.services.online_test_utils import get_mongodb_service

    mongo = get_mongodb_service()
    doc_manager = DocumentManager(mongo.db)

    doc = doc_manager.get_document(document_id, user_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    history = doc_manager.get_version_history(document_id, user_id)
    current_version = doc.get("version", 1)

    return {
        "success": True,
        "document_id": document_id,
        "current_version": current_version,
        "total_versions": len(history),
        "versions": history
    }


class SwitchVersionRequest(BaseModel):
    document_id: str
    user_id: str
    target_version: int


@router.post("/slides/versions/switch")
async def switch_version(request: SwitchVersionRequest):
    """Switch to a different version"""
    from src.services.document_manager import DocumentManager
    from src.services.online_test_utils import get_mongodb_service

    mongo = get_mongodb_service()
    doc_manager = DocumentManager(mongo.db)

    try:
        doc_manager.restore_version(
            document_id=request.document_id,
            user_id=request.user_id,
            target_version=request.target_version
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

    # Get updated document
    doc = doc_manager.get_document(request.document_id, request.user_id)

    return {
        "success": True,
        "message": f"Switched to version {request.target_version}",
        "document_id": request.document_id,
        "current_version": doc.get("version"),
        "slide_count": len(doc.get("slides_outline", [])),
        "switched_at": datetime.utcnow().isoformat()
    }
```

---

### 5. Regenerate Integration
❌ **Chưa có endpoint `/slides/regenerate`**

**Cần tạo endpoint mới:**

```python
@router.post("/slides/regenerate")
async def regenerate_from_outline(request: RegenerateRequest):
    """
    Regenerate slides from edited outline
    Uses existing SlideGenerationWorker but with partial regeneration
    """
    from src.services.points_service import get_points_service
    from src.queue.queue_manager import QueueManager
    from src.models.ai_queue_tasks import SlideGenerationTask

    # Calculate points needed
    if request.regenerate_options.regenerate_all:
        # Get total slide count
        from src.services.document_manager import DocumentManager
        from src.services.online_test_utils import get_mongodb_service

        mongo = get_mongodb_service()
        doc_manager = DocumentManager(mongo.db)
        doc = doc_manager.get_document(request.document_id, request.user_id)

        num_slides = len(doc.get("slides_outline", []))
    else:
        num_slides = len(request.regenerate_options.slide_indices or [])

    # Calculate chunks (10 slides per chunk)
    num_chunks = (num_slides + 9) // 10
    points_cost = num_chunks * 5

    # Check points
    points_service = get_points_service()
    check = await points_service.check_sufficient_points(
        user_id=request.user_id,
        points_needed=points_cost,
        service="slide_regeneration"
    )

    if not check["has_points"]:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "INSUFFICIENT_POINTS",
                "message": f"Không đủ điểm để regenerate {num_slides} slide(s)",
                "points_needed": points_cost,
                "points_available": check["points_available"]
            }
        )

    # Save current version to history
    from src.services.document_manager import DocumentManager
    from src.services.online_test_utils import get_mongodb_service

    mongo = get_mongodb_service()
    doc_manager = DocumentManager(mongo.db)

    new_version = doc_manager.save_version_snapshot(
        document_id=request.document_id,
        user_id=request.user_id,
        description=f"Before regeneration: {request.regenerate_options.description}"
    )

    # Queue regeneration task (reuse existing slide_generation queue)
    # Note: Need to modify SlideGenerationWorker to support partial regeneration

    job_id = f"regen_{request.document_id}_{int(datetime.utcnow().timestamp())}"

    # For now, return success (implement worker logic separately)
    return {
        "success": True,
        "message": "Slide regeneration queued",
        "job_id": job_id,
        "estimated_time_seconds": num_chunks * 60,
        "slides_to_regenerate": num_slides,
        "points_cost": points_cost,
        "will_create_new_version": True,
        "new_version": new_version
    }
```

---

## 🔧 Migration Needed

### Add `version_history` to existing documents

**File:** `migrate_add_version_history.py`

```python
"""
Migration: Add version_history field to all slide documents
Run once to migrate existing documents
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(".env")

from src.services.online_test_utils import get_mongodb_service

def migrate_version_history():
    """Add version_history to all slide documents"""

    mongo = get_mongodb_service()
    db = mongo.db

    # Find all documents without version_history
    documents = db.documents.find({
        "version_history": {"$exists": False}
    })

    migrated_count = 0

    for doc in documents:
        # Create initial version from current state
        initial_version = {
            "version": doc.get("version", 1),
            "created_at": doc.get("created_at", datetime.utcnow()),
            "description": "Initial version (migrated from existing document)",
            "content_html": doc.get("content_html", ""),
            "slides_outline": doc.get("slides_outline", []),
            "slide_backgrounds": doc.get("slide_backgrounds", []),
            "slide_elements": doc.get("slide_elements", []),
            "slide_count": len(doc.get("slides_outline", []))
        }

        # Update document with version_history
        db.documents.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "version_history": [initial_version]
                }
            }
        )

        migrated_count += 1

        if migrated_count % 100 == 0:
            print(f"✅ Migrated {migrated_count} documents...")

    print(f"🎉 Migration completed: {migrated_count} documents updated with version_history")

if __name__ == "__main__":
    migrate_version_history()
```

---

## 📝 Implementation Checklist

### Phase 1: Core Version Management (HIGH PRIORITY)
- [ ] Add `save_version_snapshot()` to DocumentManager
- [ ] Add `restore_version()` to DocumentManager
- [ ] Add `get_version_history()` to DocumentManager
- [ ] Run migration script to add `version_history` to existing docs
- [ ] Test version save/restore locally

### Phase 2: Outline Management API (HIGH PRIORITY)
- [ ] Create `src/api/slide_outline_routes.py`
- [ ] Implement GET `/slides/outline`
- [ ] Implement PUT `/slides/outline`
- [ ] Implement POST `/slides/outline/add`
- [ ] Implement DELETE `/slides/outline/slide`
- [ ] Add routes to `app.py`
- [ ] Test outline CRUD operations

### Phase 3: Version Management API (MEDIUM PRIORITY)
- [ ] Implement GET `/slides/versions`
- [ ] Implement POST `/slides/versions/switch`
- [ ] Test version history & switching

### Phase 4: Regeneration (LOW PRIORITY - Complex)
- [ ] Implement POST `/slides/regenerate`
- [ ] Modify SlideGenerationWorker to support partial regeneration
- [ ] Handle selective slide indices
- [ ] Test regeneration with points deduction

---

## 🚀 Deployment Steps

1. **Add methods to DocumentManager**
   ```bash
   # Edit src/services/document_manager.py
   # Add: save_version_snapshot, restore_version, get_version_history
   ```

2. **Run migration**
   ```bash
   python migrate_add_version_history.py
   ```

3. **Create outline routes**
   ```bash
   # Create src/api/slide_outline_routes.py
   # Add routes to app.py
   ```

4. **Deploy**
   ```bash
   git add -A
   git commit -m "feat: Add slide outline & version management"
   git push origin main
   ./deploy-compose-with-rollback.sh
   ```

5. **Test in production**
   ```bash
   # Test outline CRUD
   # Test version switching
   # Verify points deduction for regeneration
   ```

---

## 🎯 Summary

**Đã có:**
- ✅ Basic document CRUD
- ✅ slides_outline field in database
- ✅ Version counter (auto increment)

**Cần implement:**
- ❌ version_history storage
- ❌ save_version_snapshot() method
- ❌ restore_version() method
- ❌ Outline CRUD API endpoints
- ❌ Version management API endpoints
- ❌ Regeneration endpoint
- ❌ Migration script

**Ưu tiên:**
1. DocumentManager methods (version snapshot/restore)
2. Migration script
3. Outline CRUD API
4. Version management API
5. Regeneration (có thể để sau)
