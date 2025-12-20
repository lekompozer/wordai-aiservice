# Slide Backgrounds API Integration Guide

## Overview

Backend đã hỗ trợ **per-slide background customization** cho slide documents. Mỗi slide có thể có background riêng với các loại:
- **Solid color** (màu đơn sắc)
- **Gradient** (degradê 2+ màu)
- **Image upload** (upload ảnh từ máy)
- **AI-generated image** (generate ảnh bằng AI)

Background settings được lưu độc lập với slide content và elements.

---

## Database Schema

### `documents` Collection

Thêm field mới:

```typescript
{
  // ... existing fields
  slide_elements?: Array<{
    slideIndex: number;
    elements: Array<any>;
  }>;

  slide_backgrounds?: Array<{    // ✅ NEW FIELD
    slideIndex: number;
    background: {
      type: 'color' | 'gradient' | 'image' | 'ai-image';
      value?: string;              // Hex color hoặc image URL
      gradient?: {
        type: 'linear' | 'radial';
        angle?: number;
        colors: string[];
        stops?: number[];
      };
      // ... other background properties
    };
  }>;
}
```

---

## API Endpoints

### 1. Upload Background Image

**Endpoint:** `POST /api/book-backgrounds/upload-background`

**Authentication:** Required (Bearer token)

**Request:** `multipart/form-data`

```typescript
FormData {
  file: File  // JPG, PNG, or WebP
}
```

**File Requirements:**
- Format: JPG, PNG, WebP
- Max size: 10MB
- Recommended resolution: 1754x2480px for A4 pages (3:4 aspect ratio)

**Response:**
```typescript
{
  success: true;
  image_url: string;        // Public R2 URL (e.g., https://static.wordai.pro/backgrounds/user123/bg_1234567890.png)
  r2_key: string;          // Storage key (e.g., backgrounds/user123/bg_1234567890.png)
  file_id: string;         // Library file ID (MongoDB ObjectId)
  file_size: number;       // File size in bytes
  content_type: string;    // MIME type (e.g., image/png)
}
```

**Usage Example:**
```typescript
const formData = new FormData();
formData.append('file', imageFile);

const response = await fetch('/api/book-backgrounds/upload-background', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${firebaseToken}`
  },
  body: formData
});

const data = await response.json();
// Use data.image_url as background value
```

**Error Codes:**
- `400`: Invalid file type or file too large
- `401`: Unauthorized (missing/invalid token)
- `500`: Upload failed

---

### 2. Generate AI Background

**Endpoint:** `POST /api/slide-backgrounds/generate`

**Authentication:** Required (Bearer token)

**Cost:** 2 points per generation

**Request Body:**
```typescript
{
  prompt: string;              // 10-500 characters
  aspect_ratio?: string;       // Default: "16:9" (auto-set for slides)
  style?: string;             // Presentation style (see below)
  generation_type: "slide_background";  // Auto-set by endpoint
}
```

**Available Styles (Optimized for Presentations):**

- **`business`**: Professional corporate presentations with clean, trustworthy design
  - Color palette: Blues, grays, whites
  - Feel: Professional and authoritative
  - Best for: Business meetings, quarterly reports, corporate communications

- **`startup`**: Modern pitch decks with bold colors and dynamic design
  - Color palette: Vibrant gradients, energetic colors
  - Feel: Innovative and forward-thinking
  - Best for: Investor pitches, product launches, startup showcases

- **`corporate`**: Formal presentations with clean and professional aesthetics
  - Color palette: Conservative professional colors
  - Feel: Trustworthy and established
  - Best for: Board meetings, annual reports, executive presentations

- **`education`**: Learning-focused designs with clear, organized layouts
  - Color palette: Calm, concentration-promoting colors
  - Feel: Clear and structured
  - Best for: Lectures, training materials, educational content

- **`academic`**: Scholarly presentations for research and conferences
  - Color palette: Professional academic colors
  - Feel: Research-focused and credible
  - Best for: Academic conferences, research presentations, thesis defenses

- **`creative`**: Artistic and expressive designs
  - Color palette: Bold, creative combinations
  - Feel: Innovative and artistic
  - Best for: Creative pitches, design portfolios, artistic showcases

- **`minimalist`**: Clean, simple with lots of white space
  - Color palette: Monochromatic or very limited
  - Feel: Focused on essential elements
  - Best for: Product presentations, minimalist brands, tech talks

- **`modern`**: Contemporary sleek designs
  - Color palette: Modern trendy colors
  - Feel: Cutting-edge and contemporary
  - Best for: Tech presentations, modern brands, innovation talks

**Response:**
```typescript
{
  success: true;
  image_url: string;           // Public R2 URL
  r2_key: string;             // Storage key
  file_id: string;            // Library file ID
  prompt_used: string;        // Full optimized prompt (see what AI received)
  generation_time_ms: number; // Generation time
  points_deducted: number;    // 2 points
  ai_metadata: {
    source: "gemini-3-pro-image-preview";
    generation_type: "slide_background";
    model_version: string;
    aspect_ratio: "16:9";
    // ...
  };
}
```

**Usage Example:**
```typescript
const response = await fetch('/api/slide-backgrounds/generate', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${firebaseToken}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    prompt: "Modern tech background with gradient blue and purple tones",
    aspect_ratio: "16:9",  // Optional, auto-set to 16:9 for slides
    style: "startup",      // Optimized for startup pitch decks
    generation_type: "slide_background"
  })
});

const data = await response.json();
// Use data.image_url as background value
```

**Error Codes:**
- `400`: Invalid prompt (too short/long) or invalid parameters
- `401`: Unauthorized or missing token
- `402`: Insufficient points
- `500`: AI generation failed

**Notes:**
- **Optimized for 16:9 slides** - Aspect ratio automatically set to 16:9 (standard presentation format)
- **Different from book backgrounds** - Uses presentation-specific prompts focused on:
  - Visual impact for audience engagement
  - Professional quality for business/education contexts
  - Strategic empty space for content placement
  - High contrast for text readability
- AI generation consumes 2 points from user balance
- Generated images saved to `library_files` collection
- Images stored in R2 with public access
- Prompt is enhanced internally based on selected style

**Prompt Optimization:**
The endpoint internally transforms your prompt into a presentation-optimized format. For example:

```
User prompt: "Blue gradient with geometric shapes"
Style: "startup"

↓ Transformed to ↓

"Create a high-quality presentation slide background image (16:9 aspect ratio, 1920×1080px).

BACKGROUND DESCRIPTION: Blue gradient with geometric shapes

PRESENTATION CONTEXT: modern startup pitch deck with innovative and dynamic design

REQUIREMENTS:
- Designed specifically for presentation slides (not documents)
- Optimized for 16:9 widescreen display
- Maximum visual impact for audience engagement
- Professional quality suitable for pitch decks and conferences
- Balanced composition with strategic empty space
- High contrast for text placement
...

STYLE GUIDELINES:
- Bold and energetic color palette
- Dynamic angles and modern shapes
- Innovative and forward-thinking feel
- Gradients with vibrant colors"
```

---

### 3. Create/Load Document

**Endpoint:** `POST /api/documents/from-file`

**Response:**
```typescript
{
  document_id: string;
  title: string;
  content_html: string;
  version: number;
  last_saved_at: string;
  file_size_bytes: number;
  auto_save_count: number;
  manual_save_count: number;
  source_type: 'file' | 'created';
  document_type?: 'doc' | 'slide' | 'note';
  file_id?: string;
  slide_elements?: Array<{slideIndex: number; elements: any[]}>;
  slide_backgrounds?: Array<{slideIndex: number; background: any}>;  // ✅ NEW
}
```

**Notes:**
- `slide_backgrounds` sẽ là `[]` (empty array) nếu document mới tạo chưa có backgrounds
- Frontend cần khởi tạo `slideBackgrounds` state từ `response.slide_backgrounds`

---

### 4. Get Document

**Endpoint:** `GET /api/documents/{document_id}`

**Response:** Giống như Create/Load Document

**Notes:**
- Trả về đầy đủ `slide_backgrounds` đã lưu
- Frontend restore backgrounds vào SlideEditor component

---

### 5. Save Document (Update)

**Endpoint:** `PUT /api/documents/{document_id}`

**Request Body:**
```typescript
{
  title?: string;
  content_html: string;
  content_text?: string;
  is_auto_save: boolean;
  slide_elements?: Array<{           // Optional - overlay elements
    slideIndex: number;
    elements: Array<any>;
  }>;
  slide_backgrounds?: Array<{        // ✅ NEW - background settings
    slideIndex: number;
    background: {
      type: 'color' | 'gradient' | 'image' | 'ai-image';
      value?: string;
      gradient?: {
        type: 'linear' | 'radial';
        angle?: number;
        colors: string[];
        stops?: number[];
      };
    };
  }>;
}
```

**Response:**
```typescript
{
  success: true;
  message: 'Document saved successfully';
  is_auto_save: boolean;
}
```

---

## Frontend Integration Workflow

### 1. **When Loading Document**

```
Backend Response
     ↓
Extract slide_backgrounds array
     ↓
Set to slideBackgrounds state
     ↓
Pass to SlideEditor via initialSlideBackgrounds prop
     ↓
SlideEditor converts array → Map
     ↓
Apply backgrounds to slides
```

**Key Points:**
- Check if `slide_backgrounds` exists và không empty
- Convert array format → Map format cho SlideEditor
- Restore vào `contentCacheRef` để giữ khi switch tabs

---

### 2. **When Saving Document**

```
User applies background
     ↓
slideBackgrounds Map updated
     ↓
Click Save button
     ↓
Call getSlideBackgrounds() from SlideEditor
     ↓
Convert Map → Array format
     ↓
Send to backend via slide_backgrounds field
     ↓
Backend saves to database
     ↓
Cache in contentCacheRef
```

**Key Points:**
- Gửi cả `slide_elements` và `slide_backgrounds` cùng lúc
- Backend sẽ lưu cả 2 fields độc lập
- Auto-save cũng gửi backgrounds (nếu có thay đổi)

---

## Background Data Format

### Array Format (API Transfer)

```typescript
// Gửi lên backend và nhận từ backend
slide_backgrounds: [
  {
    slideIndex: 0,
    background: {
      type: 'color',
      value: '#FF5733'
    }
  },
  {
    slideIndex: 1,
    background: {
      type: 'gradient',
      gradient: {
        type: 'linear',
        angle: 45,
        colors: ['#667eea', '#764ba2'],
        stops: [0, 100]
      }
    }
  },
  {
    slideIndex: 2,
    background: {
      type: 'image',
      value: 'https://r2.cloudflare.com/...'
    }
  },
  {
    slideIndex: 3,
    background: {
      type: 'ai-image',
      value: 'https://r2.cloudflare.com/generated/...',
      prompt: 'A beautiful sunset over mountains'
    }
  }
]
```

### Map Format (Frontend State)

```typescript
// Lưu trong component state
const slideBackgrounds = new Map<number, BackgroundSettings>([
  [0, { type: 'color', value: '#FF5733' }],
  [1, { type: 'gradient', gradient: {...} }],
  [2, { type: 'image', value: 'https://...' }],
  [3, { type: 'ai-image', value: 'https://...', prompt: '...' }]
]);
```

---

## Implementation Checklist

### Backend (✅ Completed)

- [x] Add `slide_backgrounds` field to `DocumentUpdate` model
- [x] Add `slide_backgrounds` field to `DocumentResponse` model
- [x] Update `update_document()` in DocumentManager to save backgrounds
- [x] Return `slide_backgrounds` in GET document endpoint
- [x] Return `slide_backgrounds` in POST create document endpoint
- [x] Add logging for backgrounds save/load operations

### Frontend (Your Tasks)

#### 1. **Interface Updates**
- [ ] Add `slide_backgrounds?: Array<{slideIndex: number; background: any}>` to `DocumentTemplate` interface
- [ ] Add `slide_backgrounds?: Array<{slideIndex: number; background: any}>` to `UpdateDocumentRequest` interface

#### 2. **SlideEditor Component**
- [ ] Add `initialSlideBackgrounds` prop
- [ ] Add `getSlideBackgrounds()` method to `SlideEditorHandle`
- [ ] Add `setSlideBackgrounds()` method to `SlideEditorHandle`
- [ ] Implement `useEffect` để restore backgrounds từ `initialSlideBackgrounds`
- [ ] Convert array format → Map format khi restore

#### 3. **MainContent Component**
- [ ] Add `slideBackgrounds` state
- [ ] Thu thập backgrounds từ `SlideEditor.getSlideBackgrounds()` khi save
- [ ] Gửi `slide_backgrounds` lên backend qua `updateDocument()` API
- [ ] Cache backgrounds trong `contentCacheRef` để giữ khi switch tabs
- [ ] Restore backgrounds từ `selectedTemplatePreview.slide_backgrounds`
- [ ] Pass `initialSlideBackgrounds` vào SlideEditor component

#### 4. **Cache Management**
- [ ] Add `slide_backgrounds` vào `contentCacheRef` structure
- [ ] Restore backgrounds khi switch back to tab
- [ ] Clear backgrounds khi close tab hoặc create new document

#### 5. **Save Flow**
- [ ] Collect backgrounds cùng với elements trước khi save
- [ ] Convert Map → Array format trước khi gửi API
- [ ] Handle both auto-save và manual save

#### 6. **Load Flow**
- [ ] Extract `slide_backgrounds` từ API response
- [ ] Convert array → Map format
- [ ] Set vào state và pass vào SlideEditor
- [ ] Apply backgrounds ngay sau khi load

#### 7. **Image Upload Feature**
- [ ] Add file picker UI for custom image backgrounds
- [ ] Implement `uploadBackgroundImage()` function
- [ ] Call `POST /api/book-backgrounds/upload-background` with FormData
- [ ] Show upload progress indicator
- [ ] Handle upload errors (file too large, invalid type)
- [ ] Update `slideBackgrounds.set(slideIndex, {type: 'image', value: image_url})`
- [ ] Trigger auto-save after successful upload

#### 8. **AI Generation Feature**
- [ ] Add AI background prompt input UI with style selector
- [ ] Implement style dropdown (business, startup, corporate, education, academic, creative, minimalist, modern)
- [ ] Add style descriptions/hints for each option
- [ ] Implement `generateAIBackground()` function
- [ ] Call `POST /api/slide-backgrounds/generate` (not book endpoint!)
- [ ] Show generation progress (loading spinner)
- [ ] Handle errors (insufficient points, timeout, invalid prompt)
- [ ] Display points cost before generation (2 points)
- [ ] Update `slideBackgrounds.set(slideIndex, {type: 'ai-image', value: image_url})`
- [ ] Optionally store `prompt` in background object for reference
- [ ] Trigger auto-save after successful generation
- [ ] Show style-specific preview/hints based on selected style

#### 9. **Points System Integration**
- [ ] Check user points balance before allowing AI generation
- [ ] Show "Insufficient points" modal if balance < 2
- [ ] Deduct 2 points from UI after successful generation
- [ ] Update points display in header/sidebar

---

## Background Types Reference

### 1. Solid Color
```typescript
{
  type: 'color',
  value: '#FF5733'  // Hex color
}
```

### 2. Linear Gradient
```typescript
{
  type: 'gradient',
  gradient: {
    type: 'linear',
    angle: 45,                    // 0-360 degrees
    colors: ['#667eea', '#764ba2'],
    stops: [0, 100]               // Optional
  }
}
```

### 3. Radial Gradient
```typescript
{
  type: 'gradient',
  gradient: {
    type: 'radial',
    colors: ['#667eea', '#764ba2'],
    stops: [0, 100]
  }
}
```

### 4. Custom Image Upload
```typescript
{
  type: 'image',
  value: 'https://static.wordai.pro/backgrounds/user123/bg_1234567890.png'  // R2 URL from upload endpoint
}
```

**Workflow:**
1. User picks image file from local machine
2. Frontend calls `POST /api/book-backgrounds/upload-background` with FormData
3. Backend validates (format, size), uploads to R2, saves to library
4. Backend returns `image_url`
5. Frontend sets `{type: 'image', value: image_url}` as background
6. Save document with `slide_backgrounds` array

**Validation:**
- Formats: JPG, PNG, WebP only
- Max size: 10MB
- Recommended: High-res images (1754x2480px for A4)

### 5. AI-Generated Image
```typescript
{
  type: 'ai-image',
  value: 'https://static.wordai.pro/ai-generated-images/user123/img_1234567890.png',  // R2 URL from AI generation
  prompt?: 'A beautiful sunset over mountains'  // Optional: store prompt for reference
}
```

**Workflow:**
1. User enters text prompt (e.g., "Minimalist gradient background with soft blue tones")
2. Frontend calls `POST /api/v1/books/{book_id}/background/generate` with prompt
3. Backend:
   - Deducts 2 points from user balance
   - Calls Gemini 3 Pro Image API
   - Uploads generated image to R2
   - Saves to library with metadata
4. Backend returns `image_url` and metadata
5. Frontend sets `{type: 'ai-image', value: image_url, prompt: ...}` as background
6. Save document with `slide_backgrounds` array

**Validation:**
- Prompt length: 10-500 characters
- Cost: 2 points per generation
- Aspect ratio: Default "3:4" (adjustable)
- User must be book owner

**Error Handling:**
- Insufficient points → Show upgrade prompt
- AI generation timeout → Retry or fallback to color/gradient
- Network error → Show error message, preserve previous background

---

## Workflow Diagrams

### Upload Image Workflow

```
User picks file
      ↓
FormData with file
      ↓
POST /api/book-backgrounds/upload-background
      ↓
Validate (type, size)
      ↓
Upload to R2 (backgrounds/{user_id}/bg_{timestamp}.ext)
      ↓
Save to library_files collection
      ↓
Return {image_url, r2_key, file_id}
      ↓
Frontend: slideBackgrounds.set(slideIndex, {type: 'image', value: image_url})
      ↓
Auto-save triggers → send slide_backgrounds to backend
      ↓
Backend saves to documents.slide_backgrounds
```

### AI Generation Workflow

```
User enters prompt + selects style
      ↓
POST /api/slide-backgrounds/generate
      ↓
Check user points (≥2)
      ↓
Deduct 2 points
      ↓
Build presentation-optimized prompt based on style:
  - business → Corporate professional aesthetics
  - startup → Dynamic pitch deck design
  - education → Learning-focused layout
  - minimalist → Clean simple design
  etc.
      ↓
Call Gemini 3 Pro Image API
  - Aspect ratio: 16:9 (widescreen slides)
  - Resolution: 1920×1080px
  - Focus: Audience engagement, text readability
      ↓
Upload generated image to R2 (ai-generated-images/{user_id}/...)
      ↓
Save to library_files with metadata
      ↓
Return {image_url, prompt_used, ai_metadata}
      ↓
Frontend: slideBackgrounds.set(slideIndex, {type: 'ai-image', value: image_url, prompt: ...})
      ↓
Auto-save triggers → send slide_backgrounds to backend
      ↓
Backend saves to documents.slide_backgrounds
```

---

## Background Types Reference

### 1. Solid Color
```typescript
{
  type: 'color',
  value: '#FF5733'  // Hex color
}
```

### 2. Linear Gradient
```typescript
{
  type: 'gradient',
  gradient: {
    type: 'linear',
    angle: 45,                    // 0-360 degrees
    colors: ['#667eea', '#764ba2'],
    stops: [0, 100]               // Optional
  }
}
```

### 3. Radial Gradient
```typescript
{
  type: 'gradient',
  gradient: {
    type: 'radial',
    colors: ['#667eea', '#764ba2'],
    stops: [0, 100]
  }
}
```

### 4. Image Upload
```typescript
{
  type: 'image',
  value: 'https://r2.cloudflare.com/bucket/file.jpg'
}
```

### 5. AI-Generated Image
```typescript
{
  type: 'ai-image',
  value: 'https://r2.cloudflare.com/bucket/generated.jpg',
  prompt: 'A beautiful sunset over mountains',  // Optional
  model: 'dall-e-3'                             // Optional
}
```

---

## Error Handling

### Common Issues

1. **Backgrounds không load sau khi save**
   - Check: `slide_backgrounds` có được gửi trong request không
   - Check: Response có chứa `slide_backgrounds` không
   - Verify: Database có field `slide_backgrounds` không

2. **Backgrounds bị mất khi switch tabs**
   - Ensure: Backgrounds được cache trong `contentCacheRef`
   - Verify: Restore logic chạy khi switch back

3. **Auto-save không lưu backgrounds**
   - Check: Auto-save flow có gọi `getSlideBackgrounds()` không
   - Verify: `is_auto_save=true` request vẫn gửi `slide_backgrounds`

---

## Testing Checklist

### Functional Tests

- [ ] Create new slide document → backgrounds = []
- [ ] Apply background to slide → save → reload → background persists
- [ ] Apply different backgrounds to multiple slides → all persist
- [ ] Switch tabs → backgrounds retained in cache
- [ ] Auto-save → backgrounds saved
- [ ] Manual save → backgrounds saved
- [ ] Load existing document with backgrounds → restored correctly

### Background Type Tests

- [ ] Set color background → saved and loaded correctly
- [ ] Set linear gradient → angle and colors preserved
- [ ] Set radial gradient → colors and stops preserved
- [ ] Upload custom image → R2 URL saved and image displays
- [ ] Generate AI image → points deducted, image saved and displays
- [ ] Different backgrounds per slide → each slide independent
- [ ] Switch between background types → previous value cleared

### Image Upload Tests

- [ ] Upload JPG → successful
- [ ] Upload PNG → successful
- [ ] Upload WebP → successful
- [ ] Upload GIF → rejected (invalid type)
- [ ] Upload 15MB file → rejected (too large)
- [ ] Upload 5MB file → successful
- [ ] Verify uploaded image in library_files collection
- [ ] Verify R2 URL is publicly accessible
- [ ] Upload with special characters in filename → sanitized correctly

### AI Generation Tests

- [ ] Generate with valid prompt (50 chars) → successful
- [ ] Generate with <10 char prompt → rejected
- [ ] Generate with >500 char prompt → rejected
- [ ] Generate with insufficient points → error shown
- [ ] Generate with ≥2 points → success, balance updated
- [ ] Verify AI metadata saved to library_files
- [ ] Verify prompt stored in background object
- [ ] Multiple generations → each creates new image
- [ ] Generation timeout → error handled gracefully
- [ ] Network error during generation → points not deducted
- [ ] Test each style option (business, startup, corporate, education, academic, creative, minimalist, modern)
- [ ] Verify style affects prompt optimization (check prompt_used in response)
- [ ] Verify 16:9 aspect ratio auto-set for slides
- [ ] Generated images suitable for presentation slides (visual impact, text readability)

### Edge Cases

- [ ] Save empty backgrounds array → no errors
- [ ] Save null backgrounds → handled gracefully
- [ ] Large gradient array (10+ colors) → saved correctly
- [ ] Image URLs with special characters → encoded properly
- [ ] Concurrent saves (auto + manual) → no race conditions
- [ ] User cancels upload mid-flight → no orphaned files
- [ ] AI generation retries → idempotent (no duplicate charges)

---

## Backend Logs Reference

### When Saving
```
🎨 [SLIDE_DATA_API_SAVE] document_id=xxx, slides_with_elements=5, total_overlay_elements=23, slides_with_backgrounds=5
🎨 [SLIDE_BACKGROUNDS_SAVE] Preparing to save: document_id=xxx, slides_with_backgrounds=5
✅ [DB_SAVED] Document xxx manually saved 5 slides with 23 overlay elements 5 slides with backgrounds (version +1)
```

### When Loading
```
🎨 [SLIDE_ELEMENTS_API_LOAD] document_id=xxx, slides=5, total_overlay_elements=23, slide_backgrounds=5
```

---

## Performance Considerations

1. **Background Array Size**
   - Mỗi slide background ~100-500 bytes (color/gradient)
   - Image URLs: ~200-300 bytes
   - 100 slides với backgrounds ≈ 10-50 KB → acceptable

2. **Auto-save Frequency**
   - Backgrounds ít thay đổi hơn elements
   - Có thể optimize: chỉ save backgrounds khi có thay đổi
   - Current: Gửi full array mỗi lần save (simple but works)

3. **Cache Strategy**
   - Backgrounds được cache cùng với slide_elements
   - Clear cache khi close tab để avoid memory leak

---

## Migration Notes

### For Existing Documents

- Documents không có `slide_backgrounds` field → backend returns `[]`
- Frontend handle gracefully: empty array = no backgrounds
- Khi user apply background lần đầu → field được tạo

### Backward Compatibility

- API fully backward compatible
- Old clients (không gửi `slide_backgrounds`) → ignored by backend
- New clients → can send/receive backgrounds

---

## Example Code Integration

### Upload Background Image

```typescript
async function uploadBackgroundImage(
  file: File,
  slideIndex: number,
  firebaseToken: string
): Promise<void> {
  try {
    // Validate file
    const allowedTypes = ['image/jpeg', 'image/png', 'image/webp'];
    if (!allowedTypes.includes(file.type)) {
      throw new Error(`Invalid file type: ${file.type}`);
    }

    const maxSize = 10 * 1024 * 1024; // 10MB
    if (file.size > maxSize) {
      throw new Error(`File too large: ${(file.size / (1024*1024)).toFixed(2)}MB`);
    }

    // Show loading indicator
    setIsUploading(true);

    // Prepare FormData
    const formData = new FormData();
    formData.append('file', file);

    // Upload to backend
    const response = await fetch('/api/book-backgrounds/upload-background', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${firebaseToken}`
      },
      body: formData
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Upload failed');
    }

    const data = await response.json();

    // Update slide background
    slideBackgrounds.set(slideIndex, {
      type: 'image',
      value: data.image_url
    });

    // Trigger auto-save
    await saveDocument();

    console.log('✅ Background uploaded:', data.image_url);
  } catch (error) {
    console.error('❌ Upload failed:', error);
    alert(`Upload failed: ${error.message}`);
  } finally {
    setIsUploading(false);
  }
}

// Usage in component
<input
  type="file"
  accept="image/jpeg,image/png,image/webp"
  onChange={(e) => {
    const file = e.target.files?.[0];
    if (file) {
      uploadBackgroundImage(file, currentSlideIndex, firebaseToken);
    }
  }}
/>
```

### Generate AI Background

```typescript
async function generateAIBackground(
  prompt: string,
  slideIndex: number,
  firebaseToken: string,
  style?: string
): Promise<void> {
  try {
    // Validate prompt
    if (prompt.length < 10 || prompt.length > 500) {
      throw new Error('Prompt must be 10-500 characters');
    }

    // Check user points
    if (userPoints < 2) {
      alert('Insufficient points. You need 2 points to generate AI background.');
      return;
    }

    // Show loading indicator
    setIsGenerating(true);

    // Call slide-specific AI generation endpoint
    const response = await fetch('/api/slide-backgrounds/generate', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${firebaseToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        prompt: prompt,
        aspect_ratio: '16:9',  // Optimized for slides
        style: style || 'modern',  // business, startup, corporate, education, etc.
        generation_type: 'slide_background'
      })
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Generation failed');
    }

    const data = await response.json();

    // Update slide background
    slideBackgrounds.set(slideIndex, {
      type: 'ai-image',
      value: data.image_url,
      prompt: data.prompt_used
    });

    // Update points balance
    setUserPoints(prev => prev - data.points_deducted);

    // Trigger auto-save
    await saveDocument();

    console.log('✅ Slide AI background generated:', data.image_url);
    console.log(`   Generation time: ${data.generation_time_ms}ms`);
    console.log(`   Style: ${style || 'modern'}`);
  } catch (error) {
    console.error('❌ AI generation failed:', error);
    alert(`Generation failed: ${error.message}`);
  } finally {
    setIsGenerating(false);
  }
}

// Usage in component with style selector
<div className="ai-background-generator">
  <select
    value={selectedStyle}
    onChange={(e) => setSelectedStyle(e.target.value)}
  >
    <option value="modern">Modern</option>
    <option value="business">Business</option>
    <option value="startup">Startup</option>
    <option value="corporate">Corporate</option>
    <option value="education">Education</option>
    <option value="academic">Academic</option>
    <option value="creative">Creative</option>
    <option value="minimalist">Minimalist</option>
  </select>

  <input
    type="text"
    placeholder="Describe your slide background (e.g., 'Blue gradient with modern tech elements')"
    value={aiPrompt}
    onChange={(e) => setAiPrompt(e.target.value)}
    minLength={10}
    maxLength={500}
  />

  <button
    onClick={() => generateAIBackground(aiPrompt, currentSlideIndex, firebaseToken, selectedStyle)}
    disabled={isGenerating || aiPrompt.length < 10 || userPoints < 2}
  >
    {isGenerating ? 'Generating...' : 'Generate (2 points)'}
  </button>

  {userPoints < 2 && <p className="warning">Insufficient points</p>}

  <p className="style-hint">
    {selectedStyle === 'business' && '💼 Professional corporate design with clean aesthetics'}
    {selectedStyle === 'startup' && '🚀 Dynamic pitch deck with bold colors'}
    {selectedStyle === 'corporate' && '🏢 Formal presentation with trustworthy design'}
    {selectedStyle === 'education' && '📚 Learning-focused with clear layouts'}
    {selectedStyle === 'academic' && '🎓 Scholarly presentation for research'}
    {selectedStyle === 'creative' && '🎨 Artistic and expressive design'}
    {selectedStyle === 'minimalist' && '⚪ Clean and simple with white space'}
    {selectedStyle === 'modern' && '✨ Contemporary sleek design'}
  </p>
</div>
```

### Complete Save Flow with Backgrounds

```typescript
async function saveDocument(isAutoSave: boolean = false): Promise<void> {
  try {
    // Get slide elements
    const slideElements = slideEditorRef.current?.getSlideElements() || [];

    // Get slide backgrounds (convert Map to Array)
    const slideBackgroundsArray = Array.from(slideBackgrounds.entries()).map(
      ([slideIndex, background]) => ({
        slideIndex,
        background
      })
    );

    // Prepare request payload
    const payload = {
      title: documentTitle,
      content_html: contentHtml,
      content_text: contentText,
      is_auto_save: isAutoSave,
      slide_elements: slideElements,
      slide_backgrounds: slideBackgroundsArray  // ✅ Include backgrounds
    };

    // Send to backend
    const response = await fetch(`/api/documents/${documentId}`, {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${firebaseToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new Error('Save failed');
    }

    const data = await response.json();

    console.log('✅ Document saved:', {
      version: data.version,
      slideCount: slideElements.length,
      backgroundsCount: slideBackgroundsArray.length
    });

  } catch (error) {
    console.error('❌ Save failed:', error);
  }
}
```

### Load and Restore Backgrounds

```typescript
async function loadDocument(documentId: string): Promise<void> {
  try {
    const response = await fetch(`/api/documents/${documentId}`, {
      headers: {
        'Authorization': `Bearer ${firebaseToken}`
      }
    });

    if (!response.ok) {
      throw new Error('Load failed');
    }

    const data = await response.json();

    // Restore slide backgrounds (convert Array to Map)
    const backgroundsMap = new Map();
    if (data.slide_backgrounds && Array.isArray(data.slide_backgrounds)) {
      data.slide_backgrounds.forEach((item: any) => {
        backgroundsMap.set(item.slideIndex, item.background);
      });
    }

    // Set state
    setSlideBackgrounds(backgroundsMap);
    setDocumentTitle(data.title);
    setContentHtml(data.content_html);

    // Pass to SlideEditor component
    // SlideEditor will apply backgrounds via initialSlideBackgrounds prop

    console.log('✅ Document loaded:', {
      documentId: data.document_id,
      backgroundsCount: backgroundsMap.size
    });

  } catch (error) {
    console.error('❌ Load failed:', error);
  }
}
```

---

## Support

Nếu có vấn đề:
1. Check backend logs: search for `[SLIDE_BACKGROUNDS]`
2. Verify request payload có `slide_backgrounds` field
3. Check response có return `slide_backgrounds`
4. Validate background data format match schema

---

**Last Updated:** December 20, 2025
**API Version:** 1.0.0
**Status:** ✅ Production Ready
