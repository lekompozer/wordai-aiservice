# LetsRead Book Page API — Frontend Integration Guide

## Overview

Each LetsRead book has per-page text content stored in MongoDB and optionally generated TTS audio. The frontend calls these endpoints to render a page-flip reading experience with optional audio narration.

**Base URL (production):** `https://ai.wordai.pro`

---

## Available Books

| Book Title | `book_id` | Story Pages | Total Pages |
|-----------|-----------|-------------|-------------|
| The Protectors | `69a574023e71c1cffad9fd99` | 20 | 25 |
| The Spirit of Ocean Nights | `69a57f2395ddad1ab6b1a589` | ~20 | 25 |
| Roots Are Stronger Than Steel | `69a57f3a95ddad1ab6b1a58a` | ~25 | 30 |
| Children of the Sun and Stars | `69a5b1d5d65c532c84b3d1b5` | ~20 | 24 |

> Books are attributed to `@Storybook`. Each book has 5 post-story pages (Community Engagement Guide / discussion questions) after the main story.

---

## Endpoints

### 1. `GET /api/v1/books/{book_id}/pages` — Get All Pages (Public)

Returns all pages with text and images for a book. No auth required.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `language` | `string` | `"en"` | Language code: `"en"` or `"vi"` |
| `story_only` | `bool` | `false` | If `true`, returns only story pages (excludes Community Engagement Guide and the last promo page). Use this for PDF export or clean reading view. |
| `limit` | `int` | `100` | Max pages to return |
| `offset` | `int` | `0` | Pagination offset |

**Response:**
```json
{
  "book_id": "69a574023e71c1cffad9fd99",
  "total_pages": 20,
  "language": "en",
  "pages": [
    {
      "page_number": 1,
      "text_content": "In the heart of the rainforest...",
      "image_url": "https://storage.googleapis.com/lets-read-asia/IMAGE_PATH",
      "image_url_cdn": "https://letsread-images.hamropatro.com/...",
      "image_url_hires": "https://lh3.googleusercontent.com/...",
      "image_name": "p-1.jpg",
      "image_width": 424,
      "image_height": 600,
      "has_audio": false,
      "letsread_page_id": 3035673785431907168
    }
  ]
}
```

> **Note:** `text_content` may contain HTML tags (`<b>`, `<i>`, `<br/>`) — render as innerHTML.
> Use `image_url_cdn` for thumbnails, `image_url_hires` for full-res display.
>
> **Tip:** For PDF or ebook export, use `?story_only=true` — this strips the 5 post-story discussion pages and the LetsRead promo page, leaving only the story content.

---

### 2. `GET /api/v1/books/{book_id}/audio` — Get Book Audio (Public)

Returns the generated TTS audio URL and per-page timestamps. No auth required.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `voice` | `string` | `"aoede"` | Voice name: `aoede`, `algenib`, or `auto` |
| `language` | `string` | `"en"` | Language code: `"en"` or `"vi"` |
| `include_pages` | `bool` | `false` | If `true`, embeds story-only page text into the response |

> **Audio coverage:** Audio is generated for story pages only (stops before the Community Engagement Guide). For "The Protectors" EN: 25 timestamps, VI: 20 timestamps.

**Response (audio exists — EN):**
```json
{
  "book_id": "69a574023e71c1cffad9fd99",
  "voice": "Algenib",
  "version": 1,
  "status": "completed",
  "audio_url": "https://static.wordai.pro/book-audio/69a574023e71c1cffad9fd99/Algenib/v1/merged.wav",
  "total_duration_seconds": 421.5,
  "total_pages": 25,
  "page_timestamps": [
    { "page_number": 1, "start_time": 0.0,   "end_time": 9.615,  "duration": 9.615 },
    { "page_number": 2, "start_time": 9.615, "end_time": 21.634, "duration": 12.019 }
  ]
}
```

**Response (audio exists — VI):**
```json
{
  "book_id": "69a574023e71c1cffad9fd99",
  "voice": "Algenib",
  "version": 1,
  "status": "completed",
  "audio_url": "https://static.wordai.pro/book-audio/69a574023e71c1cffad9fd99/Algenib/vi/v1/merged.wav",
  "total_duration_seconds": 288.66,
  "total_pages": 20,
  "page_timestamps": [
    { "page_number": 1, "start_time": 0.0,   "end_time": 9.852,  "duration": 9.852 },
    { "page_number": 2, "start_time": 9.852, "end_time": 22.167, "duration": 12.315 }
  ]
}
```

**Response (audio not yet generated):**
```json
{
  "book_id": "69a574023e71c1cffad9fd99",
  "audio_url": null,
  "voice": "Aoede",
  "version": null,
  "total_duration_seconds": null,
  "page_timestamps": [],
  "status": "not_generated"
}
```

> **R2 path structure:** `book-audio/{book_id}/{voice_name}/{language}/v{version}/merged.wav`
> (EN audio generated before language support may use the legacy path: `book-audio/{book_id}/{voice_name}/v{version}/merged.wav`)

---

### 3. `POST /api/v1/books/{book_id}/audio/generate` — Start Audio Generation (Auth Required)

Starts async TTS audio generation for a book. Requires Firebase auth token.

**Headers:**
```
Authorization: Bearer <firebase_id_token>
```

**Request Body:**
```json
{
  "voice": "auto",
  "language": "en"
}
```

Voice options: `"aoede"`, `"algenib"`, `"auto"` (auto picks based on book).

**Response:**
```json
{
  "job_id": "audio_gen_abc123",
  "book_id": "69a574023e71c1cffad9fd99",
  "status": "pending",
  "voice_name": "aoede",
  "message": "Audio generation started"
}
```

---

### 4. `GET /api/v1/books/{book_id}/audio/generate/status/{job_id}` — Poll Job Status (Auth Required)

**Headers:**
```
Authorization: Bearer <firebase_id_token>
```

**Response:**
```json
{
  "job_id": "audio_gen_abc123",
  "book_id": "69a574023e71c1cffad9fd99",
  "status": "processing",
  "voice_name": "aoede",
  "progress_pct": 45,
  "error_message": null,
  "audio_url": null,
  "created_at": "2026-03-03T10:00:00Z",
  "updated_at": "2026-03-03T10:01:30Z"
}
```

Status values: `pending` → `processing` → `completed` | `failed`

---

## Frontend Integration Patterns

### Pattern 1: Display Pages Only (No Audio)

```javascript
const bookId = "69a574023e71c1cffad9fd99";

async function loadBookPages(bookId) {
  const res = await fetch(`/api/v1/books/${bookId}/pages`);
  const data = await res.json();
  return data.pages; // array of page objects
}

// Render page
function renderPage(page) {
  return `
    <div class="book-page">
      <img src="${page.image_url_cdn}" loading="lazy" />
      <div class="page-text">${page.text_content}</div>
    </div>
  `;
}
```

### Pattern 2: Display Pages + Sync Audio Playback

```javascript
const bookId = "69a574023e71c1cffad9fd99";

async function loadBookWithAudio(bookId, voice = "auto", language = "en") {
  const [pagesRes, audioRes] = await Promise.all([
    fetch(`/api/v1/books/${bookId}/pages?language=${language}`),
    fetch(`/api/v1/books/${bookId}/audio?voice=${voice}&language=${language}`)
  ]);

  const { pages } = await pagesRes.json();
  const audioData = await audioRes.json();

  return { pages, audioData };
}

// Sync audio to page turns
function setupAudioSync(audioData, getCurrentPage) {
  if (!audioData.audio_url) return null;

  const audio = new Audio(audioData.audio_url);
  const timestamps = audioData.page_timestamps; // [{page_number, start_time, end_time, duration}]

  // Jump to page's timestamp when user turns page
  function jumpToPage(pageNumber) {
    const ts = timestamps.find(t => t.page_number === pageNumber);
    if (ts) {
      audio.currentTime = ts.start_time; // seconds (not ms)
    }
  }

  // Auto-turn page as audio plays
  audio.addEventListener("timeupdate", () => {
    const currentSec = audio.currentTime;
    const activeTs = timestamps.find(
      t => currentSec >= t.start_time && currentSec < t.end_time
    );
    if (activeTs && activeTs.page_number !== getCurrentPage()) {
      onPageChange(activeTs.page_number); // your callback
    }
  });


  return { audio, jumpToPage };
}
```

### Pattern 3: Check Audio Then Trigger Generation

```javascript
async function ensureAudioReady(bookId, firebaseToken, voice = "auto", language = "en") {
  // 1. Check if audio already exists
  const checkRes = await fetch(`/api/v1/books/${bookId}/audio?voice=${voice}&language=${language}`);
  const existing = await checkRes.json();

  if (existing.status === "completed") {
    return existing; // Already ready
  }

  // 2. Start generation (will auto-translate to VI if language=vi)
  const genRes = await fetch(`/api/v1/books/${bookId}/audio/generate`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${firebaseToken}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ voice, language })
  });
  const { job_id } = await genRes.json();

  // 3. Poll until done
  return pollUntilComplete(bookId, job_id, firebaseToken);
}

async function pollUntilComplete(bookId, jobId, token, intervalMs = 5000) {
  while (true) {
    await new Promise(r => setTimeout(r, intervalMs));

    const res = await fetch(
      `/api/v1/books/${bookId}/audio/generate/status/${jobId}`,
      { headers: { "Authorization": `Bearer ${token}` } }
    );
    const status = await res.json();

    if (status.status === "completed") {
      // Re-fetch final audio data with timestamps
      const audioRes = await fetch(`/api/v1/books/${bookId}/audio`);
      return await audioRes.json();
    }

    if (status.status === "failed") {
      throw new Error(status.error_message || "Audio generation failed");
    }

    // Update progress UI: status.progress_pct (0-100)
    updateProgressUI(status.progress_pct);
  }
}
```

---

## Notes

- **Text content** may contain HTML entities and tags — render with `innerHTML`, not `textContent`
- **Audio generation** takes ~3-5 minutes per book (story pages via Gemini TTS)
- **VI generation** auto-translates EN→VI via DeepSeek before running TTS (adds ~90s)
- **Page timestamps** are in **seconds** (`start_time`, `end_time`, `duration`) — not milliseconds
- **Story pages only:** Audio covers only story pages (not Community Engagement Guide). Use `?story_only=true` for pages in the same scope.
- **Voice "auto"** picks deterministically: ~70% Aoede, ~30% Algenib (hash of book_id)
- All `GET /pages` and `GET /audio` endpoints are **public** — no auth needed for reading
- Only `POST /audio/generate` and `DELETE /audio/{voice}` require auth
- **Attribution:** Books show `authors: ["@Storybook"]` (the uploader), `metadata.original_author: "Let's Read Asia"`

---

## Confirmed Live Audio (The Protectors)

| Language | Voice | Duration | Pages | URL |
|----------|-------|----------|-------|-----|
| EN | Algenib | 421.5s | 25 | `book-audio/69a574023e71c1cffad9fd99/Algenib/v1/merged.wav` |
| VI | Algenib | 288.7s | 20 | `book-audio/69a574023e71c1cffad9fd99/Algenib/vi/v1/merged.wav` |

---

*Last updated: March 3, 2026*
