# StudyHub Permission System Analysis

## Tổng quan

StudyHub có **2 chế độ permission** hoàn toàn riêng biệt:
1. **Private Mode** - Subject đang ở trạng thái draft/private
2. **Marketplace Mode** - Subject đã publish lên marketplace công khai

---

## 1. Content Types trong Module

Mỗi Module có **5 loại content tabs**:

### 1.1. Documents (Tài liệu)
**Source**: My Edited Files (A4/Slides/Notes từ hệ thống hiện tại)

**Collections liên quan**:
- `online_documents` - Documents người dùng tạo
- `document_slides` - A4-style documents
- `document_notes` - Note-taking documents

**Permission fields hiện tại**:
```javascript
{
  owner_id: ObjectId,
  is_public: Boolean,  // ❌ KHÔNG dùng cho StudyHub
  visibility: String   // ❌ KHÔNG dùng cho StudyHub
}
```

**Permission fields MỚI cần thêm**:
```javascript
{
  studyhub_access: {
    enabled: Boolean,           // true nếu document được dùng trong StudyHub
    subject_id: ObjectId,       // Subject chứa document này
    module_id: ObjectId,        // Module chứa document này
    requires_enrollment: Boolean, // true nếu cần enrollment để access
    is_preview: Boolean         // true nếu là preview (free access)
  }
}
```

### 1.2. Tests (Bài kiểm tra)
**Source**: My Tests (từ hệ thống test hiện tại)

**Collections liên quan**:
- `online_tests` - Tests người dùng tạo
- `test_questions` - Questions trong test
- `test_results` - Kết quả làm bài

**Permission fields MỚI**:
```javascript
{
  studyhub_access: {
    enabled: Boolean,
    subject_id: ObjectId,
    module_id: ObjectId,
    requires_enrollment: Boolean,
    is_preview: Boolean,
    passing_score: Number       // Điểm tối thiểu để pass
  }
}
```

### 1.3. Books (Sách)
**Source**: My Books (Community Books hiện tại)

**Collections liên quan**:
- `online_books` - Books người dùng tạo
- `book_chapters` - Chapters trong book

**Permission fields MỚI**:
```javascript
{
  studyhub_access: {
    enabled: Boolean,
    subject_id: ObjectId,
    module_id: ObjectId,
    requires_enrollment: Boolean,
    selected_chapters: [ObjectId], // Chỉ những chapters này được access
    is_preview: Boolean
  }
}
```

### 1.4. Files (Upload Files)
**Source**: User uploaded files (PDFs, docs, etc.)

**Collections MỚI**:
- `studyhub_files` - Uploaded files cho StudyHub

**Schema**:
```javascript
{
  _id: ObjectId,
  owner_id: ObjectId,
  subject_id: ObjectId,
  module_id: ObjectId,
  file_name: String,
  file_url: String,
  file_type: String,        // "pdf", "doc", "ppt", etc.
  file_size: Number,        // bytes
  uploaded_at: DateTime,
  studyhub_access: {
    requires_enrollment: Boolean,
    is_preview: Boolean
  }
}
```

### 1.5. Results (Kết quả học tập)
**Auto-generated** - Không phải content type, là tracking data

**Collections**:
- `studyhub_learning_progress` (đã có)
- `studyhub_content_views` (mới)

**Schema cho content_views**:
```javascript
{
  _id: ObjectId,
  user_id: ObjectId,
  subject_id: ObjectId,
  module_id: ObjectId,
  content_id: ObjectId,
  content_type: String,     // "document", "test", "book", "file"
  viewed_at: DateTime,
  completed: Boolean,
  time_spent_seconds: Number,

  // Specific to content type
  test_score: Number,       // Nếu là test
  test_passed: Boolean,
  slides_viewed: [Number],  // Nếu là slides
  last_position: Object     // Last reading position
}
```

---

## 2. Permission Rules

### 2.1. PRIVATE MODE (Subject chưa publish)

**Quy tắc**:
- ✅ **Owner**: Full access - CRUD tất cả content
- ❌ **Others**: No access

**APIs cho Owner**:
```
POST   /api/studyhub/modules/{module_id}/content/documents
POST   /api/studyhub/modules/{module_id}/content/tests
POST   /api/studyhub/modules/{module_id}/content/books
POST   /api/studyhub/modules/{module_id}/content/files

GET    /api/studyhub/modules/{module_id}/content
PUT    /api/studyhub/content/{content_id}
DELETE /api/studyhub/content/{content_id}
```

**Permission Check**:
```python
async def check_owner_permission(user_id: str, subject_id: str):
    subject = await db.studyhub_subjects.find_one({
        "_id": ObjectId(subject_id),
        "owner_id": user_id
    })
    if not subject:
        raise HTTPException(403, "Only subject owner can modify content")
    return True
```

### 2.2. MARKETPLACE MODE (Subject đã publish)

**Quy tắc**:
- ✅ **Owner**: Full access (vẫn CRUD được)
- ✅ **Enrolled Users**: Read access (đã enroll + payment)
- ✅ **Preview**: Limited access (content có `is_preview=true`)
- ❌ **Others**: No access

**Permission Check Flow**:
```python
async def check_content_access(user_id: str, content_id: str):
    # 1. Get content
    content = await db.studyhub_module_contents.find_one({"_id": ObjectId(content_id)})

    # 2. Check if owner
    subject = await get_subject_from_content(content)
    if subject["owner_id"] == user_id:
        return True  # Owner always has access

    # 3. Check if preview
    if content.get("is_preview", False):
        return True  # Preview content is free

    # 4. Check enrollment
    enrollment = await db.studyhub_enrollments.find_one({
        "user_id": user_id,
        "subject_id": subject["_id"],
        "status": "active"
    })

    if not enrollment:
        raise HTTPException(403, "Enrollment required to access this content")

    return True
```

---

## 3. Enrollment & Payment System

### 3.1. Subject Pricing

**Collection**: `studyhub_subject_pricing`
```javascript
{
  _id: ObjectId,
  subject_id: ObjectId,
  is_free: Boolean,
  price_points: Number,       // Giá bằng points
  price_usd: Number,          // Hoặc USD (optional)

  // Discount
  discount_percentage: Number,
  discount_valid_until: DateTime,

  created_at: DateTime,
  updated_at: DateTime
}
```

### 3.2. Enrollment Process

**Flow**:
1. User browse marketplace → see subject
2. Click "Enroll" → Check pricing
3. If `is_free=true` → Enroll immediately
4. If `is_free=false` → Show payment dialog
5. User pays with points → Create purchase record
6. Create enrollment with `status=active`

**APIs**:
```
GET  /api/studyhub/marketplace/subjects/{subject_id}/pricing
POST /api/studyhub/subjects/{subject_id}/enroll
     Body: { payment_method: "points" | "usd" }
```

### 3.3. Access Check Middleware

```python
async def require_enrollment(
    subject_id: str,
    user_id: str,
    allow_preview: bool = False
):
    """
    Middleware to check enrollment access
    - Owner: Always allowed
    - Preview content: Allowed if allow_preview=True
    - Others: Must have active enrollment
    """
    # Check owner
    subject = await db.studyhub_subjects.find_one({"_id": ObjectId(subject_id)})
    if subject["owner_id"] == user_id:
        return True

    # Check if subject is public marketplace
    if not subject.get("is_public_marketplace", False):
        raise HTTPException(404, "Subject not found")

    # Check enrollment
    enrollment = await db.studyhub_enrollments.find_one({
        "user_id": user_id,
        "subject_id": ObjectId(subject_id),
        "status": "active"
    })

    if not enrollment:
        # Check if preview is allowed
        if allow_preview:
            return "preview_only"
        raise HTTPException(403, "Enrollment required. Please purchase this subject.")

    return True
```

---

## 4. Content Permission Type

### 4.1. Tránh conflict với permission hiện tại

**QUAN TRỌNG**: Documents/Books/Tests hiện có field `is_public`, `visibility` cho hệ thống cũ.

**Giải pháp**: Tạo permission type MỚI hoàn toàn riêng biệt

```python
class PermissionContext(Enum):
    PUBLIC = "public"              # Public bình thường (hệ thống cũ)
    STUDYHUB_PRIVATE = "studyhub_private"   # StudyHub private mode
    STUDYHUB_MARKETPLACE = "studyhub_marketplace"  # StudyHub marketplace

# Khi check permission
def check_access(user_id, content_id, context):
    content = get_content(content_id)

    if context == "PUBLIC":
        # Check old system permission
        return content.get("is_public", False)

    elif context == "STUDYHUB_PRIVATE":
        # Check owner only
        subject = get_subject_from_content(content)
        return subject["owner_id"] == user_id

    elif context == "STUDYHUB_MARKETPLACE":
        # Check enrollment
        return check_enrollment_access(user_id, content)
```

### 4.2. Database Schema Update

**Add to existing collections** (`online_documents`, `online_tests`, `online_books`):
```javascript
{
  // ... existing fields ...

  // OLD permission (keep unchanged)
  is_public: Boolean,
  visibility: String,

  // NEW StudyHub permission
  studyhub_context: {
    enabled: Boolean,           // true nếu content này dùng cho StudyHub
    mode: String,               // "private" | "marketplace"
    subject_id: ObjectId,
    module_id: ObjectId,
    requires_enrollment: Boolean,
    is_preview: Boolean,

    // Access control
    allowed_users: [ObjectId],  // Danh sách users được access (nếu có)
    restricted_until: DateTime  // Thời hạn restrict (optional)
  }
}
```

---

## 5. API Endpoints cho Content Management

### 5.1. Document Content APIs

```
POST   /api/studyhub/modules/{module_id}/content/documents
       Body: {
         document_id: "...",           // ID từ online_documents
         title: "Document Title",
         is_required: true/false,
         is_preview: true/false
       }
       → Link document vào module
       → Set studyhub_context.enabled = true

GET    /api/studyhub/modules/{module_id}/content/documents
       → List all documents in module
       → Check permission

PUT    /api/studyhub/content/documents/{content_id}
       Body: { title?, is_required?, is_preview? }
       → Update content settings

DELETE /api/studyhub/content/documents/{content_id}
       → Remove document from module
       → Set studyhub_context.enabled = false (unlink)
```

### 5.2. Test Content APIs

```
POST   /api/studyhub/modules/{module_id}/content/tests
       Body: {
         test_id: "...",
         title: "Test Title",
         passing_score: 70,
         is_required: true,
         is_preview: false
       }

GET    /api/studyhub/modules/{module_id}/content/tests

PUT    /api/studyhub/content/tests/{content_id}

DELETE /api/studyhub/content/tests/{content_id}
```

### 5.3. Book Content APIs

```
POST   /api/studyhub/modules/{module_id}/content/books
       Body: {
         book_id: "...",
         title: "Book Title",
         selected_chapters: ["chapter1", "chapter2"],  // Optional
         is_required: true,
         is_preview: false
       }

GET    /api/studyhub/modules/{module_id}/content/books

PUT    /api/studyhub/content/books/{content_id}

DELETE /api/studyhub/content/books/{content_id}
```

### 5.4. File Content APIs

```
POST   /api/studyhub/modules/{module_id}/content/files
       Body: FormData with file
       → Upload file to S3/R2
       → Create record in studyhub_files

GET    /api/studyhub/modules/{module_id}/content/files

DELETE /api/studyhub/content/files/{content_id}
       → Delete from S3
       → Delete record
```

### 5.5. Results APIs (Read-only)

```
GET    /api/studyhub/subjects/{subject_id}/results
       → Owner xem tất cả learners' results
       → Learner xem results của chính mình

GET    /api/studyhub/modules/{module_id}/results
       → Results for specific module

GET    /api/studyhub/content/{content_id}/results
       → Results for specific content (e.g., test scores)
```

---

## 6. Implementation Plan

### Phase 1: Core Permission System
- [ ] Add `studyhub_context` field to existing collections
- [ ] Create `studyhub_files` collection
- [ ] Create `studyhub_content_views` collection
- [ ] Implement `check_enrollment_access()` middleware
- [ ] Implement `require_enrollment` decorator

### Phase 2: Content APIs
- [ ] Implement Document content APIs (5 endpoints)
- [ ] Implement Test content APIs (5 endpoints)
- [ ] Implement Book content APIs (5 endpoints)
- [ ] Implement File content APIs (4 endpoints)

### Phase 3: Results & Analytics
- [ ] Implement Results APIs (3 endpoints)
- [ ] Content view tracking
- [ ] Test score tracking
- [ ] Progress analytics

### Phase 4: Pricing & Payment
- [ ] Subject pricing management
- [ ] Points-based enrollment
- [ ] Purchase history
- [ ] Revenue tracking

---

## 7. Migration Strategy

### 7.1. Existing Data
**Không ảnh hưởng** đến documents/books/tests hiện tại:
- `is_public` và `visibility` vẫn hoạt động bình thường
- Chỉ khi add vào StudyHub mới set `studyhub_context.enabled = true`

### 7.2. When Subject Published to Marketplace
```python
async def publish_subject_to_marketplace(subject_id: str):
    # 1. Update subject
    await db.studyhub_subjects.update_one(
        {"_id": ObjectId(subject_id)},
        {"$set": {
            "is_public_marketplace": True,
            "status": "published"
        }}
    )

    # 2. Update all content in subject
    modules = await db.studyhub_modules.find({"subject_id": ObjectId(subject_id)}).to_list()

    for module in modules:
        contents = await db.studyhub_module_contents.find({
            "module_id": module["_id"]
        }).to_list()

        for content in contents:
            # Update original content (document/test/book)
            collection_name = get_collection_name(content["content_type"])
            ref_id = content["data"].get(f"{content['content_type']}_id")

            await db[collection_name].update_one(
                {"_id": ObjectId(ref_id)},
                {"$set": {
                    "studyhub_context.mode": "marketplace",
                    "studyhub_context.requires_enrollment": not content.get("is_preview", False)
                }}
            )
```

---

## 8. Security Considerations

### 8.1. Content Access Validation
```python
# ALWAYS validate enrollment before returning content
@router.get("/content/{content_id}/view")
async def view_content(content_id: str, user: dict = Depends(get_current_user)):
    content = await get_content(content_id)
    subject = await get_subject_from_content(content)

    # Check access
    has_access = await check_enrollment_access(user["uid"], subject["_id"])

    if has_access == "preview_only" and not content.get("is_preview"):
        raise HTTPException(403, "Full enrollment required")

    # Track view
    await track_content_view(user["uid"], content_id)

    return content
```

### 8.2. Prevent Leaks
- ❌ NEVER return full content data to unenrolled users
- ✅ Return preview/metadata only
- ✅ Validate enrollment on every protected endpoint
- ✅ Log access attempts for audit

---

## 9. Summary

| Content Type | Source | Permission Check | APIs Count |
|--------------|--------|------------------|------------|
| Documents | `online_documents` | Enrollment + Preview | 5 |
| Tests | `online_tests` | Enrollment + Preview | 5 |
| Books | `online_books` | Enrollment + Chapters | 5 |
| Files | `studyhub_files` (new) | Enrollment + Preview | 4 |
| Results | `studyhub_content_views` (new) | Owner or Self | 3 |

**Total New APIs**: 22 endpoints

**Permission Modes**:
1. Private: Owner only
2. Marketplace: Enrollment-based (với preview exceptions)

**Key Points**:
- Tách biệt hoàn toàn permission cũ (`is_public`) và mới (`studyhub_context`)
- Enrollment = Payment (points) + Access rights
- Preview content = Marketing tool (free access)
- Results = Auto-tracked learning analytics

---

**Document Version**: 1.0
**Created**: January 9, 2026
**Purpose**: Permission system design cho StudyHub content management
