# Public Presentation API Specification

**Last Updated:** January 6, 2026
**Endpoint:** `GET /public/presentations/{public_token}`
**Authentication:** None (public access)

---

## 📋 Overview

API trả về presentation data, subtitles, và audio files dựa trên sharing settings. Hỗ trợ đa ngôn ngữ và backward compatibility.

---

## 🔗 Request

```http
GET /api/public/presentations/{public_token}?public_token={public_token}
```

### Parameters
- `public_token` (path & query): Token công khai của presentation (format: `pub_xxxxxxxx`)

### Example
```bash
curl https://app.wordai.vn/api/public/presentations/pub_eea2bdac7e06?public_token=pub_eea2bdac7e06
```

---

## ✅ Response Structure

### Root Response Object

```typescript
{
  success: boolean,
  presentation: PresentationData,
  subtitles: SubtitleData | null,        // Default language (backward compat)
  audio_files: AudioFile[],              // Default language (backward compat)
  languages: LanguageData[],             // Multi-language support
  sharing_settings: SharingSettings
}
```

---

## 📦 Data Types

### 1. PresentationData

```typescript
{
  id: string,                    // MongoDB ObjectId
  document_id: string,           // Document ID (e.g., "doc_06de72fea3d7")
  title: string,                 // Presentation title
  document_type: string,         // "slide" | "document"

  // ⚠️ Only included if sharing_settings.include_content = true
  content_html?: string,         // Raw HTML content
  slide_elements?: SlideElement[],  // 🆕 CHANGED: Now maps from slide_backgrounds
  slide_backgrounds?: SlideElement[]  // Original field (same as slide_elements)
}
```

#### SlideElement Format

**🔥 KEY CHANGE:** `slide_elements` giờ được map từ `slide_backgrounds`

```typescript
type SlideElement = {
  slideIndex: number,          // Slide number (0-based)
  elements: Element[]          // Array of visual elements
}

type Element = {
  id: string,                  // Unique element ID
  type: "text" | "image" | "shape" | "chart",
  x: number,                   // Position X (pixels)
  y: number,                   // Position Y (pixels)
  width: number,               // Width (pixels)
  height: number,              // Height (pixels)
  zIndex: number,              // Layer order

  // Text-specific fields
  content?: string,            // Text content
  fontSize?: number,
  fontFamily?: string,
  color?: string,
  fontWeight?: string,
  textAlign?: string,

  // Image-specific fields
  src?: string,                // Image URL or data URI
  objectFit?: string,          // "contain" | "cover"

  // Common fields
  opacity?: number,
  rotation?: number,
  backgroundColor?: string
}
```

**Ví dụ thực tế:**
```json
{
  "slide_elements": [
    {
      "slideIndex": 8,
      "elements": [
        {
          "id": "image-1767635679829-dmvrlcmx9",
          "type": "image",
          "x": 91.66666666666667,
          "y": 33.33333333333333,
          "width": 190,
          "height": 143,
          "zIndex": 100,
          "src": "data:image/png;base64,iVBORw0KGgo...",
          "objectFit": "contain",
          "opacity": 1
        }
      ]
    }
  ]
}
```

---

### 2. SubtitleData (Default Language Only)

Dùng cho backward compatibility. Frontend mới nên dùng `languages` array.

```typescript
{
  id: string,
  presentation_id: string,
  language: string,              // "vi" | "en" | "zh" | etc.
  version: number,               // Version number (incremental)
  slides: SlideSubtitle[],
  created_at: string,            // ISO timestamp
  audio_status?: "pending" | "processing" | "completed" | "failed"
}

type SlideSubtitle = {
  slide_index: number,
  text: string,                  // Full subtitle text
  segments: SubtitleSegment[]
}

type SubtitleSegment = {
  text: string,
  start_time: number,            // Seconds
  end_time: number,              // Seconds
  segment_index: number
}
```

---

### 3. AudioFile (Default Language Only)

```typescript
{
  _id: string,
  slide_index: number,
  audio_url: string,             // Public URL to audio file
  duration: number,              // Duration in seconds
  slide_timestamps: number[],    // Timestamps for auto-advance
  audio_type: "narration" | "music",
  chunk_index: number,           // For chunked audio
  total_chunks: number
}
```

---

### 4. LanguageData (Multi-Language Support) 🌍

**🆕 Frontend nên dùng array này thay vì `subtitles` + `audio_files`**

```typescript
{
  language: string,              // "vi" | "en" | "zh"
  subtitle_id: string,           // Subtitle document ID
  version: number,               // Subtitle version
  is_default: boolean,           // True if default language
  slides: SlideSubtitle[],       // Same format as SubtitleData.slides
  total_duration: number,        // Total audio duration (seconds)
  audio_url: string | null,      // Merged audio URL (if available)
  audio_id: string | null,       // Merged audio ID
  audio_status: string | null,   // "completed" | "processing" | etc.
  audio_files: AudioFile[]       // Per-slide audio files
}
```

---

### 5. SharingSettings

```typescript
{
  is_public: boolean,            // True if publicly accessible
  include_content: boolean,      // Include slide_elements/backgrounds
  include_subtitles: boolean,    // Include subtitle data
  include_audio: boolean,        // Include audio files
  default_language: string,      // Default language code
  allowed_languages: string[],   // Allowed language codes
  expires_at?: string,           // ISO timestamp (optional)
  password_required?: boolean,
  allow_download?: boolean,
  show_branding?: boolean
}
```

---

## 🎯 Frontend Integration Guide

### Recommended Approach (Multi-Language)

```typescript
// Fetch presentation
const response = await fetch(`/api/public/presentations/${token}?public_token=${token}`);
const data = await response.json();

// Access slide elements (🆕 NOW POPULATED!)
const slideElements = data.presentation.slide_elements;
console.log(`Found ${slideElements.length} slides with elements`);

// Get all available languages
const languages = data.languages;
const defaultLang = languages.find(l => l.is_default);

// Switch language
function switchLanguage(langCode: string) {
  const langData = languages.find(l => l.language === langCode);
  if (langData) {
    renderSubtitles(langData.slides);
    playAudio(langData.audio_url || langData.audio_files);
  }
}

// Render slides with elements
function renderSlides(slideElements) {
  slideElements.forEach(slide => {
    const slideContainer = document.getElementById(`slide-${slide.slideIndex}`);

    slide.elements.forEach(element => {
      if (element.type === 'image') {
        const img = document.createElement('img');
        img.src = element.src;
        img.style.left = `${element.x}px`;
        img.style.top = `${element.y}px`;
        img.style.width = `${element.width}px`;
        img.style.height = `${element.height}px`;
        slideContainer.appendChild(img);
      }
      // Handle other element types...
    });
  });
}
```

### Backward Compatible Approach

```typescript
// For legacy code, still works
const subtitles = data.subtitles;      // Default language
const audioFiles = data.audio_files;   // Default language

if (subtitles) {
  renderSubtitles(subtitles.slides);
}
```

---

## 🔄 Migration Notes

### Before (Old Behavior)
```json
{
  "presentation": {
    "slide_elements": null,           // ❌ Was null
    "slide_backgrounds": [...]        // ✅ Had data
  }
}
```

### After (New Behavior - dd08b6a)
```json
{
  "presentation": {
    "slide_elements": [...],          // ✅ Now populated from slide_backgrounds
    "slide_backgrounds": [...]        // ✅ Still available
  }
}
```

**Mapping Logic:**
```python
slide_backgrounds = presentation.get("slide_backgrounds")
if slide_backgrounds:
    presentation_data["slide_elements"] = slide_backgrounds  # 🔄 Direct mapping
else:
    presentation_data["slide_elements"] = presentation.get("slide_elements")  # Fallback
```

---

## ⚠️ Important Notes

1. **`slide_elements` = `slide_backgrounds`**: Cùng 1 data structure, chỉ khác tên field
2. **Multi-language**: Luôn dùng `languages` array, không dùng `subtitles` root field
3. **Audio fallback**: Nếu version mới không có audio, API tự động lấy từ version cũ
4. **Access tracking**: Mỗi request tăng access count trong sharing stats
5. **Sharing settings**: Check `include_content`, `include_subtitles`, `include_audio` trước khi render

---

## 📊 Example Full Response

```json
{
  "success": true,
  "presentation": {
    "id": "67795f5a8b0dcd0c02b65a8d",
    "document_id": "doc_06de72fea3d7",
    "title": "Slide về AI Marketing 2026",
    "document_type": "slide",
    "slide_elements": [
      {
        "slideIndex": 8,
        "elements": [
          {
            "id": "image-1767635679829",
            "type": "image",
            "x": 91.67,
            "y": 33.33,
            "width": 190,
            "height": 143,
            "zIndex": 100,
            "src": "data:image/png;base64,...",
            "objectFit": "contain",
            "opacity": 1
          }
        ]
      }
    ]
  },
  "subtitles": {
    "id": "...",
    "language": "vi",
    "version": 3,
    "slides": [...]
  },
  "audio_files": [...],
  "languages": [
    {
      "language": "vi",
      "is_default": true,
      "subtitle_id": "...",
      "version": 3,
      "slides": [...],
      "total_duration": 120.5,
      "audio_url": "https://storage/.../merged.mp3",
      "audio_files": [...]
    },
    {
      "language": "en",
      "is_default": false,
      "subtitle_id": "...",
      "version": 2,
      "slides": [...],
      "total_duration": 115.3,
      "audio_url": null,
      "audio_files": [...]
    }
  ],
  "sharing_settings": {
    "is_public": true,
    "include_content": true,
    "include_subtitles": true,
    "include_audio": true,
    "default_language": "vi",
    "allowed_languages": ["vi", "en", "zh"]
  }
}
```

---

## 🚀 Deployment

- **Commit:** `dd08b6a`
- **Deployed:** January 6, 2026
- **Status:** ✅ All containers healthy
- **Breaking Changes:** None (backward compatible)
