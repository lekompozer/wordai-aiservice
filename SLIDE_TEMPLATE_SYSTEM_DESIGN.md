# Slide Template System - Design Specification

**Last Updated:** January 6, 2026
**Purpose:** Allow users to save and reuse slide designs as templates

---

## 📋 Overview

The Slide Template System enables users to:
1. **Save** any slide as a reusable template
2. **Organize** templates in their personal library
3. **Apply** templates to any slide in their presentations
4. **Access** both system-provided and user-created templates

---

## 🏗️ Architecture

### Two Template Types

#### 1. System Templates (Built-in)
- **Source:** Pre-designed by WordAI team
- **Storage:** Frontend static assets or CDN
- **Access:** All users can view and use
- **Management:** Frontend-only (no database CRUD)
- **Examples:**
  - Title slides (5-10 variations)
  - Content slides (list, 2-column, 3-column)
  - Conclusion slides
  - Image showcase slides

#### 2. User Templates (Custom)
- **Source:** User-created from their own slides
- **Storage:** MongoDB `slide_templates` collection
- **Access:** Private to each user
- **Management:** Full CRUD via API
- **Limit:** Optional (e.g., 50 templates per user for free tier)

---

## 🗄️ Database Schema

### Collection: `slide_templates`

```javascript
{
  _id: ObjectId("..."),
  template_id: "tmpl_abc123def456",  // Unique template ID
  user_id: "firebase_uid_here",      // Owner

  // Metadata
  name: "Blue Gradient Title Slide",  // User-defined name
  description: "Professional title slide with blue gradient",
  category: "title" | "content" | "conclusion" | "custom",
  tags: ["professional", "blue", "gradient"],

  // Template data (extracted from original slide)
  template_html: "<div class=\"slide\" ...>...</div>",  // Full slide HTML
  thumbnail_url: "https://cdn.wordai.pro/templates/thumb_abc123.png",  // Auto-generated screenshot

  // Style extraction (for easier preview)
  background: "linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%)",
  font_family: "'Inter', 'SF Pro Display', sans-serif",
  primary_color: "#3b82f6",
  layout_type: "two-column" | "single-column" | "title" | "custom",

  // Usage tracking
  usage_count: 0,  // How many times user applied this template
  last_used_at: ISODate("2026-01-06T09:00:00.000Z"),

  // Timestamps
  created_at: ISODate("2026-01-05T10:00:00.000Z"),
  updated_at: ISODate("2026-01-05T10:00:00.000Z"),

  // Source tracking (optional)
  source_document_id: "doc_original123",  // Original document
  source_slide_index: 5,  // Original slide number

  // Sharing (future feature)
  is_public: false,
  is_marketplace: false,  // Allow selling templates
  price_points: 0
}
```

### Indexes

```javascript
// Required indexes for performance
db.slide_templates.createIndex({ user_id: 1, created_at: -1 });
db.slide_templates.createIndex({ template_id: 1 }, { unique: true });
db.slide_templates.createIndex({ user_id: 1, category: 1 });
db.slide_templates.createIndex({ user_id: 1, tags: 1 });
```

---

## 🔌 API Endpoints

### 1. Save Slide as Template (CREATE)

**POST** `/api/slides/templates`

**Authentication:** Required

**Request Body:**
```json
{
  "document_id": "doc_abc123",
  "slide_index": 5,
  "template_name": "My Awesome Title Slide",
  "description": "Blue gradient with centered text",
  "category": "title",
  "tags": ["professional", "blue", "title"]
}
```

**Backend Flow:**
1. Get document from MongoDB
2. Extract slide HTML from `content_html` using `slide_index`
3. Generate thumbnail (screenshot of slide HTML → PNG)
4. Upload thumbnail to storage (GCS/S3)
5. Extract style properties (background, fonts, colors)
6. Generate unique `template_id`
7. Insert into `slide_templates` collection
8. Return template metadata

**Response:**
```json
{
  "success": true,
  "template": {
    "template_id": "tmpl_abc123def456",
    "name": "My Awesome Title Slide",
    "thumbnail_url": "https://cdn.wordai.pro/templates/thumb_abc123.png",
    "created_at": "2026-01-06T09:00:00.000Z"
  }
}
```

**Error Cases:**
- 403: Slide limit reached (free users: 50 templates)
- 404: Document or slide not found
- 400: Invalid slide_index

---

### 2. List User Templates (READ)

**GET** `/api/slides/templates?category=title&limit=20&offset=0`

**Authentication:** Required

**Query Parameters:**
- `category` (optional): Filter by category
- `tags` (optional): Filter by tags (comma-separated)
- `search` (optional): Search in name/description
- `limit` (optional, default 20): Pagination
- `offset` (optional, default 0): Pagination

**Response:**
```json
{
  "success": true,
  "templates": [
    {
      "template_id": "tmpl_abc123",
      "name": "Blue Gradient Title",
      "description": "Professional title slide",
      "category": "title",
      "tags": ["professional", "blue"],
      "thumbnail_url": "https://...",
      "usage_count": 5,
      "created_at": "2026-01-05T10:00:00.000Z"
    }
  ],
  "total": 42,
  "has_more": true
}
```

---

### 3. Get Template Details (READ)

**GET** `/api/slides/templates/{template_id}`

**Authentication:** Required

**Response:**
```json
{
  "success": true,
  "template": {
    "template_id": "tmpl_abc123",
    "name": "Blue Gradient Title",
    "description": "Professional title slide",
    "category": "title",
    "tags": ["professional", "blue"],
    "thumbnail_url": "https://...",
    "template_html": "<div class=\"slide\" ...>...</div>",
    "background": "linear-gradient(...)",
    "font_family": "Inter",
    "primary_color": "#3b82f6",
    "layout_type": "title",
    "usage_count": 5,
    "created_at": "2026-01-05T10:00:00.000Z"
  }
}
```

---

### 4. Update Template (UPDATE)

**PATCH** `/api/slides/templates/{template_id}`

**Authentication:** Required

**Request Body:**
```json
{
  "name": "Updated Template Name",
  "description": "New description",
  "category": "content",
  "tags": ["modern", "clean"]
}
```

**Response:**
```json
{
  "success": true,
  "template": {
    "template_id": "tmpl_abc123",
    "name": "Updated Template Name",
    "updated_at": "2026-01-06T09:30:00.000Z"
  }
}
```

---

### 5. Delete Template (DELETE)

**DELETE** `/api/slides/templates/{template_id}`

**Authentication:** Required

**Response:**
```json
{
  "success": true,
  "message": "Template deleted successfully"
}
```

---

### 6. Apply Template to Slide (Frontend + Backend)

**POST** `/api/slides/templates/{template_id}/apply`

**Authentication:** Required

**Request Body:**
```json
{
  "document_id": "doc_abc123",
  "slide_index": 3,
  "preserve_content": true  // Keep existing text/images, only apply styles
}
```

**Backend Flow:**
1. Get template from `slide_templates`
2. Get target document from `documents`
3. Extract target slide from `content_html`
4. **If `preserve_content: true`:**
   - Extract text/images from target slide
   - Apply template's styles (background, fonts, layout)
   - Merge content back into template structure
5. **If `preserve_content: false`:**
   - Replace entire slide with template HTML
6. Update `content_html` in document
7. Increment template `usage_count`
8. Update template `last_used_at`

**Response:**
```json
{
  "success": true,
  "slide_updated": true,
  "slide_index": 3
}
```

---

## 🎨 Frontend Implementation

### User Flow: Save as Template

1. **Right-click on slide** in editor
2. Context menu shows: "Save as Template"
3. Click → Opens modal:
   ```
   ┌─────────────────────────────────────┐
   │  Save Slide as Template             │
   ├─────────────────────────────────────┤
   │  Template Name: [_______________]   │
   │  Description:   [_______________]   │
   │  Category:      [Dropdown ▼]        │
   │  Tags:          [+ Add tag]         │
   │                                     │
   │  Preview: [Slide thumbnail]         │
   │                                     │
   │  [Cancel]  [Save Template]          │
   └─────────────────────────────────────┘
   ```
4. Fill form → Click "Save Template"
5. **API Call:** `POST /api/slides/templates`
6. Show success notification
7. Template appears in "My Templates" panel

### User Flow: Apply Template

1. **Click "Templates" icon** in toolbar
2. Opens templates panel (sidebar or modal):
   ```
   ┌─────────────────────────────────────┐
   │  Templates                          │
   ├─────────────────────────────────────┤
   │  System Templates  | My Templates   │
   ├─────────────────────────────────────┤
   │  [Filter: All ▼] [Search...]        │
   │                                     │
   │  ┌──────┐  ┌──────┐  ┌──────┐      │
   │  │      │  │      │  │      │      │
   │  │Title │  │Content│  │Blue │      │
   │  │Slide │  │List  │  │Grad │      │
   │  └──────┘  └──────┘  └──────┘      │
   │                                     │
   │  [+ Create New Template]            │
   └─────────────────────────────────────┘
   ```
3. **Click on template** → Preview appears
4. **Click "Apply to Current Slide"**
5. Options modal:
   ```
   Apply template to slide?
   ○ Replace entire slide
   ● Keep content, apply styles only

   [Cancel] [Apply]
   ```
6. **API Call:** `POST /api/slides/templates/{id}/apply`
7. Slide updates in editor

---

## 🔐 Security & Permissions

### Access Control
- Users can only see/edit/delete their own templates
- System templates are read-only
- Template `template_html` is sanitized before storage
- XSS protection: Strip `<script>` tags

### Validation
```python
def validate_template_html(html: str) -> bool:
    """Ensure template HTML is safe"""
    # No script tags
    if "<script" in html.lower():
        return False
    # Must have slide wrapper
    if 'class="slide"' not in html:
        return False
    # Size limit (e.g., 500KB)
    if len(html) > 500_000:
        return False
    return True
```

### Rate Limiting
- Save template: 10/hour per user
- Apply template: 100/hour per user
- List templates: 100/hour per user

---

## 📊 Analytics & Tracking

### User Metrics
- Total templates created
- Most used template
- Template application count
- Popular categories

### System Metrics
- Total user templates in system
- Average templates per user
- Most popular template styles

---

## 🚀 Implementation Priority

### Phase 1: MVP (Week 1-2)
- [ ] Database schema & indexes
- [ ] API endpoints (CRUD)
- [ ] Save slide as template
- [ ] List user templates
- [ ] Apply template to slide

### Phase 2: Enhanced Features (Week 3)
- [ ] Template thumbnails (screenshot generation)
- [ ] Categories & tags
- [ ] Search & filter
- [ ] Template preview

### Phase 3: Advanced (Future)
- [ ] System template library
- [ ] Template marketplace (buy/sell)
- [ ] Template sharing with team
- [ ] Template versioning
- [ ] AI template suggestions

---

## 💡 Technical Considerations

### Thumbnail Generation

**Option 1: Playwright/Puppeteer (Server-side)**
```python
from playwright.async_api import async_playwright

async def generate_template_thumbnail(html: str) -> bytes:
    """Generate PNG thumbnail from slide HTML"""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})
        await page.set_content(html)
        screenshot = await page.screenshot(type="png")
        await browser.close()
        return screenshot
```

**Option 2: Client-side (Frontend)**
- Use `html2canvas` library
- Faster, no server load
- Upload screenshot to backend

### Style Extraction

```python
import re
from bs4 import BeautifulSoup

def extract_slide_styles(html: str) -> dict:
    """Extract key styles from slide HTML"""
    soup = BeautifulSoup(html, "html.parser")
    slide_div = soup.find("div", class_="slide")

    style = slide_div.get("style", "")

    # Extract background
    bg_match = re.search(r"background:\s*([^;]+);", style)
    background = bg_match.group(1) if bg_match else None

    # Extract font-family
    font_match = re.search(r"font-family:\s*([^;]+);", style)
    font_family = font_match.group(1) if font_match else None

    return {
        "background": background,
        "font_family": font_family,
        "layout_type": detect_layout_type(soup)
    }

def detect_layout_type(soup) -> str:
    """Detect slide layout from HTML structure"""
    # Count columns in grid
    if soup.find("div", style=re.compile(r"grid-template-columns.*1fr 1fr")):
        return "two-column"
    elif soup.find("h1") and not soup.find("p"):
        return "title"
    return "single-column"
```

---

## 📝 Code Structure

### New Files to Create

```
src/
├── api/
│   └── slide_template_routes.py       # API endpoints
├── services/
│   ├── slide_template_service.py      # Business logic
│   └── template_thumbnail_service.py  # Thumbnail generation
├── models/
│   └── slide_template_models.py       # Pydantic models
└── utils/
    └── slide_html_parser.py           # HTML extraction/merging
```

### Example Service Method

```python
# src/services/slide_template_service.py

from typing import Optional, List
from src.database.db_manager import DBManager
from src.models.slide_template_models import SlideTemplate, CreateTemplateRequest

class SlideTemplateService:
    def __init__(self):
        self.db = DBManager().db
        self.templates = self.db["slide_templates"]

    async def create_template(
        self,
        user_id: str,
        request: CreateTemplateRequest
    ) -> SlideTemplate:
        """Save slide as template"""

        # 1. Get source document
        doc = self.db.documents.find_one({"document_id": request.document_id})
        if not doc:
            raise ValueError("Document not found")

        # 2. Extract slide HTML
        slide_html = self._extract_slide_html(
            doc["content_html"],
            request.slide_index
        )

        # 3. Generate thumbnail
        thumbnail_url = await self._generate_thumbnail(slide_html)

        # 4. Extract styles
        styles = self._extract_styles(slide_html)

        # 5. Create template document
        template_id = f"tmpl_{generate_id()}"
        template_doc = {
            "template_id": template_id,
            "user_id": user_id,
            "name": request.name,
            "description": request.description,
            "category": request.category,
            "tags": request.tags,
            "template_html": slide_html,
            "thumbnail_url": thumbnail_url,
            **styles,
            "usage_count": 0,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "source_document_id": request.document_id,
            "source_slide_index": request.slide_index
        }

        # 6. Insert into database
        result = self.templates.insert_one(template_doc)

        return SlideTemplate(**template_doc)

    async def apply_template(
        self,
        template_id: str,
        document_id: str,
        slide_index: int,
        preserve_content: bool = True
    ) -> bool:
        """Apply template to a slide"""

        # 1. Get template
        template = self.templates.find_one({"template_id": template_id})
        if not template:
            raise ValueError("Template not found")

        # 2. Get target document
        doc = self.db.documents.find_one({"document_id": document_id})
        if not doc:
            raise ValueError("Document not found")

        # 3. Extract target slide
        target_slide_html = self._extract_slide_html(
            doc["content_html"],
            slide_index
        )

        # 4. Merge template with content
        if preserve_content:
            new_slide_html = self._merge_template_with_content(
                template["template_html"],
                target_slide_html
            )
        else:
            new_slide_html = template["template_html"]

        # 5. Update document
        updated_html = self._replace_slide_html(
            doc["content_html"],
            slide_index,
            new_slide_html
        )

        self.db.documents.update_one(
            {"document_id": document_id},
            {"$set": {"content_html": updated_html}}
        )

        # 6. Update template usage
        self.templates.update_one(
            {"template_id": template_id},
            {
                "$inc": {"usage_count": 1},
                "$set": {"last_used_at": datetime.utcnow()}
            }
        )

        return True
```

---

## ✅ Summary

**What Frontend Does:**
- Display System Templates (static library)
- Show user's saved templates from API
- Right-click menu to save slide as template
- Apply template button/modal
- Template preview & search

**What Backend Does:**
- CRUD operations on `slide_templates` collection
- Extract slide HTML from documents
- Generate thumbnails (optional)
- Merge template styles with existing content
- Track usage statistics
- Validate & sanitize template HTML

**What MongoDB Stores:**
- User templates in `slide_templates` collection
- Each template has: name, description, HTML, thumbnail, styles, metadata
- Indexed by: user_id, template_id, category, tags

This design allows flexible template management with minimal backend complexity while giving users powerful customization options.
