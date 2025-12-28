# Multi-Language Subtitle & Audio System - Summary

## Overview

Hệ thống tạo subtitle và audio đa ngôn ngữ cho presentation slides với version management.

**Tính năng chính:**
- Tạo subtitle cho nhiều ngôn ngữ (vi, en, zh, ...)
- Mỗi ngôn ngữ có nhiều version
- Generate audio từ subtitle
- Audio chunking và merging tự động
- Sharing với cấu hình ngôn ngữ

---

## Database Collections

### 1. `presentation_subtitles`
Lưu subtitle cho từng ngôn ngữ + version.

**Fields quan trọng:**
- `presentation_id`: ID của presentation
- `user_id`: Owner
- `language`: Language code (vi, en, zh)
- `version`: Version number (1, 2, 3,...)
- `mode`: presentation | academy
- `slides`: Array of slides with subtitles
- `status`: completed | processing | failed
- `audio_status`: ready | processing | failed | None
- `merged_audio_id`: Reference to merged audio file
- `created_at`, `updated_at`

**Version Management:**
- Mỗi lần generate subtitle mới cho cùng ngôn ngữ → version tăng lên
- Version 1 (vi) → Version 2 (vi) → Version 3 (vi)
- English có version riêng: Version 1 (en) → Version 2 (en)

### 2. `presentation_audio`
Lưu audio files (chunks và merged).

**Fields quan trọng:**
- `presentation_id`: ID của presentation
- `subtitle_id`: Reference to presentation_subtitles._id
- `user_id`: Owner
- `language`: Language code (matches subtitle)
- `version`: Version number (matches subtitle)
- `slide_index`: Slide index (None/-1 for merged audio)
- `audio_url`: Storage path / CDN URL
- `audio_type`: chunked | merged_presentation | full_presentation
- `chunk_index`: Chunk index if chunked
- `total_chunks`: Total chunks if chunked
- `audio_metadata`: Duration, file size, format
- `status`: ready | processing | failed | obsolete_chunk
- `replaced_by`: ID of merged audio (if chunk is obsolete)

**Audio Types:**
- `chunked`: Individual audio chunks per slide
- `merged_presentation`: Merged audio for entire presentation
- `full_presentation`: Complete presentation audio

### 3. `presentation_sharing`
Lưu cấu hình sharing.

**Fields quan trọng:**
- `presentation_id`: Unique per presentation
- `is_public`: Public access enabled
- `public_token`: Unique token for public URL
- `sharing_settings`:
  - `include_content`: Show slide HTML
  - `include_subtitles`: Show subtitles
  - `include_audio`: Provide audio playback
  - `allowed_languages`: Empty = all languages
  - `default_language`: Default language for public view

---

## API Endpoints

### Generate Subtitles V2

**POST** `/api/presentations/{presentation_id}/subtitles/v2`

**Request Body:**
- `language`: Language code (vi, en, zh)
- `mode`: presentation | academy
- `user_query`: Optional user instructions

**Response:**
- `subtitle`: Complete subtitle document
- `points_deducted`: 2

**Flow:**
1. Deduct 2 points
2. Get next version for language
3. Parse slides from presentation content_html
4. Generate subtitles using Gemini 3 Pro
5. Save to presentation_subtitles collection
6. Return subtitle document with version info

### List Subtitles V2

**GET** `/api/presentations/{presentation_id}/subtitles/v2?language={lang}`

**Query Parameters:**
- `language`: Optional filter by language

**Response:**
- `subtitles`: Array of subtitle documents
- `total_count`: Total count

**Sorting:** By language (asc), then version (desc)

**Frontend Usage:**
- Gọi endpoint này để check xem ngôn ngữ nào đã có subtitle
- Nếu có subtitle → hiển thị danh sách version
- Nếu chưa có → hiển thị button "Generate Subtitles"

### Get Subtitle V2

**GET** `/api/presentations/{presentation_id}/subtitles/v2/{subtitle_id}`

**Response:**
Complete subtitle document with audio information.

### Generate Audio V2

**POST** `/api/presentations/{presentation_id}/subtitles/v2/{subtitle_id}/audio`

**Request Body:**
- `voice_config`: Voice configuration
  - `provider`: google_cloud | elevenlabs
  - `voice_id`: Voice ID
  - `speed`: 0.9 - 1.2
  - `pitch`: 0.8 - 1.2
- `force_regenerate`: Force regenerate all chunks

**Response:**
- `audio_files`: Array of audio file documents
- `points_deducted`: Points cost

**Flow:**
1. Calculate points cost based on slides
2. Deduct points
3. Generate audio chunks (parallel processing)
4. Save chunks to presentation_audio collection
5. Merge chunks into single audio file
6. Update subtitle document with audio_status and merged_audio_id
7. Mark chunks as obsolete (replaced_by = merged_audio_id)

### Delete Subtitle V2

**DELETE** `/api/presentations/{presentation_id}/subtitles/v2/{subtitle_id}`

**Behavior:**
- Delete subtitle document
- Delete all associated audio files (chunks + merged)
- Cascade deletion

---

## User Flow

### Tạo Subtitle cho Tiếng Việt

1. User click "Generate Subtitles (Vietnamese)"
2. Frontend POST `/api/presentations/{id}/subtitles/v2`
   - Body: `{language: "vi", mode: "presentation"}`
3. Backend:
   - Deduct 2 points
   - Generate subtitles with Gemini
   - Save to DB with version=1
4. Frontend receives subtitle document
5. Frontend refresh list → hiển thị "Vietnamese (Version 1)"

### Generate Audio từ Subtitle

1. User select subtitle version
2. User configure voice settings
3. Frontend POST `/api/presentations/{id}/subtitles/v2/{subtitle_id}/audio`
   - Body: `{voice_config: {...}}`
4. Backend:
   - Calculate points (e.g., 15 slides = 15 points)
   - Deduct points
   - Generate audio chunks in parallel
   - Merge chunks into single file
   - Update subtitle.audio_status = "ready"
   - Update subtitle.merged_audio_id
5. Frontend poll subtitle status or re-fetch
6. Display audio player with merged audio URL

### Tạo Version Mới cùng Ngôn Ngữ

1. User click "Generate Subtitles (Vietnamese)" lần 2
2. Backend check existing versions for "vi" → latest is version 1
3. Create new subtitle with version=2
4. Save to DB
5. Frontend hiển thị cả Version 1 và Version 2

### Check Subtitle tồn tại

Frontend gọi GET `/api/presentations/{id}/subtitles/v2?language=vi`

**Nếu có data:**
- `subtitles.length > 0` → Ngôn ngữ này đã có subtitle
- Hiển thị list versions với audio status
- Button: "Generate Audio" (nếu chưa có audio)
- Button: "Play Audio" (nếu đã có audio)

**Nếu empty:**
- `subtitles.length === 0` → Chưa có subtitle
- Hiển thị button "Generate Subtitles"

---

## Common Issues & Solutions

### Issue 1: Frontend không thấy subtitle vừa tạo

**Nguyên nhân:**
- Frontend gọi sai endpoint (v1 thay vì v2)
- Frontend filter sai language code
- Cache cũ

**Solution:**
- Đảm bảo gọi `/api/presentations/{id}/subtitles/v2?language=vi`
- Check language code đúng (lowercase: vi, en, zh)
- Clear cache và re-fetch

### Issue 2: Audio generation không update subtitle

**Nguyên nhân:**
- Worker không update subtitle document sau khi merge

**Solution:**
- Check audio_status field trong subtitle document
- Check merged_audio_id có được set không
- Check presentation_audio collection có merged audio không

### Issue 3: Multiple audio chunks hiển thị

**Nguyên nhân:**
- Frontend query audio không filter audio_type
- Không filter status = "ready"

**Solution:**
- Filter audio_type = "merged_presentation"
- Filter status = "ready"
- Ignore chunks with status = "obsolete_chunk"

---

## Database Queries Examples

### Get latest subtitle for language

```
db.presentation_subtitles.find({
  presentation_id: "doc_xxx",
  language: "vi"
}).sort({version: -1}).limit(1)
```

### Get merged audio for subtitle

```
db.presentation_audio.findOne({
  subtitle_id: "subtitle_xxx",
  audio_type: "merged_presentation",
  status: "ready"
})
```

### Get all languages with subtitles

```
db.presentation_subtitles.aggregate([
  {$match: {presentation_id: "doc_xxx"}},
  {$group: {
    _id: "$language",
    latest_version: {$max: "$version"},
    has_audio: {$max: {$cond: [{$eq: ["$audio_status", "ready"]}, 1, 0]}}
  }}
])
```

---

## Points Cost

| Action | Cost |
|--------|------|
| Generate Subtitles | 2 points |
| Generate Audio (15 slides) | 15 points (1 point/slide) |
| Delete Subtitle | 0 points |
| List Subtitles | 0 points |

---

## Version Management Strategy

**Per Language Versioning:**
- Mỗi ngôn ngữ có version tracking riêng
- Version 1 (vi), Version 2 (vi), Version 3 (vi)
- Version 1 (en), Version 2 (en)

**Audio Versioning:**
- Audio version matches subtitle version
- Mỗi subtitle version có riêng audio files
- Regenerate audio → tạo audio mới cho version đó

**Deletion:**
- Delete subtitle → delete all audio của version đó
- Không ảnh hưởng versions khác

---

## Frontend Integration Checklist

✅ **Generate Subtitles:**
- POST `/api/presentations/{id}/subtitles/v2`
- Handle 402 insufficient points
- Display subtitle_id and version

✅ **List Subtitles:**
- GET `/api/presentations/{id}/subtitles/v2`
- Group by language
- Show latest version first
- Display audio status per version

✅ **Generate Audio:**
- POST `/api/presentations/{id}/subtitles/v2/{subtitle_id}/audio`
- Poll subtitle status for audio_status
- Display merged audio player when ready

✅ **Check Language Available:**
- Filter subtitles by language
- Check array length > 0
- Show/hide buttons accordingly

✅ **Display Audio:**
- Get merged_audio_id from subtitle
- Query presentation_audio for merged file
- Use audio_url for player source

---

## Migration Notes

**From V1 to V2:**
- V1: Single narration per presentation
- V2: Multi-language with versions
- V1 endpoint deprecated but still works
- New features only in V2

**Backward Compatibility:**
- Old presentations still use V1
- New presentations use V2
- No automatic migration needed
- Users can recreate subtitles in V2
