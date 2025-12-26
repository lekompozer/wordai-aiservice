# Slide Outline & Version Management Guide

## 📋 Overview

Hệ thống quản lý **outline** và **version** cho slide documents, cho phép user:
- Xem/Thêm/Sửa/Xóa outline của slides
- Render lại slides với AI từ outline đã chỉnh sửa
- Lưu nhiều version của cùng 1 document
- Chọn xem version nào của slide

---

## 🗂️ Data Structure

### Document Schema (MongoDB)

```javascript
{
  // Basic Info
  "document_id": "doc_abc123def456",
  "user_id": "17BeaeikPBQYk8OWeDUkqm0Ov8e2",
  "title": "Giới thiệu về AI",

  // Current Version (default version hiển thị)
  "version": 5,  // Tự động tăng mỗi khi save
  "content_html": "<div class='slide'>...</div>",  // HTML của version hiện tại
  "slides_outline": [  // Outline của version hiện tại
    {
      "slide_index": 0,
      "slide_type": "title",
      "title": "Giới thiệu về AI",
      "subtitle": "Công nghệ tạo nên tương lai"
    },
    {
      "slide_index": 1,
      "slide_type": "agenda",
      "title": "Nội dung chính",
      "bullets": ["Khái niệm AI", "Ứng dụng thực tế", "Tương lai"]
    },
    {
      "slide_index": 2,
      "slide_type": "content",
      "title": "Khái niệm AI",
      "bullets": [
        "AI là khả năng máy móc mô phỏng trí tuệ con người",
        "Bao gồm: Machine Learning, Deep Learning, NLP",
        "Ứng dụng rộng rãi trong nhiều lĩnh vực"
      ],
      "notes": "Giải thích đơn giản, dễ hiểu"
    }
  ],
  "slide_backgrounds": [  // Background của từng slide (version hiện tại)
    {"slide_index": 0, "background": "#0f172a", "theme": "dark"},
    {"slide_index": 1, "background": "#0f172a", "theme": "dark"}
  ],
  "slide_elements": [  // Overlay elements của từng slide (version hiện tại)
    {
      "slide_index": 2,
      "elements": [
        {"type": "image", "url": "https://...", "position": {...}},
        {"type": "text", "content": "Note", "position": {...}}
      ]
    }
  ],

  // Version History (NEW)
  "version_history": [
    {
      "version": 1,
      "created_at": ISODate("2025-12-26T10:00:00Z"),
      "description": "Initial AI generation",
      "content_html": "<div>...</div>",
      "slides_outline": [...],  // Outline của version 1
      "slide_backgrounds": [...],
      "slide_elements": [...],
      "slide_count": 28
    },
    {
      "version": 2,
      "created_at": ISODate("2025-12-26T11:30:00Z"),
      "description": "Regenerated after outline edit: Added more details to slide 3",
      "content_html": "<div>...</div>",
      "slides_outline": [...],  // Outline đã được edit
      "slide_backgrounds": [...],
      "slide_elements": [...],
      "slide_count": 30
    },
    {
      "version": 3,
      "created_at": ISODate("2025-12-26T12:00:00Z"),
      "description": "Manual edit: Fixed typo on slide 5",
      "content_html": "<div>...</div>",
      "slides_outline": [...],
      "slide_backgrounds": [...],
      "slide_elements": [...],
      "slide_count": 30
    }
  ],

  // Metadata
  "created_at": ISODate("2025-12-26T10:00:00Z"),
  "last_saved_at": ISODate("2025-12-26T12:00:00Z"),
  "is_deleted": false
}
```

### Outline Item Schema (Database Reality)

**⚠️ ACTUAL SCHEMA IN DATABASE:**
```javascript
{
  "slide_number": 1,           // Thứ tự slide (1-based, NOT 0-based)
  "title": "Slide Title",      // Tiêu đề chính
  "content_points": [           // Nội dung chính (array of strings)
    "First point with details",
    "Second point with examples",
    "Third point with statistics"
  ],
  "suggested_visuals": [        // Gợi ý visual elements
    "icon-list",
    "timeline",
    "graph"
  ],
  "image_suggestion": "Hình ảnh minh họa về AI và công nghệ",  // Mô tả ảnh gợi ý
  "estimated_duration": 120,    // Thời lượng ước tính (seconds)
  "image_url": null             // URL ảnh thực tế (nếu có)
}
```

**📝 Note:** Schema này được tạo bởi AI generation system và khác với schema ban đầu thiết kế. Frontend cần sử dụng đúng field names:
- `slide_number` (1-based) thay vì `slide_index` (0-based)
- `content_points` thay vì `bullets`
- Không có `slide_type`, `subtitle`, `notes`, `keywords` trong DB hiện tại

---

## 🔧 API Endpoints

### 1. Get Outline (Xem outline hiện tại)

```http
GET /api/slides/outline?document_id=doc_abc123&user_id=17Beaeik...
```

**Response:**
```json
{
  "success": true,
  "document_id": "doc_abc123def456",
  "version": 5,
  "slide_count": 30,
  "slides_outline": [
    {
      "slide_number": 1,
      "title": "Giới thiệu về AI",
      "content_points": [],
      "suggested_visuals": [],
      "image_suggestion": "",
      "estimated_duration": 60,
      "image_url": null
    },
    {
      "slide_number": 2,
      "title": "Khái niệm AI",
      "content_points": [
        "AI là khả năng máy móc mô phỏng trí tuệ con người",
        "Bao gồm: Machine Learning, Deep Learning, NLP"
      ],
      "suggested_visuals": ["icon-brain", "flowchart"],
      "image_suggestion": "Hình minh họa cấu trúc AI",
      "estimated_duration": 120,
      "image_url": null
    }
  ]
}
```

---

### 2. Update Outline (Sửa outline)

```http
PUT /api/slides/outline
Content-Type: application/json

{
  "document_id": "doc_abc123def456",
  "slides_outline": [
    {
      "slide_number": 1,
      "title": "NEW TITLE - Giới thiệu về GenAI",
      "content_points": [],
      "suggested_visuals": [],
      "image_suggestion": "",
      "estimated_duration": 60,
      "image_url": null
    },
    {
      "slide_number": 2,
      "title": "EDITED - Khái niệm GenAI",
      "content_points": [
        "EDITED - GenAI là gì?",
        "NEW BULLET - Phân biệt AI vs GenAI",
        "Ứng dụng thực tế"
      ],
      "suggested_visuals": ["comparison-chart", "examples"],
      "image_suggestion": "So sánh AI truyền thống và GenAI",
      "estimated_duration": 150,
      "image_url": null
    }
  ],
  "change_description": "Updated title and added GenAI distinction"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Outline updated successfully",
  "document_id": "doc_abc123def456",
  "updated_slides": 2,
  "can_regenerate": true
}
```

---

### 3. Add Slide to Outline (Thêm slide mới)

```http
POST /api/slides/outline/add
Content-Type: application/json

{
  "document_id": "doc_abc123def456",
  "insert_after_index": 5,
  "new_slide": {
    "slide_number": 6,
    "title": "Tương lai của AI",
    "content_points": [
      "AGI (Artificial General Intelligence)",
      "Ethical considerations",
      "Impact on jobs and society"
    ],
    "suggested_visuals": ["future-timeline", "ethics-diagram"],
    "image_suggestion": "Tầm nhìn tương lai AI và xã hội",
    "estimated_duration": 180,
    "image_url": null
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "Slide added successfully",
  "new_slide_index": 6,
  "total_slides": 31
}
```

---

### 4. Delete Slide from Outline (Xóa slide)

```http
DELETE /api/slides/outline/slide
Content-Type: application/json

{
  "document_id": "doc_abc123def456",
  "slide_index": 8,
  "reason": "Duplicate content with slide 3"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Slide 8 deleted from outline",
  "remaining_slides": 29
}
```

---

### 5. Regenerate from Outline (Tạo lại slides từ outline đã edit)

```http
POST /api/slides/regenerate
Content-Type: application/json

{
  "document_id": "doc_abc123def456",
  "regenerate_options": {
    "regenerate_all": false,  // true = tất cả, false = chỉ slides đã thay đổi
    "slide_indices": [1, 2, 5],  // Nếu regenerate_all=false, specify slides nào
    "keep_backgrounds": true,    // Giữ background design hiện tại
    "keep_animations": false,    // Tạo animations mới
    "description": "Regenerated after adding GenAI details"
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "Slide regeneration queued",
  "job_id": "regen_xyz789",
  "estimated_time_seconds": 120,
  "slides_to_regenerate": 3,
  "points_cost": 5,
  "will_create_new_version": true,
  "new_version": 6
}
```

---

### 6. Get Version History (Xem lịch sử versions)

```http
GET /api/slides/versions?document_id=doc_abc123&user_id=17Beaeik...
```

**Response:**
```json
{
  "success": true,
  "document_id": "doc_abc123def456",
  "current_version": 5,
  "total_versions": 5,
  "versions": [
    {
      "version": 5,
      "created_at": "2025-12-26T12:00:00Z",
      "description": "Manual edit: Fixed typo on slide 5",
      "slide_count": 30,
      "is_current": true,
      "thumbnail_url": "https://..."
    },
    {
      "version": 4,
      "created_at": "2025-12-26T11:45:00Z",
      "description": "Regenerated slides 1-3 after outline edit",
      "slide_count": 30,
      "is_current": false,
      "thumbnail_url": "https://..."
    },
    {
      "version": 3,
      "created_at": "2025-12-26T11:30:00Z",
      "description": "Added new slide about AI ethics",
      "slide_count": 29,
      "is_current": false,
      "thumbnail_url": "https://..."
    }
  ]
}
```

---

### 7. Switch to Version (Chuyển sang version khác)

```http
POST /api/slides/versions/switch
Content-Type: application/json

{
  "document_id": "doc_abc123def456",
  "user_id": "17Beaeik...",
  "target_version": 3
}
```

**Response:**
```json
{
  "success": true,
  "message": "Switched to version 3",
  "document_id": "doc_abc123def456",
  "current_version": 3,
  "slide_count": 29,
  "switched_at": "2025-12-26T13:00:00Z"
}
```

---

## 💾 Implementation Details

### Database Operations

#### 1. Save New Version (When regenerating or major edit)

```python
def save_new_version(
    document_id: str,
    user_id: str,
    content_html: str,
    slides_outline: list,
    slide_backgrounds: list,
    slide_elements: list,
    description: str
):
    """Save current state as new version in history"""

    # Get current document
    doc = db.documents.find_one({
        "document_id": document_id,
        "user_id": user_id
    })

    # Create version snapshot
    new_version = {
        "version": doc["version"] + 1,
        "created_at": datetime.utcnow(),
        "description": description,
        "content_html": content_html,
        "slides_outline": slides_outline,
        "slide_backgrounds": slide_backgrounds,
        "slide_elements": slide_elements,
        "slide_count": len(slides_outline)
    }

    # Update document
    db.documents.update_one(
        {"document_id": document_id},
        {
            "$set": {
                "version": new_version["version"],
                "content_html": content_html,
                "slides_outline": slides_outline,
                "slide_backgrounds": slide_backgrounds,
                "slide_elements": slide_elements,
                "last_saved_at": datetime.utcnow()
            },
            "$push": {
                "version_history": new_version
            }
        }
    )

    logger.info(f"✅ Saved version {new_version['version']} for {document_id}")
    return new_version["version"]
```

#### 2. Restore Version (Switch to older version)

```python
def restore_version(
    document_id: str,
    user_id: str,
    target_version: int
):
    """Restore document to a specific version"""

    doc = db.documents.find_one({
        "document_id": document_id,
        "user_id": user_id
    })

    # Find target version in history
    target = None
    for v in doc.get("version_history", []):
        if v["version"] == target_version:
            target = v
            break

    if not target:
        raise ValueError(f"Version {target_version} not found")

    # Restore to current
    db.documents.update_one(
        {"document_id": document_id},
        {
            "$set": {
                "version": target["version"],
                "content_html": target["content_html"],
                "slides_outline": target["slides_outline"],
                "slide_backgrounds": target["slide_backgrounds"],
                "slide_elements": target["slide_elements"],
                "last_saved_at": datetime.utcnow()
            }
        }
    )

    logger.info(f"✅ Restored {document_id} to version {target_version}")
```

---

## 🎯 Use Cases

### Use Case 1: Edit Outline & Regenerate Specific Slides

```
User workflow:
1. GET /api/slides/outline → Lấy outline hiện tại
2. Chỉnh sửa outline cho slides 2, 3, 5 (thêm bullets, sửa title)
3. PUT /api/slides/outline → Update outline
4. POST /api/slides/regenerate với slide_indices=[2,3,5]
   → Hệ thống gọi Claude để regenerate chỉ 3 slides này (5 points)
   → Tạo version mới (version 6)
5. Frontend tự động reload và hiển thị version 6
```

**Points Cost:** 5 points (1 chunk, 3 slides)

---

### Use Case 2: Add New Slide & Regenerate

```
User workflow:
1. Muốn thêm slide về "AI Ethics" sau slide 8
2. POST /api/slides/outline/add với insert_after_index=8
3. POST /api/slides/regenerate với slide_indices=[9] (slide mới)
   → Hệ thống generate slide 9 từ outline
   → Tạo version mới
4. User xem version mới
```

**Points Cost:** 5 points (1 chunk, 1 slide)

---

### Use Case 3: View History & Restore

```
User workflow:
1. Đã regenerate nhưng không thích version mới
2. GET /api/slides/versions → Xem lịch sử tất cả versions
3. Chọn version cũ muốn restore (ví dụ version 4)
4. POST /api/slides/versions/switch với target_version=4
   → Restore về version cũ (FREE - không tốn points)
5. User tiếp tục chỉnh sửa từ version 4
```

**Points Cost:** 0 points (switching là free)

---

## 🔐 Permissions & Access Control

### Edit Outline
- ✅ User phải là owner của document
- ✅ Document không bị deleted
- ✅ Không cần points để edit outline (chỉ save outline)

### Regenerate Slides
- ✅ User phải có đủ points (5 points/chunk)
- ✅ Check permissions trước khi enqueue
- ✅ Deduct points TRƯỚC khi gọi AI

### View Versions
- ✅ User phải là owner
- ✅ Free - không tốn points

### Switch Versions
- ✅ User phải là owner
- ✅ Free - không tốn points
- ✅ Có thể switch unlimited

---



---

## 🧪 Testing Checklist

- [ ] Get outline for existing document
- [ ] Update outline (edit titles, bullets)
- [ ] Add new slide to outline
- [ ] Delete slide from outline
- [ ] Regenerate all slides from edited outline
- [ ] Regenerate specific slides only
- [ ] Get version history
- [ ] Switch to older version
- [ ] Points deduction for regeneration
- [ ] Permission checks (only owner can edit)
- [ ] Error handling for invalid version
- [ ] Concurrent editing prevention

---

## 📝 Migration Plan

### Phase 1: Add Version Support to Existing Documents
```python
# Migration script
def migrate_add_version_history():
    """Add version_history field to all slide documents"""

    documents = db.documents.find({
        "document_type": "slide",
        "version_history": {"$exists": False}
    })

    for doc in documents:
        # Create initial version from current state
        initial_version = {
            "version": doc.get("version", 1),
            "created_at": doc.get("created_at", datetime.utcnow()),
            "description": "Initial version (migrated)",
            "content_html": doc.get("content_html", ""),
            "slides_outline": doc.get("slides_outline", []),
            "slide_backgrounds": doc.get("slide_backgrounds", []),
            "slide_elements": doc.get("slide_elements", []),
            "slide_count": len(doc.get("slides_outline", []))
        }

        db.documents.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "version_history": [initial_version]
                }
            }
        )

    logger.info("✅ Migration completed: Added version_history")
```

### Phase 2: Implement API Endpoints
- Create routes in `src/api/slide_outline_routes.py`
- Add services in `src/services/slide_outline_service.py`
- Update DocumentManager with version methods

### Phase 3: Frontend Integration
- Outline editor UI
- Version switcher component
- Regeneration job status polling

---

## 🎯 Summary

### Key Features
✅ **Outline Management**: CRUD operations on slide outlines
✅ **Selective Regeneration**: Regenerate specific slides only (save points)
✅ **Version Control**: Keep history of all changes
✅ **Version Switching**: Restore to any previous version (free)
✅ **Cost Optimization**: 5 points per chunk (max 10 slides/chunk)

### Benefits
- User có full control over slide content via outline
- Không mất version cũ khi regenerate
- Dễ dàng rollback nếu không thích version mới
- Tiết kiệm points bằng cách regenerate chỉ slides cần thiết

### Implementation Priority
1. **HIGH**: Get/Update outline endpoints
2. **HIGH**: Regenerate from outline with version save
3. **MEDIUM**: Version history & switching
4. **LOW**: Version comparison
