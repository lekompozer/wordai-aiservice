# LetsRead Asia - Per-Page Text Crawl + TTS Audio

> Model TTS: gemini-2.5-flash-preview-tts
> Voices: Aoede (Female, default) + Algenib (Male, ~30%)
> Goal: Crawl per-page text -> chunk -> TTS -> merge -> page timestamps -> frontend autoplay

---

## SUMMARY

This document describes the design for:
1. Crawling per-page text from letsreadasia.org Read viewer
2. Generating TTS audio per book using `gemini-2.5-flash-preview-tts`
3. Storing page timestamps so frontend can sync audio to pages

Frontend only needs: `audio_url` + `page_timestamps` array. No extra API calls needed during playback.

---

## 1. URL PATTERN

Read URL format (confirmed):
```
https://www.letsreadasia.org/read/{uuid}?bookLang={lang-id}
Example: https://www.letsreadasia.org/read/61b2f862-f64b-443b-9f6c-73f71024b538?bookLang=4846240843956224
```

- UUID = letsreadasia internal book ID — must save as `letsread_book_id` in `online_books`
- `bookLang` = language ID — must save as `letsread_lang_id`
- Viewer is a SPA — URL does NOT change when navigating pages
- Each page: illustration image + 1-3 short sentences + page number indicator
- Each page ~10-25 words = ~80-200 bytes of text

**Selenium approach:** click Next button + `WebDriverWait` for text change.
Must run `inspect_viewer_html()` first to confirm exact CSS selectors.

---

## 2. EXISTING AUDIO PATTERN (Slide Narration)

Analyzed: `src/services/slide_narration_service.py` (1946 lines)
Book page audio will **MIRROR** this pattern exactly.

### 2.1 Chunking (MAX 3500 bytes per chunk)

```python
MAX_BYTES_PER_CHUNK = 3500  # buffer under 4000 byte Gemini TTS limit

for slide in slides:
    # Combine subtitle texts, add pause marker between slides
    slide_text = ". ".join(sub["text"] for sub in slide["subtitles"])
    if not slide_text.endswith("."): slide_text += "."
    slide_text += "... "  # extended pause between slides

    if len((current_text + slide_text).encode()) > MAX_BYTES_PER_CHUNK:
        chunks.append({"slides": current_chunk, "text": current_text})
        current_chunk, current_text = [], ""

    current_chunk.append({...})
    current_text += slide_text
```

### 2.2 TTS Generation

```python
audio_data, metadata = await tts_service.generate_audio(
    text=chunk_text,
    language="en-US",       # BCP-47 (en -> en-US)
    voice_name="Aoede",
    use_pro_model=True,     # => gemini-2.5-flash-preview-tts
)
# Returns: WAV bytes + metadata{duration, format, voice_name, model}
```

### 2.3 Sentence-proportional timestamps

Counts number of periods (`.`) in each slide text as sentence count.
Proportionally distributes the chunk audio duration across slides.

```python
total_sentences = sum(slide["sentence_count"] for slide in chunk_slides)
current_pos = 0.0

for slide in chunk_slides:
    ratio = slide["sentence_count"] / total_sentences
    duration = actual_chunk_duration * ratio
    timestamps.append({
        "slide_index": slide["slide_index"],
        "start_time": current_pos,
        "end_time": current_pos + duration,
    })
    current_pos += duration
```

### 2.4 Merge multiple chunks (pydub)

When text exceeds 3500 bytes -> multiple chunks -> merge WAVs.

```python
combined = AudioSegment.empty()
global_ts = []
offset = 0.0

for chunk_doc in audio_documents:
    seg = AudioSegment.from_wav(io.BytesIO(download(chunk_doc["audio_url"])))
    actual = len(seg) / 1000.0  # ms -> seconds
    pred = chunk_doc["slide_timestamps"][-1]["end_time"]
    scale = actual / pred  # recalibrate: predicted vs actual TTS duration

    for ts in chunk_doc["slide_timestamps"]:
        global_ts.append({
            "slide_index": ts["slide_index"],
            "start_time": offset + ts["start_time"] * scale,
            "end_time": offset + ts["end_time"] * scale,
        })

    combined += seg
    offset += actual

# Export merged WAV
out = io.BytesIO()
combined.export(out, format="wav")
merged_wav_bytes = out.getvalue()
```

### 2.5 Final MongoDB document (`presentation_audio`)

```json
{
  "audio_url": "https://static.wordai.pro/narration/.../merged.wav",
  "audio_type": "merged_presentation",
  "slide_timestamps": [
    {"slide_index": 0, "start_time": 0.0, "end_time": 12.3},
    {"slide_index": 1, "start_time": 12.3, "end_time": 24.1}
  ],
  "audio_metadata": {
    "duration_seconds": 185.4,
    "voice_name": "Aoede",
    "model": "gemini-2.5-flash-preview-tts"
  },
  "status": "ready"
}
```

---

## 3. BOOK PAGES DESIGN (Mirror Slide Pattern)

### 3.1 Mapping: Slide -> Book Page

| Slide system           | Book Page system                |
|------------------------|---------------------------------|
| `slide_index`          | `page_number`                   |
| subtitle text          | `text_content`                  |
| `slide_timestamps`     | `page_timestamps`               |
| `presentation_audio`   | `book_page_audio` collection    |
| 3500 bytes/chunk       | 3500 bytes/chunk (same)         |
| sentence-proportional  | sentence-proportional (same)    |
| pydub WAV merge        | pydub WAV merge (same)          |
| `gemini-2.5-flash-...` | `gemini-2.5-flash-...` (same)   |

### 3.2 Chunking for book pages

Key insight: letsread books are children's books, each page ~10-25 words.
A 14-page book = ~2800 bytes total -> fits in **ONE chunk** -> no merge needed.

```python
MAX_BYTES_PER_CHUNK = 3500
page_chunks = []
current_chunk, current_text = [], ""

for page in sorted(pages, key=lambda p: p["page_number"]):
    text = page["text_content"]
    if not text.endswith("."): text += "."
    page_text = text + "... "  # pause between pages

    if len((current_text + page_text).encode()) > MAX_BYTES_PER_CHUNK and current_chunk:
        page_chunks.append({"pages": current_chunk, "text": current_text})
        current_chunk, current_text = [], ""

    current_chunk.append({
        "page_number": page["page_number"],
        "text": page_text,
        "sentence_count": text.count(".") or 1,
    })
    current_text += page_text

if current_chunk:
    page_chunks.append({"pages": current_chunk, "text": current_text})
```

### 3.3 Page timestamps

```python
total_sentences = sum(p["sentence_count"] for p in chunk_pages)
current_pos = 0.0

for p in chunk_pages:
    ratio = p["sentence_count"] / total_sentences
    duration = actual_chunk_duration * ratio
    page_timestamps.append({
        "page_number": p["page_number"],
        "start_time": round(current_pos, 3),
        "end_time": round(current_pos + duration, 3),
        "sentence_count": p["sentence_count"],
    })
    current_pos += duration
```

### 3.4 API response for frontend

```json
{
  "book_id": "book_0487c39b4b56",
  "voice": "aoede",
  "audio_url": "https://static.wordai.pro/books/audio/book_xxx/aoede_v1.wav",
  "total_duration_seconds": 124.5,
  "total_pages": 14,
  "page_timestamps": [
    {"page_number": 1,  "start_time": 0.0,   "end_time": 8.3},
    {"page_number": 2,  "start_time": 8.3,   "end_time": 16.7},
    {"page_number": 14, "start_time": 116.2, "end_time": 124.5}
  ]
}
```

Frontend JS (zero extra API calls during playback):
```javascript
audioEl.ontimeupdate = () => {
  const t = audioEl.currentTime;
  const pg = pageTimestamps.find(p => t >= p.start_time && t < p.end_time);
  if (pg && pg.page_number !== currentPage) showPage(pg.page_number);
};
```

---

## 4. DB SCHEMA

### `book_page_texts` collection

```python
{
    "_id": ObjectId(),
    "book_id": "book_0487c39b4b56",           # FK -> online_books
    "chapter_id": "chap_xxx",                  # FK -> book_chapters
    "letsread_book_id": "61b2f862-f64b-...",   # UUID from letsreadasia URL
    "page_number": 1,                           # 1-based
    "total_pages": 14,
    "text_content": "Once upon a time...",
    "image_url": "https://cdn.letsreadasia.org/...",
    "word_count": 18,
    "sentence_count": 2,
    "crawled_at": "datetime",
    "updated_at": "datetime",
}
# Indexes:
# {book_id: 1, page_number: 1} unique: true
# {chapter_id: 1}
```

### `book_page_audio` collection

```python
{
    "_id": ObjectId(),
    "book_id": "book_0487c39b4b56",
    "chapter_id": "chap_xxx",
    "voice_name": "Aoede",        # "Aoede" or "Algenib"
    "language": "en",
    "version": 1,
    "audio_url": "https://static.wordai.pro/books/audio/book_xxx/aoede_v1.wav",
    "r2_key": "books/audio/book_xxx/aoede_v1.wav",
    "audio_type": "full_book",    # or "chunked"
    "page_timestamps": [
        {"page_number": 1, "start_time": 0.0, "end_time": 8.3, "sentence_count": 2},
        # ...
    ],
    "audio_metadata": {
        "duration_seconds": 124.5,
        "total_pages": 14,
        "format": "wav",
        "voice_name": "Aoede",
        "model": "gemini-2.5-flash-preview-tts",
        "file_size_bytes": 3000000,
    },
    "status": "ready",      # pending|processing|ready|failed
    "generation_job_id": "uuid",
    "generated_by_user_id": "uid",
    "created_at": "datetime",
    "updated_at": "datetime",
}
# Indexes:
# {book_id: 1, voice_name: 1, version: -1}
# {generation_job_id: 1}
```

### Updates to `online_books`

Add when crawling pages:
```python
{
    "letsread_book_id": "61b2f862-f64b-443b-9f6c-73f71024b538",
    "letsread_lang_id": "4846240843956224",
    "has_page_texts": True,
    "total_pages": 14,
}
```

---

## 5. GAP ANALYSIS

### Can reuse

| Component      | File                                        | Usage                                      |
|----------------|---------------------------------------------|--------------------------------------------|
| TTS engine     | `src/services/google_tts_service.py`        | `generate_audio(text, voice_name, lang)`   |
| R2 upload      | `src/services/r2_storage_service.py`        | `upload_file(bytes, r2_key, content_type)` |
| Chunk + merge  | `src/services/slide_narration_service.py`   | Copy `generate_audio_v2` + `_merge_audio_chunks` |
| pydub          | Already in requirements                     | `AudioSegment` operations                  |
| DBManager      | `src/database/db_manager.py`                | DB connection                              |
| Firebase auth  | `src/middleware/firebase_auth.py`           | Endpoint auth                              |

### Must create new

| File                                    | Purpose                                    |
|-----------------------------------------|--------------------------------------------|
| `src/models/book_page_models.py`        | Pydantic models                            |
| `src/services/book_page_audio_service.py` | Core logic: chunk -> TTS -> merge -> timestamps |
| `src/api/book_page_routes.py`           | REST endpoints                             |
| `create_book_page_indexes.py`           | MongoDB index script                       |
| `crawler/letsread_page_crawler.py`      | Selenium per-page crawler                  |

---

## 6. NEW ENDPOINTS

```
POST /api/v1/books/{book_id}/pages/batch
  Save crawled pages to DB (admin/script only)
  Body: {letsread_book_id, letsread_lang_id, pages: [{page_number, text_content, image_url}]}
  Response: {saved: 14, book_id, chapter_id}

GET /api/v1/books/{book_id}/pages
  List pages with text
  Response: {total_pages: 14, pages: [{page_number, text_content, image_url}]}

POST /api/v1/books/{book_id}/audio/generate
  Generate audio for entire book (async job)
  Body: {voice: "aoede"|"algenib"|"both", language: "en", force_regenerate: false}
  Response: {job_id, status: "processing", total_pages: 14}

GET /api/v1/books/{book_id}/audio/generate/status/{job_id}
  Poll job status
  Response: {status: "ready"|"processing"|"failed", progress: {done: 14, total: 14}}

GET /api/v1/books/{book_id}/audio?voice=aoede        <- MAIN ENDPOINT for frontend
  Response: {audio_url, total_duration_seconds, total_pages, page_timestamps}

DELETE /api/v1/books/{book_id}/audio/{voice}
  Delete audio from R2 + DB
```

---

## 7. VOICE ASSIGNMENT

```python
import hashlib

def get_default_voice_for_book(book_id: str) -> str:
    # Deterministic: same book_id -> always same voice
    # ~70% Aoede (Female), ~30% Algenib (Male)
    h = int(hashlib.md5(book_id.encode()).hexdigest(), 16)
    return "Aoede" if (h % 10) < 7 else "Algenib"
```

Why per-book (not per-page): consistent voice throughout one book = more natural reading experience.

Voices confirmed in `src/services/google_tts_service.py`:
- **Aoede**: FEMALE, "Breezy" (line 96)
- **Algenib**: MALE, "Gravelly" (line 105)

BCP-47 conversion (same as `slide_narration_service.py`):
`en -> en-US`, `vi -> vi-VN`, `ja -> ja-JP`, etc.

---

## 8. IMPLEMENTATION ROADMAP

### Phase 1 — Verify HTML selectors (MUST DO FIRST)
- [ ] Add `inspect_viewer_html(driver, uuid, lang_id)` to `letsread_crawler.py`
- [ ] Run locally with 1 real book UUID from DB
- [ ] Confirm CSS selectors: text content, image, next button
- [ ] Commit selectors to `letsread_page_crawler.py`

### Phase 2 — Crawl and store page texts
- [ ] Create `crawler/letsread_page_crawler.py`
- [ ] Create + run `create_book_page_indexes.py` on server
- [ ] Crawl 4 existing books -> `book_page_texts` MongoDB
- [ ] Verify: correct page count, text content, image URLs
- [ ] Update `online_books`: save `letsread_book_id` + `letsread_lang_id`

### Phase 3 — Backend service + endpoints
- [ ] `src/models/book_page_models.py` (Pydantic models)
- [ ] `src/services/book_page_audio_service.py` (mirror `generate_audio_v2`)
- [ ] `src/api/book_page_routes.py` (all 6 endpoints)
- [ ] Register router in `main.py`
- [ ] Deploy: `./deploy-app-only.sh`

### Phase 4 — Test
- [ ] `POST /books/{id}/pages/batch` -> verify MongoDB
- [ ] `POST /books/{id}/audio/generate` -> wait for completion
- [ ] `GET  /books/{id}/audio?voice=aoede` -> verify `audio_url` + `page_timestamps`
- [ ] Verify: sum of page durations ~= `total_duration_seconds`
- [ ] Test in browser: play audio -> pages update at right timestamps

### Phase 5 — Full catalog
- [ ] Crawl all remaining books
- [ ] Bulk generate audio (Aoede by default)
- [ ] Remove `TEST_LIMIT=4` from `letsread_crawler.py`

---

## ARCHITECTURE SUMMARY

```
crawl_book_pages(uuid, lang_id)
    Selenium: click Next x N pages
    extract {page_number, text_content, image_url}
           |
           v
    book_page_texts (MongoDB)
           |
           v  POST /books/{id}/audio/generate
    book_page_audio_service.generate_book_audio(book_id, voice)
        1. Load pages from book_page_texts
        2. Chunk pages (MAX 3500 bytes/chunk)
        3. For each chunk:
           a. Build text: page texts joined with "... " pause markers
           b. TTS -> WAV bytes (gemini-2.5-flash-preview-tts)
           c. Count sentences per page -> proportional durations
           d. Build page_timestamps for chunk
           e. Upload WAV chunk to R2
        4. If multiple chunks: pydub merge + recalculate global timestamps
           |
           v
    book_page_audio (MongoDB)
        audio_url: R2 CDN URL for merged WAV
        page_timestamps: [{page_number, start_time, end_time}]
           |
           v
    GET /books/{id}/audio?voice=aoede
        returns {audio_url, page_timestamps, total_duration_seconds}
           |
           v
    Frontend:
        <audio src="{audio_url}" />
        ontimeupdate -> find page where start_time <= currentTime < end_time
        -> display correct page image + text
        Zero extra API calls during playback
```

`book_page_audio_service.py` mirrors `slide_narration_service.py`:
- `generate_audio_v2()` lines 1052–1600 (chunking + TTS + timestamps)
- `_merge_audio_chunks()` lines 1620–1840 (pydub merge + global timestamp recalc)

Only changes: `slide_index` -> `page_number`, subtitles list -> `text_content`,
`presentation_audio` collection -> `book_page_audio` collection.

---

## COST AND CONSTRAINTS

| Item                        | Estimate                          |
|-----------------------------|-----------------------------------|
| Text per page               | 80–200 bytes                      |
| Audio per page              | 8–12 seconds                      |
| Audio per book (14 pages)   | ~2.7 MB WAV                       |
| 20 books x 2.7 MB           | ~54 MB R2 storage                 |
| TTS cost per book           | ~2 API calls (usually 1 chunk)    |
| 20 books x 2 voices         | ~80 calls -> use admin account    |
| RAM impact                  | No new container needed           |
