# Multi-Language Narration API - Frontend Technical Specification

**Version**: 2.0
**Date**: December 24, 2025
**Base URL**: `https://ai.wordai.vn` or `http://localhost:8000`
**Authentication**: Firebase ID Token in `Authorization: Bearer <token>` header

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Subtitle Management](#subtitle-management)
4. [Audio Management](#audio-management)
5. [Sharing Configuration](#sharing-configuration)
6. [Public Access (No Auth)](#public-access-no-auth)
7. [Document Metadata](#document-metadata)
8. [Error Handling](#error-handling)
9. [Migration Notes](#migration-notes)

---

## Overview

The Multi-Language Narration System supports:
- **Multiple languages** per presentation (vi, en, zh, etc.)
- **Version management** per language (each language has independent versions)
- **Audio generation** (AI-powered) and **audio upload** (user-provided files)
- **Public sharing** with configurable access (content, subtitles, audio)
- **Private sharing** with specific users (view, comment, edit permissions)

### Key Concepts

- **Subtitle Document**: Contains subtitles for ONE language + ONE version
- **Audio Document**: Audio file for ONE slide in ONE subtitle document
- **Sharing Config**: Presentation-level public/private sharing settings
- **Version**: Auto-increments per language (vi v1, v2, v3; en v1, v2)

---

## Authentication

All authenticated endpoints require Firebase ID Token:

```
Authorization: Bearer <firebase_id_token>
```

Public endpoints (prefixed with `/api/public/`) do NOT require authentication.

---

## Subtitle Management

### 1. Generate Subtitles

**Endpoint**: `POST /api/presentations/{presentation_id}/subtitles/v2`
**Auth**: Required
**Points**: Deducts 2 points

**Request Body**:
```json
{
  "language": "vi",           // Language code: vi, en, zh, etc.
  "mode": "presentation",     // "presentation" or "academy"
  "user_query": ""            // Optional: User instructions for narration style
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "subtitle": {
    "_id": "694ba23225add25de18b0589",
    "presentation_id": "doc_1f4a9dadba09",
    "user_id": "firebase_user_123",
    "language": "vi",
    "version": 1,                          // Auto-incremented per language
    "mode": "presentation",
    "slides": [
      {
        "slide_index": 0,
        "subtitles": [
          {
            "text": "Chào mừng đến với bài thuyết trình",
            "element_references": "",
            "timestamp": null
          }
        ]
      }
    ],
    "status": "completed",
    "created_at": "2025-12-24T08:15:30Z",
    "updated_at": "2025-12-24T08:15:30Z",
    "metadata": {
      "total_slides": 23,
      "word_count": 450
    }
  },
  "points_deducted": 2
}
```

**Errors**:
- `400`: Invalid language or mode
- `403`: Insufficient points
- `404`: Presentation not found
- `500`: Generation failed

---

### 2. List Subtitles

**Endpoint**: `GET /api/presentations/{presentation_id}/subtitles/v2`
**Auth**: Required
**Query Parameters**:
- `language` (optional): Filter by language code (e.g., `?language=vi`)

**Response** (200 OK):
```json
{
  "success": true,
  "subtitles": [
    {
      "_id": "694ba23225add25de18b058c",
      "presentation_id": "doc_1f4a9dadba09",
      "user_id": "firebase_user_123",
      "language": "vi",
      "version": 3,
      "mode": "presentation",
      "slides": [...],
      "status": "completed",
      "created_at": "2025-12-24T08:20:00Z",
      "updated_at": "2025-12-24T08:20:00Z",
      "metadata": {
        "total_slides": 23,
        "word_count": 480
      }
    },
    {
      "_id": "694ba23225add25de18b058b",
      "language": "vi",
      "version": 2,
      "..."
    }
  ],
  "total_count": 3
}
```

**Notes**:
- Results ordered by language (asc), then version (desc)
- Latest version appears first for each language
- **Frontend should process this list to:**
  1. Group by language: `{ vi: [v3, v2, v1], en: [v2, v1] }`
  2. Find overall latest: Compare all `created_at` or `updated_at` timestamps
  3. Auto-select language of overall latest version
  4. Auto-select latest version within that language

---

### 2.1. Frontend Processing Example

**Given API Response**:
```json
{
  "subtitles": [
    {"_id": "id3", "language": "en", "version": 2, "created_at": "2025-12-24T10:00:00Z"},
    {"_id": "id2", "language": "en", "version": 1, "created_at": "2025-12-24T09:00:00Z"},
    {"_id": "id1", "language": "vi", "version": 3, "created_at": "2025-12-24T11:00:00Z"},
    {"_id": "id4", "language": "vi", "version": 2, "created_at": "2025-12-24T08:00:00Z"},
    {"_id": "id5", "language": "vi", "version": 1, "created_at": "2025-12-24T07:00:00Z"}
  ]
}
```

**Frontend Processing Steps**:

1. **Group by Language**:
```typescript
const grouped = {
  vi: [
    {id: "id1", version: 3, created_at: "2025-12-24T11:00:00Z"},
    {id: "id4", version: 2, created_at: "2025-12-24T08:00:00Z"},
    {id: "id5", version: 1, created_at: "2025-12-24T07:00:00Z"}
  ],
  en: [
    {id: "id3", version: 2, created_at: "2025-12-24T10:00:00Z"},
    {id: "id2", version: 1, created_at: "2025-12-24T09:00:00Z"}
  ]
}
```

2. **Find Overall Latest** (most recent `created_at`):
```typescript
const allSubtitles = response.subtitles;
const overallLatest = allSubtitles.reduce((latest, current) => {
  return new Date(current.created_at) > new Date(latest.created_at)
    ? current
    : latest;
});
// Result: {language: "vi", version: 3, created_at: "2025-12-24T11:00:00Z"}
```

3. **Set Default UI State**:
```typescript
const defaultLanguage = overallLatest.language; // "vi"
const defaultVersion = overallLatest.version;   // 3
const defaultSubtitleId = overallLatest._id;    // "id1"

// Language Dropdown: Selected = "vi"
// Version Dropdown: Selected = 3, Options = [3, 2, 1]
// Display Content: Subtitle with id="id1"
```

4. **When User Switches Language**:
```typescript
function onLanguageChange(newLanguage) {
  const versionsForLanguage = grouped[newLanguage];
  const latestVersion = versionsForLanguage[0]; // Already sorted desc

  setSelectedLanguage(newLanguage);
  setSelectedVersion(latestVersion.version);
  setSelectedSubtitleId(latestVersion.id);
  fetchSubtitleDetail(latestVersion.id); // GET /subtitles/v2/{id}
}
```

5. **When User Switches Version**:
```typescript
function onVersionChange(newVersion) {
  const subtitle = grouped[selectedLanguage].find(s => s.version === newVersion);

  setSelectedVersion(newVersion);
  setSelectedSubtitleId(subtitle.id);
  fetchSubtitleDetail(subtitle.id); // GET /subtitles/v2/{id}
}
```

**UI Flow Summary**:
- **Load**: Fetch all subtitles → Process → Auto-select overall latest (Vi v3)
- **Language Dropdown**: Shows available languages (Vi, En)
- **Version Dropdown**: Shows versions for selected language (3, 2, 1)
- **Auto-Select**: Latest version of selected language
- **Detail View**: Fetch specific subtitle by ID when selection changes

---

### 3. Get Specific Subtitle

**Endpoint**: `GET /api/presentations/{presentation_id}/subtitles/v2/{subtitle_id}`
**Auth**: Required

**Response** (200 OK):
```json
{
  "success": true,
  "subtitle": {
    "_id": "694ba23225add25de18b058c",
    "presentation_id": "doc_1f4a9dadba09",
    "language": "vi",
    "version": 3,
    "slides": [
      {
        "slide_index": 0,
        "subtitles": [
          {
            "text": "Chào mừng đến với bài thuyết trình",
            "element_references": "",
            "timestamp": null
          }
        ]
      }
    ],
    "..."
  }
}
```

**Errors**:
- `404`: Subtitle not found or unauthorized

---

### 4. Delete Subtitle

**Endpoint**: `DELETE /api/presentations/{presentation_id}/subtitles/v2/{subtitle_id}`
**Auth**: Required

**Response** (200 OK):
```json
{
  "success": true,
  "message": "Subtitle and audio deleted"
}
```

**Notes**:
- Also deletes all associated audio files
- Only owner can delete

**Errors**:
- `404`: Subtitle not found
- `403`: Unauthorized (not owner)

---

## Audio Management

### Supported Languages & Voices

**17 Supported Languages**:
- 🇬🇧 English (en) → TTS: `en-US`
- 🇻🇳 Tiếng Việt (vi) → TTS: `vi-VN`
- 🇨🇳 Chinese Simplified (zh-CN) → TTS: `zh-CN`
- 🇹🇼 Chinese Traditional (zh-TW) → TTS: `zh-TW`
- 🇯🇵 Japanese (ja) → TTS: `ja-JP`
- 🇰🇷 Korean (ko) → TTS: `ko-KR`
- 🇹🇭 Thai (th) → TTS: `th-TH`
- 🇮🇩 Indonesian (id) → TTS: `id-ID`
- 🇰🇭 Khmer (km) → TTS: `km-KH`
- 🇱🇦 Lao (lo) → TTS: `lo-LA`
- 🇮🇳 Hindi (hi) → TTS: `hi-IN`
- 🇲🇾 Malay (ms) → TTS: `ms-MY`
- 🇵🇹 Portuguese (pt) → TTS: `pt-PT`
- 🇷🇺 Russian (ru) → TTS: `ru-RU`
- 🇫🇷 French (fr) → TTS: `fr-FR`
- 🇩🇪 German (de) → TTS: `de-DE`
- 🇪🇸 Spanish (es) → TTS: `es-ES`

**Gemini TTS Voice Options**:

**Male Voices**:
`Puck`, `Charon`, `Fenrir`, `Orus`, `Enceladus`, `Iapetus`, `Algieba`, `Algenib`, `Rasalgethi`, `Alnilam`, `Gacrux`, `Zubenelgenubi`, `Sadaltager`

**Female Voices**:
`Kore`, `Leda`, `Aoede`, `Callirrhoe`, `Autonoe`, `Despina`, `Erinome`, `Laomedeia`, `Achernar`, `Pulcherrima`, `Vindemiatrix`, `Sadachbia`, `Sulafat`

**Neutral Voices**:
`Zephyr`, `Umbriel`, `Schedar`, `Achird`

**Note**: Not all voices support all languages. Check Gemini TTS documentation for language-voice compatibility.

---

### 1. Generate Audio (AI)

**Endpoint**: `POST /api/presentations/{presentation_id}/subtitles/v2/{subtitle_id}/audio`
**Auth**: Required
**Points**: Deducts 2 points

**Request Body**:
```json
{
  "voice_config": {
    "provider": "google",
    "voices": [                           // ⚠️ REQUIRED field
      {
        "voice_name": "Kore",             // Gemini TTS voice (see list above)
        "language": "vi-VN",              // TTS language code (see mapping above)
        "speaking_rate": 1.0,             // Speed: 0.5 - 2.0
        "pitch": 0.0                      // Optional: -20.0 to 20.0
      }
    ],
    "use_pro_model": true
  }
}
```

**Important Notes**:
- **`voices` array is REQUIRED** - Must contain at least one voice configuration
- **`voice_name`**: Use one of the Gemini TTS voices listed above
- **`language`**: Must use TTS language code (e.g., `vi-VN`, not `vi`)
- **`speaking_rate`**: Controls speech speed (0.5 = slow, 1.0 = normal, 2.0 = fast)
- **Frontend must map subtitle language to TTS language**:
  - Subtitle language `vi` → Voice language `vi-VN`
  - Subtitle language `en` → Voice language `en-US`
  - Subtitle language `zh-CN` → Voice language `zh-CN`

**Example Request for Vietnamese**:
```json
{
  "voice_config": {
    "provider": "google",
    "voices": [
      {
        "voice_name": "Kore",
        "language": "vi-VN",
        "speaking_rate": 1.0
      }
    ],
    "use_pro_model": true
  }
}
```

**Example Request for English**:
```json
{
  "voice_config": {
    "provider": "google",
    "voices": [
      {
        "voice_name": "Puck",
        "language": "en-US",
        "speaking_rate": 1.0
      }
    ],
    "use_pro_model": true
  }
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "audio_files": [
    {
      "_id": "694ba50a25add25de18b0590",
      "presentation_id": "doc_1f4a9dadba09",
      "subtitle_id": "694ba23225add25de18b058c",
      "user_id": "firebase_user_123",
      "language": "vi",
      "version": 3,
      "slide_index": 0,
      "audio_url": "https://cdn.r2.wordai.vn/narration_abc123_slide_0_vi_v3.mp3",
      "audio_metadata": {
        "duration_seconds": 15.5,
        "file_size_bytes": 245678,
        "format": "mp3",
        "sample_rate": 44100
      },
      "generation_method": "ai_generated",
      "voice_config": {
        "provider": "google",
        "voices": [...]
      },
      "status": "ready",
      "created_at": "2025-12-24T08:25:00Z",
      "updated_at": "2025-12-24T08:25:00Z"
    }
  ],
  "points_deducted": 2
}
```

**Notes**:
- Generates audio for ALL slides in the subtitle document
- Audio also stored in `library_audio` collection (existing behavior)

**Errors**:
- `400`: Invalid voice config
- `403`: Insufficient points or unauthorized
- `404`: Subtitle not found
- `500`: Audio generation failed

---

### 2. Upload Audio (User File)

**Endpoint**: `POST /api/presentations/{presentation_id}/subtitles/v2/{subtitle_id}/audio/upload`
**Auth**: Required
**Points**: NO points deducted

**Request Body**:
```json
{
  "slide_index": 0,
  "audio_file": "<base64_encoded_audio>",
  "audio_metadata": {
    "duration_seconds": 12.3,
    "file_size_bytes": 198400,
    "format": "mp3",
    "sample_rate": 44100
  }
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "audio": {
    "_id": "694ba60b25add25de18b0591",
    "presentation_id": "doc_1f4a9dadba09",
    "subtitle_id": "694ba23225add25de18b058c",
    "user_id": "firebase_user_123",
    "language": "vi",
    "version": 3,
    "slide_index": 0,
    "audio_url": "https://cdn.r2.wordai.vn/uploaded_abc123_slide_0_vi_v3.mp3",
    "audio_metadata": {
      "duration_seconds": 12.3,
      "file_size_bytes": 198400,
      "format": "mp3",
      "sample_rate": 44100
    },
    "generation_method": "user_uploaded",
    "voice_config": null,
    "status": "ready",
    "created_at": "2025-12-24T08:30:00Z",
    "updated_at": "2025-12-24T08:30:00Z"
  }
}
```

**Notes**:
- Upload ONE audio file per slide
- NO points deduction (user-provided content)
- `audio_file` must be base64 encoded

**Errors**:
- `400`: Invalid audio file or metadata
- `403`: Unauthorized
- `404`: Subtitle not found
- `500`: Upload failed

---

### 3. List Audio Files

**Endpoint**: `GET /api/presentations/{presentation_id}/audio/v2`
**Auth**: Required
**Query Parameters**:
- `language` (optional): Filter by language (e.g., `?language=vi`)
- `version` (optional): Filter by version (e.g., `?version=3`)

**Response** (200 OK):
```json
{
  "success": true,
  "audio_files": [
    {
      "_id": "694ba50a25add25de18b0590",
      "presentation_id": "doc_1f4a9dadba09",
      "subtitle_id": "694ba23225add25de18b058c",
      "language": "vi",
      "version": 3,
      "slide_index": 0,
      "audio_url": "https://cdn.r2.wordai.vn/...",
      "audio_metadata": {...},
      "generation_method": "ai_generated",
      "..."
    }
  ],
  "total_count": 23
}
```

**Notes**:
- Results ordered by language, version, slide_index

---

### 4. Delete Audio

**Endpoint**: `DELETE /api/presentations/{presentation_id}/audio/v2/{audio_id}`
**Auth**: Required

**Response** (200 OK):
```json
{
  "success": true,
  "message": "Audio deleted"
}
```

**Errors**:
- `404`: Audio not found
- `403`: Unauthorized (not owner)

---

## Sharing Configuration

### 1. Get Sharing Config

**Endpoint**: `GET /api/presentations/{presentation_id}/sharing`
**Auth**: Required

**Response** (200 OK):
```json
{
  "success": true,
  "config": {
    "_id": "694ba70c25add25de18b0592",
    "presentation_id": "doc_1f4a9dadba09",
    "user_id": "firebase_user_123",
    "is_public": false,
    "public_token": null,
    "sharing_settings": {
      "include_content": true,
      "include_subtitles": true,
      "include_audio": true,
      "allowed_languages": [],           // Empty = all languages allowed
      "default_language": "vi",
      "require_attribution": true
    },
    "shared_with_users": [],
    "access_stats": {
      "total_views": 0,
      "unique_visitors": 0,
      "last_accessed": null
    },
    "created_at": "2025-12-24T08:00:00Z",
    "updated_at": "2025-12-24T08:00:00Z",
    "expires_at": null
  }
}
```

**Notes**:
- Auto-creates default config if not exists
- Only owner can view

---

### 2. Update Sharing Config

**Endpoint**: `PUT /api/presentations/{presentation_id}/sharing`
**Auth**: Required

**Request Body** (all fields optional):
```json
{
  "is_public": true,                     // Enable public access
  "sharing_settings": {
    "include_content": true,
    "include_subtitles": true,
    "include_audio": false,              // Hide audio from public
    "allowed_languages": ["vi", "en"],   // Restrict to specific languages
    "default_language": "vi",
    "require_attribution": true
  }
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "config": {
    "_id": "694ba70c25add25de18b0592",
    "is_public": true,
    "public_token": "abc123def456ghi789",   // Generated when enabling public
    "sharing_settings": {
      "include_content": true,
      "include_subtitles": true,
      "include_audio": false,
      "allowed_languages": ["vi", "en"],
      "default_language": "vi",
      "require_attribution": true
    },
    "..."
  }
}
```

**Notes**:
- `public_token` auto-generated when `is_public=true`
- Token persists even if `is_public` set back to `false` (for re-enable)
- Only owner can update

**Errors**:
- `403`: Unauthorized (not owner)
- `404`: Presentation not found

---

### 3. Share with Specific User

**Endpoint**: `POST /api/presentations/{presentation_id}/sharing/users`
**Auth**: Required
**Query Parameters**:
- `target_user_id` (required): User ID to share with
- `permission` (optional): `view`, `comment`, or `edit` (default: `view`)

**Response** (200 OK):
```json
{
  "success": true,
  "message": "User added to sharing list"
}
```

**Notes**:
- Only owner can share
- If user already in list, updates permission

**Errors**:
- `403`: Unauthorized (not owner)
- `404`: Presentation not found

---

## Public Access (No Auth)

### 1. Get Public Presentation

**Endpoint**: `GET /api/public/presentations/{public_token}`
**Auth**: NOT required

**Response** (200 OK):
```json
{
  "success": true,
  "presentation": {
    "id": "doc_1f4a9dadba09",
    "title": "AI Technology Overview",
    "document_type": "slide",
    "content_html": "<div>...</div>",        // If include_content=true
    "slide_elements": [...],                 // If include_content=true
    "slide_backgrounds": [...]               // If include_content=true
  },
  "subtitles": {                             // Latest version of default_language
    "_id": "694ba23225add25de18b058c",
    "language": "vi",
    "version": 3,
    "slides": [...]
  },
  "audio_files": [                           // If include_audio=true
    {
      "_id": "694ba50a25add25de18b0590",
      "slide_index": 0,
      "audio_url": "https://cdn.r2.wordai.vn/...",
      "audio_metadata": {...}
    }
  ],
  "sharing_settings": {
    "include_content": true,
    "include_subtitles": true,
    "include_audio": true,
    "allowed_languages": ["vi", "en"],
    "default_language": "vi",
    "require_attribution": true
  }
}
```

**Notes**:
- Returns latest version of default_language
- Respects sharing_settings (only includes enabled features)
- Increments access_stats

**Errors**:
- `404`: Presentation not found, not public, or token invalid
- `403`: Presentation expired

---

### 2. Get Public Subtitles

**Endpoint**: `GET /api/public/presentations/{public_token}/subtitles`
**Auth**: NOT required
**Query Parameters**:
- `language` (optional): Language code (default: default_language from config)
- `version` (optional): Version number or `latest` (default: `latest`)

**Response** (200 OK):
```json
{
  "success": true,
  "subtitle": {
    "_id": "694ba23225add25de18b058c",
    "presentation_id": "doc_1f4a9dadba09",
    "language": "vi",
    "version": 3,
    "slides": [
      {
        "slide_index": 0,
        "subtitles": [...]
      }
    ],
    "..."
  }
}
```

**Notes**:
- Checks `allowed_languages` filter
- Checks `include_subtitles` setting

**Errors**:
- `403`: Subtitles not shared or language not allowed
- `404`: Presentation or subtitles not found

---

### 3. Get Public Audio

**Endpoint**: `GET /api/public/presentations/{public_token}/audio`
**Auth**: NOT required
**Query Parameters**:
- `language` (optional): Language code (default: default_language)
- `version` (optional): Version number or `latest` (default: `latest`)

**Response** (200 OK):
```json
{
  "success": true,
  "audio_files": [
    {
      "_id": "694ba50a25add25de18b0590",
      "presentation_id": "doc_1f4a9dadba09",
      "subtitle_id": "694ba23225add25de18b058c",
      "language": "vi",
      "version": 3,
      "slide_index": 0,
      "audio_url": "https://cdn.r2.wordai.vn/...",
      "audio_metadata": {
        "duration_seconds": 15.5,
        "file_size_bytes": 245678,
        "format": "mp3",
        "sample_rate": 44100
      },
      "generation_method": "ai_generated",
      "status": "ready"
    }
  ]
}
```

**Notes**:
- Returns audio files for specific language + version
- Checks `allowed_languages` filter
- Checks `include_audio` setting

**Errors**:
- `403`: Audio not shared or language not allowed
- `404`: Presentation or audio not found

---

## Document Metadata

### Get Document with Narration Info

**Endpoint**: `GET /api/presentations/{document_id}`
**Auth**: Required

**Response** (200 OK):
```json
{
  "document_id": "doc_1f4a9dadba09",
  "title": "AI Technology Overview",
  "content_html": "<div>...</div>",
  "version": 1,
  "document_type": "slide",
  "narration_info": {
    "total_languages": 2,
    "languages": ["vi", "en"],
    "latest_versions": {
      "vi": 3,
      "en": 1
    },
    "has_audio": {
      "vi": true,
      "en": false
    }
  },
  "has_narration": true,           // ⚠️ DEPRECATED: Use narration_info
  "narration_count": 2,             // ⚠️ DEPRECATED: Use narration_info.total_languages
  "..."
}
```

**Notes**:
- `narration_info` provides quick overview
- To get full subtitle list with all versions, call `GET /api/presentations/{id}/subtitles/v2`
- **Determining Default Language**: Call list subtitles endpoint and find overall latest (see section 2.1)

**Frontend Initial Load Flow**:

```typescript
// 1. Get document metadata (quick overview)
const doc = await GET(`/api/presentations/${docId}`);
if (doc.narration_info && doc.narration_info.total_languages > 0) {
  // Has subtitles available

  // 2. Fetch all subtitles to determine overall latest
  const subtitles = await GET(`/api/presentations/${docId}/subtitles/v2`);

  // 3. Find overall latest (most recent created_at)
  const overallLatest = subtitles.subtitles.reduce((latest, current) => {
    return new Date(current.created_at) > new Date(latest.created_at)
      ? current
      : latest;
  });

  // 4. Set default state
  setLanguage(overallLatest.language);      // e.g., "vi"
  setVersion(overallLatest.version);        // e.g., 3
  setSubtitleId(overallLatest._id);         // e.g., "id1"

  // 5. Fetch detail for display
  const detail = await GET(`/api/presentations/${docId}/subtitles/v2/${overallLatest._id}`);
  displaySubtitles(detail.subtitle);
}
```
- `narration_info` replaces deprecated fields
- Frontend should use `narration_info` for UI decisions

---

## Error Handling

### Standard Error Response

```json
{
  "detail": "Error message here"
}
```

### HTTP Status Codes

- `200`: Success
- `400`: Bad request (invalid parameters)
- `401`: Unauthorized (missing or invalid auth token)
- `403`: Forbidden (insufficient permissions or points)
- `404`: Not found (resource doesn't exist)
- `500`: Internal server error

### Common Error Scenarios

**Insufficient Points**:
```json
{
  "detail": "Insufficient points. Need 2, have 0"
}
```

**Unauthorized Access**:
```json
{
  "detail": "Only owner can update sharing config"
}
```

**Not Found**:
```json
{
  "detail": "Subtitle not found"
}
```

**Public Access Denied**:
```json
{
  "detail": "Presentation not found or not public"
}
```

---

## Migration Notes

### Backward Compatibility

**Old Endpoints** (still functional for transition period):

#### Legacy Audio Generation
**Endpoint**: `POST /api/presentations/{id}/narration/{narration_id}/generate-audio`
**Auth**: Required
**Points**: Deducts 2 points

**Request Body**:
```json
{
  "narration_id": "694b78a29fa05c10b5b7fe28",
  "voice_config": {
    "provider": "google",
    "voices": [                           // ⚠️ REQUIRED - Must include this array
      {
        "voice_name": "Kore",             // Gemini TTS voice name
        "language": "vi-VN",              // TTS language code
        "speaking_rate": 1.0
      }
    ],
    "use_pro_model": true
  }
}
```

**Common Error**:
```json
// ❌ WRONG - Missing voices array
{
  "narration_id": "...",
  "voice_config": {
    "speaking_rate": 1.0,
    "use_pro_model": true
  }
}

// ✅ CORRECT - Include voices array
{
  "narration_id": "...",
  "voice_config": {
    "provider": "google",
    "voices": [
      {
        "voice_name": "Kore",
        "language": "vi-VN",
        "speaking_rate": 1.0
      }
    ],
    "use_pro_model": true
  }
}
```

**Other Legacy Endpoints**:
- `POST /api/presentations/{id}/generate-subtitles` - Legacy subtitle generation
- `GET /api/presentations/{id}/narrations` - Legacy list

**New Endpoints** (use these):
- `POST /api/presentations/{id}/subtitles/v2` - Multi-language subtitles
- `POST /api/presentations/{id}/subtitles/v2/{subtitle_id}/audio` - Multi-language audio
- `GET /api/presentations/{id}/subtitles/v2` - List all languages/versions

### Frontend Migration Checklist

- [ ] Replace `has_narration` with `narration_info.total_languages > 0`
- [ ] Replace `narration_count` with `narration_info.languages.length`
- [ ] Update subtitle generation to use `/subtitles/v2` endpoint
- [ ] Update audio generation to use `/subtitles/v2/{subtitle_id}/audio`
- [ ] Add language selector UI (vi, en, zh)
- [ ] Add version selector UI (per language)
- [ ] Implement audio upload feature
- [ ] Add sharing configuration UI
- [ ] Implement public URL sharing feature
- [ ] Update document list to show multi-language info

### Data Model Changes

**Old Structure**:
```
slide_narrations {
  narration_id, presentation_id, language, version,
  slides: [{subtitles: [...]}],
  audio_files: [{slide_index, audio_url}]
}
```

**New Structure**:
```
presentation_subtitles {
  subtitle_id, presentation_id, language, version,
  slides: [{subtitles: [...]}]
}

presentation_audio {
  audio_id, subtitle_id, language, version, slide_index,
  audio_url, generation_method
}

presentation_sharing_config {
  config_id, presentation_id, is_public, public_token,
  sharing_settings: {...}
}
```

---

## UI Implementation Guide

### Complete Flow: Language & Version Selection

This section provides step-by-step implementation guide for frontend developers.

#### Scenario: User opens a presentation with existing subtitles

**Given**: Presentation has:
- Vietnamese (vi): Version 1, 2, 3
- English (en): Version 1, 2
- Latest overall: Vietnamese Version 3 (created most recently)

---

#### Step 1: Load Document & Check Subtitles

```typescript
const document = await fetch(`/api/presentations/${presentationId}`, {
  headers: { Authorization: `Bearer ${firebaseToken}` }
}).then(r => r.json());

// Check if has subtitles
if (!document.narration_info || document.narration_info.total_languages === 0) {
  // Show "Generate Subtitles" button
  return;
}

// Has subtitles - proceed to step 2
```

---

#### Step 2: Fetch All Subtitles

```typescript
const response = await fetch(
  `/api/presentations/${presentationId}/subtitles/v2`,
  { headers: { Authorization: `Bearer ${firebaseToken}` } }
).then(r => r.json());

// Response.subtitles is array of all subtitle documents
// Already sorted by language (asc), version (desc)
```

---

#### Step 3: Process & Group Subtitles

```typescript
// Group by language
const groupedByLanguage = response.subtitles.reduce((acc, sub) => {
  if (!acc[sub.language]) {
    acc[sub.language] = [];
  }
  acc[sub.language].push(sub);
  return acc;
}, {});

// Result:
// {
//   vi: [
//     {_id: "id1", language: "vi", version: 3, created_at: "2025-12-24T11:00:00Z"},
//     {_id: "id2", language: "vi", version: 2, created_at: "2025-12-24T10:00:00Z"},
//     {_id: "id3", language: "vi", version: 1, created_at: "2025-12-24T09:00:00Z"}
//   ],
//   en: [
//     {_id: "id4", language: "en", version: 2, created_at: "2025-12-24T10:30:00Z"},
//     {_id: "id5", language: "en", version: 1, created_at: "2025-12-24T09:30:00Z"}
//   ]
// }
```

---

#### Step 4: Find Overall Latest (Default Selection)

```typescript
// Find subtitle with most recent created_at across ALL languages
const overallLatest = response.subtitles.reduce((latest, current) => {
  return new Date(current.created_at) > new Date(latest.created_at)
    ? current
    : latest;
});

// Result: {_id: "id1", language: "vi", version: 3, created_at: "..."}

// Set initial UI state
const [selectedLanguage, setSelectedLanguage] = useState(overallLatest.language); // "vi"
const [selectedVersion, setSelectedVersion] = useState(overallLatest.version);   // 3
const [selectedSubtitleId, setSelectedSubtitleId] = useState(overallLatest._id); // "id1"
```

---

#### Step 5: Render Language Dropdown

```typescript
// Get unique languages from grouped data
const availableLanguages = Object.keys(groupedByLanguage); // ["vi", "en"]

// Render dropdown
<Select value={selectedLanguage} onChange={handleLanguageChange}>
  {availableLanguages.map(lang => (
    <Option key={lang} value={lang}>
      {getLanguageName(lang)} {/* e.g., "Vietnamese", "English" */}
    </Option>
  ))}
</Select>
```

---

#### Step 6: Render Version Dropdown

```typescript
// Get versions for selected language
const versionsForSelectedLang = groupedByLanguage[selectedLanguage];

// Render dropdown (show latest first)
<Select value={selectedVersion} onChange={handleVersionChange}>
  {versionsForSelectedLang.map(sub => (
    <Option key={sub.version} value={sub.version}>
      Version {sub.version}
      {sub.version === versionsForSelectedLang[0].version && " (Latest)"}
    </Option>
  ))}
</Select>
```

---

#### Step 7: Load & Display Subtitle Content

```typescript
// Fetch full subtitle detail
const subtitleDetail = await fetch(
  `/api/presentations/${presentationId}/subtitles/v2/${selectedSubtitleId}`,
  { headers: { Authorization: `Bearer ${firebaseToken}` } }
).then(r => r.json());

// Display slides with subtitles
subtitleDetail.subtitle.slides.forEach(slide => {
  console.log(`Slide ${slide.slide_index}:`);
  slide.subtitles.forEach(sub => {
    console.log(`  - ${sub.text}`);
  });
});
```

---

#### Step 8: Handle Language Change

```typescript
function handleLanguageChange(newLanguage) {
  // Get versions for new language
  const versionsForNewLang = groupedByLanguage[newLanguage];

  // Auto-select latest version (first in array, already sorted desc)
  const latestVersion = versionsForNewLang[0];

  // Update state
  setSelectedLanguage(newLanguage);
  setSelectedVersion(latestVersion.version);
  setSelectedSubtitleId(latestVersion._id);

  // Fetch and display new subtitle
  loadSubtitleDetail(latestVersion._id);
}
```

---

#### Step 9: Handle Version Change

```typescript
function handleVersionChange(newVersion) {
  // Find subtitle with matching version in selected language
  const subtitle = groupedByLanguage[selectedLanguage].find(
    s => s.version === newVersion
  );

  // Update state
  setSelectedVersion(newVersion);
  setSelectedSubtitleId(subtitle._id);

  // Fetch and display new subtitle
  loadSubtitleDetail(subtitle._id);
}
```



---

## Best Practices

### Language Handling
- Always specify language explicitly (don't assume default)
- Use ISO 639-1 codes (vi, en, zh)
- Show language selector before generating subtitles

### Version Management
- Display latest version by default
- Allow users to browse older versions
- Show version history timeline

### Audio Handling
- Show both AI-generated and uploaded audio
- Indicate generation method in UI
- Allow users to replace audio per slide

### Public Sharing
- Generate short, shareable URLs using `public_token`
- Preview sharing settings before enabling
- Show access statistics to owner

### Error Handling
- Check points balance before subtitle/audio generation
- Validate file format/size before upload
- Handle network errors gracefully
- Show clear error messages to users

---

## Support

For questions or issues:
- Backend API Issues: Check `/docs` endpoint for OpenAPI schema
- Feature Requests: Submit to development team
- Bug Reports: Include request/response details

---

**Last Updated**: December 24, 2025
**API Version**: 2.0
**Migration Status**: ✅ Complete - All endpoints deployed to production
