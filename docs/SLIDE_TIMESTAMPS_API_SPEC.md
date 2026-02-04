# Slide Timestamps API - Technical Specification

## 📋 Overview

API để lấy và cập nhật slide timestamps cho merged audio của presentation.

**Use Case:** Fix audio-slide sync issues (voice ở slide 15 nhưng UI đã ở slide 17)

---

## 🗄️ Database Structure

### Collection: `presentation_audio`

```javascript
{
  _id: ObjectId("695f6277d49fadb943f96b9f"),  // ← AUDIO_ID (dùng cho timestamps endpoints)

  // Links
  presentation_id: "doc_98348b1a574a",
  subtitle_id: "695f5ffdde3cd5cf7e8d8ab7",  // ← Link to presentation_subtitles._id
  user_id: "17BeaeikPBQYk8OWeDUkqm0Ov8e2",

  // Audio type
  audio_type: "merged_presentation",  // MUST be this type to edit timestamps

  // Timestamps array (THIS IS WHAT YOU EDIT)
  slide_timestamps: [
    {
      slide_index: 0,
      start_time: 0.0,
      end_time: 49.4,
      duration: 49.4  // Optional, calculated field
    },
    {
      slide_index: 1,
      start_time: 49.4,
      end_time: 137.6,
      duration: 88.2
    },
    // ... more slides
  ],

  // Metadata
  language: "en",
  version: 2,
  slide_count: 5,
  status: "ready",

  // Audio file info
  audio_url: "https://static.wordai.pro/narration/.../merged.wav",
  audio_metadata: {
    duration_seconds: 315.622,
    file_size_bytes: 15149896,
    format: "wav",
    sample_rate: 24000
  },

  created_at: ISODate("2026-01-08T07:53:27.571Z"),
  updated_at: ISODate("2026-01-08T07:53:27.571Z")
}
```

### Collection: `presentation_subtitles`

```javascript
{
  _id: ObjectId("695f5ffdde3cd5cf7e8d8ab7"),  // ← SUBTITLE_ID

  presentation_id: "doc_98348b1a574a",
  user_id: "17BeaeikPBQYk8OWeDUkqm0Ov8e2",
  language: "en",
  version: 2,

  slides: [...],  // Subtitle text data

  // Audio reference (populated after audio generation)
  merged_audio_id: ObjectId("695f6277d49fadb943f96b9f"),  // ← Points to presentation_audio._id

  created_at: ISODate("2026-01-08T07:53:00Z")
}
```

**⚠️ CRITICAL: ID Relationship**
- `presentation_audio._id` = **AUDIO_ID** (use this for timestamps endpoints!)
- `presentation_subtitles._id` = **SUBTITLE_ID** (use this for subtitle endpoints)
- `presentation_subtitles.merged_audio_id` → `presentation_audio._id` (link)

---

## 🔌 API Endpoints

### 1. GET Slide Timestamps

**Endpoint:** `GET /api/presentations/{presentation_id}/audio/{audio_id}/timestamps`

**Purpose:** Lấy timestamps hiện tại để edit

**URL Parameters:**
- `presentation_id`: Document ID (e.g., "doc_98348b1a574a")
- `audio_id`: **presentation_audio._id** (e.g., "695f6277d49fadb943f96b9f")

**Headers:**
```
Authorization: Bearer <firebase_token>
```

**Response 200:**
```json
{
  "success": true,
  "audio_id": "695f6277d49fadb943f96b9f",
  "presentation_id": "doc_98348b1a574a",
  "language": "en",
  "version": 2,
  "slide_count": 5,
  "audio_duration": 315.622,
  "slide_timestamps": [
    {
      "slide_index": 0,
      "start_time": 0.0,
      "end_time": 49.4
    },
    {
      "slide_index": 1,
      "start_time": 49.4,
      "end_time": 137.6
    },
    {
      "slide_index": 2,
      "start_time": 137.6,
      "end_time": 177.531
    },
    {
      "slide_index": 3,
      "start_time": 177.531,
      "end_time": 239.406
    },
    {
      "slide_index": 4,
      "start_time": 239.406,
      "end_time": 315.622
    }
  ]
}
```

**Response 404:**
```json
{
  "detail": "Audio not found"
}
```

**Response 400:**
```json
{
  "detail": "Cannot edit timestamps for audio_type 'chunked'. Only 'merged_presentation' audio can be edited."
}
```

**Database Query:**
```javascript
db.presentation_audio.findOne({
  _id: ObjectId("695f6277d49fadb943f96b9f"),
  user_id: "17BeaeikPBQYk8OWeDUkqm0Ov8e2",
  presentation_id: "doc_98348b1a574a"
})
```

---

### 2. PATCH Update Slide Timestamps

**Endpoint:** `PATCH /api/presentations/{presentation_id}/audio/{audio_id}/timestamps`

**Purpose:** Cập nhật timestamps để fix sync issues

**URL Parameters:**
- `presentation_id`: Document ID
- `audio_id`: **presentation_audio._id** (NOT subtitle_id!)

**Headers:**
```
Authorization: Bearer <firebase_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "slide_timestamps": [
    {
      "slide_index": 0,
      "start_time": 0.0,
      "end_time": 49.4
    },
    {
      "slide_index": 1,
      "start_time": 49.4,
      "end_time": 137.6
    },
    {
      "slide_index": 2,
      "start_time": 138.0,
      "end_time": 178.0
    },
    {
      "slide_index": 3,
      "start_time": 178.5,
      "end_time": 240.0
    },
    {
      "slide_index": 4,
      "start_time": 240.5,
      "end_time": 316.0
    }
  ]
}
```

**Validation Rules:**
1. ✅ Slide count MUST match current count (cannot add/remove slides)
2. ✅ Each slide: `end_time > start_time`
3. ✅ No overlaps: `slide[i].end_time <= slide[i+1].start_time`
4. ✅ Timestamps in ascending order

**Response 200:**
```json
{
  "success": true,
  "audio_id": "695f6277d49fadb943f96b9f",
  "presentation_id": "doc_98348b1a574a",
  "updated_count": 5,
  "slide_timestamps": [
    {
      "slide_index": 0,
      "start_time": 0.0,
      "end_time": 49.4
    },
    // ... updated timestamps
  ],
  "message": "Slide timestamps updated successfully"
}
```

**Response 400 (Count Mismatch):**
```json
{
  "detail": "Slide count mismatch: provided 3 but audio has 5 slides"
}
```

**Response 400 (Wrong Audio Type):**
```json
{
  "detail": "Cannot edit timestamps for audio_type 'chunked'. Only 'merged_presentation' audio can be edited."
}
```

**Response 404:**
```json
{
  "detail": "Audio not found"
}
```

**Database Update:**
```javascript
db.presentation_audio.updateOne(
  { _id: ObjectId("695f6277d49fadb943f96b9f") },
  {
    $set: {
      slide_timestamps: [
        { slide_index: 0, start_time: 0.0, end_time: 49.4 },
        // ... new timestamps
      ],
      slide_count: 5,
      updated_at: new Date()
    }
  }
)
```

---

## 🔄 Frontend Integration

### Step 1: Get Audio ID from Subtitle

**Scenario:** User has subtitle_id, needs to find audio_id

```typescript
// Option A: From subtitle response
const subtitle = await api.get(`/presentations/${presentationId}/subtitles/v2/${subtitleId}`);

// If audio generated, it has merged_audio_id reference (but this is ObjectId string)
// Better: Use GET audio list endpoint

// Option B: List audio files (RECOMMENDED)
const audioResponse = await api.get(
  `/presentations/${presentationId}/audio/v2?language=${language}&version=${version}`
);

// Find merged audio
const mergedAudio = audioResponse.audio_files.find(
  audio => audio.audio_type === 'merged_presentation' && audio.version === version
);

const audioId = mergedAudio._id;  // ← THIS is the audio_id for timestamps!
```

### Step 2: Get Current Timestamps

```typescript
interface SlideTimestamp {
  slide_index: number;
  start_time: number;
  end_time: number;
}

const response = await api.get<{
  success: boolean;
  audio_id: string;
  slide_timestamps: SlideTimestamp[];
}>(
  `/presentations/${presentationId}/audio/${audioId}/timestamps`
);

const currentTimestamps = response.slide_timestamps;
```

### Step 3: Edit Timestamps

```typescript
// User adjusts in UI
const editedTimestamps = currentTimestamps.map((ts, index) => {
  if (index === 2) {
    // Fix slide 2 drift
    return {
      ...ts,
      start_time: ts.start_time + 0.5,  // Add 0.5s delay
      end_time: ts.end_time + 0.5
    };
  }
  return ts;
});
```

### Step 4: Update Timestamps

```typescript
const updateResponse = await api.patch(
  `/presentations/${presentationId}/audio/${audioId}/timestamps`,
  {
    slide_timestamps: editedTimestamps
  }
);

if (updateResponse.success) {
  console.log('✅ Timestamps updated!');
  // Reload audio player with new timestamps
  reloadAudioPlayer();
}
```

---

## ❌ Common Errors & Solutions

### Error 1: "Audio not found"

**Cause:** Frontend gửi sai ID (dùng subtitle_id thay vì audio_id)

**Solution:**
```typescript
// ❌ WRONG: Using subtitle_id
const audioId = "695f5ffdde3cd5cf7e8d8ab7";  // This is subtitle_id!

// ✅ CORRECT: Get audio_id from audio list
const audioResponse = await api.get(`/presentations/${presentationId}/audio/v2`);
const mergedAudio = audioResponse.audio_files.find(
  a => a.audio_type === 'merged_presentation'
);
const audioId = mergedAudio._id;  // "695f6277d49fadb943f96b9f"
```

### Error 2: "Cannot edit timestamps for audio_type 'chunked'"

**Cause:** Frontend đang gửi audio_id của chunked audio thay vì merged

**Solution:** Filter by `audio_type === 'merged_presentation'`

```typescript
const mergedAudio = audioList.find(
  audio => audio.audio_type === 'merged_presentation'  // NOT 'chunked'!
);
```

### Error 3: "Slide count mismatch: provided 3 but audio has 5 slides"

**Cause:** Frontend không gửi đủ số slides

**Solution:** MUST gửi ALL slides (không được thêm/bớt)

```typescript
// Get current timestamps first
const current = await api.get(`/audio/${audioId}/timestamps`);

// Edit them (but keep same count!)
const edited = current.slide_timestamps.map(ts => ({
  ...ts,
  // Only modify times, keep same array length
}));

// Send ALL timestamps back
await api.patch(`/audio/${audioId}/timestamps`, {
  slide_timestamps: edited  // Same count as current!
});
```

---

## 🔍 How to Find the Correct audio_id

### Method 1: From Audio List Endpoint (RECOMMENDED)

```bash
GET /api/presentations/doc_98348b1a574a/audio/v2?language=en&version=2

# Response
{
  "audio_files": [
    {
      "_id": "695f6277d49fadb943f96b9f",  # ← THIS IS audio_id!
      "audio_type": "merged_presentation",
      "language": "en",
      "version": 2,
      "slide_timestamps": [...]
    }
  ]
}
```

### Method 2: From Subtitle Response

```bash
GET /api/presentations/doc_98348b1a574a/subtitles/v2/695f5ffdde3cd5cf7e8d8ab7

# Response includes merged_audio_id (but you need to convert to string)
{
  "subtitle": {
    "_id": "695f5ffdde3cd5cf7e8d8ab7",
    "merged_audio_id": {...},  # ObjectId reference
    # But better to use Method 1 to get actual audio document
  }
}
```

### Method 3: MongoDB Query (Production Debug)

```javascript
// Step 1: Find subtitle
db.presentation_subtitles.findOne({
  _id: ObjectId("695f5ffdde3cd5cf7e8d8ab7")
})
// → merged_audio_id: ObjectId("695f6277d49fadb943f96b9f")

// Step 2: Find audio using that ID
db.presentation_audio.findOne({
  _id: ObjectId("695f6277d49fadb943f96b9f")
})
// → This is the audio document with slide_timestamps
```

---

## 📊 Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    SUBTITLE GENERATION                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
POST /subtitles/v2 → presentation_subtitles collection
{
  _id: "695f5ffdde3cd5cf7e8d8ab7",  ← subtitle_id
  slides: [...subtitle text...]
}
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     AUDIO GENERATION                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
POST /subtitles/v2/{subtitle_id}/audio
      → Creates presentation_audio documents
      → Updates subtitle.merged_audio_id

presentation_audio collection:
{
  _id: "695f6277d49fadb943f96b9f",  ← audio_id (USE THIS!)
  subtitle_id: "695f5ffdde3cd5cf7e8d8ab7",
  audio_type: "merged_presentation",
  slide_timestamps: [...]  ← EDITABLE!
}

presentation_subtitles updated:
{
  _id: "695f5ffdde3cd5cf7e8d8ab7",
  merged_audio_id: ObjectId("695f6277d49fadb943f96b9f")  ← Link
}
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  TIMESTAMPS EDITING                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
1. GET /audio/v2?language=en  → Find audio_id
2. GET /audio/{audio_id}/timestamps  → Get current
3. Edit in UI
4. PATCH /audio/{audio_id}/timestamps  → Update

Updates presentation_audio.slide_timestamps array directly!
```

---

## 🛠️ TypeScript Interfaces

```typescript
// Request/Response Models
interface SlideTimestamp {
  slide_index: number;
  start_time: number;
  end_time: number;
  duration?: number;  // Optional, auto-calculated
}

interface UpdateSlideTimestampsRequest {
  slide_timestamps: SlideTimestamp[];
}

interface GetSlideTimestampsResponse {
  success: boolean;
  audio_id: string;
  presentation_id: string;
  language: string;
  version: number;
  slide_count: number;
  audio_duration: number;
  slide_timestamps: SlideTimestamp[];
}

interface UpdateSlideTimestampsResponse {
  success: boolean;
  audio_id: string;
  presentation_id: string;
  updated_count: number;
  slide_timestamps: SlideTimestamp[];
  message: string;
}

// Full Audio Document
interface PresentationAudio {
  _id: string;
  presentation_id: string;
  subtitle_id: string;
  user_id: string;
  language: string;
  version: number;
  audio_type: 'merged_presentation' | 'chunked';
  audio_url: string;
  slide_timestamps: SlideTimestamp[];
  slide_count: number;
  status: 'ready' | 'processing' | 'failed';
  audio_metadata: {
    duration_seconds: number;
    file_size_bytes: number;
    format: string;
    sample_rate: number;
  };
  created_at: string;
  updated_at: string;
}
```

---

## ⚠️ CRITICAL NOTES

1. **audio_id ≠ subtitle_id**
   - Timestamps endpoints use `presentation_audio._id`
   - Subtitle endpoints use `presentation_subtitles._id`
   - Don't mix them up!

2. **Only merged_presentation can edit timestamps**
   - `audio_type` MUST be "merged_presentation"
   - Chunked audio cannot be edited

3. **Cannot add/remove slides**
   - Slide count must match exactly
   - Can only adjust start_time/end_time

4. **Direct database update**
   - No undo functionality
   - Make sure timestamps are correct before PATCH

5. **Query correct collection**
   - GET/PATCH timestamps → `presentation_audio` ✅
   - GET/PUT subtitle → `presentation_subtitles` ✅

---

## 📝 Summary

**To update slide timestamps:**

1. **Get audio_id:**
   ```
   GET /presentations/{id}/audio/v2?language=en
   → Find merged_presentation audio
   → Use its _id as audio_id
   ```

2. **Get current timestamps:**
   ```
   GET /presentations/{id}/audio/{audio_id}/timestamps
   ```

3. **Edit timestamps in UI**

4. **Update timestamps:**
   ```
   PATCH /presentations/{id}/audio/{audio_id}/timestamps
   Body: { slide_timestamps: [...] }
   ```

**Common mistake:** Using subtitle_id instead of audio_id → 404 error!

**Correct ID flow:**
- subtitle_id ("695f5ffdde3cd5cf7e8d8ab7") → For subtitle text editing
- audio_id ("695f6277d49fadb943f96b9f") → For timestamps editing
- They are linked via subtitle.merged_audio_id → audio._id
