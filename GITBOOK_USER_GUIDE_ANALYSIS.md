# GitBook-Style User Guide Feature - Technical Analysis

## 📋 Overview

Phân tích tính năng chuyển đổi **Document Editor** (Tiptap) thành **User Guide** (GitBook-style) với:
- **Sidebar Navigation**: Danh sách documents dạng tree/nested chapters
- **Content View**: Hiển thị nội dung document khi click vào title
- **Public Access**: View công khai không cần auth
- **Backend Integration**: API endpoints và data models

---

## 🎯 Feature Requirements

### Frontend UI (GitBook Style)

```
┌─────────────────────────────────────────────────────────┐
│  User Guide: "Getting Started with WordAI"              │
├──────────────┬──────────────────────────────────────────┤
│              │                                           │
│  Sidebar     │  Content Area                            │
│              │                                           │
│  📘 Intro    │  ┌─────────────────────────────────┐    │
│  📘 Setup    │  │ # Introduction                   │    │
│    ├─ Install│  │                                  │    │
│    └─ Config │  │ Welcome to WordAI User Guide...  │    │
│  📘 Features │  │                                  │    │
│    ├─ Editor │  │ ## What is WordAI?               │    │
│    └─ AI     │  │ WordAI is a powerful...          │    │
│  📘 API      │  │                                  │    │
│              │  └─────────────────────────────────┘    │
│              │                                           │
└──────────────┴──────────────────────────────────────────┘
```

### Key Features

1. **User Guide Collection** (giống GitBook Space)
   - Tên: "Getting Started Guide"
   - Mô tả: "Complete guide for beginners"
   - Public URL: `https://wordai.pro/guides/getting-started-guide`
   - Visibility: `public` | `private` | `unlisted`

2. **Chapter Organization** (nested documents)
   - Document 1: "Introduction" (order: 1)
   - Document 2: "Installation" (order: 2, parent: Setup)
   - Document 3: "Configuration" (order: 3, parent: Setup)
   - Support nested chapters (max 3 levels)

3. **Public View**
   - No auth required for `public` guides
   - Clean URL: `/guides/{guide_slug}/{chapter_slug}`
   - SEO-friendly (meta tags, OpenGraph)
   - Responsive design

4. **Edit Mode** (Owner only)
   - Reorder chapters (drag & drop)
   - Add/remove documents
   - Edit document content (Tiptap editor)
   - Publish/unpublish changes

---

## 🗄️ Database Schema

### Collection: `user_guides`

```javascript
{
  _id: ObjectId("..."),
  guide_id: "guide_abc123",           // UUID
  user_id: "firebase_uid",            // Owner

  // Metadata
  title: "Getting Started with WordAI",
  description: "Complete beginner guide",
  slug: "getting-started-guide",     // URL-friendly, unique per user

  // Settings
  visibility: "public",               // "public" | "private" | "unlisted"
  is_published: true,                 // Draft vs Published

  // Branding (optional)
  logo_url: "https://...",
  cover_image_url: "https://...",
  primary_color: "#4F46E5",

  // Access control
  allowed_domains: ["company.com"],   // Email domain whitelist (optional)
  require_auth: false,                // Force login even if public

  // SEO
  meta_title: "Getting Started | WordAI",
  meta_description: "Learn how to use...",

  // Stats
  view_count: 1250,
  last_published_at: ISODate("2025-11-15T10:00:00Z"),

  // Timestamps
  created_at: ISODate("2025-11-01T10:00:00Z"),
  updated_at: ISODate("2025-11-15T10:00:00Z")
}
```

**Indexes:**
```javascript
db.user_guides.createIndex({ guide_id: 1 }, { unique: true });
db.user_guides.createIndex({ user_id: 1, slug: 1 }, { unique: true }); // Unique slug per user
db.user_guides.createIndex({ slug: 1, visibility: 1 }); // Public access lookup
db.user_guides.createIndex({ user_id: 1, updated_at: -1 }); // User's guides list
```

---

### Collection: `guide_chapters`

```javascript
{
  _id: ObjectId("..."),
  chapter_id: "chapter_xyz789",       // UUID
  guide_id: "guide_abc123",           // Foreign key to user_guides
  document_id: "doc_def456",          // Foreign key to documents

  // Organization
  parent_chapter_id: null,            // null = root level, or parent's chapter_id
  order: 1,                           // Display order in sidebar (1, 2, 3...)
  depth: 0,                           // 0 = root, 1 = nested, 2 = deeply nested

  // Navigation
  title: "Introduction",              // Override document title (optional)
  slug: "introduction",               // URL slug for this chapter
  icon: "📘",                         // Emoji or icon class

  // State
  is_visible: true,                   // Show/hide in navigation
  is_expanded: true,                  // Default expanded state for nested chapters

  // Timestamps
  added_at: ISODate("2025-11-01T10:00:00Z"),
  updated_at: ISODate("2025-11-15T10:00:00Z")
}
```

**Indexes:**
```javascript
db.guide_chapters.createIndex({ chapter_id: 1 }, { unique: true });
db.guide_chapters.createIndex({ guide_id: 1, order: 1 }); // Get chapters in order
db.guide_chapters.createIndex({ guide_id: 1, parent_chapter_id: 1, order: 1 }); // Nested structure
db.guide_chapters.createIndex({ document_id: 1 }); // Find chapters using a document
db.guide_chapters.createIndex({ guide_id: 1, slug: 1 }, { unique: true }); // Unique chapter slug per guide
```

---

### Existing Collection: `documents` (No changes needed)

Documents remain as-is:
- `document_id`, `user_id`, `title`, `content_html`, `content_text`
- `source_type`, `document_type`, `folder_id`
- Already support Tiptap content

**Relationship:**
- A document CAN be used in MULTIPLE guides (reusable)
- A document CAN exist WITHOUT being in any guide (standalone)
- Deleting a guide does NOT delete documents
- Deleting a document removes it from all guides (with warning)

---

## 🔌 Backend API Endpoints

### 1. User Guide Management

#### `POST /api/v1/guides`
Create new user guide

**Auth:** Required (Firebase token)

**Request:**
```json
{
  "title": "Getting Started with WordAI",
  "description": "Complete beginner guide",
  "slug": "getting-started-guide",
  "visibility": "public",
  "is_published": false
}
```

**Response:**
```json
{
  "success": true,
  "guide": {
    "guide_id": "guide_abc123",
    "title": "Getting Started with WordAI",
    "slug": "getting-started-guide",
    "visibility": "public",
    "is_published": false,
    "public_url": "https://wordai.pro/guides/getting-started-guide",
    "created_at": "2025-11-15T10:00:00Z"
  }
}
```

---

#### `GET /api/v1/guides`
List user's guides

**Auth:** Required

**Query Params:**
- `page`: int (default: 1)
- `limit`: int (default: 20)
- `visibility`: "all" | "public" | "private" | "unlisted"
- `sort`: "updated" | "created" | "title"

**Response:**
```json
{
  "success": true,
  "guides": [
    {
      "guide_id": "guide_abc123",
      "title": "Getting Started with WordAI",
      "slug": "getting-started-guide",
      "description": "Complete beginner guide",
      "visibility": "public",
      "is_published": true,
      "chapter_count": 8,
      "view_count": 1250,
      "last_published_at": "2025-11-15T10:00:00Z",
      "updated_at": "2025-11-15T10:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 3,
    "total_pages": 1
  }
}
```

---

#### `GET /api/v1/guides/{guide_id}`
Get guide details (Owner view - with edit permissions)

**Auth:** Required

**Response:**
```json
{
  "success": true,
  "guide": {
    "guide_id": "guide_abc123",
    "title": "Getting Started with WordAI",
    "slug": "getting-started-guide",
    "description": "Complete beginner guide",
    "visibility": "public",
    "is_published": true,
    "logo_url": null,
    "cover_image_url": null,
    "primary_color": "#4F46E5",
    "meta_title": "Getting Started | WordAI",
    "meta_description": "Learn how to use...",
    "view_count": 1250,
    "created_at": "2025-11-01T10:00:00Z",
    "updated_at": "2025-11-15T10:00:00Z",
    "last_published_at": "2025-11-15T10:00:00Z"
  },
  "permissions": {
    "can_edit": true,
    "can_delete": true,
    "can_publish": true
  }
}
```

---

#### `PATCH /api/v1/guides/{guide_id}`
Update guide metadata

**Auth:** Required (Owner only)

**Request:**
```json
{
  "title": "Updated Title",
  "description": "Updated description",
  "visibility": "unlisted",
  "primary_color": "#10B981"
}
```

**Response:**
```json
{
  "success": true,
  "guide": { /* updated guide object */ }
}
```

---

#### `DELETE /api/v1/guides/{guide_id}`
Delete guide (does NOT delete documents)

**Auth:** Required (Owner only)

**Response:**
```json
{
  "success": true,
  "message": "Guide deleted successfully",
  "deleted_chapters_count": 8
}
```

---

### 2. Chapter Management

#### `POST /api/v1/guides/{guide_id}/chapters`
Add document to guide as chapter

**Auth:** Required (Owner only)

**Request:**
```json
{
  "document_id": "doc_def456",
  "parent_chapter_id": null,          // null = root level
  "order": 1,                         // Position in sidebar
  "title": "Introduction",            // Override document title (optional)
  "slug": "introduction",             // Auto-generated if not provided
  "icon": "📘"
}
```

**Response:**
```json
{
  "success": true,
  "chapter": {
    "chapter_id": "chapter_xyz789",
    "guide_id": "guide_abc123",
    "document_id": "doc_def456",
    "parent_chapter_id": null,
    "order": 1,
    "depth": 0,
    "title": "Introduction",
    "slug": "introduction",
    "icon": "📘",
    "is_visible": true,
    "added_at": "2025-11-15T10:00:00Z"
  }
}
```

---

#### `GET /api/v1/guides/{guide_id}/chapters`
Get all chapters for a guide (nested tree structure)

**Auth:** Optional (public if guide is public)

**Query Params:**
- `include_hidden`: boolean (default: false) - Show hidden chapters (owner only)

**Response:**
```json
{
  "success": true,
  "chapters": [
    {
      "chapter_id": "chapter_001",
      "title": "Introduction",
      "slug": "introduction",
      "icon": "📘",
      "order": 1,
      "depth": 0,
      "is_visible": true,
      "document_id": "doc_001",
      "children": []
    },
    {
      "chapter_id": "chapter_002",
      "title": "Setup",
      "slug": "setup",
      "icon": "⚙️",
      "order": 2,
      "depth": 0,
      "is_visible": true,
      "document_id": "doc_002",
      "children": [
        {
          "chapter_id": "chapter_003",
          "title": "Installation",
          "slug": "installation",
          "icon": "📦",
          "order": 1,
          "depth": 1,
          "is_visible": true,
          "document_id": "doc_003",
          "children": []
        },
        {
          "chapter_id": "chapter_004",
          "title": "Configuration",
          "slug": "configuration",
          "icon": "🔧",
          "order": 2,
          "depth": 1,
          "is_visible": true,
          "document_id": "doc_004",
          "children": []
        }
      ]
    }
  ],
  "total_chapters": 4
}
```

---

#### `PATCH /api/v1/guides/{guide_id}/chapters/{chapter_id}`
Update chapter settings

**Auth:** Required (Owner only)

**Request:**
```json
{
  "title": "Updated Title",
  "icon": "🚀",
  "is_visible": false,
  "order": 3,
  "parent_chapter_id": "chapter_002"
}
```

**Response:**
```json
{
  "success": true,
  "chapter": { /* updated chapter object */ }
}
```

---

#### `POST /api/v1/guides/{guide_id}/chapters/reorder`
Reorder chapters (bulk update)

**Auth:** Required (Owner only)

**Request:**
```json
{
  "chapters": [
    {
      "chapter_id": "chapter_001",
      "order": 1,
      "parent_chapter_id": null
    },
    {
      "chapter_id": "chapter_002",
      "order": 2,
      "parent_chapter_id": null
    },
    {
      "chapter_id": "chapter_003",
      "order": 1,
      "parent_chapter_id": "chapter_002"
    }
  ]
}
```

**Response:**
```json
{
  "success": true,
  "message": "Chapters reordered successfully",
  "updated_count": 3
}
```

---

#### `DELETE /api/v1/guides/{guide_id}/chapters/{chapter_id}`
Remove chapter from guide (does NOT delete document)

**Auth:** Required (Owner only)

**Response:**
```json
{
  "success": true,
  "message": "Chapter removed from guide",
  "chapter_id": "chapter_xyz789"
}
```

---

### 3. Public View API

#### `GET /api/v1/public/guides/{slug}`
Get public guide by slug (no auth required)

**Auth:** None (if guide is public)

**Response:**
```json
{
  "success": true,
  "guide": {
    "guide_id": "guide_abc123",
    "title": "Getting Started with WordAI",
    "slug": "getting-started-guide",
    "description": "Complete beginner guide",
    "logo_url": null,
    "cover_image_url": null,
    "primary_color": "#4F46E5",
    "meta_title": "Getting Started | WordAI",
    "meta_description": "Learn how to use...",
    "author": {
      "name": "John Doe",
      "avatar": "https://..."
    }
  },
  "chapters": [
    {
      "chapter_id": "chapter_001",
      "title": "Introduction",
      "slug": "introduction",
      "icon": "📘",
      "order": 1,
      "children": []
    }
  ]
}
```

**Error Response (404):**
```json
{
  "detail": "Guide not found or not public"
}
```

---

#### `GET /api/v1/public/guides/{guide_slug}/chapters/{chapter_slug}`
Get chapter content (public view)

**Auth:** None (if guide is public)

**Response:**
```json
{
  "success": true,
  "guide": {
    "guide_id": "guide_abc123",
    "title": "Getting Started with WordAI",
    "slug": "getting-started-guide"
  },
  "chapter": {
    "chapter_id": "chapter_001",
    "title": "Introduction",
    "slug": "introduction",
    "icon": "📘"
  },
  "content": {
    "document_id": "doc_001",
    "content_html": "<h1>Introduction</h1><p>Welcome to...</p>",
    "content_text": "Introduction\nWelcome to...",
    "last_updated_at": "2025-11-15T10:00:00Z"
  },
  "navigation": {
    "previous": null,
    "next": {
      "chapter_id": "chapter_002",
      "title": "Setup",
      "slug": "setup"
    }
  }
}
```

---

#### `POST /api/v1/public/guides/{guide_slug}/views`
Track view count (analytics)

**Auth:** None

**Request:**
```json
{
  "chapter_slug": "introduction",
  "referrer": "https://google.com",
  "user_agent": "Mozilla/5.0..."
}
```

**Response:**
```json
{
  "success": true
}
```

---

### 4. Document Integration

#### `GET /api/documents/{document_id}/usage`
Check where a document is used (in which guides)

**Auth:** Required (Owner only)

**Response:**
```json
{
  "success": true,
  "document_id": "doc_def456",
  "title": "Introduction",
  "used_in_guides": [
    {
      "guide_id": "guide_abc123",
      "guide_title": "Getting Started Guide",
      "chapter_title": "Introduction",
      "chapter_slug": "introduction"
    },
    {
      "guide_id": "guide_xyz789",
      "guide_title": "Advanced Tutorial",
      "chapter_title": "Welcome",
      "chapter_slug": "welcome"
    }
  ],
  "total_guides": 2
}
```

---

#### `DELETE /api/documents/{document_id}`
Delete document (with guide usage warning)

**Auth:** Required (Owner only)

**Response (409 Conflict):**
```json
{
  "detail": {
    "error": "document_in_use",
    "message": "This document is used in 2 user guides. Please remove it from guides first.",
    "used_in_guides": [
      {
        "guide_id": "guide_abc123",
        "guide_title": "Getting Started Guide"
      }
    ]
  }
}
```

---

## 🔄 Frontend-Backend Flow

### Flow 1: Create User Guide

```
┌─────────────┐                 ┌─────────────┐
│  Frontend   │                 │   Backend   │
└──────┬──────┘                 └──────┬──────┘
       │                                │
       │  1. User clicks "Create Guide" │
       │────────────────────────────────>│
       │     POST /api/v1/guides         │
       │     { title, slug, ... }        │
       │                                 │
       │  2. Create user_guides doc      │
       │  <─────────────────────────────┤
       │     { guide_id, slug, ... }     │
       │                                 │
       │  3. Navigate to guide editor    │
       │     /guides/{guide_id}/edit     │
       │                                 │
```

---

### Flow 2: Add Documents to Guide

```
┌─────────────┐                 ┌─────────────┐
│  Frontend   │                 │   Backend   │
└──────┬──────┘                 └──────┬──────┘
       │                                │
       │  1. Show document picker       │
       │     (list user's documents)    │
       │                                │
       │  2. User selects documents     │
       │     & sets order/nesting       │
       │                                │
       │  3. Batch add chapters         │
       │────────────────────────────────>│
       │  POST /api/v1/guides/{id}/     │
       │       chapters (multiple)       │
       │                                 │
       │  4. Create guide_chapters docs  │
       │  <─────────────────────────────┤
       │     { chapter_id, order, ... }  │
       │                                 │
       │  5. Update UI with sidebar tree │
       │                                 │
```

---

### Flow 3: Public View Access

```
┌─────────────┐                 ┌─────────────┐
│  Browser    │                 │   Backend   │
└──────┬──────┘                 └──────┬──────┘
       │                                │
       │  1. Visit public URL           │
       │     /guides/getting-started    │
       │────────────────────────────────>│
       │  GET /api/v1/public/guides/    │
       │      getting-started            │
       │                                 │
       │  2. Check visibility = public   │
       │  <─────────────────────────────┤
       │     { guide, chapters tree }    │
       │                                 │
       │  3. Render guide + sidebar      │
       │                                 │
       │  4. User clicks chapter         │
       │     /guides/slug/introduction   │
       │────────────────────────────────>│
       │  GET /api/v1/public/guides/    │
       │      slug/chapters/introduction │
       │                                 │
       │  5. Get document content        │
       │  <─────────────────────────────┤
       │     { content_html, nav }       │
       │                                 │
       │  6. Render content + track view │
       │     POST /api/.../views         │
       │                                 │
```

---

### Flow 4: Reorder Chapters (Drag & Drop)

```
┌─────────────┐                 ┌─────────────┐
│  Frontend   │                 │   Backend   │
└──────┬──────┘                 └──────┬──────┘
       │                                │
       │  1. User drags chapter in tree │
       │     "Installation" under "Setup"│
       │                                 │
       │  2. Calculate new order/parent  │
       │     chapter_003:                │
       │       order: 1                  │
       │       parent: chapter_002       │
       │                                 │
       │  3. Send bulk reorder           │
       │────────────────────────────────>│
       │  POST /api/v1/guides/{id}/     │
       │       chapters/reorder          │
       │     { chapters: [...] }         │
       │                                 │
       │  4. Update all chapter.order    │
       │     & parent_chapter_id         │
       │  <─────────────────────────────┤
       │     { success: true }           │
       │                                 │
       │  5. Update UI tree structure    │
       │                                 │
```

---

### Flow 5: Edit Document Content in Guide Context

```
┌─────────────┐                 ┌─────────────┐
│  Frontend   │                 │   Backend   │
└──────┬──────┘                 └──────┬──────┘
       │                                │
       │  1. User clicks "Edit" in guide│
       │     context (sidebar active)    │
       │                                 │
       │  2. Load Tiptap editor          │
       │────────────────────────────────>│
       │  GET /api/documents/{doc_id}    │
       │                                 │
       │  3. Return document content     │
       │  <─────────────────────────────┤
       │     { document_id, content_html }│
       │                                 │
       │  4. Edit content in Tiptap      │
       │     (auto-save every 2s)        │
       │                                 │
       │  5. Save changes                │
       │────────────────────────────────>│
       │  PATCH /api/documents/{doc_id}  │
       │     { content_html }            │
       │                                 │
       │  6. Update documents collection │
       │  <─────────────────────────────┤
       │     { success: true }           │
       │                                 │
       │  7. Changes reflected in guide  │
       │     (refresh guide view to see) │
       │                                 │
```

---

## 🎨 UI/UX Recommendations

### 1. Guide Management Page

**Location:** `/guides` (Dashboard)

**Features:**
- List all user guides (cards)
- Quick actions: Edit, Duplicate, Delete, View Public
- Stats: Views, Chapters, Last Updated
- Create new guide button

---

### 2. Guide Editor Page

**Location:** `/guides/{guide_id}/edit`

**Layout:**
```
┌──────────────────────────────────────────────────┐
│  Getting Started Guide          [Preview] [Publish]│
├────────────────┬─────────────────────────────────┤
│                │                                  │
│  Sidebar Tree  │  Settings Panel                  │
│                │                                  │
│  [+ Add Doc]   │  Title: [.....................]  │
│                │  Slug: [.....................]   │
│  📘 Intro      │  Visibility: [Public ▼]          │
│  📘 Setup      │  Published: [Yes/No Toggle]      │
│    ├─ Install  │                                  │
│    └─ Config   │  Branding:                       │
│                │    Primary Color: [#4F46E5]      │
│  [Drag to      │    Logo: [Upload]                │
│   reorder]     │                                  │
│                │  SEO:                            │
│                │    Meta Title: [............]    │
│                │    Description: [............]   │
│                │                                  │
└────────────────┴─────────────────────────────────┘
```

**Features:**
- Drag & drop to reorder chapters
- Nest chapters (indent/outdent buttons)
- Click chapter → edit document content
- Preview mode → see public view
- Publish toggle → make live

---

### 3. Public Guide View Page

**Location:** `/guides/{guide_slug}` or `/guides/{guide_slug}/{chapter_slug}`

**Layout:**
```
┌──────────────────────────────────────────────────┐
│  [Logo] Getting Started Guide     [Search]       │
├────────────────┬─────────────────────────────────┤
│                │                                  │
│  📘 Introduction│  # Introduction                 │
│  📘 Setup      │                                  │
│    📦 Install  │  Welcome to Getting Started...   │
│    🔧 Config   │                                  │
│  📘 Features   │  ## What is WordAI?              │
│  📘 API        │  WordAI is a powerful...         │
│                │                                  │
│  ────────      │                                  │
│                │                                  │
│  [Edit Guide]  │  [← Previous] [Next →]          │
│  (owner only)  │                                  │
│                │                                  │
└────────────────┴─────────────────────────────────┘
```

**Features:**
- Collapsible sidebar
- Search within guide
- Prev/Next navigation
- Breadcrumbs
- Table of contents (auto-generated from H2/H3)
- Mobile-responsive

---

## 🔐 Security & Permissions

### 1. Owner Permissions

**User can:**
- Create/edit/delete their guides
- Add/remove chapters
- Reorder chapters
- Publish/unpublish guides
- Change visibility settings
- View analytics

---

### 2. Public Access

**Anyone can (if guide is public):**
- View guide content
- Navigate chapters
- Search within guide
- Share links

**Cannot:**
- Edit content
- See hidden chapters
- Access analytics

---

### 3. Private/Unlisted Guides

**Private:** Only owner can view
**Unlisted:** Anyone with link can view (not listed publicly)

---

### 4. Auth Validation

```python
# Owner-only endpoints
@router.post("/api/v1/guides")
async def create_guide(
    request: GuideCreate,
    user_data: Dict = Depends(verify_firebase_token)  # Required
):
    user_id = user_data["uid"]
    # ... create guide for user_id


# Public endpoints (conditional auth)
@router.get("/api/v1/public/guides/{slug}")
async def get_public_guide(
    slug: str,
    user_data: Optional[Dict] = Depends(optional_firebase_token)  # Optional
):
    guide = get_guide_by_slug(slug)

    # Check visibility
    if guide["visibility"] == "private":
        if not user_data or user_data["uid"] != guide["user_id"]:
            raise HTTPException(403, "Guide is private")

    # Return guide
    return guide
```

---

## 📊 Analytics & Tracking

### 1. Guide Analytics

**Track:**
- Total views per guide
- Views per chapter
- Unique visitors
- Referrer sources
- Search queries (internal search)
- Time spent on page

**Storage:** Separate collection `guide_analytics`

```javascript
{
  guide_id: "guide_abc123",
  date: ISODate("2025-11-15"),
  views: 125,
  unique_visitors: 87,
  top_chapters: [
    { chapter_id: "chapter_001", views: 45 },
    { chapter_id: "chapter_002", views: 38 }
  ],
  referrers: {
    "google.com": 42,
    "direct": 30,
    "twitter.com": 13
  }
}
```

---

### 2. Dashboard Stats (Owner View)

**Show:**
- Total guides created
- Total views (all guides)
- Most popular guide
- Recent activity
- Publish status

---

## 🚀 Implementation Plan

### Phase 1: Database & Models (Week 1)

1. Create collections: `user_guides`, `guide_chapters`
2. Create indexes
3. Pydantic models:
   - `GuideCreate`, `GuideUpdate`, `GuideResponse`
   - `ChapterCreate`, `ChapterUpdate`, `ChapterResponse`
4. MongoDB manager methods

---

### Phase 2: Backend API (Week 2)

1. Guide management endpoints
   - POST/GET/PATCH/DELETE `/api/v1/guides`
2. Chapter management endpoints
   - POST/GET/PATCH/DELETE `/api/v1/guides/{id}/chapters`
   - POST `/api/v1/guides/{id}/chapters/reorder`
3. Public view endpoints
   - GET `/api/v1/public/guides/{slug}`
   - GET `/api/v1/public/guides/{slug}/chapters/{chapter_slug}`
4. Document integration
   - GET `/api/documents/{id}/usage`
   - Update DELETE `/api/documents/{id}` with usage check

---

### Phase 3: Frontend - Owner View (Week 3-4)

1. Guide list page (`/guides`)
   - List guides with stats
   - Create guide modal
2. Guide editor page (`/guides/{id}/edit`)
   - Sidebar tree with drag & drop
   - Settings panel
   - Document picker
3. Integration with existing Tiptap editor
   - Edit document in guide context
   - Auto-save functionality

---

### Phase 4: Frontend - Public View (Week 5)

1. Public guide page (`/guides/{slug}`)
   - Responsive layout
   - Sidebar navigation
   - Content rendering
2. SEO optimization
   - Meta tags
   - OpenGraph
   - Sitemap
3. Analytics tracking
   - View counter
   - Event logging

---

### Phase 5: Polish & Deploy (Week 6)

1. Testing
   - Unit tests (backend)
   - E2E tests (frontend)
2. Performance optimization
   - Caching
   - CDN for static assets
3. Documentation
   - API docs (Swagger)
   - User guide (self-hosted!)
4. Deploy to production

---

## 🧪 Testing Checklist

### Backend Tests

- [ ] Create guide (valid/invalid data)
- [ ] Get guide by ID (owner vs non-owner)
- [ ] Update guide (owner only)
- [ ] Delete guide (cascading delete chapters)
- [ ] Add chapter to guide
- [ ] Reorder chapters (bulk update)
- [ ] Remove chapter (keep document intact)
- [ ] Public access (visibility checks)
- [ ] Nested chapters (3 levels deep)
- [ ] Document usage tracking
- [ ] Delete document with guide usage warning

---

### Frontend Tests

- [ ] Create guide form validation
- [ ] Guide list pagination
- [ ] Drag & drop reordering
- [ ] Nest/unnest chapters
- [ ] Add document to guide (picker)
- [ ] Remove chapter confirmation
- [ ] Publish/unpublish toggle
- [ ] Preview mode
- [ ] Public view (desktop/mobile)
- [ ] Navigation (prev/next)
- [ ] Search within guide
- [ ] SEO meta tags rendering

---

## 🔧 Technical Considerations

### 1. Slug Generation

```python
def generate_unique_slug(title: str, user_id: str) -> str:
    """Generate URL-friendly unique slug"""
    import re
    from unidecode import unidecode

    # Convert to ASCII, lowercase, replace spaces
    slug = unidecode(title).lower()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[-\s]+', '-', slug)

    # Check uniqueness
    base_slug = slug
    counter = 1

    while guide_exists(user_id, slug):
        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug
```

---

### 2. Tree Structure Algorithm

```python
def build_chapter_tree(chapters: List[Dict]) -> List[Dict]:
    """Build nested tree from flat chapter list"""
    chapter_map = {c["chapter_id"]: {**c, "children": []} for c in chapters}
    tree = []

    for chapter in chapters:
        if chapter["parent_chapter_id"] is None:
            tree.append(chapter_map[chapter["chapter_id"]])
        else:
            parent = chapter_map.get(chapter["parent_chapter_id"])
            if parent:
                parent["children"].append(chapter_map[chapter["chapter_id"]])

    # Sort by order
    def sort_tree(nodes):
        nodes.sort(key=lambda x: x["order"])
        for node in nodes:
            if node["children"]:
                sort_tree(node["children"])

    sort_tree(tree)
    return tree
```

---

### 3. Caching Strategy

**Redis cache for public guides:**
- Key: `guide:public:{slug}`
- TTL: 5 minutes
- Invalidate on publish/update

```python
async def get_public_guide_cached(slug: str):
    """Get guide with caching"""
    cache_key = f"guide:public:{slug}"

    # Try cache first
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    # Query DB
    guide = await get_guide_by_slug(slug)

    # Cache result
    redis_client.setex(cache_key, 300, json.dumps(guide))

    return guide
```

---

### 4. Performance Optimization

**For large guides (100+ chapters):**
- Lazy load chapter content (only load on click)
- Paginate sidebar (virtual scrolling)
- Cache rendered HTML
- CDN for static assets

**Database indexing:**
- Ensure compound indexes for nested queries
- Monitor query performance with explain()

---

## 📝 Summary

### Required Collections
1. **user_guides** - Guide metadata
2. **guide_chapters** - Chapter organization
3. **documents** - Existing (no changes)

### Required Endpoints
- **8 endpoints** for guide management
- **6 endpoints** for chapter management
- **3 endpoints** for public view
- **1 endpoint** for document usage

### Key Features
- ✅ GitBook-style navigation
- ✅ Nested chapters (3 levels)
- ✅ Drag & drop reordering
- ✅ Public/private/unlisted visibility
- ✅ Reusable documents
- ✅ SEO optimization
- ✅ Analytics tracking

### Estimated Timeline
**6 weeks** for full implementation (backend + frontend + testing)

---

*Document version: 1.0*
*Last updated: 2025-11-15*
*Author: AI Assistant*
