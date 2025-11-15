# Online Books System - Final Architecture & Implementation Plan

**Date**: November 15, 2025
**System**: Online Books with Point System, Community Books & Document Integration

---

## 🎯 System Overview

### **Key Requirements:**
1. ✅ **User chooses points** when creating book
2. ✅ **Community Books** (tương tự Community Tests)
3. ✅ **Revenue split 80/20** (same as Online Tests)
4. ✅ **PDF export** (similar to Slides export with Playwright)
5. ✅ **Document → Chapter conversion** (any document can become a chapter)

---

## 📊 Database Architecture

### **1. Collection: `online_books`** (renamed from `user_guides`)

```javascript
{
  "_id": ObjectId("..."),
  "book_id": "book_abc123",
  "user_id": "user_xyz",  // Creator/Owner

  // Basic info
  "title": "Learn Python Programming",
  "slug": "learn-python-programming",
  "description": "Complete Python guide for beginners",

  // Visibility & Access
  "visibility": "public | point_based",  // public = free, point_based = paid

  // Point Configuration (USER CHOOSES when creating book)
  "access_config": {
    "one_time_view_points": 50,      // User sets: "Xem 1 lần: X points"
    "forever_view_points": 200,      // User sets: "Xem mãi mãi: Y points"
    "download_pdf_points": 500,      // User sets: "Download PDF: Z points"
    "is_one_time_enabled": true,     // Toggle each option
    "is_forever_enabled": true,
    "is_download_enabled": true
  },

  // Community Publishing (similar to marketplace_config in online_tests)
  "community_config": {
    "is_public": false,              // Published to Community Books?
    "published_at": ISODate("..."),
    "category": "programming",       // programming, business, marketing, design, etc.
    "tags": ["python", "beginner", "tutorial"],
    "difficulty_level": "beginner",  // beginner, intermediate, advanced, expert
    "short_description": "Learn Python in 30 days",
    "cover_image_url": "https://...",

    // Stats
    "total_views": 1523,
    "total_downloads": 234,
    "total_purchases": 456,          // Số người đã mua
    "average_rating": 4.5,
    "rating_count": 89,
    "version": "1.0.0"
  },

  // Revenue Tracking
  "stats": {
    "total_revenue_points": 45600,   // Tổng điểm thu được (100%)
    "owner_reward_points": 36480,    // Owner nhận 80%
    "system_fee_points": 9120        // System 20%
  },

  // Branding (same as before)
  "logo_url": "https://...",
  "custom_domain": "python.example.com",
  "branding": {
    "primary_color": "#3776AB",
    "font_family": "Inter"
  },

  // SEO
  "is_indexed": true,  // For search engines (only if visibility = public)

  "created_at": ISODate("2025-11-15T08:00:00Z"),
  "updated_at": ISODate("2025-11-15T10:30:00Z")
}
```

**Indexes:**
```javascript
db.online_books.createIndex({ "book_id": 1 }, { unique: true });
db.online_books.createIndex({ "user_id": 1, "updated_at": -1 });
db.online_books.createIndex({ "slug": 1 });
db.online_books.createIndex({ "custom_domain": 1 }, { unique: true, sparse: true });
db.online_books.createIndex({ "community_config.is_public": 1, "community_config.published_at": -1 });
db.online_books.createIndex({ "community_config.category": 1, "community_config.average_rating": -1 });
```

---

### **2. Collection: `book_chapters`** (renamed from `guide_chapters`)

**Now chapters can be:**
1. Created directly in book editor (inline content)
2. Converted from existing documents (reference `document_id`)

```javascript
{
  "_id": ObjectId("..."),
  "chapter_id": "chapter_def456",
  "book_id": "book_abc123",

  // Chapter Identity
  "title": "Introduction to Python",
  "slug": "introduction",

  // Content Source (TWO OPTIONS)
  "content_source": "inline | document",  // NEW FIELD

  // Option 1: Inline Content (created directly)
  "content_html": "<h1>Introduction</h1><p>Python is...</p>",  // If content_source = inline
  "content_json": {  // TipTap JSON
    "type": "doc",
    "content": [...]
  },

  // Option 2: Document Reference (converted from document)
  "document_id": "doc_abc123",  // If content_source = document
  // → Content loaded from documents collection dynamically

  // Table of Contents Structure
  "parent_id": null,           // Nested structure (max 3 levels)
  "order_index": 1,            // Position in TOC
  "depth": 0,                  // 0, 1, 2

  // Publishing
  "is_published": true,

  "created_at": ISODate("2025-11-15T08:15:00Z"),
  "updated_at": ISODate("2025-11-15T10:00:00Z")
}
```

**Indexes:**
```javascript
db.book_chapters.createIndex({ "chapter_id": 1 }, { unique: true });
db.book_chapters.createIndex({ "book_id": 1, "order_index": 1 });
db.book_chapters.createIndex({ "book_id": 1, "slug": 1 }, { unique: true });
db.book_chapters.createIndex({ "document_id": 1 });  // For document references
```

---

### **3. Collection: `documents`** (EXISTING - from Document Editor)

**Current schema** (no changes needed):

```javascript
{
  "_id": ObjectId("..."),
  "document_id": "doc_abc123",
  "user_id": "user_xyz",

  // Document Type
  "document_type": "doc | slide | note",  // A4 doc, FullHD slide, or note

  // Content
  "title": "Python Basics",
  "content_html": "<h1>Python</h1><p>...</p>",
  "content_text": "Python ...",  // For search

  // Source
  "source_type": "file | created",  // From file upload or created new
  "file_id": "file_xyz",           // If from file
  "original_r2_url": "https://...",
  "original_file_type": "pdf | docx | txt",

  // Organization
  "folder_id": "folder_123",

  // Usage Tracking (NEW - track if document used in books)
  "used_in_books": [               // Array of book_ids using this document
    "book_abc123",
    "book_def456"
  ],

  "created_at": ISODate("..."),
  "last_saved_at": ISODate("...")
}
```

**New Index:**
```javascript
db.documents.createIndex({ "used_in_books": 1 });  // Track document usage
```

---

### **4. Collection: `book_access_grants`** (NEW)

Tracks user purchases (one-time, forever, download)

```javascript
{
  "_id": ObjectId("..."),
  "access_id": "access_ghi789",
  "book_id": "book_abc123",
  "user_id": "user_buyer",         // User who purchased

  // Access Type
  "access_type": "one_time | forever | download",

  // Transaction
  "points_paid": 200,              // Points user paid
  "owner_reward": 160,             // Owner gets 80%
  "system_fee": 40,                // System gets 20%

  // Usage Tracking
  "view_count": 3,                 // For one_time only
  "max_views": 1,                  // For one_time only
  "is_active": true,
  "expires_at": null,              // Optional expiry

  // Download tracking
  "download_count": 1,
  "last_downloaded_at": ISODate("..."),

  "purchased_at": ISODate("2025-11-15T10:00:00Z"),
  "last_accessed_at": ISODate("2025-11-15T14:00:00Z")
}
```

**Indexes:**
```javascript
db.book_access_grants.createIndex({ "access_id": 1 }, { unique: true });
db.book_access_grants.createIndex({ "book_id": 1, "user_id": 1 });
db.book_access_grants.createIndex({ "user_id": 1, "purchased_at": -1 });
```

---

### **5. Collection: `book_transactions`** (NEW)

Transaction history (similar to test point transactions)

```javascript
{
  "_id": ObjectId("..."),
  "transaction_id": "txn_jkl012",
  "book_id": "book_abc123",
  "buyer_user_id": "user_xyz",
  "owner_user_id": "user_owner",

  // Transaction type
  "transaction_type": "one_time_view | forever_view | download_pdf",

  // Points flow
  "total_points": 200,
  "owner_reward": 160,             // 80%
  "system_fee": 40,                // 20%

  // Status
  "status": "completed | failed | refunded",

  // Reference
  "access_grant_id": "access_ghi789",

  "created_at": ISODate("2025-11-15T10:00:00Z")
}
```

**Indexes:**
```javascript
db.book_transactions.createIndex({ "transaction_id": 1 }, { unique: true });
db.book_transactions.createIndex({ "book_id": 1, "created_at": -1 });
db.book_transactions.createIndex({ "buyer_user_id": 1, "created_at": -1 });
db.book_transactions.createIndex({ "owner_user_id": 1, "created_at": -1 });
```

---

### **6. Collection: `users`** (EXISTING - UPDATE)

Already has point system from Online Tests, just use it:

```javascript
{
  "_id": ObjectId("..."),
  "firebase_uid": "user_xyz",

  // Two types of points (EXISTING from Online Tests)
  "points": 1000,                  // System points (buy, gift, tasks)
  "earnings_points": 3200,         // Earnings from selling tests/books (80% share)

  // Transactions (EXISTING)
  "point_transactions": [
    {
      "type": "deduct | add",
      "amount": 200,
      "reason": "Purchased book: Learn Python",
      "book_id": "book_abc123",    // Add book reference
      "timestamp": ISODate("...")
    }
  ],

  "earnings_transactions": [
    {
      "type": "book_sale | test_sale",  // Add book_sale type
      "amount": 160,
      "source_id": "book_abc123",
      "source_type": "book",
      "buyer_id": "user_buyer",
      "timestamp": ISODate("...")
    }
  ],

  // ... other user fields
}
```

---

## 🔄 Core Workflows

### **Workflow 1: Create Book with Point Configuration**

```
1. POST /books
   Body: {
     title: "Learn Python",
     description: "Complete guide",
     visibility: "point_based",  // User chooses
     access_config: {
       one_time_view_points: 50,    // User sets price
       forever_view_points: 200,
       download_pdf_points: 500,
       is_one_time_enabled: true,
       is_forever_enabled: true,
       is_download_enabled: true
     }
   }

   Response: {
     book_id: "book_abc123",
     slug: "learn-python",
     visibility: "point_based",
     access_config: { ... }
   }
```

---

### **Workflow 2: Add Chapter from Existing Document**

```
User has document "doc_abc123" (A4 article about Python variables)

1. POST /books/{book_id}/chapters/from-document
   Body: {
     document_id: "doc_abc123",
     title: "Python Variables",  // Optional override
     order_index: 2,
     parent_id: null
   }

   Backend:
   - Get document from documents collection
   - Create chapter with content_source = "document"
   - Store document_id reference (NO COPY)
   - Add book_id to document.used_in_books[]
   - Return chapter_id

2. GET /books/{book_id}/chapters/{chapter_id}
   → Backend dynamically loads content from document:
     {
       chapter_id: "chapter_def456",
       title: "Python Variables",
       content_source: "document",
       document_id: "doc_abc123",
       content_html: "<h1>Variables</h1>...",  // Loaded from document
       content_json: { ... }
     }
```

**Benefits:**
- ✅ No content duplication
- ✅ Document updates reflect in book
- ✅ Can reuse same document in multiple books
- ✅ Easy to manage: update document → all books updated

---

### **Workflow 3: Publish to Community Books**

Similar to Community Tests:

```
1. PATCH /books/{book_id}/publish-community
   Body: {
     category: "programming",
     tags: ["python", "beginner"],
     difficulty_level: "beginner",
     short_description: "Learn Python in 30 days",
     cover_image: <file>
   }

   Backend:
   - Upload cover image to R2
   - Set community_config.is_public = true
   - Set published_at timestamp
   - Return success

2. Book appears in Community Books:
   GET /community/books?category=programming&sort=popular

   Response: [
     {
       book_id: "book_abc123",
       title: "Learn Python",
       cover_image_url: "https://...",
       price_points: 200,  // forever_view_points
       category: "programming",
       average_rating: 4.5,
       total_purchases: 456
     }
   ]
```

---

### **Workflow 4: Purchase & View Book**

Same as Online Tests:

```
1. User browses Community Books:
   GET /community/books

2. User views book details:
   GET /books/{book_id}/community-preview
   → Returns: title, description, TOC, pricing (no content)

3. User purchases access:
   POST /books/{book_id}/access/purchase
   Body: {
     access_type: "forever_view",
     points_source: "points"  // or "earnings_points"
   }

   Backend:
   - Deduct 200 points from buyer
   - Create book_access_grant
   - Create book_transaction
   - Add 160 earnings_points to owner (80%)
   - System keeps 40 points (20%)

4. User views book:
   GET /books/{book_id}/view
   → Returns full book + all chapters
```

---

### **Workflow 5: Download PDF**

Similar to Slides PDF export (using Playwright):

```
1. POST /books/{book_id}/download-pdf
   Headers: Authorization: Bearer <token>

   Backend checks:
   - User has download access?
   - Generate PDF:
     * Collect all chapters (inline + document-referenced)
     * Merge into single HTML
     * Use Playwright to generate PDF (A4 format)
     * Apply book branding (logo, colors)

   Response: PDF binary
   Headers:
     Content-Type: application/pdf
     Content-Disposition: attachment; filename="learn-python.pdf"
```

---

## 🛠️ PDF Generation (Similar to Slides)

**Reuse existing Playwright PDF service:**

```python
# src/services/document_export_service.py (EXISTING)

async def export_to_pdf_playwright(
    self,
    html_content: str,
    title: str = "document",
    document_type: str = "doc"  # "doc" for books
) -> Tuple[bytes, str]:
    """
    Already implemented for Slides!
    - doc: A4 format (210mm x 297mm)
    - slide: FullHD (1920x1080)
    """
    # ... Playwright PDF generation
```

**For books:**
```python
# New method in DocumentExportService

async def export_book_to_pdf(
    self,
    book_id: str,
    user_id: str
) -> Tuple[bytes, str]:
    """
    Export entire book as PDF
    1. Get all chapters
    2. Merge HTML (inline + document-referenced)
    3. Apply book branding
    4. Use export_to_pdf_playwright()
    """
    # Get book
    book = db.online_books.find_one({"book_id": book_id})

    # Get all chapters sorted by order_index
    chapters = db.book_chapters.find({
        "book_id": book_id,
        "is_published": True
    }).sort("order_index", 1)

    # Merge HTML
    html_parts = [f"<h1>{book['title']}</h1>"]

    for chapter in chapters:
        if chapter["content_source"] == "inline":
            # Use chapter's content directly
            html_parts.append(chapter["content_html"])
        else:  # document
            # Load content from document
            doc = db.documents.find_one({"document_id": chapter["document_id"]})
            html_parts.append(doc["content_html"])

    full_html = "\n".join(html_parts)

    # Apply book branding
    branding = book.get("branding", {})
    styled_html = f"""
    <style>
        body {{
            font-family: {branding.get('font_family', 'Arial')};
        }}
        h1, h2 {{
            color: {branding.get('primary_color', '#000')};
        }}
    </style>
    {full_html}
    """

    # Generate PDF (A4)
    pdf_bytes, filename = await self.export_to_pdf_playwright(
        styled_html,
        title=book["title"],
        document_type="doc"  # A4 format
    )

    return pdf_bytes, filename
```

---

## 🆕 New API Endpoints (Phase 6)

### **Book Management**

```
POST   /books                           - Create book (user sets points)
GET    /books                           - List user's books
GET    /books/{book_id}                 - Get book details
PATCH  /books/{book_id}                 - Update book
DELETE /books/{book_id}                 - Delete book
```

### **Chapter Management**

```
POST   /books/{book_id}/chapters                    - Create inline chapter
POST   /books/{book_id}/chapters/from-document      - Create chapter from document
GET    /books/{book_id}/chapters                    - List chapters
GET    /books/{book_id}/chapters/{chapter_id}       - Get chapter (loads document if needed)
PATCH  /books/{book_id}/chapters/{chapter_id}       - Update chapter
DELETE /books/{book_id}/chapters/{chapter_id}       - Delete chapter
```

### **Community Books**

```
PATCH  /books/{book_id}/publish-community           - Publish to community
PATCH  /books/{book_id}/unpublish-community         - Unpublish
GET    /community/books                             - Browse community books
GET    /community/books/{book_id}                   - Public preview (no content)
```

### **Access & Purchase**

```
POST   /books/{book_id}/access/purchase             - Purchase access
GET    /books/{book_id}/view                        - View book (check access)
POST   /books/{book_id}/download-pdf                - Download PDF
GET    /users/me/books/purchased                    - User's purchased books
```

### **Revenue & Earnings**

```
GET    /users/me/books/earnings                     - Book earnings dashboard
GET    /users/me/earnings/withdraw                  - Withdraw earnings (same as tests)
```

---

## 📋 Migration Plan: Guide → Book

### **Step 1: Rename Collections**

```javascript
// MongoDB migration script
db.user_guides.renameCollection("online_books");
db.guide_chapters.renameCollection("book_chapters");
db.guide_permissions.renameCollection("book_permissions");  // Keep for now
```

### **Step 2: Update Field Names**

```javascript
// Update all documents
db.online_books.updateMany({}, {
  $rename: {
    "guide_id": "book_id"
  }
});

db.book_chapters.updateMany({}, {
  $rename: {
    "guide_id": "book_id"
  }
});

db.book_permissions.updateMany({}, {
  $rename: {
    "guide_id": "book_id"
  }
});
```

### **Step 3: Add New Fields**

```javascript
// Add access_config to all books
db.online_books.updateMany({}, {
  $set: {
    "access_config": {
      "one_time_view_points": 0,
      "forever_view_points": 0,
      "download_pdf_points": 0,
      "is_one_time_enabled": false,
      "is_forever_enabled": false,
      "is_download_enabled": false
    },
    "community_config": {
      "is_public": false,
      "category": null,
      "tags": [],
      "total_views": 0,
      "total_purchases": 0,
      "average_rating": 0,
      "rating_count": 0
    },
    "stats": {
      "total_revenue_points": 0,
      "owner_reward_points": 0,
      "system_fee_points": 0
    }
  }
});

// Add content_source to chapters
db.book_chapters.updateMany({}, {
  $set: {
    "content_source": "inline",  // All existing chapters are inline
    "document_id": null
  }
});
```

### **Step 4: Update All API Endpoints**

```
OLD → NEW:
/api/v1/guides → /api/v1/books
/api/v1/guides/{guide_id} → /api/v1/books/{book_id}
/api/v1/guides/{guide_id}/chapters → /api/v1/books/{book_id}/chapters
... (all 18 endpoints)
```

### **Step 5: Rename Python Files**

```
src/services/user_guide_manager.py → src/services/book_manager.py
src/services/guide_chapter_manager.py → src/services/book_chapter_manager.py
src/services/guide_permission_manager.py → src/services/book_permission_manager.py
src/models/user_guide_models.py → src/models/book_models.py
src/models/public_guide_models.py → src/models/public_book_models.py
src/api/user_guide_routes.py → src/api/book_routes.py
```

### **Step 6: Find & Replace in Code**

```python
# Replace all occurrences:
"guide_id" → "book_id"
"user_guides" → "online_books"
"guide_chapters" → "book_chapters"
"guide_permissions" → "book_permissions"
GuideManager → BookManager
ChapterManager → BookChapterManager
PermissionManager → BookPermissionManager
```

---

## 🚀 Implementation Priority

### **Phase 6A: Migration (FIRST)**
1. ✅ Backup database
2. ✅ Run MongoDB migration scripts
3. ✅ Rename Python files
4. ✅ Find & replace terminology
5. ✅ Update all imports
6. ✅ Run existing tests (should still pass)
7. ✅ Deploy migration
8. ⏸️ Notify frontend team

### **Phase 6B: Point System (NEXT)**
1. ✅ Update book creation: add access_config (user sets points)
2. ✅ Create book_access_grants collection
3. ✅ Create book_transactions collection
4. ✅ Implement purchase endpoint
5. ✅ Implement view endpoint (check access)
6. ✅ Update user points logic (deduct/reward)

### **Phase 6C: Document Integration**
1. ✅ Add content_source field to chapters
2. ✅ Implement POST /chapters/from-document
3. ✅ Dynamic content loading for document-referenced chapters
4. ✅ Track document usage (used_in_books array)

### **Phase 6D: Community Books**
1. ✅ Add community_config to books
2. ✅ Implement publish/unpublish endpoints
3. ✅ Browse community books endpoint
4. ✅ Public preview endpoint
5. ✅ Cover image upload (R2)

### **Phase 6E: PDF Export**
1. ✅ Implement book PDF export (reuse Playwright)
2. ✅ Merge chapters (inline + document)
3. ✅ Apply book branding
4. ✅ Track downloads

### **Phase 6F: Revenue & Earnings**
1. ✅ Earnings dashboard
2. ✅ Withdrawal request (reuse from Online Tests)

---

## ✅ Ready to Execute!

**Next Command:** Bạn confirm là bắt đầu migration ngay! 🚀

**Steps:**
1. Backup database ✅
2. Run migration script ✅
3. Update code (find & replace) ✅
4. Test ✅
5. Deploy ✅

**Estimated Time:** 3-4 hours

---

**Ready?** 🎯
