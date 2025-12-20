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

### 1. Create/Load Document

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

### 2. Get Document

**Endpoint:** `GET /api/documents/{document_id}`

**Response:** Giống như Create/Load Document

**Notes:**
- Trả về đầy đủ `slide_backgrounds` đã lưu
- Frontend restore backgrounds vào SlideEditor component

---

### 3. Save Document (Update)

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

### Edge Cases

- [ ] Save empty backgrounds array → no errors
- [ ] Save null backgrounds → handled gracefully
- [ ] Large gradient array (10+ colors) → saved correctly
- [ ] Image URLs with special characters → encoded properly
- [ ] Concurrent saves (auto + manual) → no race conditions

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
