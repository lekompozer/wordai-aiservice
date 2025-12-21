# Slide Subtitles & Audio Generation System

## 📖 Overview

Hệ thống tự động tạo **subtitles** (phụ đề có timestamp) và **audio narration** cho toàn bộ slides presentation. Hỗ trợ 2 chế độ:

1. **Presentation Mode** - Giọng nói ngắn gọn, súc tích cho thuyết trình
2. **Academy Mode** - Giọng nói chi tiết, giải thích sâu cho giảng dạy

### 🎯 Key Features

- ✅ AI phân tích toàn bộ slides để tạo narration mạch lạc
- ✅ Subtitles có timestamp chính xác (giây)
- ✅ Audio TTS (Text-to-Speech) đồng bộ với subtitles
- ✅ Auto-transition animations dựa trên timing
- ✅ 2 modes: Presentation (ngắn) vs Academy (dài)

---

## 🏗️ System Architecture (2-Step Flow)

```
┌─────────────────────────────────────────────────────────────────┐
│              SLIDE NARRATION PIPELINE (2-STEP PROCESS)           │
└─────────────────────────────────────────────────────────────────┘

STEP 1: GENERATE SUBTITLES (Endpoint 1)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1️⃣ INPUT
   ├─ All Slides Content (HTML + Elements + Background)
   ├─ Presentation Metadata (Title, Topic)
   ├─ Mode Selection (Presentation / Academy)
   ├─ User Query (e.g., "Focus on technical details")
   └─ Language (vi/en/zh)

2️⃣ AI ANALYSIS (Gemini 3 Pro)
   ├─ Analyze slide overview + elements + flow
   ├─ Generate coherent narration script
   ├─ Calculate timestamps based on speaking rate
   └─ Output: Subtitles JSON with timestamps

3️⃣ SAVE TO DATABASE (Version 1)
   ├─ Save subtitles to MongoDB
   ├─ Link to presentation_id
   ├─ Store version metadata
   └─ Return subtitles for user preview

4️⃣ USER PREVIEW & APPROVAL
   ├─ Frontend displays subtitles with timing
   ├─ User can edit/adjust if needed
   └─ User clicks "Generate Audio" when ready

STEP 2: GENERATE AUDIO (Endpoint 2)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
5️⃣ AUDIO CONFIGURATION
   ├─ User selects voice provider (Google/ElevenLabs)
   ├─ User selects voices (multiple for different speakers)
   ├─ User adjusts speaking rate if needed
   └─ Submit audio generation request

6️⃣ TTS GENERATION (Google Cloud TTS / Gemini Audio)
   ├─ Use SAME flow as Listening Test
   ├─ Convert subtitles to multi-speaker script
   ├─ Generate audio with voice assignments
   ├─ Upload to library_audio collection (R2)
   └─ Return audio URLs

7️⃣ SAVE TO DATABASE (Version Update)
   ├─ Update narration record with audio URLs
   ├─ Calculate actual audio duration
   ├─ Generate animation timing metadata
   └─ Mark version as "completed"

8️⃣ OUTPUT
   ├─ Subtitles JSON (with timestamps)
   ├─ Audio files (MP3 in library_audio)
   ├─ Animation metadata (slide transitions)
   └─ Total presentation duration
```

### 🔄 Flow Comparison: Listening Test vs Slide Narration

| Step | Listening Test | Slide Narration |
|------|----------------|-----------------|
| **Input** | Topic + Questions | Slides Content + Elements + Mode |
| **Step 1** | Generate script + questions | Generate subtitles from slides |
| **Storage** | Save script to `listening_tests` | Save subtitles to `slide_narrations` |
| **User Review** | Preview script | Preview subtitles + edit |
| **Step 2** | Generate multi-speaker audio | Generate multi-speaker audio (SAME) |
| **Audio API** | Google TTS Multi-Speaker | Google TTS Multi-Speaker (SAME) |
| **Storage** | Upload to `library_audio` | Upload to `library_audio` (SAME) |
| **Output** | Test + Audio URLs | Subtitles + Audio + Animations |

**Key Insight:** Step 2 (Audio Generation) is IDENTICAL to Listening Test flow!

---

## 📊 Data Models

### Subtitle Entry

```typescript
interface SubtitleEntry {
  slide_index: number;           // Slide index (0-based)
  subtitle_index: number;         // Subtitle sequence in slide
  start_time: number;             // Start time in seconds (e.g., 0.5)
  end_time: number;               // End time in seconds (e.g., 3.2)
  duration: number;               // Duration = end_time - start_time
  text: string;                   // Narration text
  speaker_index?: number;         // Speaker assignment (0, 1, 2...)
  element_references?: string[];  // Element IDs mentioned (e.g., ["shape_1", "icon_2"])
}
```

### Slide Narration Response

```typescript
interface SlideNarrationResponse {
  narration_id: string;           // Narration record ID
  presentation_id: string;
  version: number;                // Version number (1, 2, 3...)
  status: "pending" | "subtitles_ready" | "audio_ready" | "completed";
  mode: "presentation" | "academy";
  total_duration: number;         // Total presentation time (seconds)
  slides: SlideNarration[];
  audio_files?: AudioFile[];      // Only present after Step 2
  processing_time_ms: number;
  points_deducted: number;
}

interface SlideNarration {
  slide_index: number;
  slide_duration: number;         // Total duration for this slide
  subtitles: SubtitleEntry[];     // Array of subtitle entries
  audio_url: string;              // URL to generated audio file
  auto_advance: boolean;          // Auto-transition to next slide
  transition_delay: number;       // Delay before transition (seconds)
}

interface AudioFile {
  slide_index: number;
  audio_url: string;              // R2 URL
  file_size: number;              // File size in bytes
  format: "mp3" | "wav";
  duration: number;               // Audio duration
}
```

---

## 🤖 AI Prompt Design

### Step 1: Generate Narration Script

**Input to Gemini 3 Pro:**

```python
def build_narration_prompt(slides: List[Slide], mode: str, metadata: Dict) -> str:
    """
    Build AI prompt for generating narration with timestamps

    Args:
        slides: All slides with content
        mode: "presentation" or "academy"
        metadata: Presentation title, topic, author
    """

    # Extract slide overview WITH element details
    slide_overview = []
    for idx, slide in enumerate(slides):
        # Include element types and positions for context
        element_details = []
        for elem in slide.elements:
            element_details.append({
                "id": elem.id,
                "type": elem.type,  # shape, image, icon, text
                "position": elem.position,
                "description": elem.properties.get("description", ""),
            })

        overview = {
            "index": idx,
            "html": slide.html,
            "elements": element_details,  # Now includes full element context
            "background_type": slide.background.type if slide.background else None,
        }
        slide_overview.append(overview)

    # Mode-specific instructions
    if mode == "presentation":
        style_instructions = """
        PRESENTATION MODE:
        - Concise and engaging narration (30-60 seconds per slide)
        - Focus on key points only
        - Professional presentation tone
        - Clear transitions between slides
        - Assume audience is viewing slides simultaneously
        """
    else:  # academy
        style_instructions = """
        ACADEMY MODE:
        - Detailed explanatory narration (60-180 seconds per slide)
        - Explain concepts thoroughly
        - Teaching/instructional tone
        - Provide examples and context
        - Assume audience is learning new material
        """

    prompt = f"""You are an expert presentation narrator. Generate natural, engaging narration with accurate timestamps for this presentation.

PRESENTATION OVERVIEW:
Title: {metadata['title']}
Topic: {metadata['topic']}
Total Slides: {len(slides)}
Language: {metadata['language']}
User Requirements: {metadata['user_query']}

SLIDES CONTENT (Including Visual Elements):
{json.dumps(slide_overview, indent=2, ensure_ascii=False)}

{style_instructions}

IMPORTANT - Element References:
- When narrating, REFERENCE visual elements when appropriate
- Example: "As you can see in the diagram on the left..." (for shape/image)
- Example: "Notice the three icons representing..." (for icons)
- Include element_references array in subtitle JSON for animation sync

TIMING GUIDELINES:
- Speaking rate: ~150 words per minute (natural pace)
- Pause between sentences: 0.3-0.5 seconds
- Pause between paragraphs: 0.8-1.0 seconds
- Transition to next slide: 1.5-2.0 seconds

OUTPUT FORMAT (JSON):
{{
  "narration": [
    {{
      "slide_index": 0,
      "subtitles": [
        {{
          "start_time": 0.0,
          "end_time": 3.5,
          "text": "Welcome to this presentation on advanced data structures."
        }},
        {{
          "start_time": 4.0,
          "end_time": 8.2,
          "text": "Today we'll explore how hash tables enable O(1) lookup performance."
        }}
      ]
    }},
    {{
      "slide_index": 1,
      "subtitles": [...]
    }}
  ]
}}

REQUIREMENTS:
1. Create coherent narration that flows naturally across all slides
2. Calculate accurate start_time and end_time based on text length
3. Add natural pauses between sentences and slides
4. Ensure timestamps don't overlap
5. Match narration style to mode (presentation vs academy)
6. Make content engaging and easy to follow
7. Reference visual elements when appropriate (e.g., "As you can see in this diagram...")

Generate the complete narration now:"""

    return prompt
```

### Example AI Response

```json
{
  "narration": [
    {
      "slide_index": 0,
      "subtitles": [
        {
          "start_time": 0.0,
          "end_time": 3.5,
          "text": "Welcome everyone to today's presentation on Machine Learning fundamentals."
        },
        {
          "start_time": 4.0,
          "end_time": 7.8,
          "text": "Over the next few minutes, we'll explore the core concepts that power modern AI."
        },
        {
          "start_time": 8.5,
          "end_time": 11.2,
          "text": "Let's dive right in."
        }
      ]
    },
    {
      "slide_index": 1,
      "subtitles": [
        {
          "start_time": 0.0,
          "end_time": 4.2,
          "text": "Machine learning is fundamentally about teaching computers to learn from data."
        },
        {
          "start_time": 4.8,
          "end_time": 9.5,
          "text": "Instead of programming explicit rules, we provide examples and let algorithms discover patterns."
        }
      ]
    }
  ]
}
```

---

## 🔊 Audio Generation

### TTS Provider Selection

| Provider | Pros | Cons | Use Case |
|----------|------|------|----------|
| **Google Cloud TTS** | ✅ Cheap ($4/1M chars)<br>✅ Good quality<br>✅ Multiple languages | ❌ Less natural | Presentation mode |
| **ElevenLabs** | ✅ Very natural voices<br>✅ Emotion/tone control<br>✅ Cloning support | ❌ Expensive ($0.30/1K chars)<br>❌ Slower | Academy mode (premium) |
| **OpenAI TTS** | ✅ Natural voices<br>✅ Good quality<br>✅ Fast | ❌ Medium cost ($15/1M chars) | Both modes |

**Recommendation:** Start with **Google Cloud TTS** for MVP, add ElevenLabs as premium option.

### Audio Generation Flow

```python
async def generate_slide_audio(
    slide_index: int,
    subtitles: List[SubtitleEntry],
    voice_config: Dict,
) -> str:
    """
    Generate audio for a single slide from subtitles

    Returns:
        R2 URL to audio file
    """
    # 1. Combine all subtitle texts for this slide
    full_text = " ".join([sub.text for sub in subtitles])

    # 2. Calculate timing markers (SSML for pauses)
    ssml_text = build_ssml_with_timing(subtitles)

    # 3. Call TTS API
    audio_data = await tts_client.synthesize(
        text=ssml_text,
        voice=voice_config["voice_name"],
        language=voice_config["language"],
        speaking_rate=voice_config.get("rate", 1.0),
    )

    # 4. Upload to R2
    audio_key = f"presentations/{presentation_id}/audio/slide_{slide_index}.mp3"
    audio_url = await upload_to_r2(audio_data, audio_key, content_type="audio/mpeg")

    return audio_url


def build_ssml_with_timing(subtitles: List[SubtitleEntry]) -> str:
    """
    Build SSML with precise timing markers

    SSML (Speech Synthesis Markup Language) allows controlling:
    - Pauses: <break time="500ms"/>
    - Emphasis: <emphasis level="strong">important</emphasis>
    - Rate: <prosody rate="slow">slower speech</prosody>
    """
    ssml_parts = ['<speak>']

    for idx, subtitle in enumerate(subtitles):
        # Add text
        ssml_parts.append(subtitle.text)

        # Add pause before next subtitle
        if idx < len(subtitles) - 1:
            next_sub = subtitles[idx + 1]
            pause_duration = int((next_sub.start_time - subtitle.end_time) * 1000)
            if pause_duration > 0:
                ssml_parts.append(f'<break time="{pause_duration}ms"/>')

    ssml_parts.append('</speak>')
    return ''.join(ssml_parts)
```

### Voice Configuration

```python
# Voice presets for different modes
VOICE_CONFIGS = {
    "presentation": {
        "google": {
            "voice_name": "en-US-Neural2-J",  # Professional male
            "language": "en-US",
            "rate": 1.1,  # Slightly faster for engagement
            "pitch": 0,
        },
        "vietnamese": {
            "voice_name": "vi-VN-Neural2-A",  # Clear female
            "language": "vi-VN",
            "rate": 1.0,
            "pitch": 0,
        }
    },
    "academy": {
        "google": {
            "voice_name": "en-US-Neural2-F",  # Warm female teacher
            "language": "en-US",
            "rate": 0.95,  # Slower for clarity
            "pitch": 0,
        },
        "vietnamese": {
            "voice_name": "vi-VN-Neural2-D",  # Patient male teacher
            "language": "vi-VN",
            "rate": 0.9,  # Slower for teaching
            "pitch": 0,
        }
    }
}
```

---

## ⏱️ Slide Timing & Animation System

### Calculate Slide Duration

```python
def calculate_slide_timing(subtitles: List[SubtitleEntry]) -> Dict:
    """
    Calculate total duration and transition timing for a slide

    Returns:
        {
            "total_duration": float,  # Total time for this slide
            "auto_advance": bool,      # Should auto-advance to next slide
            "transition_delay": float, # Delay before transition (for final pause)
        }
    """
    if not subtitles:
        return {
            "total_duration": 5.0,  # Default 5 seconds for empty slides
            "auto_advance": True,
            "transition_delay": 1.0,
        }

    # Get last subtitle's end time
    last_subtitle = max(subtitles, key=lambda s: s.end_time)
    content_duration = last_subtitle.end_time

    # Add buffer time for final pause and transition
    transition_buffer = 2.0  # 2 seconds pause before next slide

    total_duration = content_duration + transition_buffer

    return {
        "total_duration": total_duration,
        "auto_advance": True,
        "transition_delay": transition_buffer,
    }
```

### Auto-Transition Animations

```typescript
interface SlideTransition {
  slide_index: number;
  transition_type: "fade" | "slide" | "zoom";
  duration: number;              // Transition animation duration (0.5s)
  trigger_time: number;          // When to trigger (slide_duration - transition_delay)
}

// Example: Calculate transitions for all slides
function calculatePresentationTransitions(
  slides: SlideNarration[]
): SlideTransition[] {
  const transitions: SlideTransition[] = [];

  for (let i = 0; i < slides.length - 1; i++) {
    const slide = slides[i];

    transitions.push({
      slide_index: i,
      transition_type: "fade",
      duration: 0.5,
      trigger_time: slide.slide_duration - slide.transition_delay,
    });
  }

  return transitions;
}
```

### Frontend Animation Control

```typescript
// Auto-play presentation with synchronized audio and transitions
class PresentationPlayer {
  private currentSlide = 0;
  private audioElement: HTMLAudioElement;
  private subtitleInterval: NodeJS.Timeout;

  async playPresentation(narration: SlideNarrationResponse) {
    for (const slide of narration.slides) {
      // 1. Show slide
      this.showSlide(slide.slide_index);

      // 2. Load and play audio
      this.audioElement.src = slide.audio_url;
      await this.audioElement.play();

      // 3. Start subtitle display
      this.displaySubtitles(slide.subtitles);

      // 4. Wait for slide duration
      await this.waitForDuration(slide.slide_duration);

      // 5. Transition to next slide
      if (slide.auto_advance) {
        await this.transitionToNextSlide();
      }
    }
  }

  displaySubtitles(subtitles: SubtitleEntry[]) {
    let currentSubIndex = 0;
    const startTime = Date.now();

    this.subtitleInterval = setInterval(() => {
      const elapsed = (Date.now() - startTime) / 1000;

      // Find current subtitle based on elapsed time
      const currentSub = subtitles.find(
        sub => sub.start_time <= elapsed && elapsed <= sub.end_time
      );

      if (currentSub) {
        this.showSubtitle(currentSub.text);
      } else {
        this.hideSubtitle();
      }
    }, 100); // Check every 100ms
  }

  async transitionToNextSlide() {
    // Fade out current slide
    await this.animateSlide('fadeOut', 500);

    // Move to next
    this.currentSlide++;

    // Fade in next slide
    await this.animateSlide('fadeIn', 500);
  }
}
```

---

## 🚀 API Endpoints (2-Step Process)

### Step 1: Generate Subtitles Only

```
POST /api/presentations/{presentation_id}/narration/generate-subtitles
```

**Request:**

```json
{
  "mode": "presentation",
  "language": "vi",
  "user_query": "Focus on technical details and use simple examples",
  "custom_instructions": "Emphasize practical applications"
}
```

**Response:**

```json
{
  "success": true,
  "narration_id": "narr_12345",
  "presentation_id": "pres_67890",
  "version": 1,
  "status": "subtitles_ready",
  "mode": "presentation",
  "total_duration": 245.5,
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
          "text": "Chào mừng các bạn đến với bài thuyết trình về Machine Learning.",
          "speaker_index": 0,
          "element_references": []
        },
        {
          "subtitle_index": 1,
          "start_time": 4.0,
          "end_time": 8.2,
          "duration": 4.2,
          "text": "Như bạn thấy trong biểu đồ bên trái, neural networks bao gồm nhiều layers.",
          "speaker_index": 0,
          "element_references": ["shape_diagram_1"]
        }
      ],
      "auto_advance": true,
      "transition_delay": 2.0
    }
  ],
  "processing_time_ms": 8450,
  "points_deducted": 3
}
```

---

### Step 2: Generate Audio from Subtitles

```
POST /api/presentations/{presentation_id}/narration/{narration_id}/generate-audio
```

**Request:**

```json
{
  "voice_provider": "google",
  "voice_config": {
    "voices": [
      {
        "speaker_index": 0,
        "voice_name": "vi-VN-Neural2-A",
        "language": "vi-VN",
        "speaking_rate": 1.0
      }
    ],
    "use_pro_model": true
  }
}
```

**Response:**

```json
{
  "success": true,
  "narration_id": "narr_12345",
  "version": 1,
  "status": "completed",
  "audio_files": [
    {
      "slide_index": 0,
      "audio_url": "https://r2.wordai.vn/library_audio/narr_12345_slide_0_v1.mp3",
      "file_size": 245678,
      "format": "mp3",
      "duration": 15.5,
      "speaker_count": 1
    }
  ],
  "total_audio_duration": 245.5,
  "processing_time_ms": 18200,
  "points_deducted": 10
}
```

---

### Get Narration Details

```
GET /api/presentations/{presentation_id}/narration/{narration_id}
```

**Response:**

```json
{
  "narration_id": "narr_12345",
  "presentation_id": "pres_67890",
  "version": 1,
  "status": "completed",
  "mode": "presentation",
  "language": "vi",
  "user_query": "Focus on technical details",
  "slides": [...],
  "audio_files": [...],
  "created_at": "2024-12-21T10:00:00Z",
  "updated_at": "2024-12-21T10:05:30Z",
  "total_points": 13
}
```

---

### List Narration Versions

```
GET /api/presentations/{presentation_id}/narrations
```

**Response:**

```json
{
  "narrations": [
    {
      "narration_id": "narr_12345",
      "version": 1,
      "status": "completed",
      "mode": "presentation",
      "created_at": "2024-12-21T10:00:00Z",
      "total_duration": 245.5
    },
    {
      "narration_id": "narr_12346",
      "version": 2,
      "status": "subtitles_ready",
      "mode": "academy",
      "created_at": "2024-12-21T11:30:00Z",
      "total_duration": 480.0
    }
  ]
}
```

---

## 💰 Pricing Model (Unified 2-Point Pricing)

### Points Cost Calculation

```python
def calculate_narration_points(step: str) -> int:
    """
    Calculate points cost for narration generation

    UNIFIED PRICING: Both steps cost 2 points each

    STEP 1 - Subtitles: 2 points
    - AI narration generation (Gemini 3 Pro)
    - Timestamp calculation
    - Element context analysis

    STEP 2 - Audio: 2 points
    - TTS audio generation (Google/ElevenLabs)
    - Multi-speaker support
    - Upload to library_audio
    """
    return 2  # Both steps: 2 points each


# Examples:
# ─────────────────────────────────────────────────────

# Step 1 (subtitles): 2 points
# Step 2 (audio):     2 points
# TOTAL:              4 points

# User can:
# - Generate subtitles only (2 points) → preview → decide
# - Generate audio later (2 points) → total 4 points
```

### Pricing Summary

| Step | Cost | Total |
|------|------|-------|
| **Step 1: Subtitles** | 2 pts | 2 pts |
| **Step 2: Audio** | 2 pts | 4 pts |

**Advantage:** Simple, predictable pricing. User can preview subtitles for 2 points before committing to audio generation.

---## 🔧 Implementation Plan

### Phase 1: Subtitles Generation (Week 1) - Step 1 Only

**Backend:**
- [ ] Create `src/services/slide_narration_service.py`
- [ ] Implement Gemini prompt with element context
- [ ] Add subtitle timestamp calculation
- [ ] Create MongoDB schema: `slide_narrations` collection
- [ ] Add API endpoint: `POST /api/presentations/{id}/narration/generate-subtitles`
- [ ] Points integration (Step 1 cost: 2 points)
- [ ] Version management system

**Frontend:**
- [ ] Subtitle generation modal with mode selection
- [ ] User query input field
- [ ] Subtitle preview component with timestamps
- [ ] Edit subtitle functionality
- [ ] "Generate Audio" button (triggers Step 2)

### Phase 2: Audio Generation (Week 2) - Step 2 Implementation

**Backend:**
- [ ] Reuse `GoogleTTSService` from Listening Test
- [ ] Convert subtitles to multi-speaker script format
- [ ] Add API endpoint: `POST /api/presentations/{id}/narration/{narration_id}/generate-audio`
- [ ] Upload audio to `library_audio` collection (R2)
- [ ] Update narration record with audio URLs
- [ ] Points integration (Step 2 cost: 2 points)

**Frontend:**
- [ ] Voice configuration modal
- [ ] Voice selection per speaker
- [ ] Speaking rate adjustment slider
- [ ] Audio preview player
- [ ] Download audio files button

### Phase 3: Animation Sync (Week 3)

**Backend:**
- [ ] Calculate slide durations from actual audio
- [ ] Generate transition timing metadata
- [ ] Generate element reveal animations based on `element_references`
- [ ] Add animation data to narration record

**Frontend:**
- [ ] Presentation player component
- [ ] Auto-advance slide transitions
- [ ] Subtitle overlay display (synchronized)
- [ ] Element reveal animations on mention
- [ ] Playback controls (play, pause, seek, speed)

### Phase 4: Version Management & Polish (Week 4)

**Backend:**
- [ ] List all narration versions endpoint
- [ ] Delete narration version endpoint
- [ ] Set active narration version
- [ ] Regenerate subtitles with edits
- [ ] Export presentation as MP4 (optional)

**Frontend:**
- [ ] Narration version selector
- [ ] Compare versions side-by-side
- [ ] Batch export (all slides as ZIP)
- [ ] Analytics dashboard (playback stats)

---

## 🔄 Code Reuse from Listening Test

### Services to Reuse (100% Compatible)

```python
# 1. GoogleTTSService - Multi-speaker audio generation
from src.services.google_tts_service import GoogleTTSService

# Example usage (SAME as Listening Test):
tts_service = GoogleTTSService()

# Convert subtitles to script format
script = {
    "speaker_roles": ["Narrator"],
    "lines": [
        {"speaker": 0, "text": "Welcome to this presentation."},
        {"speaker": 0, "text": "Today we'll learn about AI."},
    ]
}

audio_bytes, metadata = await tts_service.generate_multi_speaker_audio(
    script=script,
    voice_names=["vi-VN-Neural2-A"],
    language="vi-VN",
    speaking_rate=1.0,
    use_pro_model=True,
)

# Upload to library_audio (SAME collection as Listening Test)
from src.services.library_audio_service import LibraryAudioService

audio_service = LibraryAudioService()
audio_record = await audio_service.upload_audio(
    user_id=user_id,
    audio_bytes=audio_bytes,
    file_name=f"narr_{narration_id}_slide_{slide_index}_v{version}.mp3",
    source_type="slide_narration",  # NEW source type
    source_id=narration_id,
    metadata={
        "voice_provider": "google",
        "voice_name": "vi-VN-Neural2-A",
        "language": "vi-VN",
        "duration_seconds": metadata["duration_seconds"],
    }
)
```

### Database Collections to Reuse

- ✅ `library_audio` - Audio file storage (add `source_type: "slide_narration"`)
- ✅ TTS configuration logic
- ✅ R2 upload service
- ✅ Points deduction service

---

## 📝 Database Schema

### MongoDB Collection: `slide_narrations`

```javascript
{
  _id: ObjectId("..."),
  narration_id: "narr_12345",  // Unique narration ID
  presentation_id: ObjectId("..."),
  user_id: "firebase_uid",
  version: 1,  // Version number for tracking multiple narrations

  // Configuration
  mode: "presentation",  // or "academy"
  language: "vi",
  user_query: "Focus on technical details",
  custom_instructions: "Use simple examples",

  // Narration data (Step 1)
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
          text: "Chào mừng các bạn...",
          speaker_index: 0,
          element_references: ["shape_1"],  // Element IDs mentioned
        }
      ],
      auto_advance: true,
      transition_delay: 2.0,
    }
  ],

  // Audio data (Step 2 - only after audio generation)
  audio_files: [
    {
      slide_index: 0,
      audio_url: "https://r2.wordai.vn/library_audio/narr_12345_slide_0_v1.mp3",
      library_audio_id: ObjectId("..."),  // Reference to library_audio collection
      file_size: 245678,
      format: "mp3",
      duration: 15.5,
      speaker_count: 1,
    }
  ],

  // Voice configuration (Step 2)
  voice_config: {
    provider: "google",  // or "elevenlabs"
    voices: [
      {
        speaker_index: 0,
        voice_name: "vi-VN-Neural2-A",
        language: "vi-VN",
        speaking_rate: 1.0,
      }
    ],
    use_pro_model: true,
  },

  // Metadata
  total_duration: 245.5,
  total_slides: 10,
  total_subtitles: 45,

  // Points tracking
  points_step1: 3,  // Subtitles generation
  points_step2: 10,  // Audio generation
  total_points: 13,

  // Status tracking
  status: "completed",  // pending, subtitles_ready, audio_processing, completed, failed
  error_message: null,

  // Animation metadata (for frontend)
  animations: {
    transitions: [
      {
        slide_index: 0,
        trigger_time: 13.5,  // slide_duration - transition_delay
        transition_type: "fade",
        duration: 0.5,
      }
    ],
    element_reveals: [
      {
        slide_index: 0,
        element_id: "shape_1",
        trigger_time: 4.0,  // When element is mentioned in subtitle
        animation_type: "fadeIn",
      }
    ],
  },

  // Timestamps
  created_at: ISODate("2024-12-21T10:00:00Z"),
  updated_at: ISODate("2024-12-21T10:05:30Z"),
  subtitles_generated_at: ISODate("2024-12-21T10:00:15Z"),
  audio_generated_at: ISODate("2024-12-21T10:05:30Z"),
  processing_time_step1_ms: 8450,
  processing_time_step2_ms: 18200,
}
```

### MongoDB Collection: `library_audio` (Reused from Listening Test)

```javascript
{
  _id: ObjectId("..."),
  user_id: "firebase_uid",

  // Audio file details
  file_name: "narr_12345_slide_0_v1.mp3",
  r2_key: "library_audio/narr_12345_slide_0_v1.mp3",
  r2_url: "https://r2.wordai.vn/library_audio/narr_12345_slide_0_v1.mp3",

  // Metadata
  duration_seconds: 15.5,
  file_size: 245678,
  format: "mp3",
  sample_rate: 24000,

  // Source tracking
  source_type: "slide_narration",  // NEW type (was "listening_test")
  source_id: "narr_12345",  // narration_id

  // TTS details
  voice_provider: "google",
  voice_name: "vi-VN-Neural2-A",
  language: "vi-VN",
  speaking_rate: 1.0,

  // Timestamps
  created_at: ISODate("2024-12-21T10:05:30Z"),
}
```

**Key Points:**
- ✅ Reuse `library_audio` collection (same as Listening Test)
- ✅ Use `source_type: "slide_narration"` to distinguish
- ✅ Version tracking in `slide_narrations` collection
- ✅ Animation metadata stored for frontend sync

---## 🧪 Testing Strategy

### Unit Tests

```python
# test_slide_narration_service.py

async def test_generate_narration_presentation_mode():
    """Test narration generation in presentation mode"""
    slides = create_test_slides(num=5)

    result = await narration_service.generate_narration(
        slides=slides,
        mode="presentation",
        language="vi",
    )

    assert len(result["slides"]) == 5
    assert result["total_duration"] > 0

    # Check subtitle timestamps don't overlap
    for slide in result["slides"]:
        subtitles = slide["subtitles"]
        for i in range(len(subtitles) - 1):
            assert subtitles[i]["end_time"] <= subtitles[i+1]["start_time"]


async def test_audio_generation():
    """Test audio file generation from subtitles"""
    subtitles = [
        {"start_time": 0.0, "end_time": 3.5, "text": "Test subtitle one"},
        {"start_time": 4.0, "end_time": 7.0, "text": "Test subtitle two"},
    ]

    audio_url = await audio_service.generate_audio(
        subtitles=subtitles,
        voice_config=VOICE_CONFIGS["presentation"]["vietnamese"],
    )

    assert audio_url.startswith("https://")
    assert ".mp3" in audio_url


def test_timing_calculation():
    """Test slide timing calculation"""
    subtitles = [
        {"start_time": 0.0, "end_time": 3.5},
        {"start_time": 4.0, "end_time": 8.0},
    ]

    timing = calculate_slide_timing(subtitles)

    assert timing["total_duration"] == 10.0  # 8.0 + 2.0 buffer
    assert timing["auto_advance"] == True
    assert timing["transition_delay"] == 2.0
```

### Integration Tests

```python
async def test_full_narration_pipeline():
    """Test complete narration generation pipeline"""
    # 1. Create test presentation
    presentation = await create_test_presentation(num_slides=3)

    # 2. Generate narration
    response = await client.post(
        f"/api/presentations/{presentation.id}/generate-narration",
        json={"mode": "presentation", "language": "vi"},
        headers={"Authorization": f"Bearer {test_token}"},
    )

    assert response.status_code == 200
    data = response.json()

    # 3. Verify response structure
    assert data["success"] == True
    assert len(data["slides"]) == 3
    assert data["total_duration"] > 0

    # 4. Verify audio files exist
    for slide in data["slides"]:
        audio_response = await client.get(slide["audio_url"])
        assert audio_response.status_code == 200
        assert audio_response.headers["content-type"] == "audio/mpeg"

    # 5. Verify points deduction
    user_points = await points_service.get_user_points(test_user_id)
    assert user_points["balance"] < initial_balance
```

---

## 🎨 Frontend UI/UX

### Narration Generation Modal

```
┌────────────────────────────────────────────────┐
│ 🎙️ Generate Presentation Narration            │
├────────────────────────────────────────────────┤
│                                                │
│ Mode:                                          │
│ ⚪ Presentation (Concise, 30-60s per slide)   │
│ ⚫ Academy (Detailed, 60-180s per slide)      │
│                                                │
│ Language:                                      │
│ [Vietnamese ▼]                                 │
│                                                │
│ Voice:                                         │
│ ⚪ Google TTS (Standard quality, cheaper)     │
│ ⚫ ElevenLabs (Premium quality, natural)      │
│                                                │
│ Estimated cost: 15 points                      │
│ Estimated duration: ~5-8 minutes               │
│                                                │
│ Custom instructions (optional):                │
│ ┌──────────────────────────────────────────┐  │
│ │ Focus on practical examples and use      │  │
│ │ simple language for beginners            │  │
│ └──────────────────────────────────────────┘  │
│                                                │
│         [Cancel]  [Generate (15 points)]       │
└────────────────────────────────────────────────┘
```

### Presentation Player

```
┌─────────────────────────────────────────────────────────────┐
│                    Slide Title Here                         │
│                                                             │
│                  [Slide Content Area]                       │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Subtitle: "Chào mừng đến với bài giảng..."          │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ▶ [==============================>---------] 2:35   │   │
│  │ 🔊 ━━━━━━━━━━━━━━━●━━ 80%                           │   │
│  │                                                      │   │
│  │ [⏮] [⏸️] [⏭]  Speed: 1x  Subtitles: On             │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Slide 5 / 10                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚨 Error Handling

### Common Issues

**Issue 1: AI generates overlapping timestamps**

```python
def validate_subtitles(subtitles: List[Dict]) -> bool:
    """Validate that subtitles don't overlap"""
    for i in range(len(subtitles) - 1):
        current = subtitles[i]
        next_sub = subtitles[i + 1]

        if current["end_time"] > next_sub["start_time"]:
            logger.error(f"Overlap detected: {current} vs {next_sub}")
            return False

    return True

# Fix: Auto-adjust timestamps
def fix_overlapping_subtitles(subtitles: List[Dict]) -> List[Dict]:
    """Auto-fix overlapping timestamps"""
    fixed = []

    for i, sub in enumerate(subtitles):
        if i == 0:
            fixed.append(sub)
            continue

        prev = fixed[-1]
        if sub["start_time"] < prev["end_time"]:
            # Add 0.3s gap
            sub["start_time"] = prev["end_time"] + 0.3
            sub["end_time"] = sub["start_time"] + sub["duration"]

        fixed.append(sub)

    return fixed
```

**Issue 2: TTS fails for very long text**

```python
async def generate_audio_chunked(text: str, max_chars: int = 5000):
    """Split long text into chunks for TTS"""
    if len(text) <= max_chars:
        return await tts_service.synthesize(text)

    # Split by sentences
    sentences = split_into_sentences(text)
    chunks = []
    current_chunk = []
    current_length = 0

    for sentence in sentences:
        if current_length + len(sentence) > max_chars:
            # Generate audio for current chunk
            chunk_text = " ".join(current_chunk)
            chunk_audio = await tts_service.synthesize(chunk_text)
            chunks.append(chunk_audio)

            # Start new chunk
            current_chunk = [sentence]
            current_length = len(sentence)
        else:
            current_chunk.append(sentence)
            current_length += len(sentence)

    # Final chunk
    if current_chunk:
        chunk_audio = await tts_service.synthesize(" ".join(current_chunk))
        chunks.append(chunk_audio)

    # Merge audio files
    return merge_audio_files(chunks)
```

**Issue 3: Audio-subtitle sync drift**

```python
async def verify_audio_sync(audio_file: str, subtitles: List[Dict]):
    """Verify audio duration matches subtitle timing"""
    audio_duration = get_audio_duration(audio_file)
    last_subtitle = max(subtitles, key=lambda s: s["end_time"])
    expected_duration = last_subtitle["end_time"]

    drift = abs(audio_duration - expected_duration)

    if drift > 1.0:  # More than 1 second drift
        logger.warning(f"Audio sync drift: {drift}s")

        # Adjust subtitle timestamps proportionally
        ratio = audio_duration / expected_duration
        for sub in subtitles:
            sub["start_time"] *= ratio
            sub["end_time"] *= ratio

    return subtitles
```

---

## 📊 Performance Optimization

### Parallel Processing

```python
async def generate_all_audio_parallel(slides: List[Dict]) -> List[str]:
    """Generate audio for all slides in parallel"""
    tasks = []

    for slide in slides:
        task = generate_slide_audio(
            slide_index=slide["slide_index"],
            subtitles=slide["subtitles"],
            voice_config=get_voice_config(),
        )
        tasks.append(task)

    # Run all in parallel
    audio_urls = await asyncio.gather(*tasks)

    return audio_urls
```

### Caching

```python
# Cache narration results for 24 hours
@lru_cache(maxsize=100)
def get_cached_narration(presentation_id: str, mode: str) -> Optional[Dict]:
    """Check if narration already generated"""
    result = db.presentation_narrations.find_one({
        "presentation_id": ObjectId(presentation_id),
        "mode": mode,
        "status": "completed",
        "created_at": {"$gte": datetime.now() - timedelta(hours=24)},
    })

    return result
```

---

## 🔮 Future Enhancements

### Phase 5+: Advanced Features

- [ ] **Multi-voice narration**: Different voices for different speakers
- [ ] **Background music**: Add subtle background music
- [ ] **Sound effects**: Add emphasis sounds (applause, ding, etc.)
- [ ] **Voice cloning**: Clone user's voice with ElevenLabs
- [ ] **Real-time editing**: Edit subtitles and regenerate audio segments
- [ ] **Translation**: Auto-translate subtitles to multiple languages
- [ ] **Video export**: Export as MP4 video with slides + audio + subtitles
- [ ] **Live presentation mode**: Show presenter notes + auto-advance
- [ ] **Analytics**: Track viewer engagement with audio playback

---

## 📚 References

- **Google Cloud TTS**: https://cloud.google.com/text-to-speech
- **ElevenLabs API**: https://elevenlabs.io/docs
- **SSML Guide**: https://www.w3.org/TR/speech-synthesis11/
- **Gemini API**: https://ai.google.dev/docs
- **Web Audio API**: https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API

---

**Last Updated:** December 21, 2024
**Status:** 📋 Design Phase - Ready for Implementation
**Estimated Development:** 4 weeks (4 phases)
**Priority:** High (Key differentiating feature)
