# 🗑️ Trash System Implementation Plan

## 📋 Overview

Implement soft delete / trash system for books with:
- Move to Trash (soft delete)
- View Trash
- Restore from Trash
- Empty Trash (permanent delete)

---

## 🏗️ Database Schema Changes

### Add to Book Collection

```python
{
  "is_deleted": False,           # Soft delete flag
  "deleted_at": None,            # Timestamp when moved to trash
  "deleted_by": None             # User who deleted (for audit)
}
```

### Migration Script Needed

```python
# Update all existing books
db.online_books.update_many(
    {"is_deleted": {"$exists": False}},
    {"$set": {
        "is_deleted": False,
        "deleted_at": None,
        "deleted_by": None
    }}
)
```

---

## 🔧 API Endpoints

### 1. **Soft Delete (Move to Trash)**

```
DELETE /api/v1/books/{book_id}?permanent=false
```

**Query Parameters:**
- `permanent`: boolean (default: false)
  - `false`: Soft delete (move to trash)
  - `true`: Hard delete (permanent)

**Response:**
```json
{
  "message": "Book moved to trash",
  "book_id": "book_xxx",
  "can_restore": true,
  "deleted_at": "2025-11-17T10:00:00Z"
}
```

---

### 2. **List Trash**

```
GET /api/v1/books/trash
```

**Query Parameters:**
- `page`: int (default: 1)
- `limit`: int (default: 20, max: 100)
- `sort_by`: string (default: "deleted_at")

**Response:**
```json
{
  "items": [
    {
      "book_id": "book_xxx",
      "title": "My Book",
      "slug": "my-book",
      "deleted_at": "2025-11-17T10:00:00Z",
      "deleted_by": "user_xxx",
      "chapters_count": 5,
      "can_restore": true
    }
  ],
  "total": 10,
  "page": 1,
  "limit": 20,
  "total_pages": 1
}
```

---

### 3. **Restore from Trash**

```
POST /api/v1/books/{book_id}/restore
```

**Response:**
```json
{
  "message": "Book restored successfully",
  "book_id": "book_xxx",
  "restored_at": "2025-11-17T10:30:00Z"
}
```

---

### 4. **Permanent Delete (Single)**

```
DELETE /api/v1/books/{book_id}?permanent=true
```

**Response:**
```json
{
  "message": "Book permanently deleted",
  "book_id": "book_xxx",
  "deleted_chapters": 5,
  "deleted_permissions": 3
}
```

---

### 5. **Empty Trash (Delete All)**

```
DELETE /api/v1/books/trash/empty
```

**Response:**
```json
{
  "message": "Trash emptied successfully",
  "deleted_books": 10,
  "deleted_chapters": 45,
  "deleted_permissions": 15
}
```

---

## 📝 Implementation Steps

### Step 1: Update Models

**File:** `src/models/book_models.py`

```python
class BookResponse(BaseModel):
    """Response model for book"""

    book_id: str
    user_id: str
    title: str
    slug: str
    description: Optional[str]
    visibility: BookVisibility
    is_published: bool

    # Trash fields
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[str] = None

    # ... other fields


class TrashBookItem(BaseModel):
    """Trash book item"""

    book_id: str
    title: str
    slug: str
    deleted_at: datetime
    deleted_by: str
    chapters_count: int
    can_restore: bool = True


class TrashListResponse(BaseModel):
    """Response for trash listing"""

    items: List[TrashBookItem]
    total: int
    page: int
    limit: int
    total_pages: int
```

### Step 2: Update BookManager

**File:** `src/services/book_manager.py`

```python
def soft_delete_book(self, book_id: str, user_id: str) -> Dict[str, Any]:
    """Move book to trash (soft delete)"""
    result = self.books_collection.update_one(
        {"book_id": book_id, "user_id": user_id},
        {
            "$set": {
                "is_deleted": True,
                "deleted_at": datetime.utcnow(),
                "deleted_by": user_id,
                "updated_at": datetime.utcnow()
            }
        }
    )
    return result.modified_count > 0


def list_trash(
    self,
    user_id: str,
    skip: int = 0,
    limit: int = 20,
    sort_by: str = "deleted_at"
) -> tuple[List[Dict], int]:
    """List books in trash"""
    query = {
        "user_id": user_id,
        "is_deleted": True
    }

    sort_field = [(sort_by, -1)]  # Descending order

    books = list(
        self.books_collection.find(query, {"_id": 0})
        .sort(sort_field)
        .skip(skip)
        .limit(limit)
    )

    total = self.books_collection.count_documents(query)

    return books, total


def restore_book(self, book_id: str, user_id: str) -> bool:
    """Restore book from trash"""
    result = self.books_collection.update_one(
        {
            "book_id": book_id,
            "user_id": user_id,
            "is_deleted": True
        },
        {
            "$set": {
                "is_deleted": False,
                "updated_at": datetime.utcnow()
            },
            "$unset": {
                "deleted_at": "",
                "deleted_by": ""
            }
        }
    )
    return result.modified_count > 0


def empty_trash(self, user_id: str) -> Dict[str, int]:
    """Permanently delete all books in trash"""
    # Get all books in trash
    trash_books = self.books_collection.find(
        {"user_id": user_id, "is_deleted": True},
        {"book_id": 1}
    )

    stats = {
        "deleted_books": 0,
        "deleted_chapters": 0,
        "deleted_permissions": 0
    }

    for book in trash_books:
        book_id = book["book_id"]

        # Delete chapters
        chapters_result = self.db["book_chapters"].delete_many(
            {"book_id": book_id}
        )
        stats["deleted_chapters"] += chapters_result.deleted_count

        # Delete permissions
        perms_result = self.db["book_permissions"].delete_many(
            {"book_id": book_id}
        )
        stats["deleted_permissions"] += perms_result.deleted_count

        # Delete book
        self.books_collection.delete_one({"book_id": book_id})
        stats["deleted_books"] += 1

    return stats
```

### Step 3: Update Routes

**File:** `src/api/book_routes.py`

```python
@router.delete("/{book_id}")
async def delete_book(
    book_id: str,
    permanent: bool = Query(False, description="Permanent delete (true) or move to trash (false)"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Delete book (soft or hard delete)

    **Query Parameters:**
    - permanent: false (default) = Move to trash, true = Permanent delete

    **Soft Delete (permanent=false):**
    - Sets is_deleted=true
    - Keeps all data
    - Can be restored

    **Hard Delete (permanent=true):**
    - Deletes book permanently
    - Deletes all chapters
    - Deletes all permissions
    - Cannot be restored
    """
    user_id = current_user["uid"]

    # Verify ownership
    book = book_manager.get_book(book_id)
    if not book:
        raise HTTPException(404, "Book not found")

    if book["user_id"] != user_id:
        raise HTTPException(403, "Not your book")

    if permanent:
        # Hard delete
        chapter_manager.delete_guide_chapters(book_id)
        permission_manager.delete_guide_permissions(book_id)
        book_manager.delete_book(book_id)

        return {
            "message": "Book permanently deleted",
            "book_id": book_id
        }
    else:
        # Soft delete
        success = book_manager.soft_delete_book(book_id, user_id)
        if not success:
            raise HTTPException(400, "Failed to move book to trash")

        return {
            "message": "Book moved to trash",
            "book_id": book_id,
            "can_restore": True,
            "deleted_at": datetime.utcnow()
        }


@router.get("/trash")
async def list_trash(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort_by: str = Query("deleted_at", description="Sort field"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    List books in trash

    **Authentication:** Required

    **Query Parameters:**
    - page: Page number (default: 1)
    - limit: Items per page (default: 20, max: 100)
    - sort_by: Sort by field (default: deleted_at)
    """
    user_id = current_user["uid"]
    skip = (page - 1) * limit

    books, total = book_manager.list_trash(user_id, skip, limit, sort_by)

    # Transform to TrashBookItem
    items = []
    for book in books:
        chapters_count = chapter_manager.count_chapters(book["book_id"])
        items.append(TrashBookItem(
            book_id=book["book_id"],
            title=book["title"],
            slug=book["slug"],
            deleted_at=book["deleted_at"],
            deleted_by=book.get("deleted_by", user_id),
            chapters_count=chapters_count,
            can_restore=True
        ))

    return TrashListResponse(
        items=items,
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit
    )


@router.post("/{book_id}/restore")
async def restore_book(
    book_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Restore book from trash

    **Authentication:** Required (Owner only)
    """
    user_id = current_user["uid"]

    success = book_manager.restore_book(book_id, user_id)
    if not success:
        raise HTTPException(404, "Book not found in trash")

    return {
        "message": "Book restored successfully",
        "book_id": book_id,
        "restored_at": datetime.utcnow()
    }


@router.delete("/trash/empty")
async def empty_trash(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Empty trash (permanently delete all trashed books)

    **Authentication:** Required

    **Warning:** This action cannot be undone!
    """
    user_id = current_user["uid"]

    stats = book_manager.empty_trash(user_id)

    return {
        "message": "Trash emptied successfully",
        **stats
    }
```

### Step 4: Update Queries

**Update list_user_books to exclude deleted:**

```python
def list_user_books(self, user_id: str, ...):
    query = {
        "user_id": user_id,
        "is_deleted": False  # ← Add this
    }
    # ... rest of query
```

---

## 🎨 Frontend Implementation

### Trash Page UI

```typescript
interface TrashBook {
  book_id: string;
  title: string;
  slug: string;
  deleted_at: string;
  deleted_by: string;
  chapters_count: number;
  can_restore: boolean;
}

// List trash
const { data } = await api.get('/api/v1/books/trash?page=1&limit=20');

// Restore
await api.post(`/api/v1/books/${bookId}/restore`);

// Permanent delete
await api.delete(`/api/v1/books/${bookId}?permanent=true`);

// Empty trash
await api.delete('/api/v1/books/trash/empty');
```

### Delete Button Flow

```typescript
// Delete button click
const handleDelete = async (bookId: string) => {
  // Show confirmation
  const confirmed = await showConfirm(
    "Move to Trash?",
    "You can restore it later from Trash"
  );

  if (confirmed) {
    // Soft delete (move to trash)
    await api.delete(`/api/v1/books/${bookId}?permanent=false`);
    toast.success("Moved to trash");
  }
};

// Permanent delete from trash
const handlePermanentDelete = async (bookId: string) => {
  const confirmed = await showConfirm(
    "Delete Permanently?",
    "This action cannot be undone!"
  );

  if (confirmed) {
    await api.delete(`/api/v1/books/${bookId}?permanent=true`);
    toast.success("Deleted permanently");
  }
};
```

---

## 📊 Summary

### New Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| DELETE | `/books/{id}?permanent=false` | Move to trash |
| GET | `/books/trash` | List trash |
| POST | `/books/{id}/restore` | Restore from trash |
| DELETE | `/books/{id}?permanent=true` | Permanent delete |
| DELETE | `/books/trash/empty` | Empty trash |

### Database Changes

- Add `is_deleted`, `deleted_at`, `deleted_by` fields
- Update queries to filter `is_deleted: false`

### Benefits

- ✅ Safe deletion (can undo)
- ✅ Trash management
- ✅ Permanent delete option
- ✅ Audit trail (who deleted, when)
- ✅ Bulk empty trash

---

**Ready to implement?** 🚀
