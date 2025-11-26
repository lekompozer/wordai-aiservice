# Book & Chapter Background API - Technical Specification

## Overview

API endpoints cho phép quản lý background (hình nền) của sách và chương, bao gồm tạo background bằng AI, sử dụng preset themes, hoặc tùy chỉnh màu sắc/gradient. Chapter có thể kế thừa background từ sách hoặc sử dụng background riêng.

**Base URL Production:** `https://ai.wordai.pro/api/v1/books`

**Base URL Local:** `http://localhost:8000/api/v1/books`

**Version:** 1.1

**Authentication:** Bearer token trong header `Authorization: Bearer {token}`

---

## Background Types

Hệ thống hỗ trợ 5 loại background:

| Type | Mô tả |
|------|-------|
| `solid` | Màu đơn sắc |
| `gradient` | Gradient 2 màu (linear, radial, hoặc conic) |
| `theme` | Preset theme - **Frontend tự render** (8 themes) |
| `ai_image` | Background được tạo bởi AI (Gemini 3 Pro Image) |
| `custom_image` | Upload hình ảnh tùy chỉnh |

---

## Background Configuration Schema

### Simplified Structure

Backend chỉ lưu minimal data, frontend tự xử lý rendering (đặc biệt là themes).

```json
{
  "type": "solid | gradient | theme | ai_image | custom_image",

  // Type: solid - chỉ cần hex color
  "color": "#ffffff",

  // Type: gradient - nested object
  "gradient": {
    "colors": ["#hex1", "#hex2"],
    "type": "linear | radial | conic",
    "angle": 135
  },

  // Type: theme - CHỈ LƯU TÊN (frontend tự render)
  "theme": "ocean | forest | sunset | minimal | dark | light | tech | vintage",

  // Type: ai_image hoặc custom_image - nested object
  "image": {
    "url": "https://static.wordai.pro/...",  // R2 public URL from env
    "overlay_opacity": 0.3,
    "overlay_color": "#000000"
  },

  // AI metadata - tự động thêm khi type = ai_image
  "ai_metadata": {
    "prompt": "user prompt",
    "model": "gemini-3-pro-image-preview",
    "generated_at": "2025-11-25T10:00:00Z",
    "generation_time_ms": 3500,
    "cost_points": 2
  }
}
```

### Field Rules

**Type: solid**
- Required: `color` (hex format: `#RRGGBB`)

**Type: gradient**
- Required: `gradient.colors` (array of exactly 2 hex colors)
- Required: `gradient.type` (`"linear"`, `"radial"`, hoặc `"conic"`)
- Optional: `gradient.angle` (0-360 degrees, default: 135)

**Type: theme**
- Required: `theme` (one of 8 theme names)
- **Frontend handles rendering** - backend chỉ validate và lưu tên

**Type: ai_image hoặc custom_image**
- Required: `image.url` (R2 URL)
- Optional: `image.overlay_opacity` (0.0-1.0)
- Optional: `image.overlay_color` (hex format)

**AI Metadata** (auto-populated for ai_image)
- Automatically added by backend sau khi generate
- Read-only fields

---

## API Endpoints

**Note:** Tất cả endpoints đều có prefix `/api/v1/books` (VD: `https://ai.wordai.pro/api/v1/books/{book_id}/background`)

### 1. Generate AI Background

Tạo background bằng AI dựa trên text prompt. Tốn **2 points** từ user balance.

**Endpoint:** `POST /{book_id}/background/generate`

**Authentication:** Required (Bearer token)

**Path Parameters:**
- `book_id` (string, required): Book ID

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `prompt` | string | Yes | Mô tả background muốn tạo (10-500 chars) |
| `aspect_ratio` | string | No | Tỷ lệ khung hình: `"16:9"`, `"1:1"`, `"3:4"`. Default: `"3:4"` (A4 portrait) |
| `style` | string | No | Phong cách: `"realistic"`, `"illustration"`, `"minimalist"`, `"watercolor"`, `"abstract"` |

**Success Response (200):**

```json
{
  "success": true,
  "image_url": "https://static.wordai.pro/backgrounds/user123/bg_a1b2c3d4.png",
  "r2_key": "backgrounds/user123/bg_a1b2c3d4.png",
  "file_id": "674...",
  "prompt_used": "Full optimized prompt sent to AI...",
  "generation_time_ms": 3500,
  "points_deducted": 2,
  "ai_metadata": {
    "prompt": "original user prompt",
    "model": "gemini-3-pro-image-preview",
    "generated_at": "2025-11-25T10:00:00Z",
    "generation_time_ms": 3500,
    "cost_points": 2
  }
}
```

**Error Responses:**

- `400 Bad Request`: Invalid prompt, aspect_ratio, hoặc style
- `401 Unauthorized`: Token không hợp lệ
- `403 Forbidden`: Không đủ points (min 2 points)
- `404 Not Found`: Book không tồn tại hoặc user không phải owner
- `500 Internal Server Error`: Lỗi AI generation hoặc R2 upload

---

### 2. Update Book Background

Cập nhật background configuration cho sách.
### 2. Update Book Background

Cập nhật background configuration cho sách.

**Endpoint:** `PUT /{book_id}/background`

**Authentication:** Required (Bearer token)

**Path Parameters:**
- `book_id` (string, required): Book ID

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `background_config` | object | Yes | Background configuration object (xem phần Background Configuration Schema) |

**Example Request Bodies:**

**Solid color:**
```json
{
  "background_config": {
    "type": "solid",
    "color": "#ffffff"
  }
}
```

**Gradient:**
```json
{
  "background_config": {
    "type": "gradient",
    "gradient": {
      "colors": ["#ff6b6b", "#4ecdc4"],
      "type": "linear",
      "angle": 135
    }
  }
}
```

**Theme (ĐƠN GIẢN NHẤT - chỉ lưu tên):**
```json
{
  "background_config": {
    "type": "theme",
    "theme": "ocean"
  }
}
```

**AI Image with overlay:**
```json
{
  "background_config": {
    "type": "ai_image",
    "image": {
      "url": "https://static.wordai.pro/backgrounds/user123/bg_abc123.png",
      "overlay_opacity": 0.3,
      "overlay_color": "#000000"
    }
  }
}
```

**Success Response (200):**

```json
{
  "success": true,
  "background_config": {
    "type": "theme",
    "theme": "ocean"
  },
  "message": "Background updated successfully"
}
```

**Error Responses:**

- `400 Bad Request`: Invalid background_config, missing required fields, hoặc hex color không hợp lệ
- `401 Unauthorized`: Token không hợp lệ
- `404 Not Found`: Book không tồn tại hoặc user không phải owner

---

### 3. Get Book Background

Lấy background configuration của sách. **Public endpoint** - không cần authentication.

**Endpoint:** `GET /{book_id}/background`

**Authentication:** Optional

**Path Parameters:**
- `book_id` (string, required): Book ID

**Success Response (200):**

```json
{
  "book_id": "67...",
  "background_config": {
    "type": "gradient",
    "gradient": {
      "colors": ["#ff6b6b", "#4ecdc4"],
      "type": "linear",
      "angle": 45
    }
  }
}
```

**Response khi chưa có background:**

```json
{
  "book_id": "67...",
  "background_config": null
}
```

**Error Responses:**

- `404 Not Found`: Book không tồn tại

---

### 4. Delete Book Background

Reset background của sách về default (null).

**Endpoint:** `DELETE /{book_id}/background`

**Authentication:** Required (Bearer token)

**Path Parameters:**
- `book_id` (string, required): Book ID

**Success Response (200):**

```json
{
  "success": true,
  "message": "Background đã được reset về default"
}
```

**Error Responses:**

- `401 Unauthorized`: Token không hợp lệ
- `404 Not Found`: Book không tồn tại hoặc user không phải owner

---

### 5. Update Chapter Background

Cập nhật background configuration cho chapter. Chapter có thể:
- Kế thừa background từ sách (`use_book_background: true`)
- Sử dụng background riêng (`use_book_background: false` + `background_config`)

**Endpoint:** `PUT /{book_id}/chapters/{chapter_id}/background`

**Authentication:** Required (Bearer token)

**Path Parameters:**
- `book_id` (string, required): Book ID
- `chapter_id` (string, required): Chapter ID

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `use_book_background` | boolean | Yes | `true`: kế thừa từ sách, `false`: dùng riêng |
| `background_config` | object | Conditional | Bắt buộc khi `use_book_background = false` |

**Example Request - Kế thừa từ sách:**
```json
{
  "use_book_background": true
}
```

**Example Request - Background riêng (solid):**
```json
{
  "use_book_background": false,
  "background_config": {
    "type": "solid",
    "color": "#f0f0f0"
  }
}
```

**Example Request - Background riêng (theme):**
```json
{
  "use_book_background": false,
  "background_config": {
    "type": "theme",
    "theme": "minimal"
  }
}
```

**Success Response (200):**

```json
{
  "success": true,
  "book_id": "67...",
  "chapter_id": "67...",
  "use_book_background": false,
  "background_config": {
    "type": "theme",
    "theme": "minimal"
  },
  "message": "Chapter background updated"
}
```

**Error Responses:**

- `400 Bad Request`: Missing background_config khi use_book_background = false
- `401 Unauthorized`: Token không hợp lệ
- `404 Not Found`: Book hoặc chapter không tồn tại, hoặc user không phải owner

---

### 6. Get Chapter Background

Lấy background configuration của chapter. **Public endpoint** - không cần authentication.

Nếu chapter dùng `use_book_background: true`, API sẽ tự động trả về background của sách.

**Endpoint:** `GET /{book_id}/chapters/{chapter_id}/background`

**Authentication:** Optional

**Path Parameters:**
- `book_id` (string, required): Book ID
- `chapter_id` (string, required): Chapter ID

**Success Response (200) - Chapter có background riêng:**

```json
{
  "book_id": "67...",
  "chapter_id": "67...",
  "use_book_background": false,
  "background_config": {
    "type": "theme",
    "theme": "forest"
  }
}
```

**Success Response (200) - Chapter kế thừa từ sách:**

```json
{
  "book_id": "67...",
  "chapter_id": "67...",
  "use_book_background": true,
  "background_config": {
    "type": "gradient",
    "gradient": {
      "colors": ["#667eea", "#764ba2"],
      "type": "linear",
      "angle": 45
    }
  }
}
```

**Response khi cả chapter và book đều chưa có background:**

```json
{
  "book_id": "67...",
  "chapter_id": "67...",
  "use_book_background": true,
  "background_config": null
}
```

**Error Responses:**

- `404 Not Found`: Book hoặc chapter không tồn tại

---

### 7. Delete Chapter Background

Reset chapter về trạng thái kế thừa background từ sách.

**Endpoint:** `DELETE /{book_id}/chapters/{chapter_id}/background`

**Authentication:** Required (Bearer token)

**Path Parameters:**
- `book_id` (string, required): Book ID
- `chapter_id` (string, required): Chapter ID

**Success Response (200):**

```json
{
  "success": true,
  "message": "Chapter background đã được reset về kế thừa từ sách"
}
```

**Error Responses:**

- `401 Unauthorized`: Token không hợp lệ
- `404 Not Found`: Book hoặc chapter không tồn tại, hoặc user không phải owner

---

### 8. Upload Custom Background Image

Upload hình ảnh tùy chỉnh để sử dụng làm background.

**Endpoint:** `POST /upload-background`

**Note:** Endpoint này **KHÔNG có prefix** `/api/v1/books`

**Full URL:** `https://ai.wordai.pro/upload-background` (production) hoặc `http://localhost:8000/upload-background` (local)

**Authentication:** Required (Bearer token)

**Request:** Multipart form data

**Form Fields:**
- `file` (file, required): Image file to upload

**File Requirements:**
- **Format**: JPG, PNG, WebP
- **Max size**: 10MB
- **Recommended resolution**: 1754x2480px (3:4 aspect ratio for A4 portrait)

**Success Response (200):**

```json
{
  "success": true,
  "image_url": "https://static.wordai.pro/backgrounds/user123/bg_1234567890.png",
  "r2_key": "backgrounds/user123/bg_1234567890.png",
  "file_id": "674...",
  "file_size": 524288,
  "content_type": "image/png"
}
```

**Usage:** Sau khi upload thành công, sử dụng `image_url` trong background config:

```json
{
  "background_config": {
    "type": "custom_image",
    "image": {
      "url": "https://static.wordai.pro/backgrounds/user123/bg_1234567890.png",
      "overlay_opacity": 0.2,
      "overlay_color": "#000000"
    }
  }
}
```

**Error Responses:**

- `400 Bad Request`: Invalid file type hoặc file quá lớn
- `401 Unauthorized`: Token không hợp lệ
- `500 Internal Server Error`: Upload failed

---

## Preset Themes (Frontend Handles)

❌ **Không có endpoint GET /backgrounds/themes** - Backend không cung cấp themes list

✅ **Frontend tự quản lý themes trong constants**

Backend chỉ validate theme name khi update (1 trong 8 themes: `ocean`, `forest`, `sunset`, `minimal`, `dark`, `light`, `tech`, `vintage`)

**Frontend Theme Registry Example:**

```typescript
// Frontend constants - không cần fetch từ backend
const THEMES = {
  ocean: {
    name: "Ocean Blue",
    gradient: { colors: ["#667eea", "#764ba2"], type: "linear", angle: 135 }
  },
  forest: {
    name: "Forest Green",
    gradient: { colors: ["#134e5e", "#71b280"], type: "linear", angle: 45 }
  },
  sunset: {
    name: "Sunset Orange",
    gradient: { colors: ["#ff6b6b", "#feca57"], type: "linear", angle: 180 }
  },
  minimal: {
    name: "Minimal White",
    solid: { color: "#f8f9fa" }
  },
  dark: {
    name: "Dark Theme",
    solid: { color: "#1a1a1a" }
  },
  light: {
    name: "Light Theme",
    solid: { color: "#ffffff" }
  },
  tech: {
    name: "Tech Blue",
    gradient: { colors: ["#2193b0", "#6dd5ed"], type: "linear", angle: 90 }
  },
  vintage: {
    name: "Vintage Paper",
    solid: { color: "#f4e5d3" }
  }
};
```

**Backend validation:**
- Khi `type === "theme"`, validate `theme` field chỉ chứa 1 trong 8 tên trên
- Backend **KHÔNG** lưu gradient/color details của theme
- Backend CHỈ lưu theme name
        "gradient_type": "linear",
        "gradient_angle": 45
      }
    },
    {
      "name": "sunset",
      "display_name": "Sunset Orange",
      "description": "Warm sunset colors",
      "config": {
        "type": "gradient",
        "gradient_colors": ["#ff6b6b", "#feca57"],
        "gradient_type": "linear",
        "gradient_angle": 180
      }
    },
    {
      "name": "minimal",
      "display_name": "Minimal Gray",
      "description": "Clean minimal gray background",
      "config": {
        "type": "solid",
        "solid_color": "#f8f9fa"
      }
    },
    {
      "name": "dark",
      "display_name": "Dark Theme",
      "description": "Professional dark background",
      "config": {
        "type": "solid",
        "solid_color": "#1a1a1a"
      }
    },
    {
      "name": "light",
      "display_name": "Light Theme",
      "description": "Clean white background",
      "config": {
        "type": "solid",
        "solid_color": "#ffffff"
      }
    },
    {
      "name": "tech",
      "display_name": "Tech Blue",
      "description": "Modern tech-inspired blue gradient",
      "config": {
        "type": "gradient",
        "gradient_colors": ["#2193b0", "#6dd5ed"],
        "gradient_type": "linear",
        "gradient_angle": 90
      }
    },
    {
      "name": "vintage",
      "display_name": "Vintage Paper",
      "description": "Aged paper texture feel",
      "config": {
        "type": "solid",
        "solid_color": "#f4e5d3"
      }
    }
  ]
}
```

---

## Common Error Response Format

Tất cả error responses đều có format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

**HTTP Status Codes:**

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad Request - Invalid input, validation failed |
| 401 | Unauthorized - Missing or invalid token |
| 403 | Forbidden - Insufficient points hoặc permissions |
| 404 | Not Found - Resource không tồn tại |
| 500 | Internal Server Error - Server-side error |

---

## Validation Rules

### Hex Color Validation
- Format: `#` + 6 hex characters (e.g., `#ff6b6b`)
- Regex: `^#[0-9A-Fa-f]{6}$`
- Case-insensitive

### Gradient Validation
- `gradient.colors`: Array phải có đúng 2 màu hex hợp lệ
- `gradient.type`: Chỉ chấp nhận `"linear"`, `"radial"`, hoặc `"conic"`
- `gradient.angle`: Số từ 0-360 (degrees), optional default 135

### Theme Validation
- `theme`: Phải là 1 trong 8 giá trị: `ocean`, `forest`, `sunset`, `minimal`, `dark`, `light`, `tech`, `vintage`
- Backend **CHỈ** validate và lưu theme name
- Frontend tự render theme dựa trên name

### Image Validation
- `image.url`: Bắt buộc, phải là valid URL (thường là R2 URL)
- `image.overlay_opacity`: Optional, range 0.0-1.0
- `image.overlay_color`: Optional, phải là hex color hợp lệ

### AI Prompt Validation
- Minimum length: 10 characters
- Maximum length: 500 characters
- Không chứa HTML tags hoặc special characters nguy hiểm

### Aspect Ratio Validation
- Chỉ chấp nhận: `"16:9"`, `"1:1"`, `"3:4"`
- Default: `"3:4"` (A4 portrait - 210mm × 297mm)

### Style Validation
- Chỉ chấp nhận: `"realistic"`, `"illustration"`, `"minimalist"`, `"watercolor"`, `"abstract"`
- Optional field

---

## Business Logic & Rules

### Simplified Schema Design

**Backend responsibility:**
- Validate input data (hex colors, theme names, required fields)
- Store minimal configuration
- Serve data to frontend

**Frontend responsibility:**
- Render themes from theme name (no need to fetch theme details)
- Handle gradient/pattern rendering
- A/B test theme designs without backend changes
- Cache theme constants locally

### Theme Handling
- Backend stores **ONLY** theme name (e.g., `"ocean"`)
- Backend validates theme name against 8 allowed values
- Frontend maintains theme registry with rendering details
- Frontend can update theme appearance without backend deployment

### Chapter Background Inheritance

1. **Default behavior**: Khi tạo chapter mới, mặc định `use_book_background = true`
2. **Fallback logic**: Khi GET chapter background:
   - Nếu `use_book_background = true`: Trả về book's background_config
   - Nếu `use_book_background = false`: Trả về chapter's background_config
   - Nếu cả 2 đều null: Trả về null (frontend dùng default white)

3. **Update behavior**:
   - Set `use_book_background = true`: Xóa chapter's background_config, kế thừa từ sách
   - Set `use_book_background = false`: Bắt buộc phải có `background_config`

### Points System

- **AI Generation cost**: 2 points mỗi lần generate
- **Check before generation**: API tự động check user balance trước khi generate
- **Deduct after success**: Points chỉ bị trừ sau khi generate thành công
- **Library file**: Tất cả AI-generated backgrounds đều được lưu vào `library_files` collection

**Image Storage**

- **Service**: Cloudflare R2
- **Path format**: `backgrounds/{user_id}/{timestamp}_{random}.png`
- **Image specs**:
  - Format: PNG
  - Quality: High
  - Size: Tùy aspect_ratio (A4 = 1754x2480px for 3:4)
- **Public URL**: Configured via `R2_PUBLIC_URL` env variable
  - Production default: `https://static.wordai.pro`
  - Can also use: `https://cdn.wordai.vn` or custom domain

### Ownership & Permissions

- **Book operations**: Chỉ owner của book mới có thể update/delete
- **Chapter operations**: Chỉ owner của book chứa chapter mới có thể update/delete
- **Public read**: GET endpoints không cần authentication, ai cũng xem được

---

## Frontend Integration Notes

### Recommended UI Flow

1. **Book Settings Page**:
   - Tabs: Solid Color | Gradient | Themes | AI Generate | Custom Image
   - Show preview realtime khi user thay đổi settings
   - Button "Apply to all chapters" để áp dụng book background cho tất cả chapters

2. **Chapter Editor**:
   - Toggle: "Use book background" (default ON)
   - Khi toggle OFF: Hiện background settings cho chapter
   - Preview background ở chế độ edit

3. **AI Generation Dialog**:
   - Input: Prompt (textarea với placeholder gợi ý)
   - Dropdown: Aspect Ratio (default 3:4)
   - Dropdown: Style (optional)
   - Show points cost: "This will cost 2 points"
   - Show remaining points after generation

4. **Theme Picker**:
   - Grid layout 4x2 với 8 themes
   - **Frontend tự render** preview từ theme constants
   - Hover effect để preview
   - Click to apply - chỉ gửi theme name lên backend
   - **KHÔNG cần fetch themes từ backend**

### State Management

**Background Config Types:**
```typescript
type BackgroundConfig =
  | { type: "solid", color: string }
  | { type: "gradient", gradient: { colors: [string, string], type: "linear" | "radial" | "conic", angle?: number } }
  | { type: "theme", theme: "ocean" | "forest" | "sunset" | "minimal" | "dark" | "light" | "tech" | "vintage" }
  | { type: "ai_image" | "custom_image", image: { url: string, overlay_opacity?: number, overlay_color?: string }, ai_metadata?: AIMetadata }
```

**Book Background State:**
```typescript
interface BookBackground {
  book_id: string;
  background_config: BackgroundConfig | null;
}
```

**Chapter Background State:**
```typescript
interface ChapterBackground {
  book_id: string;
  chapter_id: string;
  use_book_background: boolean;
  background_config: BackgroundConfig | null;
}
```

### Error Handling

- **Insufficient points**: Show modal với link đến trang nạp points
- **Network errors**: Show retry button với error message
- **Validation errors**: Inline validation với red text dưới input
- **404 errors**: Redirect về book list hoặc show "Not found" page

### Performance Tips

- Cache themes response (không thay đổi)
- Debounce color picker changes (300ms)
- Show loading skeleton khi fetch background
- Lazy load AI generation dialog (code splitting)

---

## Database Schema

### online_books collection

Thêm field mới:
```json
{
  "_id": "ObjectId",
  "title": "string",
  "background_config": {
    "type": "string",
    "solid_color": "string",
    "gradient_colors": ["string"],
    "gradient_type": "string",
    "gradient_angle": "number",
    "theme_name": "string",
    "image_url": "string",
## Database Schema

### online_books collection

Thêm field mới:
```json
{
  "_id": "ObjectId",
  "title": "string",
  "background_config": {
    "type": "solid | gradient | theme | ai_image | custom_image",

    // Solid
    "color": "string",  // hex color

    // Gradient
    "gradient": {
      "colors": ["string", "string"],  // 2 hex colors
      "type": "linear | radial | conic",
      "angle": "number"  // 0-360
    },

    // Theme - CHỈ LƯU TÊN
    "theme": "string",  // ocean | forest | sunset | minimal | dark | light | tech | vintage

    // Image
    "image": {
      "url": "string",
      "overlay_opacity": "number",  // 0.0-1.0
      "overlay_color": "string"  // hex color
    },

    // AI metadata (auto for ai_image)
    "ai_metadata": {
      "prompt": "string",
      "model": "string",
      "generated_at": "datetime",
      "generation_time_ms": "number",
      "cost_points": "number"
    }
  }
}
```

### book_chapters collection

Thêm fields mới:
```json
{
  "_id": "ObjectId",
  "book_id": "ObjectId",
  "title": "string",
  "use_book_background": "boolean",  // Default: true
  "background_config": {
    // same structure as online_books.background_config
    // Only exists if use_book_background = false
  }
}
```

### library_files collection

AI-generated backgrounds được lưu với:
```json
{
  "_id": "ObjectId",
  "user_id": "ObjectId",
  "file_url": "string",
  "file_type": "background",
  "metadata": {
    "prompt": "string",
    "aspect_ratio": "string",
    "style": "string",
    "generated_at": "datetime"
  }
}
```

---

## Migration

File `migrate_add_background_fields.py` đã được chạy trên production:

**Results:**
- ✅ 6 books updated with `background_config: null`
- ✅ 74 chapters updated with `use_book_background: true` and `background_config: null`
- ✅ 100% verification passed

---

## Cost & Limits

| Operation | Cost | Limit |
|-----------|------|-------|
| AI Generation | 2 points | Minimum 2 points required |
| Update/Delete | Free | Owner only |
| Get/Read | Free | Public access |

**Rate Limiting**: Chưa implement, có thể thêm sau nếu cần.

---

## API Summary

**Total Endpoints: 8** (7 main endpoints + 1 upload endpoint)

| Method | Endpoint | Auth | Full URL Example |
|--------|----------|------|------------------|
| POST | `/{book_id}/background/generate` | Required | `POST https://ai.wordai.pro/api/v1/books/{book_id}/background/generate` |
| PUT | `/{book_id}/background` | Required | `PUT https://ai.wordai.pro/api/v1/books/{book_id}/background` |
| GET | `/{book_id}/background` | Optional | `GET https://ai.wordai.pro/api/v1/books/{book_id}/background` |
| DELETE | `/{book_id}/background` | Required | `DELETE https://ai.wordai.pro/api/v1/books/{book_id}/background` |
| PUT | `/{book_id}/chapters/{chapter_id}/background` | Required | `PUT https://ai.wordai.pro/api/v1/books/{book_id}/chapters/{chapter_id}/background` |
| GET | `/{book_id}/chapters/{chapter_id}/background` | Optional | `GET https://ai.wordai.pro/api/v1/books/{book_id}/chapters/{chapter_id}/background` |
| DELETE | `/{book_id}/chapters/{chapter_id}/background` | Required | `DELETE https://ai.wordai.pro/api/v1/books/{book_id}/chapters/{chapter_id}/background` |
| POST | `/upload-background` | Required | `POST https://ai.wordai.pro/upload-background` |

**Note:** Upload endpoint **không có prefix** `/api/v1/books`

---

## Key Design Decisions

### ✅ Simplified Theme Handling
- **Backend**: Chỉ validate và lưu theme name (1 trong 8 tên)
- **Frontend**: Tự quản lý theme registry, tự render themes
- **Benefits**:
  - Frontend có thể A/B test theme designs
  - Không cần fetch themes từ backend
  - Dễ dàng update theme appearance
  - Cached themes - faster UX

### ✅ Nested Object Structure
- **Before**: Flat fields (`gradient_colors`, `gradient_type`, `image_url`, `overlay_opacity`)
- **After**: Nested objects (`gradient: { colors, type, angle }`, `image: { url, overlay_opacity, overlay_color }`)
- **Benefits**:
  - Cleaner schema
  - Better validation
  - Easier to extend
  - Type-safe frontend models

### ✅ Minimal Backend Storage
- Backend chỉ lưu essential data
- Frontend handle rendering logic
- Separation of concerns
- Better performance

---

## Version History

### v1.1 - November 25, 2025 (Current)
- **BREAKING CHANGES:**
  - Removed `GET /backgrounds/themes` endpoint
  - Simplified schema: nested objects (gradient, image)
  - Changed field names: `color` (not `solid_color`), `theme` (not `theme_name`)
- Frontend now manages theme registry
- Backend only validates theme names
- Improved validation with nested structures

### v1.0 - November 25, 2025
- Initial release
- 8 endpoints for book/chapter background management
- AI generation using Gemini 3 Pro Image
- 8 preset themes with GET endpoint
- A4 page size support (3:4 aspect ratio)
- Chapter inheritance from book background
- Full CRUD operations

---

## Support & Contact

**API Documentation**: https://wordai.vn/docs (Swagger UI)

**Backend Repository**: https://github.com/lekompozer/wordai-aiservice

**Questions**: Contact backend team