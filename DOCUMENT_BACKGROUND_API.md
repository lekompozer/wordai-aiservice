# Document Background API Guide

## Overview

A4 documents giờ hỗ trợ **background configuration** giống như Books và Chapters - cho phép:
- Solid colors
- Gradients
- AI-generated images
- Custom uploaded images
- Predefined themes

**Nhất quán với:**
- ✅ Book backgrounds
- ✅ Chapter backgrounds
- ✅ Slide backgrounds

---

## API Endpoints

Base URL: `/api/document-backgrounds`

### 1. Update Document Background

**PUT** `/api/document-backgrounds/{document_id}`

Set hoặc update background cho A4 document.

**Headers:**
```
Authorization: Bearer {firebase_token}
```

**Request Body:**
```json
{
  "config": {
    "type": "ai_image",
    "image": {
      "url": "https://cdn.r2.wordai.vn/files/user123/background.png",
      "overlay_opacity": 0.3,
      "overlay_color": "#000000"
    },
    "ai_metadata": {
      "prompt": "Professional document background",
      "model": "gemini-3-pro-image-preview",
      "generated_at": "2026-01-05T10:00:00Z",
      "generation_time_ms": 3500,
      "cost_points": 2
    }
  }
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "document_id": "doc_abc123",
  "background_config": {
    "type": "ai_image",
    "image": {
      "url": "https://cdn.r2.wordai.vn/files/user123/background.png",
      "overlay_opacity": 0.3,
      "overlay_color": "#000000"
    }
  }
}
```

**Error Response (404):**
```json
{
  "detail": "Document not found or access denied"
}
```

---

### 2. Get Document Background

**GET** `/api/document-backgrounds/{document_id}`

Lấy background configuration của document.

**Headers:**
```
Authorization: Bearer {firebase_token}
```

**Response (200 OK):**
```json
{
  "document_id": "doc_abc123",
  "background_config": {
    "type": "gradient",
    "gradient": {
      "colors": ["#667eea", "#764ba2"],
      "type": "linear",
      "angle": 135
    }
  }
}
```

**Response (No Background):**
```json
{
  "document_id": "doc_abc123",
  "background_config": null
}
```

---

### 3. Delete Document Background

**DELETE** `/api/document-backgrounds/{document_id}`

Xóa background (reset về trắng mặc định).

**Headers:**
```
Authorization: Bearer {firebase_token}
```

**Response (200 OK):**
```json
{
  "success": true,
  "document_id": "doc_abc123",
  "message": "Background removed successfully"
}
```

**Error Response (404):**
```json
{
  "detail": "Document not found or background already empty"
}
```

---

## Background Configuration Schema

### Type: `solid`
```json
{
  "type": "solid",
  "color": "#ffffff"
}
```

### Type: `gradient`
```json
{
  "type": "gradient",
  "gradient": {
    "colors": ["#667eea", "#764ba2"],
    "type": "linear",
    "angle": 135
  }
}
```

**Gradient Types:**
- `linear` - Linear gradient (default)
- `radial` - Radial gradient
- `conic` - Conic gradient

### Type: `theme`
```json
{
  "type": "theme",
  "theme": "ocean"
}
```

**Predefined Themes:**
- `ocean` - Ocean waves
- `forest` - Forest green
- `newspaper` - Newspaper texture
- `book_page` - Aged book page
- `leather` - Leather texture
- `minimalist` - Minimalist design
- `modern` - Modern tech
- (Frontend quản lý theme registry)

### Type: `ai_image`
```json
{
  "type": "ai_image",
  "image": {
    "url": "https://cdn.r2.wordai.vn/...",
    "overlay_opacity": 0.3,
    "overlay_color": "#000000"
  },
  "ai_metadata": {
    "prompt": "Professional document background",
    "model": "gemini-3-pro-image-preview",
    "generated_at": "2026-01-05T10:00:00Z",
    "generation_time_ms": 3500,
    "cost_points": 2
  }
}
```

### Type: `custom_image`
```json
{
  "type": "custom_image",
  "image": {
    "url": "https://cdn.r2.wordai.vn/user_uploads/...",
    "overlay_opacity": 0.2,
    "overlay_color": "#ffffff"
  }
}
```

---

## Generate AI Background

**Để tạo AI background, sử dụng endpoint chung:**

**POST** `/api/book-backgrounds/generate`

```json
{
  "prompt": "Professional corporate document background, minimalist",
  "aspect_ratio": "3:4",
  "style": "minimalist",
  "generation_type": "book_cover"
}
```

**Response:**
```json
{
  "success": true,
  "image_url": "https://cdn.r2.wordai.vn/files/user123/background_a4_xyz.png",
  "r2_key": "files/user123/background_a4_xyz.png",
  "file_id": "img_xyz789",
  "prompt_used": "Create a high-quality A4 portrait background...",
  "generation_time_ms": 3500,
  "points_deducted": 2,
  "ai_metadata": {
    "prompt": "Professional corporate...",
    "model": "gemini-3-pro-image-preview",
    "generated_at": "2026-01-05T10:00:00Z",
    "generation_time_ms": 3500,
    "cost_points": 2
  }
}
```

**Sau đó, dùng `image_url` để update document background:**
```json
{
  "config": {
    "type": "ai_image",
    "image": {
      "url": "{{image_url}}",
      "overlay_opacity": 0.3
    },
    "ai_metadata": {
      "prompt": "Professional corporate...",
      "model": "gemini-3-pro-image-preview",
      "generated_at": "2026-01-05T10:00:00Z",
      "generation_time_ms": 3500,
      "cost_points": 2
    }
  }
}
```

---

## Frontend Integration

### 1. Tạo AI Background cho Document

```typescript
// Step 1: Generate AI background
const generateResponse = await fetch('/api/book-backgrounds/generate', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${firebaseToken}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    prompt: "Professional document background, clean and minimal",
    aspect_ratio: "3:4",
    style: "minimalist",
    generation_type: "book_cover"
  })
});

const bgData = await generateResponse.json();

// Step 2: Apply to document
const updateResponse = await fetch(`/api/document-backgrounds/${documentId}`, {
  method: 'PUT',
  headers: {
    'Authorization': `Bearer ${firebaseToken}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    config: {
      type: "ai_image",
      image: {
        url: bgData.image_url,
        overlay_opacity: 0.3,
        overlay_color: "#000000"
      },
      ai_metadata: bgData.ai_metadata
    }
  })
});
```

### 2. Set Gradient Background

```typescript
await fetch(`/api/document-backgrounds/${documentId}`, {
  method: 'PUT',
  headers: {
    'Authorization': `Bearer ${firebaseToken}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    config: {
      type: "gradient",
      gradient: {
        colors: ["#667eea", "#764ba2"],
        type: "linear",
        angle: 135
      }
    }
  })
});
```

### 3. Get Current Background

```typescript
const response = await fetch(`/api/document-backgrounds/${documentId}`, {
  headers: {
    'Authorization': `Bearer ${firebaseToken}`
  }
});

const data = await response.json();
// data.background_config sẽ là null nếu chưa set
```

### 4. Remove Background

```typescript
await fetch(`/api/document-backgrounds/${documentId}`, {
  method: 'DELETE',
  headers: {
    'Authorization': `Bearer ${firebaseToken}`
  }
});
```

---

## MongoDB Schema

Documents collection (`documents`):

```javascript
{
  "_id": ObjectId("..."),
  "document_id": "doc_abc123",
  "user_id": "firebase_user_id",
  "title": "Company Report",
  "document_type": "doc",  // A4 document
  "content_html": "<div>...</div>",

  // ⭐ NEW: Background configuration
  "background_config": {
    "type": "ai_image",
    "image": {
      "url": "https://cdn.r2.wordai.vn/...",
      "overlay_opacity": 0.3,
      "overlay_color": "#000000"
    },
    "ai_metadata": {
      "prompt": "Professional document background",
      "model": "gemini-3-pro-image-preview",
      "generated_at": ISODate("2026-01-05T10:00:00Z"),
      "generation_time_ms": 3500,
      "cost_points": 2
    }
  },

  "created_at": ISODate("..."),
  "last_saved_at": ISODate("...")
}
```

---

## Implementation Details

### Backend Services

**1. DocumentManager** (`src/services/document_manager.py`)
- `create_document()` - Thêm param `background_config`
- `update_document()` - Thêm param `background_config`

**2. BookBackgroundService** (`src/services/book_background_service.py`)
- `update_document_background()` - Set background cho document
- `get_document_background()` - Get background từ document
- `delete_document_background()` - Xóa background

**3. API Routes** (`src/api/book_background_routes.py`)
- `PUT /api/document-backgrounds/{document_id}` - Update
- `GET /api/document-backgrounds/{document_id}` - Get
- `DELETE /api/document-backgrounds/{document_id}` - Delete

---

## Comparison: Slide vs Book vs Document

| Feature | Slides | Books/Chapters | Documents (A4) |
|---------|--------|----------------|----------------|
| Background per item | ✅ `slide_backgrounds` array | ✅ `background_config` | ✅ `background_config` |
| Solid colors | ✅ | ✅ | ✅ |
| Gradients | ✅ | ✅ | ✅ |
| Themes | ❌ | ✅ | ✅ |
| AI images | ✅ | ✅ | ✅ |
| Custom images | ✅ | ✅ | ✅ |
| Inherit from parent | ❌ | ✅ (chapter from book) | ❌ |
| Item-level config | ✅ Per slide | ✅ Per chapter | ✅ Per document |

**Key Differences:**
- **Slides**: Mỗi slide có background riêng → Array of backgrounds
- **Books**: Book có 1 background, chapter có thể inherit hoặc override
- **Documents**: Mỗi document có 1 background → Single config object

---

## Common Use Cases

### 1. Professional Reports
```json
{
  "type": "gradient",
  "gradient": {
    "colors": ["#1e3a8a", "#3b82f6"],
    "type": "linear",
    "angle": 135
  }
}
```

### 2. Academic Papers
```json
{
  "type": "theme",
  "theme": "book_page"
}
```

### 3. Marketing Documents
```json
{
  "type": "ai_image",
  "image": {
    "url": "https://cdn.r2.wordai.vn/...",
    "overlay_opacity": 0.2,
    "overlay_color": "#ffffff"
  }
}
```

### 4. Minimalist Docs
```json
{
  "type": "solid",
  "color": "#f8fafc"
}
```

---

## Error Handling

### Insufficient Points (AI Generation)
```json
{
  "detail": {
    "error": "INSUFFICIENT_POINTS",
    "message": "Không đủ điểm...",
    "points_needed": 2,
    "points_available": 0
  }
}
```

### Document Not Found
```json
{
  "detail": "Document not found or access denied"
}
```

### Invalid Background Type
```json
{
  "detail": "Invalid background type. Must be: solid, gradient, theme, ai_image, custom_image"
}
```

---

## Notes

1. **Ownership Check**: Tất cả endpoints đều verify `user_id` match
2. **Points Cost**: AI generation = 2 points (same as book covers)
3. **Aspect Ratio**: Documents dùng 3:4 (A4 portrait)
4. **Reusable**: Background có thể share giữa documents/books/chapters
5. **Frontend Control**: Themes được frontend quản lý, backend chỉ lưu tên

---

**Last Updated:** January 5, 2026
**Version:** 1.0
**Status:** Production Ready ✅
