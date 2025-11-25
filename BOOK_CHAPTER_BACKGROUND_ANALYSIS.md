# 📋 PHÂN TÍCH: Background A4 Cho Book & Chapter

**Ngày:** November 25, 2025
**Mục tiêu:** Thêm tính năng background có thể edit cho Book (toàn bộ) và Chapter (riêng lẻ) với kích thước A4

---

## 1. 🎯 YÊU CẦU CHỨC NĂNG

### A. Background Types
| Type | Description | Fields Required | AI Support |
|------|-------------|----------------|------------|
| **solid** | Màu thuần | `color` | ❌ |
| **gradient** | Gradient 2-3 màu | `gradient_colors[]`, `gradient_direction` | ❌ |
| **theme** | Preset themes | `theme_id` | ❌ |
| **ai_image** | AI generate | `prompt`, `image_url` (after gen) | ✅ Gemini 3 Pro Image |
| **custom_image** | Upload | `image_url` | ❌ |

### B. Apply Scope
```
Book Level
  ├─ Background applies to ALL chapters by default
  └─ Stored in: books.background_config

Chapter Level (Optional Override)
  ├─ Override book background for specific chapter
  ├─ Stored in: book_chapters.background_config
  └─ Flag: use_book_background (true/false)
```

### C. A4 Size Specifications
- **Width**: 210mm (8.27 inches) → 794px @ 96 DPI
- **Height**: 297mm (11.69 inches) → 1123px @ 96 DPI
- **Aspect Ratio**: 1:√2 (1:1.414)
- **Recommended Resolution**: 2480 × 3508 px (300 DPI for print)

---

## 2. 📊 DATABASE SCHEMA

### A. MongoDB Collections Update

#### `online_books` Collection
```javascript
{
  "book_id": "book_abc123",
  "title": "Python Programming Guide",
  "background_config": {
    // NEW FIELD
    "type": "ai_image",           // solid|gradient|theme|ai_image|custom_image
    "color": null,                // For type='solid': "#FF5733"
    "gradient_colors": null,       // For type='gradient': ["#FF5733", "#C70039", "#900C3F"]
    "gradient_direction": null,    // "to-br" | "to-tr" | "to-bl" | "to-tl" | "to-r" | "to-b"
    "theme_id": null,              // For type='theme': "ocean" | "forest" | "sunset" | "minimal"
    "image_url": "https://static.wordai.pro/ai-generated-images/user_123/bg_abc.png",
    "image_opacity": 0.3,          // 0.0 - 1.0
    "image_size": "cover",         // "cover" | "contain" | "auto"

    // Text Overlay (Optional)
    "show_text_overlay": false,
    "overlay_text": null,
    "overlay_position": "center",  // center|top|bottom|top-left|top-right|bottom-left|bottom-right
    "overlay_text_color": "#FFFFFF",
    "overlay_text_size": "2xl",    // sm|base|lg|xl|2xl|3xl|4xl
    "overlay_font_weight": "bold", // normal|medium|semibold|bold

    // A4 Specific
    "page_size": "A4",             // A4 | A5 | Letter | Legal
    "orientation": "portrait",     // portrait | landscape

    // Generation Metadata (for AI images)
    "ai_metadata": {
      "prompt": "Modern minimalist tech background with gradients",
      "model": "gemini-3-pro-image-preview",
      "generated_at": "2025-11-25T10:30:00Z",
      "generation_time_ms": 3500,
      "cost_points": 2
    }
  }
}
```

#### `book_chapters` Collection
```javascript
{
  "chapter_id": "ch_xyz789",
  "book_id": "book_abc123",
  "title": "Chapter 1: Introduction",

  // NEW FIELDS
  "use_book_background": true,   // If true, inherit from book. If false, use chapter background
  "background_config": null,     // Same structure as book background_config, only used if use_book_background=false

  // Example: Chapter with custom override
  "use_book_background": false,
  "background_config": {
    "type": "solid",
    "color": "#F9FAFB",
    "page_size": "A4",
    "orientation": "portrait"
  }
}
```

### B. Pydantic Models (FastAPI)

```python
# src/models/book_background_models.py

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime

class AIMetadata(BaseModel):
    """AI generation metadata"""
    prompt: str
    model: str = "gemini-3-pro-image-preview"
    generated_at: datetime
    generation_time_ms: int
    cost_points: int = 2

class BackgroundConfig(BaseModel):
    """Background configuration for book or chapter"""

    # Background type
    type: Literal["solid", "gradient", "theme", "ai_image", "custom_image"] = Field(
        ..., description="Type of background"
    )

    # Type: solid
    color: Optional[str] = Field(
        None, pattern="^#[0-9A-Fa-f]{6}$", description="Hex color for solid background"
    )

    # Type: gradient
    gradient_colors: Optional[List[str]] = Field(
        None, min_items=2, max_items=4, description="Array of hex colors for gradient"
    )
    gradient_direction: Optional[Literal[
        "to-br", "to-tr", "to-bl", "to-tl", "to-r", "to-b", "to-t", "to-l"
    ]] = Field(None, description="Tailwind gradient direction")

    # Type: theme
    theme_id: Optional[Literal[
        "ocean", "forest", "sunset", "minimal", "dark", "light", "tech", "vintage"
    ]] = Field(None, description="Preset theme ID")

    # Type: ai_image or custom_image
    image_url: Optional[str] = Field(None, description="Image URL")
    image_opacity: Optional[float] = Field(
        0.3, ge=0.0, le=1.0, description="Image overlay opacity"
    )
    image_size: Optional[Literal["cover", "contain", "auto"]] = Field(
        "cover", description="CSS background-size"
    )

    # Text overlay
    show_text_overlay: bool = Field(False, description="Show text overlay on background")
    overlay_text: Optional[str] = Field(None, max_length=200)
    overlay_position: Optional[Literal[
        "center", "top", "bottom", "top-left", "top-right", "bottom-left", "bottom-right"
    ]] = Field("center")
    overlay_text_color: Optional[str] = Field("#FFFFFF", pattern="^#[0-9A-Fa-f]{6}$")
    overlay_text_size: Optional[Literal[
        "sm", "base", "lg", "xl", "2xl", "3xl", "4xl"
    ]] = Field("2xl")
    overlay_font_weight: Optional[Literal[
        "normal", "medium", "semibold", "bold"
    ]] = Field("bold")

    # Page settings
    page_size: Optional[Literal["A4", "A5", "Letter", "Legal"]] = Field("A4")
    orientation: Optional[Literal["portrait", "landscape"]] = Field("portrait")

    # AI metadata (only for ai_image type)
    ai_metadata: Optional[AIMetadata] = None

class GenerateBackgroundRequest(BaseModel):
    """Request to generate AI background"""
    prompt: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Detailed description for background generation"
    )
    aspect_ratio: str = Field(
        "3:4",
        description="A4 portrait ratio (3:4 approximation)"
    )
    style: Optional[str] = Field(
        None,
        description="Style modifier (minimalist, modern, abstract, etc.)"
    )

class UpdateBookBackgroundRequest(BaseModel):
    """Update book background"""
    background_config: BackgroundConfig

class UpdateChapterBackgroundRequest(BaseModel):
    """Update chapter background"""
    use_book_background: bool = Field(
        True,
        description="If true, use book background. If false, use custom background"
    )
    background_config: Optional[BackgroundConfig] = Field(
        None,
        description="Custom background config (required if use_book_background=false)"
    )

class BackgroundResponse(BaseModel):
    """Response with background info"""
    success: bool
    background_config: Optional[BackgroundConfig] = None
    message: Optional[str] = None
```

---

## 3. 🔌 API ENDPOINTS

### A. Book Background Endpoints

#### 1. **Generate AI Background for Book**
```http
POST /api/v1/books/{book_id}/background/generate
Authorization: Bearer <firebase_token>
Content-Type: application/json

{
  "prompt": "Modern minimalist tech background with blue gradients and subtle geometric patterns",
  "aspect_ratio": "3:4",
  "style": "minimalist"
}

Response 200:
{
  "success": true,
  "image_url": "https://static.wordai.pro/ai-generated-images/user_123/bg_abc.png",
  "r2_key": "ai-generated-images/user_123/bg_abc.png",
  "file_id": "lib_xyz123",
  "prompt_used": "Create A4 portrait background (3:4 ratio): Modern minimalist tech background...",
  "generation_time_ms": 3500,
  "points_deducted": 2,
  "ai_metadata": {
    "model": "gemini-3-pro-image-preview",
    "generated_at": "2025-11-25T10:30:00Z"
  }
}

Response 402:
{
  "error": "INSUFFICIENT_POINTS",
  "message": "Không đủ điểm để tạo background",
  "points_needed": 2,
  "points_available": 0
}
```

#### 2. **Update Book Background**
```http
PUT /api/v1/books/{book_id}/background
Authorization: Bearer <firebase_token>
Content-Type: application/json

{
  "background_config": {
    "type": "ai_image",
    "image_url": "https://static.wordai.pro/ai-generated-images/user_123/bg_abc.png",
    "image_opacity": 0.3,
    "image_size": "cover",
    "show_text_overlay": true,
    "overlay_text": "Python Programming",
    "overlay_position": "center",
    "overlay_text_color": "#FFFFFF",
    "page_size": "A4",
    "orientation": "portrait"
  }
}

Response 200:
{
  "success": true,
  "background_config": { /* updated config */ },
  "message": "Book background updated successfully"
}
```

#### 3. **Get Book Background**
```http
GET /api/v1/books/{book_id}/background
Authorization: Bearer <firebase_token> (optional for public books)

Response 200:
{
  "book_id": "book_abc123",
  "background_config": {
    "type": "gradient",
    "gradient_colors": ["#667eea", "#764ba2"],
    "gradient_direction": "to-br",
    "page_size": "A4",
    "orientation": "portrait"
  }
}
```

#### 4. **Delete Book Background (Reset to Default)**
```http
DELETE /api/v1/books/{book_id}/background
Authorization: Bearer <firebase_token>

Response 200:
{
  "success": true,
  "message": "Book background reset to default"
}
```

---

### B. Chapter Background Endpoints

#### 1. **Update Chapter Background**
```http
PUT /api/v1/books/{book_id}/chapters/{chapter_id}/background
Authorization: Bearer <firebase_token>
Content-Type: application/json

# Case 1: Use book background
{
  "use_book_background": true
}

# Case 2: Custom chapter background
{
  "use_book_background": false,
  "background_config": {
    "type": "solid",
    "color": "#F9FAFB",
    "page_size": "A4",
    "orientation": "portrait"
  }
}

Response 200:
{
  "success": true,
  "chapter_id": "ch_xyz789",
  "use_book_background": false,
  "background_config": { /* config */ },
  "message": "Chapter background updated successfully"
}
```

#### 2. **Get Chapter Background**
```http
GET /api/v1/books/{book_id}/chapters/{chapter_id}/background
Authorization: Bearer <firebase_token> (optional for public)

Response 200:
{
  "chapter_id": "ch_xyz789",
  "use_book_background": false,
  "background_config": {
    "type": "solid",
    "color": "#F9FAFB"
  },
  "inherited_from_book": false
}
```

#### 3. **Reset Chapter Background (Use Book's)**
```http
DELETE /api/v1/books/{book_id}/chapters/{chapter_id}/background
Authorization: Bearer <firebase_token>

Response 200:
{
  "success": true,
  "message": "Chapter background reset to use book background"
}
```

---

### C. Background Themes Endpoint

#### **Get Available Themes**
```http
GET /api/v1/backgrounds/themes

Response 200:
{
  "themes": [
    {
      "id": "ocean",
      "name": "Ocean Blue",
      "preview_colors": ["#0077be", "#1e90ff", "#87ceeb"],
      "type": "gradient",
      "direction": "to-br"
    },
    {
      "id": "forest",
      "name": "Forest Green",
      "preview_colors": ["#228b22", "#32cd32", "#90ee90"],
      "type": "gradient",
      "direction": "to-br"
    },
    {
      "id": "sunset",
      "name": "Warm Sunset",
      "preview_colors": ["#ff6b6b", "#ee5a6f", "#c44569"],
      "type": "gradient",
      "direction": "to-br"
    },
    {
      "id": "minimal",
      "name": "Minimal White",
      "preview_colors": ["#ffffff"],
      "type": "solid"
    }
  ]
}
```

---

## 4. 🔧 BACKEND IMPLEMENTATION

### A. Service Layer

```python
# src/services/book_background_service.py

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import uuid

from src.services.gemini_image_service import get_gemini_image_service
from src.models.book_background_models import (
    BackgroundConfig,
    GenerateBackgroundRequest,
    AIMetadata
)

logger = logging.getLogger(__name__)

class BookBackgroundService:
    """Service for managing book/chapter backgrounds"""

    def __init__(self, db):
        self.db = db
        self.gemini_service = get_gemini_image_service()

    async def generate_ai_background(
        self,
        user_id: str,
        request: GenerateBackgroundRequest
    ) -> Dict[str, Any]:
        """
        Generate AI background using Gemini 3 Pro Image

        Returns:
            - image_url: R2 public URL
            - r2_key: Storage key
            - file_id: Library file ID
            - ai_metadata: Generation metadata
        """
        # Build A4-optimized prompt
        a4_prompt = self._build_a4_prompt(request.prompt, request.style)

        # Generate image
        result = await self.gemini_service.generate_image(
            prompt=a4_prompt,
            generation_type="background_a4",
            user_options={"style": request.style},
            aspect_ratio=request.aspect_ratio  # "3:4" for A4 portrait
        )

        # Upload to R2
        filename = f"background_a4_{uuid.uuid4().hex[:8]}.png"
        upload_result = await self.gemini_service.upload_to_r2(
            image_bytes=result["image_bytes"],
            user_id=user_id,
            filename=filename
        )

        # Save to library
        from src.models.image_generation_models import ImageGenerationMetadata
        metadata = ImageGenerationMetadata(
            source="gemini-3-pro-image-preview",
            generation_type="background_a4",
            prompt=request.prompt,
            aspect_ratio=request.aspect_ratio,
            generation_time_ms=result["generation_time_ms"],
            model_version="gemini-3-pro-image-preview",
            user_options={"style": request.style, "page_size": "A4"}
        )

        library_doc = await self.gemini_service.save_to_library(
            user_id=user_id,
            filename=filename,
            file_size=result["image_size"],
            r2_key=upload_result["r2_key"],
            file_url=upload_result["file_url"],
            generation_metadata=metadata,
            db=self.db
        )

        return {
            "image_url": upload_result["file_url"],
            "r2_key": upload_result["r2_key"],
            "file_id": library_doc["file_id"],
            "prompt_used": a4_prompt,
            "generation_time_ms": result["generation_time_ms"],
            "ai_metadata": {
                "prompt": request.prompt,
                "model": "gemini-3-pro-image-preview",
                "generated_at": datetime.now(timezone.utc),
                "generation_time_ms": result["generation_time_ms"],
                "cost_points": 2
            }
        }

    def _build_a4_prompt(self, user_prompt: str, style: Optional[str]) -> str:
        """Build A4-optimized prompt for Gemini"""
        prompt_parts = [
            "Create a high-quality A4 portrait background image (3:4 aspect ratio, 210mm × 297mm).",
            "",
            f"BACKGROUND DESCRIPTION: {user_prompt}",
            "",
            "REQUIREMENTS:",
            "- Suitable for document/book chapter backgrounds",
            "- Professional and clean design",
            "- Not too busy or distracting",
            "- Good contrast for text overlay",
            "- Print-ready quality"
        ]

        if style:
            prompt_parts.append(f"- Style: {style}")

        return "\n".join(prompt_parts)

    def update_book_background(
        self,
        book_id: str,
        user_id: str,
        config: BackgroundConfig
    ) -> Optional[Dict[str, Any]]:
        """Update book background configuration"""
        result = self.db.online_books.find_one_and_update(
            {"book_id": book_id, "user_id": user_id},
            {
                "$set": {
                    "background_config": config.dict(exclude_none=True),
                    "updated_at": datetime.now(timezone.utc)
                }
            },
            return_document=True
        )

        if result:
            logger.info(f"✅ Updated book background: {book_id}")
            return result
        return None

    def get_book_background(self, book_id: str) -> Optional[Dict[str, Any]]:
        """Get book background configuration"""
        book = self.db.online_books.find_one(
            {"book_id": book_id},
            {"background_config": 1}
        )
        return book.get("background_config") if book else None

    def delete_book_background(self, book_id: str, user_id: str) -> bool:
        """Reset book background to default"""
        result = self.db.online_books.update_one(
            {"book_id": book_id, "user_id": user_id},
            {
                "$unset": {"background_config": ""},
                "$set": {"updated_at": datetime.now(timezone.utc)}
            }
        )
        return result.modified_count > 0

    def update_chapter_background(
        self,
        book_id: str,
        chapter_id: str,
        user_id: str,
        use_book_background: bool,
        config: Optional[BackgroundConfig] = None
    ) -> Optional[Dict[str, Any]]:
        """Update chapter background configuration"""
        update_data = {
            "use_book_background": use_book_background,
            "updated_at": datetime.now(timezone.utc)
        }

        if use_book_background:
            # Reset to use book background
            update_data["background_config"] = None
        else:
            # Use custom chapter background
            if not config:
                raise ValueError("background_config required when use_book_background=false")
            update_data["background_config"] = config.dict(exclude_none=True)

        # Verify book ownership
        book = self.db.online_books.find_one(
            {"book_id": book_id, "user_id": user_id}
        )
        if not book:
            return None

        result = self.db.book_chapters.find_one_and_update(
            {"chapter_id": chapter_id, "book_id": book_id},
            {"$set": update_data},
            return_document=True
        )

        if result:
            logger.info(f"✅ Updated chapter background: {chapter_id}")
            return result
        return None

    def get_chapter_background(
        self,
        book_id: str,
        chapter_id: str
    ) -> Dict[str, Any]:
        """Get chapter background (with fallback to book)"""
        chapter = self.db.book_chapters.find_one(
            {"chapter_id": chapter_id, "book_id": book_id},
            {"use_book_background": 1, "background_config": 1}
        )

        if not chapter:
            return None

        use_book_bg = chapter.get("use_book_background", True)

        if use_book_bg:
            # Get book background
            book_bg = self.get_book_background(book_id)
            return {
                "chapter_id": chapter_id,
                "use_book_background": True,
                "background_config": book_bg,
                "inherited_from_book": True
            }
        else:
            # Use chapter background
            return {
                "chapter_id": chapter_id,
                "use_book_background": False,
                "background_config": chapter.get("background_config"),
                "inherited_from_book": False
            }

# Singleton
_book_background_service = None

def get_book_background_service(db) -> BookBackgroundService:
    global _book_background_service
    if _book_background_service is None:
        _book_background_service = BookBackgroundService(db)
    return _book_background_service
```

---

### B. Route Handlers

```python
# src/api/book_background_routes.py

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any
import logging

from src.middleware.firebase_auth import get_current_user
from src.database.db_manager import DBManager
from src.services.book_background_service import get_book_background_service
from src.services.book_manager import UserBookManager
from src.services.points_service import get_points_service
from src.models.book_background_models import (
    GenerateBackgroundRequest,
    UpdateBookBackgroundRequest,
    UpdateChapterBackgroundRequest,
    BackgroundResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/books", tags=["Book Backgrounds"])

db_manager = DBManager()
db = db_manager.db
book_manager = UserBookManager(db)

POINTS_COST_BACKGROUND = 2  # Same as cover generation

@router.post("/{book_id}/background/generate")
async def generate_book_background(
    book_id: str,
    request: GenerateBackgroundRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Generate AI background for book using Gemini 3 Pro Image"""
    user_id = current_user["uid"]

    # Verify book ownership
    book = book_manager.get_book(book_id)
    if not book or book["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Check points
    points_service = get_points_service()
    check = await points_service.check_sufficient_points(
        user_id=user_id,
        points_needed=POINTS_COST_BACKGROUND,
        service="ai_background_generation"
    )

    if not check["has_points"]:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "INSUFFICIENT_POINTS",
                "points_needed": POINTS_COST_BACKGROUND,
                "points_available": check["points_available"]
            }
        )

    # Generate background
    bg_service = get_book_background_service(db)
    result = await bg_service.generate_ai_background(user_id, request)

    # Deduct points
    await points_service.deduct_points(
        user_id=user_id,
        amount=POINTS_COST_BACKGROUND,
        service="ai_background_generation",
        description=f"AI background: {request.prompt[:50]}"
    )

    return {
        "success": True,
        **result,
        "points_deducted": POINTS_COST_BACKGROUND
    }

@router.put("/{book_id}/background")
async def update_book_background(
    book_id: str,
    request: UpdateBookBackgroundRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update book background configuration"""
    user_id = current_user["uid"]

    bg_service = get_book_background_service(db)
    result = bg_service.update_book_background(
        book_id, user_id, request.background_config
    )

    if not result:
        raise HTTPException(status_code=404, detail="Book not found")

    return BackgroundResponse(
        success=True,
        background_config=request.background_config,
        message="Book background updated successfully"
    )

@router.get("/{book_id}/background")
async def get_book_background(book_id: str):
    """Get book background configuration"""
    bg_service = get_book_background_service(db)
    config = bg_service.get_book_background(book_id)

    return {
        "book_id": book_id,
        "background_config": config
    }

@router.delete("/{book_id}/background")
async def delete_book_background(
    book_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Reset book background to default"""
    user_id = current_user["uid"]

    bg_service = get_book_background_service(db)
    success = bg_service.delete_book_background(book_id, user_id)

    if not success:
        raise HTTPException(status_code=404, detail="Book not found")

    return {"success": True, "message": "Book background reset"}

@router.put("/{book_id}/chapters/{chapter_id}/background")
async def update_chapter_background(
    book_id: str,
    chapter_id: str,
    request: UpdateChapterBackgroundRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update chapter background configuration"""
    user_id = current_user["uid"]

    bg_service = get_book_background_service(db)
    result = bg_service.update_chapter_background(
        book_id,
        chapter_id,
        user_id,
        request.use_book_background,
        request.background_config
    )

    if not result:
        raise HTTPException(status_code=404, detail="Chapter not found")

    return {
        "success": True,
        "chapter_id": chapter_id,
        "use_book_background": request.use_book_background,
        "background_config": request.background_config,
        "message": "Chapter background updated successfully"
    }

@router.get("/{book_id}/chapters/{chapter_id}/background")
async def get_chapter_background(book_id: str, chapter_id: str):
    """Get chapter background (with fallback to book)"""
    bg_service = get_book_background_service(db)
    result = bg_service.get_chapter_background(book_id, chapter_id)

    if not result:
        raise HTTPException(status_code=404, detail="Chapter not found")

    return result

# Preset Themes Endpoint
@router.get("/backgrounds/themes", tags=["Background Themes"])
async def get_background_themes():
    """Get available preset background themes"""
    return {
        "themes": [
            {
                "id": "ocean",
                "name": "Ocean Blue",
                "preview_colors": ["#0077be", "#1e90ff", "#87ceeb"],
                "type": "gradient",
                "direction": "to-br"
            },
            {
                "id": "forest",
                "name": "Forest Green",
                "preview_colors": ["#228b22", "#32cd32", "#90ee90"],
                "type": "gradient",
                "direction": "to-br"
            },
            {
                "id": "sunset",
                "name": "Warm Sunset",
                "preview_colors": ["#ff6b6b", "#ee5a6f", "#c44569"],
                "type": "gradient",
                "direction": "to-br"
            },
            {
                "id": "minimal",
                "name": "Minimal White",
                "preview_colors": ["#ffffff"],
                "type": "solid"
            },
            {
                "id": "dark",
                "name": "Dark Mode",
                "preview_colors": ["#1f2937"],
                "type": "solid"
            },
            {
                "id": "tech",
                "name": "Tech Purple",
                "preview_colors": ["#667eea", "#764ba2"],
                "type": "gradient",
                "direction": "to-br"
            }
        ]
    }
```

---

## 5. 🎨 FRONTEND INTEGRATION

### A. API Calls (TypeScript)

```typescript
// lib/api/bookBackground.ts

export interface BackgroundConfig {
  type: 'solid' | 'gradient' | 'theme' | 'ai_image' | 'custom_image';
  color?: string;
  gradient_colors?: string[];
  gradient_direction?: string;
  theme_id?: string;
  image_url?: string;
  image_opacity?: number;
  image_size?: 'cover' | 'contain' | 'auto';
  show_text_overlay?: boolean;
  overlay_text?: string;
  overlay_position?: string;
  overlay_text_color?: string;
  page_size?: 'A4' | 'A5' | 'Letter';
  orientation?: 'portrait' | 'landscape';
}

export async function generateBookBackground(
  bookId: string,
  prompt: string,
  style?: string
): Promise<GenerateBackgroundResponse> {
  const res = await fetch(`/api/v1/books/${bookId}/background/generate`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${await getFirebaseToken()}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ prompt, style, aspect_ratio: '3:4' })
  });

  if (!res.ok) throw new Error('Failed to generate background');
  return res.json();
}

export async function updateBookBackground(
  bookId: string,
  config: BackgroundConfig
): Promise<void> {
  const res = await fetch(`/api/v1/books/${bookId}/background`, {
    method: 'PUT',
    headers: {
      'Authorization': `Bearer ${await getFirebaseToken()}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ background_config: config })
  });

  if (!res.ok) throw new Error('Failed to update background');
}

export async function getBookBackground(bookId: string): Promise<BackgroundConfig | null> {
  const res = await fetch(`/api/v1/books/${bookId}/background`);
  const data = await res.json();
  return data.background_config;
}
```

### B. React Component Integration

```tsx
// components/BackgroundPreview.tsx

import { BackgroundConfig } from '@/lib/api/bookBackground';

export function BackgroundPreview({
  config
}: {
  config: BackgroundConfig
}) {
  const getBackgroundStyle = () => {
    switch (config.type) {
      case 'solid':
        return { backgroundColor: config.color };

      case 'gradient':
        return {
          backgroundImage: `linear-gradient(${config.gradient_direction}, ${config.gradient_colors?.join(', ')})`
        };

      case 'ai_image':
      case 'custom_image':
        return {
          backgroundImage: `url(${config.image_url})`,
          backgroundSize: config.image_size || 'cover',
          backgroundPosition: 'center'
        };

      default:
        return {};
    }
  };

  return (
    <div
      className="relative w-[210mm] h-[297mm] overflow-hidden"
      style={getBackgroundStyle()}
    >
      {config.show_text_overlay && config.overlay_text && (
        <div className={`
          absolute flex items-center justify-center
          ${config.overlay_position === 'center' ? 'inset-0' : ''}
          ${config.overlay_position === 'top' ? 'top-8 left-0 right-0' : ''}
        `}>
          <h1
            className={`text-${config.overlay_text_size} font-${config.overlay_font_weight}`}
            style={{ color: config.overlay_text_color }}
          >
            {config.overlay_text}
          </h1>
        </div>
      )}

      {/* Chapter content */}
      <div className="relative z-10 p-8">
        {/* Content here */}
      </div>
    </div>
  );
}
```

---

## 6. 📝 MIGRATION SCRIPT

```python
# scripts/add_background_fields.py

from src.database.db_manager import DBManager
from datetime import datetime, timezone

def migrate_add_background_fields():
    """Add background_config fields to existing books and chapters"""
    db_manager = DBManager()
    db = db_manager.db

    # Add background_config to books (set to null initially)
    result_books = db.online_books.update_many(
        {"background_config": {"$exists": False}},
        {"$set": {"background_config": None}}
    )

    print(f"✅ Updated {result_books.modified_count} books with background_config field")

    # Add background fields to chapters
    result_chapters = db.book_chapters.update_many(
        {"use_book_background": {"$exists": False}},
        {
            "$set": {
                "use_book_background": True,
                "background_config": None
            }
        }
    )

    print(f"✅ Updated {result_chapters.modified_count} chapters with background fields")

if __name__ == "__main__":
    migrate_add_background_fields()
```

---

## 7. ✅ TESTING CHECKLIST

### Backend Tests
- [ ] Generate AI background (2 points deduction)
- [ ] Insufficient points error
- [ ] Update book background (all types)
- [ ] Get book background
- [ ] Delete book background
- [ ] Update chapter background (use_book_background=true)
- [ ] Update chapter background (use_book_background=false)
- [ ] Get chapter background (inherited from book)
- [ ] Get chapter background (custom)
- [ ] Get preset themes

### Frontend Tests
- [ ] BackgroundForm component integration
- [ ] A4 preview rendering
- [ ] Background preview (solid, gradient, theme, image)
- [ ] Text overlay rendering
- [ ] Chapter inherits book background
- [ ] Chapter custom background override

---

## 8. 📊 COST ESTIMATION

| Action | Points Cost | Notes |
|--------|-------------|-------|
| Generate AI Background | 2 points | Same as book cover |
| Update Background (non-AI) | 0 points | Free (color, gradient, theme) |
| Storage (R2) | Included | Part of R2 subscription |

**Expected Usage:**
- Average book: 1 AI background (2 points)
- Average book with custom chapters: 1-3 additional chapter backgrounds (0-6 points if AI)
- **Total: 2-8 points per book** (depending on AI usage)

---

## 9. 🚀 DEPLOYMENT PLAN

### Phase 1: Backend (Week 1)
1. Add Pydantic models
2. Create service layer
3. Add API routes
4. Migration script
5. Unit tests

### Phase 2: Frontend (Week 2)
1. Integrate BackgroundForm component
2. Add API calls
3. Background preview component
4. Chapter editor integration
5. E2E tests

### Phase 3: Polish (Week 3)
1. Performance optimization
2. Error handling
3. Documentation
4. Beta testing
5. Production rollout

---

## 10. 📚 RELATED FEATURES

- ✅ **Gemini Image Generation** (already implemented)
- ✅ **Book Cover AI** (already implemented)
- ✅ **R2 Storage** (already implemented)
- ✅ **Library Files** (already implemented)
- 🔲 **PDF Export with Background** (future)
- 🔲 **Print Preview** (future)
- 🔲 **Template Library** (future)

---

**Document Version:** 1.0
**Last Updated:** November 25, 2025
**Status:** Ready for Implementation ✅
