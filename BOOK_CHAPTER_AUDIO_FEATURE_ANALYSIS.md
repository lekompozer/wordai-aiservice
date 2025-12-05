# Book Chapter Audio Feature - Technical Analysis

## Overview

Add audio narration capability to book chapters, allowing users to listen to chapter content while reading. Supports both user-uploaded audio files and AI-generated text-to-speech using Google Cloud Text-to-Speech API.

---

## Feature Requirements

### Core Functionality

1. **Audio Attachment per Chapter**
   - Each chapter can have one audio file attached
   - Audio plays on-demand when user clicks play button
   - Audio syncs with chapter language versions
   - Audio inheritable from book-level default or chapter-specific

2. **Two Audio Input Methods**

   **Method 1: User Upload**
   - Upload audio file (MP3, WAV, M4A, OGG)
   - Maximum file size: 50MB
   - Store in Cloudflare R2 with CDN delivery
   - Preview before confirming upload

   **Method 2: AI Generation (Text-to-Speech)**
   - Uses Google Cloud Text-to-Speech API via VERTEX_API_KEY
   - Parse text from `content_html` OR user-provided text (preferred)
   - User selects voice from available options
   - Preview generated audio before saving
   - Auto-save to library after successful generation

3. **Voice Selection**
   - Fetch available voices from Google Cloud TTS
   - Filter by language (match chapter language)
   - Display voice characteristics: gender, accent, neural/standard
   - Allow preview of sample voice before generation

4. **Audio Library Integration**
   - Save generated/uploaded audio to user's library
   - Categorize as "Chapter Audio" type
   - Link audio file to specific chapter
   - Reuse audio across language versions if desired

5. **Public Access Control**
   - Audio follows same permissions as chapter content
   - Public chapters: Audio accessible without auth
   - Premium chapters: Audio only for purchasers/owners
   - Respect `is_preview_free` flag for marketplace

---

## Database Schema Changes

### Chapters Collection (Owner's Audio)

**New Fields:**

```javascript
{
  // Existing fields...
  "audio_config": {
    "enabled": true,                    // Audio available for this chapter
    "audio_url": "https://static.wordai.pro/audio/chapter_xxx.mp3",
    "audio_file_id": "file_abc123",     // Reference to owner's library file
    "duration_seconds": 320,            // Audio length
    "file_size_bytes": 5242880,         // ~5MB
    "format": "mp3",                    // mp3, wav, m4a, ogg
    "source_type": "ai_generated",      // "user_upload" | "ai_generated"
    "voice_settings": {                 // Only for AI-generated
      "voice_name": "en-US-Neural2-A",
      "language_code": "en-US",
      "gender": "FEMALE",
      "speaking_rate": 1.0,
      "pitch": 0.0,
      "volume_gain_db": 0.0
    },
    "generated_at": "2024-12-05T10:00:00Z",
    "generated_by_user_id": "owner_123",
    "generation_cost_points": 2         // Points used for TTS
  },

  // Audio per language translation
  "audio_translations": {
    "vi": {
      "audio_url": "https://static.wordai.pro/audio/chapter_xxx_vi.mp3",
      "audio_file_id": "file_def456",
      "duration_seconds": 340,
      "voice_settings": {
        "voice_name": "vi-VN-Neural2-A",
        "language_code": "vi-VN",
        "gender": "FEMALE"
      }
    }
  }
}
```

**Indexes:**

```javascript
db.book_chapters.createIndex({ "audio_config.enabled": 1 })
db.book_chapters.createIndex({ "audio_config.audio_file_id": 1 })
```

---

### User Files Collection (Library)

**New Audio File Type:**

```javascript
{
  "file_id": "file_abc123",
  "user_id": "user_123",             // Owner OR Community User
  "file_type": "audio",              // New type alongside "image", "document"
  "category": "audio",               // Matches LibraryManager category
  "audio_type": "chapter_narration", // Subcategory
  "original_filename": "chapter1_narration.mp3",
  "r2_url": "https://static.wordai.pro/audio/user_123/chapter_abc.mp3",
  "r2_key": "audio/user_123/chapter_abc.mp3",
  "file_size_bytes": 5242880,
  "mime_type": "audio/mpeg",
  "duration_seconds": 320,
  "audio_format": "mp3",

  // For AI-generated audio
  "source_type": "ai_generated",
  "ai_metadata": {
    "provider": "google_cloud_tts",
    "voice_name": "en-US-Neural2-A",
    "language_code": "en-US",
    "generation_model": "text-to-speech-v1",
    "generation_cost_points": 2
  },

  // Linkage (CRITICAL for Community Users)
  "linked_to": {
    "type": "book_chapter",
    "book_id": "book_123",
    "chapter_id": "chapter_456",
    "language": "en"                 // Language version of the audio
  },

  "created_at": "2024-12-05T10:00:00Z",
  "updated_at": "2024-12-05T10:00:00Z",
  "is_deleted": false
}
```---

## Google Cloud Text-to-Speech Integration

### API Configuration

**Authentication:**
- Use existing `VERTEX_API_KEY` from `.env`
- Endpoint: `https://texttospeech.googleapis.com/v1/text:synthesize`
- API Key: `VERTEX_API_KEY=AQ.Ab8RN6KSNnUPEOKtyauy80dB9aO0O1C7dVrWiDLXrRqxCJOuvA`

**Available Voices Endpoint:**
- GET `https://texttospeech.googleapis.com/v1/voices?key={VERTEX_API_KEY}`
- Returns list of all available voices with metadata

**Voice Characteristics:**
- **Neural2 Voices**: High-quality neural network voices (recommended)
- **Wavenet Voices**: Good quality with natural prosody
- **Standard Voices**: Basic quality, lower cost
- **Studio Voices**: Premium quality for professional use

### Supported Languages (17 languages matching book translation)

| Language Code | Voice Examples | Neural2 Available |
|--------------|----------------|-------------------|
| `en-US` | Neural2-A/B/C/D (Male/Female) | ✅ Yes |
| `vi-VN` | Neural2-A/B (Male/Female) | ✅ Yes |
| `zh-CN` (Simplified) | cmn-CN-Wavenet-A/B/C/D | ✅ Yes |
| `zh-TW` (Traditional) | cmn-TW-Wavenet-A/B/C | ✅ Yes |
| `ja-JP` | Neural2-B/C/D (Male/Female) | ✅ Yes |
| `ko-KR` | Neural2-A/B/C (Male/Female) | ✅ Yes |
| `th-TH` | Neural2-C (Female) | ✅ Yes |
| `id-ID` | Wavenet-A/B/C/D | ⚠️ Wavenet only |
| `km-KH` | Wavenet-A (Female) | ⚠️ Limited |
| `lo-LA` | Standard (Basic) | ⚠️ Limited |
| `hi-IN` | Neural2-A/B/C/D | ✅ Yes |
| `ms-MY` | Wavenet-A/B/C/D | ⚠️ Wavenet only |
| `pt-BR` | Neural2-A/B/C | ✅ Yes |
| `ru-RU` | Wavenet-A/B/C/D/E | ✅ Yes |
| `fr-FR` | Neural2-A/B/C/D/E | ✅ Yes |
| `de-DE` | Neural2-A/B/C/D/F | ✅ Yes |
| `es-ES` | Neural2-A/B/C/D/E/F | ✅ Yes |

**Voice Naming Convention:**
- Format: `{language_code}-{voice_type}-{letter}`
- Example: `en-US-Neural2-A` (English US, Neural2 quality, Voice A)
- Gender: A/C/E typically Female, B/D/F typically Male

### Text-to-Speech Request

**Request Body:**

```json
{
  "input": {
    "text": "Chapter content extracted from HTML..."
  },
  "voice": {
    "languageCode": "en-US",
    "name": "en-US-Neural2-A",
    "ssmlGender": "FEMALE"
  },
  "audioConfig": {
    "audioEncoding": "MP3",
    "speakingRate": 1.0,
    "pitch": 0.0,
    "volumeGainDb": 0.0,
    "effectsProfileId": ["headphone-class-device"]
  }
}
```

**Response:**

```json
{
  "audioContent": "base64_encoded_audio_data..."
}
```

**Response Processing:**
1. Decode base64 audio data
2. Upload to Cloudflare R2
3. Generate public URL
4. Save metadata to database
5. Link to chapter and user library

---

## Text Extraction from HTML

### Extraction Strategy

**Priority 1: User-Provided Text (Recommended)**
- User pastes clean text into textarea
- Avoids HTML parsing issues
- User can edit/customize narration text
- Faster and more reliable

**Priority 2: Auto-Extract from content_html**
- Strip all HTML tags using BeautifulSoup
- Remove code blocks, tables, images
- Extract only readable text
- Clean whitespace and formatting

**Python Implementation:**

```python
from bs4 import BeautifulSoup
import re

def extract_text_from_html(content_html: str) -> str:
    """
    Extract clean text from chapter HTML content
    Removes code blocks, tables, and formatting
    """
    # Parse HTML
    soup = BeautifulSoup(content_html, 'html.parser')

    # Remove unwanted elements
    for element in soup(['script', 'style', 'code', 'pre', 'table']):
        element.decompose()

    # Get text
    text = soup.get_text(separator=' ', strip=True)

    # Clean whitespace
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n+', '\n', text)

    # Limit length (Google TTS max: 5000 characters per request)
    if len(text) > 5000:
        text = text[:5000] + "..."

    return text.strip()
```

**Character Limits:**
- Google Cloud TTS: 5000 characters per request
- For longer chapters: Split into multiple requests and concatenate audio
- Estimated: 5000 chars ≈ 5-7 minutes of audio

---

## Points System & Pricing

### Cost Structure

**AI Audio Generation:**
- **Owner Generation:** **2 points per chapter** (Standard/Neural2)
- **Community User Generation:** **2 points per chapter** (if owner hasn't provided audio)
- **Voice Types:** Same price for Neural2 and Wavenet (simplified pricing)

**User Upload:**
- **FREE** (0 points)
- Only available to Book Owner

**Community Listening:**
- **FREE** if audio already exists (created by owner or previously by user)
- **2 points** if user needs to generate audio for themselves

**Regeneration:**
- Same cost as initial generation (2 points)

**Audio Library Storage:**
- All audio files saved to library automatically
- No additional storage cost
- Count towards user's total storage quota

---

## Audio Storage & Priority Logic

### Storage Strategy

**1. Owner's Audio:**
- Stored in `book_chapters` collection under `audio_config` field
- Also saved in Owner's Library (`library_files`)
- Publicly accessible to all readers (subject to book permissions)

**2. Community User's Audio:**
- Stored **ONLY** in User's Library (`library_files`)
- Linked to the chapter via `linked_to` metadata
- **Private** to that specific user (other community users cannot access it)
- Persists for future visits (user pays once, listens forever)

### Playback Priority (Frontend Logic)

When a user views a chapter, the system determines which audio to play:

1.  **Priority 1: Owner's Audio**
    - Check `chapter.audio_config` (or `audio_translations` for current language)
    - If exists: Play this audio (FREE for user)

2.  **Priority 2: User's Existing Audio**
    - If Owner's audio missing, check User's Library
    - Query: `library_files` where `user_id=current_user` AND `linked_to.chapter_id=current_chapter`
    - If exists: Play this audio (FREE, already paid)

3.  **Priority 3: Generate New Audio**
    - If neither exists: Show "Generate Audio" button
    - Cost: **2 points**
    - Action: Generates audio, saves to User's Library, then plays

---

## API Endpoints Design

### 1. Get Available Voices

**Endpoint:** `GET /api/v1/audio/voices?language={language_code}`

**Purpose:** Fetch available TTS voices for voice selection UI

**Query Parameters:**
- `language` (optional): Filter by language code (e.g., "en-US", "vi-VN")

**Response:**

```json
{
  "voices": [
    {
      "name": "en-US-Neural2-A",
      "language_code": "en-US",
      "ssml_gender": "FEMALE",
      "natural_sample_rate_hertz": 24000,
      "voice_type": "Neural2",
      "description": "US English female neural voice"
    },
    {
      "name": "en-US-Neural2-B",
      "language_code": "en-US",
      "ssml_gender": "MALE",
      "natural_sample_rate_hertz": 24000,
      "voice_type": "Neural2",
      "description": "US English male neural voice"
    }
  ],
  "total": 245,
  "filtered": 8
}
```

---

### 2. Generate Audio (AI Text-to-Speech)

**Endpoint:** `POST /api/v1/books/{book_id}/chapters/{chapter_id}/audio/generate`

**Purpose:** Generate audio narration using Google Cloud TTS

**Request Body:**

```json
{
  "text_source": "user_provided",
  "text_content": "Chapter content for narration...",
  "voice_settings": {
    "voice_name": "en-US-Neural2-A",
    "language_code": "en-US",
    "speaking_rate": 1.0,
    "pitch": 0.0,
    "volume_gain_db": 0.0
  },
  "language": "en"
}
```

**Request Fields:**
- `text_source`: "user_provided" (preferred) or "auto_extract"
- `text_content`: Text to narrate (required if text_source=user_provided)
- `voice_settings`: Voice configuration
- `language`: Target language for audio (for translations)

**Response:**

```json
{
  "success": true,
  "audio_url": "https://static.wordai.pro/audio/chapter_xxx.mp3",
  "audio_file_id": "file_abc123",
  "duration_seconds": 320,
  "file_size_bytes": 5242880,
  "points_deducted": 5,
  "voice_used": "en-US-Neural2-A",
  "message": "Audio generated successfully"
}
```

**Error Responses:**

`400 Bad Request` - Text too long:
```json
{
  "detail": "Text exceeds 5000 characters. Please shorten or split content."
}
```

`402 Payment Required` - Insufficient points:
```json
{
  "detail": "Not enough points. Need 5, have 2"
}
```

---

### 3. Upload Audio File

**Endpoint:** `POST /api/v1/books/{book_id}/chapters/{chapter_id}/audio/upload`

**Purpose:** Upload user-provided audio file

**Request:** Multipart form-data

```
audio_file: <binary audio file>
language: "en" (optional, for translations)
```

**Supported Formats:**
- MP3 (recommended)
- WAV
- M4A
- OGG

**Max Size:** 50MB

**Response:**

```json
{
  "success": true,
  "audio_url": "https://static.wordai.pro/audio/chapter_xxx.mp3",
  "audio_file_id": "file_abc123",
  "duration_seconds": 340,
  "file_size_bytes": 4567890,
  "format": "mp3",
  "points_deducted": 0,
  "message": "Audio uploaded successfully"
}
```

---

### 4. Get Chapter Audio

**Endpoint:** `GET /api/v1/books/{book_id}/chapters/{chapter_id}/audio?language={language_code}`

**Purpose:** Retrieve audio URL for playback (respects permissions)

**Query Parameters:**
- `language` (optional): Get audio for specific language version

**Response:**

```json
{
  "audio_available": true,
  "audio_url": "https://static.wordai.pro/audio/chapter_xxx.mp3",
  "duration_seconds": 320,
  "format": "mp3",
  "voice_settings": {
    "voice_name": "en-US-Neural2-A",
    "language_code": "en-US",
    "gender": "FEMALE"
  },
  "source_type": "ai_generated"
}
```

**Permission Logic:**
- Public chapter: Audio accessible to everyone
- Premium chapter: Audio only for owners/purchasers
- Check `is_preview_free`: If true, audio accessible in preview
- If user not authenticated: Return 401 for premium chapters

**Error Responses:**

`404 Not Found` - No audio:
```json
{
  "audio_available": false,
  "message": "No audio attached to this chapter"
}
```

`403 Forbidden` - Premium content:
```json
{
  "detail": "Purchase required to access audio"
}
```

---

### 5. Delete Chapter Audio

**Endpoint:** `DELETE /api/v1/books/{book_id}/chapters/{chapter_id}/audio?language={language_code}`

**Purpose:** Remove audio from chapter (keep in library as archived)

**Response:**

```json
{
  "success": true,
  "message": "Audio removed from chapter (archived in library)"
}
```

---

### 6. Preview Generated Audio (Before Saving)

**Endpoint:** `POST /api/v1/audio/preview`

**Purpose:** Generate preview audio without saving (no points cost)

**Request Body:**

```json
{
  "text_content": "Sample text to preview...",
  "voice_name": "en-US-Neural2-A",
  "language_code": "en-US"
}
```

**Response:**

```json
{
  "preview_url": "https://static.wordai.pro/audio/preview_temp_xxx.mp3",
  "duration_seconds": 15,
  "expires_at": "2024-12-05T10:15:00Z"
}
```

**Note:** Preview URL expires after 15 minutes, not saved to library

---

## Frontend Integration

### Audio Player Component

**Features:**
- Play/Pause button
- Progress bar with seek
- Playback speed control (0.5x, 1x, 1.5x, 2x)
- Volume control
- Show duration and current time
- Download button (for premium users)

**Player Placement:**
- Sticky player at top of chapter content
- Or floating player button (bottom-right corner)
- Minimizable when not in use

**Player States:**
- Loading: Show spinner while fetching audio
- Ready: Display play button
- Playing: Animated waveform/progress
- Paused: Static progress bar
- Error: Display error message with retry

---

### Audio Generation Modal

**Step 1: Choose Method**
- Radio buttons: "Upload Audio" or "Generate with AI"

**Step 2a: Upload Audio (if selected)**
- Drag-and-drop file zone
- File picker button
- Show file info: name, size, duration
- Preview player before upload
- Upload button

**Step 2b: Generate with AI (if selected)**
- **Text Source Selection:**
  - Radio: "Paste text manually" (recommended)
  - Radio: "Auto-extract from content"
- **Text Input:**
  - Large textarea for manual input
  - Character counter (max 5000)
  - Extract button (if auto-extract selected)
- **Voice Selection Dropdown:**
  - Group by language
  - Show voice name, gender, type (Neural2/Wavenet)
  - Sample audio preview button
- **Voice Settings (Advanced):**
  - Speaking rate slider (0.5x - 2.0x)
  - Pitch slider (-20 to +20)
  - Volume slider (-10dB to +10dB)
- **Preview Button:**
  - Generate 15-second preview
  - Play preview before committing
- **Generate & Save Button:**
  - Shows points cost (5 points)
  - Confirms generation

**Step 3: Confirmation**
- Show success message
- Display audio player
- "Add to another chapter" button
- "Close" button

---

### Voice Selection UI Example

```
┌─────────────────────────────────────────┐
│ Select Voice                             │
├─────────────────────────────────────────┤
│ Language: English (US)          [Filter]│
├─────────────────────────────────────────┤
│ ◉ en-US-Neural2-A (Female) [▶ Preview] │
│   Neural2 - High Quality                │
│                                          │
│ ○ en-US-Neural2-B (Male)   [▶ Preview] │
│   Neural2 - High Quality                │
│                                          │
│ ○ en-US-Wavenet-A (Female) [▶ Preview] │
│   Wavenet - Good Quality                │
│                                          │
│ ○ en-US-Wavenet-B (Male)   [▶ Preview] │
│   Wavenet - Good Quality                │
└─────────────────────────────────────────┘
```

---

## Community Books Integration

### Public Book Reader

**Audio Player Display:**
- Show audio player if chapter has audio
- Respect permission flags:
  - `is_published`: Chapter must be published
  - `is_preview_free`: Show audio in preview mode
  - Purchase status: Check if user purchased book

**Permission Logic:**

```python
def can_access_audio(chapter, book, user):
    # Owner always has access
    if user and user.id == book.user_id:
        return True

    # Public chapter with audio
    if chapter.is_published and book.is_published:
        # Free preview chapters
        if chapter.is_preview_free:
            return True

        # Premium chapters - check purchase
        if user:
            purchase = get_user_purchase(user.id, book.id)
            if purchase and purchase.status == "completed":
                return True

    return False
```

**UI Behavior:**
- Authenticated owner: Always show player
- Public chapter: Show player to everyone
- Preview chapter: Show player with "Purchase to unlock full book"
- Premium chapter (no purchase): Show locked icon "Purchase required"
- Premium chapter (purchased): Show full player

---

### Marketplace Book Preview

**Audio Preview Card:**
- Show audio icon if book has chapters with audio
- Display: "Includes audio narration" badge
- Sample audio player for preview chapters
- Encourage purchase: "Unlock audio for all chapters"

**Sample Implementation:**

```
┌──────────────────────────────────────┐
│ 📖 Book Title                         │
│ by Author Name                        │
├──────────────────────────────────────┤
│ 🎧 Includes Audio Narration          │
│                                       │
│ Preview Chapter 1:                    │
│ ▶ Listen to audio (3:45)             │
│                                       │
│ 💎 Purchase to unlock audio for      │
│    all 12 chapters                    │
└──────────────────────────────────────┘
```

---

## Implementation Phases

### Phase 1: Core Audio Infrastructure (Week 1-2)

**Backend:**
- Database schema for `audio_config` and `audio_translations`
- R2 audio file upload service
- Audio library integration (user_files collection)
- Basic API endpoints: upload, get, delete

**Frontend:**
- Audio player component
- Upload modal UI
- Chapter settings audio tab

**Testing:**
- Upload MP3 files
- Play audio in chapter reader
- Delete audio files

---

### Phase 2: Google Cloud TTS Integration (Week 2-3)

**Backend:**
- Google Cloud TTS service integration
- Voice fetching endpoint
- Text extraction from HTML
- Audio generation endpoint
- Points deduction system

**Frontend:**
- Voice selection UI
- Text input modal
- Preview functionality
- Generation progress indicator

**Testing:**
- Generate audio with various voices
- Test all supported languages
- Verify points deduction

---

### Phase 3: Multi-Language Audio (Week 3-4)

**Backend:**
- Audio per translation support
- Language-specific voice selection
- Translation audio synchronization

**Frontend:**
- Language switcher with audio
- Audio indicator per language
- Bulk generate for all languages

**Testing:**
- Generate audio for Vietnamese, English, Chinese
- Switch languages and verify audio changes
- Test audio fallback behavior

---

### Phase 4: Public Access & Permissions (Week 4-5)

**Backend:**
- Permission checking for audio access
- Public/premium audio logic
- Preview mode audio handling

**Frontend:**
- Locked audio UI for premium chapters
- Preview audio player
- Purchase prompt integration

**Testing:**
- Test public vs premium audio access
- Verify purchase unlocks audio
- Test preview chapter audio

---

### Phase 5: Advanced Features (Week 5-6)

**Backend:**
- Audio analytics (play count, duration)
- Batch audio generation for book
- Audio quality optimization

**Frontend:**
- Playback speed controls
- Audio download (for premium)
- Audio waveform visualization
- Auto-play next chapter

**Testing:**
- Test playback controls
- Test batch generation
- Performance testing with large books

---

## Technical Considerations

### Audio File Storage

**Cloudflare R2 Structure:**

```
wordai/
  audio/
    users/
      {user_id}/
        chapters/
          {chapter_id}_{language}_{timestamp}.mp3
    previews/
      temp_{uuid}.mp3 (15min expiry)
```

**Implementation Details:**
- Use `R2StorageService` for all uploads
- Use `LibraryManager` to create file records in `library_files`
- Set `category="audio"` for all audio files
- Use `linked_to` metadata to associate with books/chapters

**CDN Optimization:**
- Cache audio files aggressively (1 year)
- Use range requests for streaming
- Enable compression for smaller files

---

### Audio Format Recommendations

**Primary Format: MP3**
- Best browser compatibility
- Good compression (128-192 kbps)
- Smaller file sizes

**Secondary Format: OGG Vorbis**
- Better quality at same bitrate
- Open source codec
- Fallback for modern browsers

**Upload Support:**
- Accept: MP3, WAV, M4A, OGG
- Convert WAV to MP3 on server
- Normalize audio volume

---

### Text-to-Speech Optimization

**Character Splitting:**
- Google TTS limit: 5000 chars per request
- For long chapters: Split into segments
- Concatenate audio files seamlessly
- Add 0.5s silence between segments

**Voice Caching:**
- Cache voice list for 24 hours
- Reduce API calls to Google
- Update cache daily

**Cost Optimization:**
- Prefer user-provided text over auto-extract
- Use Neural2 voices (best quality-price ratio)
- Batch generate multiple chapters
- Offer voice preview without points cost

---

### Performance Metrics

**Audio Generation Time:**
- Text extraction: <1 second
- TTS generation: 2-5 seconds per 1000 characters
- R2 upload: 1-2 seconds
- Total: ~10-20 seconds per chapter

**Audio Streaming:**
- Use HTTP range requests
- Start playback before full download
- Prefetch next chapter audio
- Cache in browser for replay

---

## Points Cost Summary

| Action | Points Cost | Notes |
|--------|-------------|-------|
| Generate Audio (Neural2) | 5 points | High quality, recommended |
| Generate Audio (Wavenet) | 3 points | Good quality, fallback |
| Generate Audio (Standard) | 2 points | Basic quality, budget |
| Upload Audio | 0 points | FREE, encourage user uploads |
| Preview Audio (15s) | 0 points | FREE, no commitment |
| Regenerate Audio | Same as initial | Change voice and regenerate |
| Delete Audio | 0 points | Keep in library as archived |

**Bulk Discount:**
- Generate 10+ chapters: 10% discount
- Generate entire book: 20% discount
- Example: 25 chapters × 5 points × 0.8 = 100 points

---

## Security & Privacy

**Audio Access Control:**
- Verify user authentication for premium content
- Check purchase status before serving audio
- Use signed URLs with expiration (1 hour)
- Rate limit audio generation (10 per hour per user)

**Content Moderation:**
- Check text content for inappropriate content
- Validate uploaded audio files (malware scan)
- Monitor API usage for abuse

**Data Privacy:**
- Audio files linked to user_id
- Allow users to delete audio permanently
- GDPR compliance: Export/delete user audio data

---

## Error Handling

**Common Errors:**

1. **Text Too Long**
   - Limit: 5000 characters
   - Solution: Split into multiple requests
   - UI: Show character counter

2. **Insufficient Points**
   - Check points before generation
   - Show clear pricing before action
   - Prompt user to purchase points

3. **API Rate Limit**
   - Google TTS: 600 requests/minute
   - Implement queue system
   - Show "Audio generation in progress" message

4. **Audio Upload Failed**
   - Validate file format before upload
   - Check file size (<50MB)
   - Retry upload with exponential backoff

5. **Voice Not Available**
   - Fallback to default voice for language
   - Show warning to user
   - Suggest alternative voices

---

## Monitoring & Analytics

**Track Metrics:**
- Audio generation count per day
- Most popular voices
- Audio play count per chapter
- Average audio duration
- Points spent on audio generation
- Upload vs AI-generated ratio

**Alerts:**
- High API error rate (>5%)
- TTS API quota exceeded
- R2 storage approaching limit
- Unusual audio generation patterns

---

## Future Enhancements

**Phase 6+ Ideas:**

1. **Advanced Voice Cloning**
   - Upload voice sample
   - Clone user's voice for narration
   - Premium feature: 50 points

2. **Multi-Voice Narration**
   - Different voices for dialogue
   - Character voice assignment
   - Automatic speaker detection

3. **Audio Effects**
   - Background music
   - Sound effects for scenes
   - Ambient noise (rain, cafe, etc.)

4. **Synchronized Text Highlighting**
   - Highlight text as audio plays
   - Karaoke-style word highlighting
   - Improve reading comprehension

5. **Podcast-Style Chapters**
   - Add intro/outro music
   - Chapter summaries
   - Author commentary

6. **Offline Audio Download**
   - Download for offline reading
   - Mobile app integration
   - Background playback

7. **Audio Translation**
   - Auto-translate audio to other languages
   - Preserve voice characteristics
   - Cross-language narration

---

## Conclusion

This audio narration feature significantly enhances the book reading experience on WordAI platform. By offering both user-uploaded audio and AI-generated text-to-speech with Google Cloud TTS, users have flexibility in how they create audio content. The integration with the existing translation system ensures audio is available across all supported languages, making books more accessible to a global audience.

**Key Benefits:**
- ✅ Accessibility: Audio narration for visually impaired users
- ✅ Multi-tasking: Listen while driving, exercising, cooking
- ✅ Language Learning: Hear pronunciation in foreign languages
- ✅ Premium Value: Audio adds value to premium books
- ✅ Monetization: Audio generation costs points, drives revenue
- ✅ User Engagement: Longer session times with audio playback

**Implementation Priority:**
1. Core audio upload/playback (MVP)
2. Google TTS integration (Key differentiator)
3. Multi-language support (Scale)
4. Public access permissions (Monetization)
5. Advanced features (Retention)

**Estimated Timeline:** 5-6 weeks for full implementation
**Estimated Development Cost:** 200-250 hours
**Expected ROI:** 30% increase in premium book purchases, 50% increase in user engagement time

---

## Implementation Checklist

### Phase 1: Core Audio Infrastructure ✅ COMPLETED (2025-12-05)

**Backend:** ✅ ALL DONE
- [x] Update `book_chapter_models.py` with `audio_config` and `audio_translations` fields
- [x] Create `AudioConfig`, `AudioVoiceSettings`, `AudioUploadRequest` Pydantic models
- [x] Create `src/services/audio_service.py` with upload, storage, and retrieval functions
- [x] Create `src/api/book_chapter_audio_routes.py` with POST/GET/DELETE endpoints
- [x] Update `LibraryManager` to handle audio files with `category="audio"`
- [x] Add `R2StorageService.upload_file()` async method for direct uploads
- [x] Add database indexes for audio queries (`migrate_add_audio_support.py`)
- [x] Register audio routes in `app.py`

**Indexes Created:**
- `book_chapters.audio_config.enabled` - Find chapters with audio
- `book_chapters.audio_config.audio_file_id` - Link to library
- `book_chapters.audio_translations` - Per-language audio lookup
- `library_files.user_id + file_type + category` - User's audio files
- `library_files.user_id + linked_to.chapter_id` - Chapter-specific audio
- `library_files.user_id + linked_to.book_id + category` - Book audio files

**Frontend:**
- [ ] Audio player component
- [ ] Upload modal UI
- [ ] Chapter settings audio tab

**Testing:**
- [ ] Upload MP3 files
- [ ] Play audio in chapter reader
- [ ] Delete audio files

---

### Phase 2: Google Cloud TTS Integration ✅ COMPLETED (2025-12-05)

**Backend:** ✅ ALL DONE
- [x] Google Gemini TTS service integration with API key auth
- [x] Voice fetching endpoint (GET /audio/voices) - 7 Vietnamese voices
- [x] Text extraction from HTML (BeautifulSoup)
- [x] Audio generation endpoint (POST /audio/generate)
- [x] Points deduction system (2 points per chapter)
- [x] Support both flash and pro models (gemini-2.5-flash-preview-tts, gemini-2.5-pro-preview-tts)

**Vietnamese Voices Available:**
- **Female:** Despina, Gacrux, Leda, Sulafat
- **Male:** Enceladus, Orus, Alnilam

**Models:**
- `gemini-2.5-flash-preview-tts`: Fast, lower cost
- `gemini-2.5-pro-preview-tts`: Higher quality, premium

**Frontend:**
- [ ] Voice selection UI
- [ ] Model selection (flash/pro)
- [ ] Text input modal
- [ ] Preview functionality
- [ ] Generation progress indicator

**Testing:**
- [x] Generate audio with all 7 Vietnamese voices
- [x] Test both flash and pro models
- [x] Verify audio quality (WAV format, 24kHz)
- [ ] Verify points deduction

---

### Phase 3: Multi-Language Audio ⏳ NEXT

**Backend:**
- [ ] Audio per translation support
- [ ] Language-specific voice selection
- [ ] Translation audio synchronization

**Frontend:**
- [ ] Language switcher with audio
- [ ] Audio indicator per language
- [ ] Bulk generate for all languages

**Testing:**
- [ ] Generate audio for Vietnamese, English, Chinese
- [ ] Switch languages and verify audio changes
- [ ] Test audio fallback behavior

---

### Phase 4: Public Access & Permissions ⏳ PENDING

**Backend:**
- [ ] Permission checking for audio access
- [ ] Public/premium audio logic
- [ ] Preview mode audio handling
- [ ] Community user audio generation (save to user's library)

**Frontend:**
- [ ] Locked audio UI for premium chapters
- [ ] Preview audio player
- [ ] Purchase prompt integration
- [ ] "Generate Audio" button for community users

**Testing:**
- [ ] Test public vs premium audio access
- [ ] Verify purchase unlocks audio
- [ ] Test preview chapter audio
- [ ] Test community user audio generation and persistence

---

### Phase 5: Advanced Features ⏳ PENDING

**Backend:**
- [ ] Audio analytics (play count, duration)
- [ ] Batch audio generation for book
- [ ] Audio quality optimization

**Frontend:**
- [ ] Playback speed controls
- [ ] Audio download (for premium)
- [ ] Audio waveform visualization
- [ ] Auto-play next chapter

**Testing:**
- [ ] Test playback controls
- [ ] Test batch generation
- [ ] Performance testing with large books
