# Slide Narration System - Complete Reference

## 📊 Database Structure

### Collection: `presentation_subtitles`

**Primary storage** for all subtitle data across all languages and versions.

```javascript
{
  _id: ObjectId("695f47d0a537e581fa782c95"),

  // Core identifiers
  presentation_id: "doc_98348b1a574a",  // String (NOT ObjectId)
  user_id: "17BeaeikPBQYk8OWeDUkqm0Ov8e2",  // Firebase UID (NOT ObjectId)

  // Language & Version
  language: "en",  // Normalized ISO 639-1 code (ja-JP → ja)
  version: 1,      // Auto-increment per language

  // Subtitle data
  slides: [
    {
      slide_index: 0,
      slide_duration: 15.5,
      subtitles: [
        {
          subtitle_index: 0,
          start_time: 0.0,
          end_time: 3.5,
          duration: 3.5,
          text: "Welcome to this presentation.",
          speaker_index: 0,
          element_references: ["elem_0"]
        }
      ],
      auto_advance: true,
      transition_delay: 2.0
    }
  ],

  // Metadata
  mode: "comprehensive",  // "minimal" | "balanced" | "comprehensive"
  total_duration: 45.8,
  user_query: "Focus on technical details",

  // Audio reference (populated after audio generation)
  merged_audio_id: ObjectId("695f..."),  // → presentation_audio._id
  audio_url: "https://cdn.r2.com/...",   // Populated from presentation_audio

  // Timestamps
  created_at: ISODate("2026-01-08T10:00:00Z"),
  updated_at: ISODate("2026-01-08T10:05:00Z")
}
```

### Collection: `presentation_audio`

**Audio files storage** for generated audio from subtitles.

```javascript
{
  _id: ObjectId("695f..."),

  // Core identifiers
  presentation_id: "doc_98348b1a574a",
  subtitle_id: ObjectId("695f47d0a537e581fa782c95"),  // → presentation_subtitles._id
  user_id: "17BeaeikPBQYk8OWeDUkqm0Ov8e2",

  // Language
  language: "en",

  // Audio URL (merged/final audio)
  audio_url: "https://cdn.r2.com/merged_695f47d0a537e581fa782c95.mp3",

  // Per-slide audio files
  slide_audio_files: [
    {
      slide_index: 0,
      audio_url: "https://cdn.r2.com/slide_0_695f47d0.mp3",
      duration: 15.5,
      file_size: 245678,
      format: "mp3"
    }
  ],

  // Voice configuration
  voice_config: {
    provider: "google",
    voices: [...]
  },

  // Timestamps
  created_at: ISODate("2026-01-08T10:10:00Z")
}
```

### Collection: `documents`

**Presentation document** - NOT used for subtitle storage!

```javascript
{
  _id: ObjectId("695f4115f2448e0bbf57c2e7"),
  document_id: "doc_98348b1a574a",  // String ID
  user_id: "17BeaeikPBQYk8OWeDUkqm0Ov8e2",
  document_type: "slide",

  // Slide content (NO SUBTITLES HERE!)
  slide_elements: [...],      // Element data per slide
  slide_backgrounds: [...],   // Background config per slide
  slides_outline: [...],      // AI generation outline

  // AI generation metadata
  ai_generation_status: "completed",
  ai_num_slides: 10,
  ai_language: "en",

  // Note: NO subtitle_history, narration_config, or subtitles fields!
  // Subtitles are in presentation_subtitles collection!
}
```

---

## 🔄 API Endpoints (V2 System)

### 1. POST Generate Subtitles

**Endpoint:** `POST /api/presentations/{presentation_id}/subtitles/v2`

**Purpose:** Generate new subtitle version for a language

**Cost:** 2 points (deducted immediately)

**Request:**
```typescript
{
  "language": "en",  // or "ja-JP" (auto-normalized to "ja")
  "mode": "comprehensive",  // "minimal" | "balanced" | "comprehensive"
  "user_query": "Focus on technical terms"  // Optional
}
```

**Response:**
```json
{
  "success": true,
  "subtitle": {
    "_id": "695f47d0a537e581fa782c95",
    "presentation_id": "doc_98348b1a574a",
    "user_id": "17BeaeikPBQYk8OWeDUkqm0Ov8e2",
    "language": "en",
    "version": 1,
    "slides": [...],
    "total_duration": 45.8,
    "mode": "comprehensive",
    "created_at": "2026-01-08T10:00:00Z"
  },
  "points_deducted": 2
}
```

**Database Operations:**
1. Insert into `presentation_subtitles`
2. Auto-increment version per language
3. Normalize language code (ja-JP → ja)

---

### 2. GET List Subtitles (All Languages)

**Endpoint:** `GET /api/presentations/{presentation_id}/subtitles/v2`

**Purpose:** Get all subtitle versions across all languages

**Used in:** `fetchAllSubtitles()` - Initial load, auto-detect language

**Request:** No parameters

**Response:**
```json
{
  "success": true,
  "subtitles": [
    {
      "_id": "695f47d0a537e581fa782c95",
      "language": "en",
      "version": 2,
      "total_duration": 45.8,
      "audio_url": "https://cdn.r2.com/...",  // If audio generated
      "created_at": "2026-01-08T10:00:00Z"
    },
    {
      "_id": "695f48e1b638f692eb893da6",
      "language": "ja",
      "version": 1,
      "total_duration": 52.3,
      "created_at": "2026-01-08T11:00:00Z"
    }
  ],
  "total_count": 2
}
```

**Database Query:**
```javascript
db.presentation_subtitles.find({
  presentation_id: "doc_98348b1a574a",
  user_id: "17BeaeikPBQYk8OWeDUkqm0Ov8e2"
}).sort({ language: 1, version: -1 })
```

**Logic:**
- Sort by language (alphabetical), then version (newest first)
- Auto-populate `audio_url` from `presentation_audio` if `merged_audio_id` exists
- Returns ALL languages for language selector dropdown

---

### 3. GET List Subtitles (Specific Language)

**Endpoint:** `GET /api/presentations/{presentation_id}/subtitles/v2?language={lang}`

**Purpose:** Get subtitle versions for ONE language

**Used in:** `fetchSubtitles()` - When user selects language from dropdown

**Request:** `?language=en` or `?language=ja-JP` (auto-normalized)

**Response:**
```json
{
  "success": true,
  "subtitles": [
    {
      "_id": "695f47d0a537e581fa782c95",
      "language": "en",
      "version": 2,
      "slides": [...],  // Full slide data
      "total_duration": 45.8,
      "audio_url": "https://cdn.r2.com/...",
      "created_at": "2026-01-08T10:00:00Z"
    },
    {
      "_id": "695f46c2d426d471ca671b84",
      "language": "en",
      "version": 1,
      "slides": [...],
      "total_duration": 43.2,
      "created_at": "2026-01-07T15:00:00Z"
    }
  ],
  "total_count": 2
}
```

**Database Query:**
```javascript
db.presentation_subtitles.find({
  presentation_id: "doc_98348b1a574a",
  user_id: "17BeaeikPBQYk8OWeDUkqm0Ov8e2",
  language: "en"  // Filtered by language
}).sort({ version: -1 })
```

**Logic:**
- Language code normalized (ja-JP → ja)
- Returns versions sorted by version (newest first)
- Each subtitle has full `slides` array with subtitle data

---

### 4. GET Single Subtitle

**Endpoint:** `GET /api/presentations/{presentation_id}/subtitles/v2/{subtitle_id}`

**Purpose:** Get specific subtitle version by ID

**Request:** No parameters

**Response:**
```json
{
  "success": true,
  "subtitle": {
    "_id": "695f47d0a537e581fa782c95",
    "presentation_id": "doc_98348b1a574a",
    "user_id": "17BeaeikPBQYk8OWeDUkqm0Ov8e2",
    "language": "en",
    "version": 2,
    "slides": [
      {
        "slide_index": 0,
        "slide_duration": 15.5,
        "subtitles": [
          {
            "subtitle_index": 0,
            "start_time": 0.0,
            "end_time": 3.5,
            "duration": 3.5,
            "text": "Welcome to this presentation.",
            "speaker_index": 0,
            "element_references": ["elem_0"]
          }
        ],
        "auto_advance": true,
        "transition_delay": 2.0
      }
    ],
    "total_duration": 45.8,
    "mode": "comprehensive",
    "audio_url": "https://cdn.r2.com/...",
    "created_at": "2026-01-08T10:00:00Z"
  }
}
```

**Database Query:**
```javascript
db.presentation_subtitles.findOne({
  _id: ObjectId("695f47d0a537e581fa782c95"),
  presentation_id: "doc_98348b1a574a",
  user_id: "17BeaeikPBQYk8OWeDUkqm0Ov8e2"
})
```

---

### 5. PUT Update Subtitle

**Endpoint:** `PUT /api/presentations/{presentation_id}/subtitles/v2/{subtitle_id}`

**Purpose:** Edit subtitle text and timing BEFORE audio generation

**Cost:** FREE (no points deducted)

**Request:**
```typescript
{
  "slides": [
    {
      "slide_index": 0,
      "slide_duration": 15.5,
      "subtitles": [
        {
          "subtitle_index": 0,
          "start_time": 0.0,
          "end_time": 3.5,
          "duration": 3.5,
          "text": "Welcome to this presentation.",  // ← Can edit text
          "speaker_index": 0,
          "element_references": ["elem_0"]
        }
      ],
      "auto_advance": true,
      "transition_delay": 2.0
    }
  ]
}
```

**Response:**
```json
{
  "success": true,
  "narration_id": "695f47d0a537e581fa782c95",
  "slides": [...],  // Updated slides
  "total_duration": 45.8,
  "updated_at": "2026-01-08T10:15:00Z"
}
```

**Database Operations:**
```javascript
db.presentation_subtitles.update_one(
  { _id: ObjectId("695f47d0a537e581fa782c95") },
  {
    $set: {
      slides: [...],
      total_duration: 45.8,
      updated_at: ISODate("2026-01-08T10:15:00Z")
    }
  }
)
```

**Restrictions:**
- ❌ **Cannot edit after audio generated** (if `merged_audio_id` exists)
- ❌ **Timestamps cannot overlap**
- ✅ Can edit text, timing, speaker assignments
- ✅ Must create new version if audio already exists

**Frontend Flow:**
1. User clicks "Edit" on subtitle
2. Frontend shows editor modal
3. User edits text/timing
4. Call `PUT /subtitles/v2/{subtitle_id}` to save
5. Call `POST /subtitles/v2/{subtitle_id}/audio` to generate audio with updated text

---

### 6. POST Generate Audio

**Endpoint:** `POST /api/presentations/{presentation_id}/subtitles/v2/{subtitle_id}/audio`

**Purpose:** Generate audio from subtitles

**Cost:** 2 points (deducted immediately)

**Request:**
```typescript
{
  "voice_config": {
    "provider": "google",
    "voices": [
      {
        "voice_name": "en-US-Neural2-A",
        "language": "en-US",
        "speaking_rate": 1.0
      }
    ]
  }
}
```

**Response:**
```json
{
  "success": true,
  "audio_id": "695f...",
  "merged_audio_url": "https://cdn.r2.com/merged_695f47d0.mp3",
  "slide_audio_files": [
    {
      "slide_index": 0,
      "audio_url": "https://cdn.r2.com/slide_0_695f47d0.mp3",
      "duration": 15.5
    }
  ],
  "points_deducted": 2
}
```

**Database Operations:**
1. Insert into `presentation_audio`
2. Update `presentation_subtitles.merged_audio_id` with audio._id
3. Save merged audio URL

---

### 6. POST Generate Audio

**Endpoint:** `POST /api/presentations/{presentation_id}/subtitles/v2/{subtitle_id}/audio`

**Purpose:** Generate audio from subtitles

**Cost:** 2 points (deducted immediately)

**Request:**
```typescript
{
  "voice_config": {
    "provider": "google",
    "voices": [
      {
        "voice_name": "en-US-Neural2-A",
        "language": "en-US",
        "speaking_rate": 1.0
      }
    ]
  }
}
```

**Response:**
```json
{
  "success": true,
  "audio_id": "695f...",
  "merged_audio_url": "https://cdn.r2.com/merged_695f47d0.mp3",
  "slide_audio_files": [
    {
      "slide_index": 0,
      "audio_url": "https://cdn.r2.com/slide_0_695f47d0.mp3",
      "duration": 15.5
    }
  ],
  "points_deducted": 2
}
```

**Database Operations:**
1. Insert into `presentation_audio`
2. Update `presentation_subtitles.merged_audio_id` with audio._id
3. Save merged audio URL

---

### 7. DELETE Subtitle

---

### 7. DELETE Subtitle

**Endpoint:** `DELETE /api/presentations/{presentation_id}/subtitles/v2/{subtitle_id}`

**Purpose:** Delete subtitle version

**Database Operations:**
1. Delete from `presentation_subtitles`
2. Delete associated audio from `presentation_audio` (if exists)

**Cost:** FREE (no points)

---

## 🔑 Key Concepts

### Language Normalization

**Input:** `ja-JP`, `en-US`, `zh-CN`
**Stored:** `ja`, `en`, `zh` (ISO 639-1, 2-letter code)

```python
def normalize_language_code(language: str) -> str:
    """
    ja-JP → ja
    en-US → en
    zh-Hans → zh
    """
    return language.split("-")[0]
```

### Version System

- **Auto-increment** per language per presentation
- Query latest: `db.presentation_subtitles.find({...}).sort({version: -1}).limit(1)`
- Example:
  ```javascript
  // Same presentation, multiple languages
  { presentation_id: "doc_123", language: "en", version: 2 }
  { presentation_id: "doc_123", language: "en", version: 1 }
  { presentation_id: "doc_123", language: "ja", version: 1 }
  ```

### Audio Linking

**Flow:**
1. Generate subtitle → `presentation_subtitles` (no audio)
2. Generate audio → `presentation_audio` (insert)
3. Update subtitle → `presentation_subtitles.merged_audio_id = audio._id`
4. Frontend GET → Auto-populate `audio_url` from `presentation_audio`

**Query:**
```javascript
// Backend auto-populates audio_url
subtitle = db.presentation_subtitles.findOne({_id: "..."})
if (subtitle.merged_audio_id) {
  audio = db.presentation_audio.findOne({_id: subtitle.merged_audio_id})
  subtitle.audio_url = audio.audio_url  // Populated!
}
```

---

## 🎯 Frontend Flow

### Initial Load (fetchAllSubtitles)

```typescript
// GET /presentations/{id}/subtitles/v2
const response = await api.get(`/presentations/${presentationId}/subtitles/v2`);

// Response: All languages
{
  subtitles: [
    { language: "en", version: 2, audio_url: "..." },
    { language: "ja", version: 1, audio_url: null }
  ]
}

// Auto-detect: Pick latest subtitle (first in array)
const latestSubtitle = response.subtitles[0];
setCurrentLanguage(latestSubtitle.language);

// Build language dropdown
const languages = [...new Set(response.subtitles.map(s => s.language))];
```

### Language Selection (fetchSubtitles)

```typescript
// User clicks "Japanese" in dropdown
const selectedLanguage = "ja";

// GET /presentations/{id}/subtitles/v2?language=ja
const response = await api.get(
  `/presentations/${presentationId}/subtitles/v2?language=${selectedLanguage}`
);

// Response: Only Japanese versions
{
  subtitles: [
    { _id: "...", language: "ja", version: 1, slides: [...] }
  ]
}

// Use latest version
const subtitle = response.subtitles[0];
setSubtitleData(subtitle.slides);
```

### Edit Subtitle

**SUPPORTED!** Use PUT endpoint to edit BEFORE audio generation.

```typescript
// 1. User edits subtitle in UI
const editedSlides = [...]; // Modified subtitle data

// 2. Save changes
await api.put(`/presentations/${presentationId}/subtitles/v2/${subtitleId}`, {
  slides: editedSlides
});

// 3. Generate audio with updated text
await api.post(`/presentations/${presentationId}/subtitles/v2/${subtitleId}/audio`, {
  voice_config: {...}
});
```

**Restrictions:**
- ❌ Cannot edit after audio generated (create new version instead)
- ✅ Can edit text, timing, speaker assignments before audio
- ✅ No points cost for editing

**Alternative:** If audio already exists, generate new version:
```typescript
// Generate new version with custom prompt
await api.post(`/presentations/${presentationId}/subtitles/v2`, {
  language: "en",
  user_query: "Make it more technical and detailed"
});
```

---

## 📝 Indexes

```javascript
// presentation_subtitles
db.presentation_subtitles.createIndex(
  { presentation_id: 1, user_id: 1, language: 1, version: -1 }
)
db.presentation_subtitles.createIndex(
  { presentation_id: 1, user_id: 1 }
)
db.presentation_subtitles.createIndex(
  { _id: 1, presentation_id: 1, user_id: 1 }  // For security checks
)

// presentation_audio
db.presentation_audio.createIndex(
  { subtitle_id: 1 }
)
db.presentation_audio.createIndex(
  { presentation_id: 1, user_id: 1 }
)
```

---

## � V1 vs V2 System

### V1 (REMOVED) - `slide_narrations` collection

**ALL V1 endpoints have been REMOVED from the codebase!**

The following endpoints NO LONGER EXIST:
- ❌ POST `/presentations/{id}/narration/generate-subtitles`
- ❌ POST `/presentations/{id}/narration/{id}/generate-audio`
- ❌ GET `/presentations/{id}/narrations`
- ❌ GET `/presentations/{id}/narration/{id}`
- ❌ PUT `/presentations/{id}/narration/{id}`
- ❌ DELETE `/presentations/{id}/narration/{id}`

**Why removed:**
- Used deprecated `slide_narrations` collection
- Caused confusion when mixed with V2
- PUT endpoint was updating wrong collection

**Migration:** All functionality replaced by V2 endpoints

---

### V2 (CURRENT) - `presentation_subtitles` collection

**Endpoints:**
- ✅ POST `/presentations/{id}/subtitles/v2` - Generate subtitle
- ✅ GET `/presentations/{id}/subtitles/v2` - List all languages
- ✅ GET `/presentations/{id}/subtitles/v2?language=en` - Filter by language
- ✅ GET `/presentations/{id}/subtitles/v2/{subtitle_id}` - Get single subtitle
- ✅ PUT `/presentations/{id}/subtitles/v2/{subtitle_id}` - **Edit subtitle (NEW!)**
- ✅ POST `/presentations/{id}/subtitles/v2/{subtitle_id}/audio` - Generate audio
- ✅ DELETE `/presentations/{id}/subtitles/v2/{subtitle_id}` - Delete subtitle

**Features:**
- Multi-language support (unlimited languages per presentation)
- Version management (auto-increment per language)
- Immutable after audio generation
- Edit support BEFORE audio generation
- Separate audio storage (`presentation_audio`)

---

## 🚨 Common Issues

### Issue 1: "Narration not found" (404)

**Cause:** Frontend using wrong collection or wrong ID

**Solution:**
- ✅ V2 uses `presentation_subtitles` collection
- ❌ V1 uses `slide_narrations` collection (deprecated)
- Check: `db.presentation_subtitles.findOne({_id: ObjectId("...")})`
- **Don't cache subtitle IDs across sessions!**

### Issue 2: PUT endpoint updates wrong collection

**Cause:** Using deprecated V1 PUT endpoint (`/narration/{id}`)

**Solution:**
- ❌ OLD: `PUT /presentations/{id}/narration/{id}` → Updates `slide_narrations` (wrong!)
- ✅ NEW: `PUT /presentations/{id}/subtitles/v2/{subtitle_id}` → Updates `presentation_subtitles` (correct!)

**How to identify:**
- If subtitle_id starts with `695f...` → Check which endpoint you're calling
- V1 endpoint is marked as `deprecated=True` in API docs

### Issue 3: Language mismatch

### Issue 3: Language mismatch

**Cause:** Frontend sends `ja-JP`, backend expects `ja`

**Solution:** Backend auto-normalizes, but frontend should:
```typescript
const normalizedLanguage = language.split("-")[0];  // ja-JP → ja
```

### Issue 4: Audio URL missing

**Cause:** `merged_audio_id` not set or audio not generated

**Solution:**
1. Check: `subtitle.merged_audio_id` exists?
2. Generate audio first: POST `/subtitles/v2/{subtitle_id}/audio`
3. Backend auto-populates `audio_url` in GET response

### Issue 5: Edit not working / Audio uses old subtitle

**Cause:** Calling wrong PUT endpoint or not calling PUT before audio generation

**Solution:**
```typescript
// ✅ CORRECT: Edit first, then generate audio
await api.put(`/presentations/{id}/subtitles/v2/${subtitleId}`, {
  slides: editedSlides
});

await api.post(`/presentations/{id}/subtitles/v2/${subtitleId}/audio`, {
  voice_config: {...}
});

// ❌ WRONG: Using V1 endpoint
await api.put(`/presentations/{id}/narration/${subtitleId}`, {...});
// This updates slide_narrations (wrong collection!)
```

**Check:**
1. Which endpoint are you calling? V1 (`/narration/{id}`) or V2 (`/subtitles/v2/{id}`)?
2. Is `merged_audio_id` null? (Can only edit if no audio generated)
3. Did you refresh subtitle data after PUT?

### Issue 6: Cannot edit subtitle after audio generation

### Issue 4: Cannot edit subtitle

**Cause:** V2 is immutable

**Solution:** Generate new version instead of editing

---

## 🔍 Debugging Commands

### Check subtitle exists
```bash
docker exec mongodb mongosh ai_service_db -u ai_service_user -p PASSWORD --eval '
  db.presentation_subtitles.findOne({
    _id: ObjectId("695f47d0a537e581fa782c95")
  }, {
    _id: 1, presentation_id: 1, language: 1, version: 1,
    slides: {$size: "$slides"}, merged_audio_id: 1
  })
'
```

### List all subtitles for presentation
```bash
docker exec mongodb mongosh ai_service_db -u ai_service_user -p PASSWORD --eval '
  db.presentation_subtitles.find({
    presentation_id: "doc_98348b1a574a"
  }, {
    _id: 1, language: 1, version: 1,
    total_duration: 1, merged_audio_id: 1
  }).toArray()
'
```

### Check audio exists
```bash
docker exec mongodb mongosh ai_service_db -u ai_service_user -p PASSWORD --eval '
  db.presentation_audio.findOne({
    subtitle_id: ObjectId("695f47d0a537e581fa782c95")
  }, {
    _id: 1, audio_url: 1, language: 1
  })
'
```

---

## 📊 Summary

| Collection | Purpose | Key Fields |
|------------|---------|-----------|
| `presentation_subtitles` | Subtitle data | `presentation_id`, `language`, `version`, `slides[]`, `merged_audio_id` |
| `presentation_audio` | Audio files | `subtitle_id`, `audio_url`, `slide_audio_files[]` |
| `documents` | Presentation | `slide_elements[]`, `slide_backgrounds[]` - NO SUBTITLES! |

| Endpoint | Purpose | Filter |
|----------|---------|--------|
| `GET /subtitles/v2` | List all languages | None |
| `GET /subtitles/v2?language=en` | List one language | Language |
| `GET /subtitles/v2/{id}` | Get specific subtitle | ID |
| `POST /subtitles/v2` | Generate subtitle | - |
| `POST /subtitles/v2/{id}/audio` | Generate audio | - |

**Key Points:**
- ✅ V2 uses `presentation_subtitles` (NOT `slide_narrations`)
- ✅ Language normalized to 2-letter code (ja-JP → ja)
- ✅ Version auto-increments per language
- ✅ Audio linked via `merged_audio_id`
- ✅ Immutable - no edit, generate new version instead
- ✅ 2 endpoints for listing: no filter (all languages) vs language filter
