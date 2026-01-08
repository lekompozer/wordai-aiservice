# Slide Narration API - Technical Specification

## Overview
Hệ thống narration 2 bước: **Subtitle (Step 1) → Audio (Step 2)**

**Critical**: Phải đảm bảo language và version đúng khi update và generate audio.

---

## Flow Chính Xác

### Option 1: Edit → Save → Generate Audio (2 requests)
```
1. User edit subtitle trong UI
2. Click "Save" → PUT /narration/{id} (save to DB)
3. Click "Generate Audio" → POST /generate-audio (read from DB)
```

### Option 2: Edit → Generate Audio Directly (1 request, khuyến nghị)
```
1. User edit subtitle trong UI
2. Click "Generate Audio" → POST /generate-audio (gửi kèm edited slides)
   → Backend tự động save vào DB trước khi generate
```

---

## 1. PUT Update Subtitles (Optional)

**Endpoint:** `PUT /api/presentations/{presentation_id}/narration/{narration_id}`

### Request Headers
```
Authorization: Bearer {firebase_token}
Content-Type: application/json
```

### Request Body
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
          "text": "Chào mừng đến với bài thuyết trình.",
          "speaker_index": 0,
          "element_references": []
        },
        {
          "subtitle_index": 1,
          "start_time": 4.0,
          "end_time": 8.2,
          "duration": 4.2,
          "text": "Biểu đồ này cho thấy 3 giai đoạn chính.",
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

### TypeScript Model
```typescript
interface UpdateSubtitlesRequest {
  slides: SlideSubtitleData[];
}

interface SlideSubtitleData {
  slide_index: number;
  slide_duration: number;
  subtitles: SubtitleEntry[];
  auto_advance: boolean;
  transition_delay: number;
}

interface SubtitleEntry {
  subtitle_index: number;
  start_time: number;      // seconds
  end_time: number;        // seconds
  duration: number;        // seconds
  text: string;
  speaker_index: number;   // 0-based, for multi-voice
  element_references: string[];  // ["elem_0", "elem_1"]
}
```

### Response
```json
{
  "success": true,
  "narration_id": "507f1f77bcf86cd799439099",
  "slides": [...],  // Same as request
  "total_duration": 45.8,
  "updated_at": "2026-01-08T12:45:30Z"
}
```

### Response Model
```typescript
interface UpdateSubtitlesResponse {
  success: boolean;
  narration_id: string;
  slides: SlideSubtitleData[];
  total_duration: number;
  updated_at: string;  // ISO 8601
}
```

### Validation Rules
1. **Timestamps không overlap**: `current.end_time <= next.start_time`
2. **Status check**: Chỉ edit khi `status != "completed"` (chưa generate audio)
3. **Ownership**: `narration.user_id === current_user.uid`
4. **Presentation match**: `narration.presentation_id === presentation_id`

### Database Update
```javascript
db.slide_narrations.update_one(
  { _id: ObjectId(narration_id) },
  {
    $set: {
      slides: [...],           // Edited slides
      total_duration: 45.8,
      updated_at: new Date()
    }
  }
)
```

---

## 2. POST Generate Audio (Required)

**Endpoint:** `POST /api/presentations/{presentation_id}/narration/{narration_id}/generate-audio`

### Request Headers
```
Authorization: Bearer {firebase_token}
Content-Type: application/json
```

### Request Body (Option A - Gửi slides edited)
```typescript
{
  "narration_id": "507f1f77bcf86cd799439099",
  "voice_config": {
    "provider": "google",
    "voices": [
      {
        "voice_name": "vi-VN-Neural2-A",
        "language": "vi-VN",
        "speaking_rate": 1.0,
        "pitch": 0.0
      }
    ],
    "use_pro_model": true
  },
  "slides": [
    {
      "slide_index": 0,
      "slide_duration": 15.5,
      "subtitles": [...]  // EDITED SUBTITLES từ UI
    }
  ]
}
```

### Request Body (Option B - Không gửi slides)
```typescript
{
  "narration_id": "507f1f77bcf86cd799439099",
  "voice_config": {
    "provider": "google",
    "voices": [...]
  }
  // slides: undefined → Backend sẽ lấy từ database
}
```

### TypeScript Model
```typescript
interface AudioGenerateRequest {
  narration_id: string;
  voice_config: VoiceConfig;
  slides?: SlideSubtitleData[];  // ← OPTIONAL nhưng khuyến nghị gửi!
}

interface VoiceConfig {
  provider: "google" | "openai" | "elevenlabs";
  voices?: VoiceItem[];
  gender?: "male" | "female";  // Alternative to voices
  use_pro_model: boolean;
}

interface VoiceItem {
  voice_name: string;      // "vi-VN-Neural2-A"
  language: string;        // "vi-VN"
  speaking_rate?: number;  // 0.5 - 2.0, default 1.0
  pitch?: number;          // -20.0 - 20.0, default 0.0
}
```

### Backend Logic (CRITICAL!)
```python
# Line 734-756 in slide_narration_routes.py

if request.slides:
    # ✅ Option 1: Use edited slides from request (KHUYẾN NGHỊ)
    logger.info(f"🎯 Using {len(request.slides)} slides from request (edited)")
    slides_with_subtitles = [slide.dict() for slide in request.slides]

    # Save to DB immediately for consistency
    db.slide_narrations.update_one(
        {"_id": ObjectId(narration_id)},
        {
            "$set": {
                "slides": slides_with_subtitles,
                "total_duration": sum(s.slide_duration for s in request.slides),
                "updated_at": datetime.now()
            }
        }
    )
else:
    # ❌ Option 2: Read from database (FALLBACK)
    logger.info(f"📚 Using slides from database (saved version)")
    slides_with_subtitles = narration["slides"]  # ← Có thể là version cũ!
```

### Response
```json
{
  "success": true,
  "narration_id": "507f1f77bcf86cd799439099",
  "audio_files": [
    {
      "slide_index": 0,
      "audio_url": "https://cdn.r2.com/narr_507f_slide_0_en.mp3",
      "library_audio_id": "507f1f77bcf86cd799439088",
      "file_size": 245678,
      "format": "mp3",
      "duration": 15.5,
      "speaker_count": 1
    }
  ],
  "total_duration": 45.8,
  "processing_time_ms": 3200,
  "points_deducted": 2
}
```

### Response Model
```typescript
interface AudioGenerateResponse {
  success: boolean;
  narration_id: string;
  audio_files: AudioFile[];
  total_duration: number;
  processing_time_ms: number;
  points_deducted: number;  // Always 2
}

interface AudioFile {
  slide_index: number;
  audio_url: string;          // R2 CDN URL
  library_audio_id: string;   // MongoDB library_audio._id
  file_size: number;          // bytes
  format: string;             // "mp3"
  duration: number;           // seconds
  speaker_count: number;
}
```

### Validation Rules
1. **Narration ID match**: `request.narration_id === narration_id` (URL)
2. **Ownership**: `narration.user_id === current_user.uid`
3. **Points check**: User có đủ 2 điểm không
4. **Status check**: `narration.status != "completed"` (chưa có audio)
5. **Subtitles exist**: `narration.slides.length > 0` hoặc `request.slides.length > 0`

---

## 3. Database Schema

### Collection: `slide_narrations`

```javascript
{
  _id: ObjectId("507f1f77bcf86cd799439099"),
  narration_id: "507f1f77bcf86cd799439099",  // Same as _id
  presentation_id: "507f1f77bcf86cd799439011",
  user_id: "firebase_uid_123",

  // Language & Version (CRITICAL!)
  language: "en",              // ISO 639-1 code
  version: 1,                  // Auto-increment per language

  // Status
  status: "subtitles_only",    // "subtitles_only" | "completed" | "failed"

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
          element_references: []
        }
      ],
      auto_advance: true,
      transition_delay: 2.0
    }
  ],
  total_duration: 45.8,

  // Audio data (populated after Step 2)
  audio_files: [
    {
      slide_index: 0,
      audio_url: "https://cdn.r2.com/...",
      library_audio_id: "507f...",
      file_size: 245678,
      format: "mp3",
      duration: 15.5,
      speaker_count: 1
    }
  ],
  voice_config: {...},

  // Timestamps
  created_at: ISODate("2026-01-08T10:00:00Z"),
  updated_at: ISODate("2026-01-08T10:05:00Z"),

  // Mode & Scope
  mode: "comprehensive",       // "minimal" | "balanced" | "comprehensive"
  scope: "current"             // "current" | "all"
}
```

### Indexes
```javascript
db.slide_narrations.createIndex({ presentation_id: 1, language: 1, version: -1 })
db.slide_narrations.createIndex({ user_id: 1, created_at: -1 })
db.slide_narrations.createIndex({ narration_id: 1 }, { unique: true })
```

---

## 4. Frontend Implementation

### ❌ WRONG: Không gửi slides
```typescript
// BAD - Sẽ lấy version CŨ từ database
const response = await api.post(`/narration/${id}/generate-audio`, {
  narration_id: id,
  voice_config: selectedVoice
  // slides: undefined ← Database có thể là version cũ!
});
```

### ✅ CORRECT Option 1: Gửi slides (Khuyến nghị)
```typescript
// GOOD - Gửi slides đã edit
const response = await api.post(`/narration/${id}/generate-audio`, {
  narration_id: id,
  voice_config: selectedVoice,
  slides: editedSlides  // ← Slides vừa edit trong UI
});
```

### ✅ CORRECT Option 2: Save trước, generate sau
```typescript
// GOOD - 2 bước rõ ràng
// Step 1: Save edited subtitles
await api.put(`/narration/${id}`, {
  slides: editedSlides
});

// Step 2: Generate audio (sẽ lấy từ DB)
const response = await api.post(`/narration/${id}/generate-audio`, {
  narration_id: id,
  voice_config: selectedVoice
  // slides không cần gửi vì đã save ở Step 1
});
```

### Complete Frontend Flow
```typescript
// Component state
const [editedSlides, setEditedSlides] = useState<SlideSubtitleData[]>([]);
const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

// User edit subtitle
const handleSubtitleEdit = (slideIndex: number, subtitleIndex: number, newText: string) => {
  const updated = [...editedSlides];
  updated[slideIndex].subtitles[subtitleIndex].text = newText;
  setEditedSlides(updated);
  setHasUnsavedChanges(true);
};

// Option A: Save button
const handleSave = async () => {
  const response = await api.put(`/narration/${narrationId}`, {
    slides: editedSlides
  });
  setHasUnsavedChanges(false);
  toast.success("Đã lưu subtitle!");
};

// Option B: Generate audio (khuyến nghị)
const handleGenerateAudio = async () => {
  // Gửi kèm edited slides
  const response = await api.post(
    `/presentations/${presentationId}/narration/${narrationId}/generate-audio`,
    {
      narration_id: narrationId,
      voice_config: selectedVoice,
      slides: editedSlides  // ← CRITICAL: Gửi slides đã edit!
    }
  );

  setHasUnsavedChanges(false);
  toast.success("Đang tạo audio...");
};
```

---

## 5. Language & Version Management

### Language Code
- **ISO 639-1**: `en`, `vi`, `zh`, `ja`, etc.
- **Stored in**: `slide_narrations.language`
- **Used for**:
  - Grouping narrations by language
  - Auto-selecting TTS voice
  - UI language switcher

### Version System
- **Auto-increment** per language: `1, 2, 3, ...`
- **Query**: Get latest version
  ```javascript
  db.slide_narrations.find({
    presentation_id: "...",
    language: "en"
  }).sort({ version: -1 }).limit(1)
  ```

### Example: Multiple Languages
```javascript
// Presentation có 3 ngôn ngữ
{
  presentation_id: "pres_123",
  language: "en",
  version: 2  // English version 2
}
{
  presentation_id: "pres_123",
  language: "vi",
  version: 1  // Vietnamese version 1
}
{
  presentation_id: "pres_123",
  language: "zh",
  version: 1  // Chinese version 1
}
```

---

## 6. Error Handling

### 400 Bad Request
```json
{
  "detail": "Overlapping timestamps in slide 0: subtitle 1 ends at 8.0s, but subtitle 2 starts at 7.5s"
}
```

### 403 Forbidden
```json
{
  "detail": "Not authorized to edit this narration"
}
```

### 402 Payment Required
```json
{
  "detail": {
    "error": "insufficient_points",
    "message": "Không đủ điểm. Cần: 2, Còn: 1",
    "points_needed": 2,
    "points_available": 1
  }
}
```

### 404 Not Found
```json
{
  "detail": "Narration not found"
}
```

---

## 7. Testing Checklist

### ✅ Test Cases

1. **Edit → Save → Generate**
   - Edit subtitle text
   - PUT /narration/{id}
   - POST /generate-audio (no slides)
   - Verify audio uses edited version

2. **Edit → Generate Directly**
   - Edit subtitle text
   - POST /generate-audio (with slides)
   - Verify audio uses edited version
   - Verify database updated

3. **Language Switching**
   - Generate EN subtitle (version 1)
   - Switch to VI → Generate VI subtitle (version 1)
   - Edit EN subtitle → Generate EN audio
   - Verify VI not affected

4. **Version Management**
   - Generate EN v1 with audio
   - Generate EN v2 subtitles (new version)
   - Edit v2 → Generate v2 audio
   - Verify v1 unchanged

5. **Validation**
   - Overlapping timestamps → 400 error
   - Edit after audio generated → 400 error
   - Insufficient points → 402 error
   - Wrong user → 403 error

---

## 8. Performance Notes

- **Database**: Single collection query (O(1) lookup by `_id`)
- **Audio generation**: 2-5s per slide (Google TTS)
- **Points deduction**: Optimistic (deduct first, refund on failure)
- **CDN**: R2 with permanent URLs (no expiry)

---

## Summary

**CRITICAL RULES:**
1. ✅ **Always gửi `slides` trong POST /generate-audio request** (khuyến nghị)
2. ✅ Hoặc gọi PUT /narration/{id} trước (alternative)
3. ✅ Backend tự động save slides vào DB khi generate audio
4. ✅ Language + version đúng → audio đúng
5. ❌ KHÔNG generate audio mà không update slides trước

**Frontend phải:**
- Gửi `slides` edited trong audio request
- Hoặc gọi PUT endpoint trước khi generate

**Backend guarantee:**
- Slides từ request > Slides từ database
- Tự động save vào DB khi có slides trong request
- Language/version được maintain đúng
