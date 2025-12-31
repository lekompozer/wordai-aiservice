# Presentation Mode API Guide

## Overview

API endpoints để xử lý **presentation mode** (xem lại presentation với subtitle + audio).

Hỗ trợ:
- Nhiều ngôn ngữ (vi, en, zh, ...)
- Nhiều version cho mỗi ngôn ngữ
- User chọn default version cho từng ngôn ngữ
- Tự động fallback sang latest version nếu không có preference

---

## Core Concepts

### Version Management

Mỗi lần generate subtitle mới cho cùng ngôn ngữ → **version tăng lên**:

```
English: Version 1 → Version 2 → Version 3
Vietnamese: Version 1 → Version 2
Chinese: Version 1
```

### Default Version Selection

User có thể chọn version nào hiển thị mặc định:

**Ví dụ:**
- English có 3 versions
- User thích version 1 nhất
- Set version 1 as default
- Player sẽ load version 1 thay vì version 3 (latest)

### Latest vs Default

- **Latest**: Version cao nhất (tự động)
- **Default**: Version user chọn (thủ công)

Nếu user không set default → tự động dùng latest.

---

## API Endpoints

### 1. Get Player Data (Main Endpoint)

**GET** `/api/presentations/{presentation_id}/player-data`

Lấy **TẤT CẢ** subtitle + audio data cho presentation mode.

**Headers:**
```
Authorization: Bearer <firebase_token>
```

**Response:**
```json
{
  "success": true,
  "presentation_id": "doc_c49e8af18c03",
  "available_languages": ["vi", "en", "zh"],
  "total_versions": 5,
  "languages": [
    {
      "language": "vi",
      "subtitle_id": "69541bd00ba86cce6e4b8bab",
      "version": 2,
      "is_default": true,    // User đã set version 2 làm default
      "is_latest": true,     // Version 2 cũng là latest
      "slides": [
        {
          "slide_index": 0,
          "subtitles": [
            {
              "text": "Chào mừng đến với bài thuyết trình",
              "start_time": 0.0,
              "end_time": 3.5,
              "duration": 3.5
            }
          ]
        }
      ],
      "total_duration": 186.4,
      "audio_url": "https://r2.wordai.app/audio/lib_cb56643814ff.wav",
      "audio_id": "67743bd00ba86cce6e4b8bac",
      "audio_status": "ready",
      "created_at": "2025-12-31T09:47:19.387Z",
      "updated_at": "2025-12-31T09:47:19.387Z"
    },
    {
      "language": "en",
      "subtitle_id": "69541bd00ba86cce6e4b8bad",
      "version": 1,
      "is_default": false,   // Không có preference, dùng latest
      "is_latest": true,
      "slides": [...],
      "total_duration": 202.0,
      "audio_url": "https://r2.wordai.app/audio/lib_0d39d814b234.wav",
      "audio_id": "67743bd00ba86cce6e4b8bae",
      "audio_status": "ready",
      "created_at": "2025-12-31T09:47:23.791Z",
      "updated_at": "2025-12-31T09:47:23.791Z"
    }
  ]
}
```

**Frontend Usage:**

```typescript
async function loadPresentationPlayer(presentationId: string) {
  const response = await fetch(
    `/api/presentations/${presentationId}/player-data`,
    {
      headers: {
        'Authorization': `Bearer ${firebaseToken}`
      }
    }
  );

  const data = await response.json();

  // Initialize player with all languages
  data.languages.forEach(lang => {
    // Load subtitles
    loadSubtitles(lang.slides);

    // Load audio if available
    if (lang.audio_url && lang.audio_status === 'ready') {
      loadAudio(lang.audio_url, lang.total_duration);
    }

    // Show badge
    const badge = lang.is_default ? 'Default' :
                  lang.is_latest ? 'Latest' :
                  `v${lang.version}`;

    showLanguageOption(lang.language, badge);
  });
}
```

---

### 2. Set Default Version

**PUT** `/api/presentations/{presentation_id}/preferences/{language}/default`

Chọn version nào làm mặc định cho language.

**Headers:**
```
Authorization: Bearer <firebase_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "subtitle_id": "69541bd00ba86cce6e4b8bab"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Default version set for en",
  "presentation_id": "doc_c49e8af18c03",
  "language": "en",
  "subtitle_id": "69541bd00ba86cce6e4b8bab",
  "version": 1
}
```

**Frontend Usage:**

```typescript
async function setDefaultVersion(
  presentationId: string,
  language: string,
  subtitleId: string
) {
  const response = await fetch(
    `/api/presentations/${presentationId}/preferences/${language}/default`,
    {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${firebaseToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ subtitle_id: subtitleId })
    }
  );

  const result = await response.json();

  if (result.success) {
    console.log(`✅ Version ${result.version} set as default for ${language}`);

    // Reload player data to reflect change
    await loadPresentationPlayer(presentationId);
  }
}
```

---

### 3. List All Subtitle Versions

**GET** `/api/presentations/{presentation_id}/subtitles/v2?language={lang}`

Lấy **TẤT CẢ** versions cho một ngôn ngữ (để hiển thị dropdown chọn version).

**Query Parameters:**
- `language` (optional): Filter by language code

**Headers:**
```
Authorization: Bearer <firebase_token>
```

**Response:**
```json
{
  "success": true,
  "total_count": 3,
  "subtitles": [
    {
      "_id": "69541bd00ba86cce6e4b8bab",
      "presentation_id": "doc_c49e8af18c03",
      "language": "en",
      "version": 3,
      "mode": "academy",
      "status": "completed",
      "audio_status": "ready",
      "audio_url": "https://r2.wordai.app/audio/lib_v3.wav",
      "total_duration": 210.5,
      "created_at": "2025-12-31T11:00:00Z"
    },
    {
      "_id": "69541bd00ba86cce6e4b8bac",
      "language": "en",
      "version": 2,
      "audio_status": "ready",
      "total_duration": 202.0,
      "created_at": "2025-12-31T10:00:00Z"
    },
    {
      "_id": "69541bd00ba86cce6e4b8bad",
      "language": "en",
      "version": 1,
      "audio_status": "ready",
      "total_duration": 186.4,
      "created_at": "2025-12-31T09:00:00Z"
    }
  ]
}
```

**Frontend Usage:**

```typescript
async function loadVersionDropdown(presentationId: string, language: string) {
  const response = await fetch(
    `/api/presentations/${presentationId}/subtitles/v2?language=${language}`,
    {
      headers: {
        'Authorization': `Bearer ${firebaseToken}`
      }
    }
  );

  const data = await response.json();

  // Build dropdown options
  data.subtitles.forEach(subtitle => {
    const option = {
      label: `Version ${subtitle.version} - ${formatDate(subtitle.created_at)}`,
      value: subtitle._id,
      isLatest: subtitle.version === data.subtitles[0].version
    };

    addDropdownOption(option);
  });
}
```

---

## UI/UX Recommendations

### Language Selector

```
┌────────────────────────────────┐
│ Language:                      │
│ ○ Vietnamese (Default, v2) ✓   │
│ ○ English (Latest, v3)         │
│ ○ Chinese (v1)                 │
└────────────────────────────────┘
```

### Version Selector (when clicked "...")

```
┌────────────────────────────────┐
│ English Versions:              │
│ ○ v3 - Latest (Dec 31, 11:00)  │
│ ● v2 - Default (Dec 31, 10:00) │ ← Currently selected
│ ○ v1 - (Dec 31, 09:00)         │
│                                │
│ [Set as Default]               │
└────────────────────────────────┘
```

### Badges

- **Default**: User-selected version (green badge)
- **Latest**: Highest version number (blue badge)
- **v{N}**: Version number only (gray badge)

---

## Workflow Examples

### Example 1: Normal Playback (No Preferences)

```
User opens presentation
  ↓
GET /player-data
  ↓
Response: vi (v2, latest), en (v1, latest)
  ↓
Load Vietnamese v2 (default language)
  ↓
User switches to English
  ↓
Load English v1
```

### Example 2: With Preferences

```
User generates English v2
  ↓
But prefers v1 narration style
  ↓
PUT /preferences/en/default {subtitle_id: v1_id}
  ↓
GET /player-data
  ↓
Response: en (v1, is_default: true, is_latest: false)
  ↓
Player loads v1 instead of v2
  ↓
UI shows "Default (v1)" badge
```

### Example 3: Generate New Version

```
User has: vi v2 (default), en v1 (default)
  ↓
Generate new English subtitles
  ↓
Now has: en v1 (default), en v2 (latest)
  ↓
GET /player-data
  ↓
Still loads en v1 (respects user preference)
  ↓
UI shows: "Default (v1)" and "New: v2 available"
```

---

## Error Handling

### 404 Errors

```json
{
  "detail": "Subtitle not found or not owned by you"
}
```

**Causes:**
- Invalid subtitle_id
- Subtitle belongs to different user
- Subtitle deleted

**Frontend Action:**
- Clear preference from localStorage
- Reload player-data (will use latest)

### 400 Errors

```json
{
  "detail": "Subtitle language 'vi' does not match 'en'"
}
```

**Causes:**
- Wrong language in URL path
- Subtitle_id for different language

**Frontend Action:**
- Validate language before API call
- Show error message to user

---

## MongoDB Collections

### presentation_preferences

```javascript
{
  _id: ObjectId("..."),
  presentation_id: "doc_c49e8af18c03",
  user_id: "firebase_uid_123",
  preferences: {
    "vi": {
      subtitle_id: "69541bd00ba86cce6e4b8bab",
      version: 2,
      updated_at: ISODate("2025-12-31T10:00:00Z")
    },
    "en": {
      subtitle_id: "69541bd00ba86cce6e4b8bad",
      version: 1,
      updated_at: ISODate("2025-12-31T09:00:00Z")
    }
  },
  updated_at: ISODate("2025-12-31T10:00:00Z")
}
```

**Indexes:**
```javascript
db.presentation_preferences.createIndex(
  { presentation_id: 1, user_id: 1 },
  { unique: true }
)
```

---

## Migration Notes

Existing presentations **không cần migration**:
- Endpoint tự động fallback sang latest version
- Preferences collection tạo mới khi user set default lần đầu
- Backward compatible với presentations cũ

---

## Testing Checklist

- [ ] Generate 2 versions for same language
- [ ] Set version 1 as default
- [ ] Verify /player-data returns version 1
- [ ] Generate version 3
- [ ] Verify still returns version 1 (not version 3)
- [ ] Delete default preference
- [ ] Verify returns version 3 (latest)
- [ ] Test with multiple languages simultaneously
- [ ] Test 404 error (invalid subtitle_id)
- [ ] Test 400 error (wrong language)

---

**Last Updated:** December 31, 2025
**Backend Version:** e207fab
