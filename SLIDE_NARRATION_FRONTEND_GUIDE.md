# Slide Narration - Frontend Implementation Guide

## 📖 Overview

Hướng dẫn implement modals cho Slide Narration system:

1. **Modal 1: Generate Subtitles** - Tạo/nhận subtitles từ AI
2. **Modal 2: Generate Audio** - Chọn version, edit subtitles, tạo audio
3. **Modal 3: Library Audio Browser** - Chọn audio từ library cho slides

---

## 🎯 Modal 1: Generate Subtitles

### Features

- ✅ Chọn scope: **Current slide** hoặc **All slides**
- ✅ Chọn mode: **Presentation** (ngắn gọn) hoặc **Academy** (chi tiết)
- ✅ Chọn language: **Vietnamese**, **English**, **Chinese**
- ✅ Optional: User instructions (custom narration style)
- ✅ Loading state với progress (tối đa 4 phút)
- ✅ Preview subtitles sau khi nhận từ AI
- ✅ Options sau khi nhận: **Save**, **Generate Audio**, **Discard**

### UI Components

```typescript
interface SubtitleGenerateModal {
  // Step 1: Configuration
  scope: 'current_slide' | 'all_slides';
  mode: 'presentation' | 'academy';
  language: 'vi' | 'en' | 'zh';
  userQuery: string;  // Optional custom instructions

  // Step 2: AI Generation (Loading)
  isGenerating: boolean;
  progress: number;        // 0-100
  elapsedTime: number;     // seconds
  estimatedTime: number;   // seconds (max 240)

  // Step 3: Preview & Actions
  subtitles: SlideSubtitleData[];
  totalDuration: number;
  narrationId: string;

  actions: {
    onSave: () => void;
    onGenerateAudio: () => void;
    onDiscard: () => void;
  };
}
```

### API Call Flow

```typescript
async function generateSubtitles() {
  // 1. Show loading state
  setIsGenerating(true);
  setProgress(0);

  // 2. Start progress timer
  const timer = setInterval(() => {
    setElapsedTime(prev => prev + 1);
    setProgress(Math.min((elapsedTime / 240) * 100, 95));
  }, 1000);

  try {
    // 3. Call API (wait up to 4 minutes)
    const response = await fetch(
      `/api/presentations/${presentationId}/narration/generate-subtitles`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          presentation_id: presentationId,
          mode: selectedMode,
          language: selectedLanguage,
          user_query: userInstructions
        }),
        signal: AbortSignal.timeout(240000)  // 4 minutes
      }
    );

    if (!response.ok) {
      if (response.status === 402) {
        throw new Error('Không đủ điểm. Cần 2 điểm để generate subtitles.');
      }
      throw new Error('Failed to generate subtitles');
    }

    const data = await response.json();

    // 4. Show preview
    clearInterval(timer);
    setProgress(100);
    setIsGenerating(false);
    setSubtitles(data.slides);
    setNarrationId(data.narration_id);
    setShowPreview(true);

  } catch (error) {
    clearInterval(timer);
    setIsGenerating(false);
    handleError(error);
  }
}
```

### UI Layout

```
┌──────────────────────────────────────────┐
│  🎙️ Generate Slide Narration            │
├──────────────────────────────────────────┤
│                                          │
│  Scope:                                  │
│  ○ Current slide only                    │
│  ● All slides                            │
│                                          │
│  Mode:                                   │
│  ● Presentation (Concise, 30-60s/slide) │
│  ○ Academy (Detailed, 60-180s/slide)    │
│                                          │
│  Language:                               │
│  [Vietnamese ▼]                          │
│                                          │
│  Instructions (optional):                │
│  ┌────────────────────────────────────┐ │
│  │ Focus on key benefits, keep it     │ │
│  │ professional and engaging...       │ │
│  └────────────────────────────────────┘ │
│                                          │
│  Cost: 2 points (Your balance: 50 pts) │
│                                          │
│  [Cancel]              [Generate (2⭐)] │
└──────────────────────────────────────────┘

// While generating:

┌──────────────────────────────────────────┐
│  🎙️ Generating Subtitles...              │
├──────────────────────────────────────────┤
│                                          │
│  ████████████░░░░░░░░░░░░░░░░ 60%      │
│                                          │
│  Analyzing slides with Gemini 3 Pro...  │
│  Elapsed: 25s / Est: ~30s               │
│                                          │
│  Please wait (max 4 minutes)            │
│                                          │
│  [Cancel]                               │
└──────────────────────────────────────────┘

// After generation:

┌──────────────────────────────────────────┐
│  ✅ Subtitles Generated                  │
├──────────────────────────────────────────┤
│                                          │
│  Version: 1                              │
│  Total Duration: 45.8s                   │
│  Slides: 5                               │
│                                          │
│  Preview:                                │
│  ┌────────────────────────────────────┐ │
│  │ Slide 1 (15.5s)                    │ │
│  │ • 0.0s - 3.5s: "Chào mừng..."     │ │
│  │ • 4.0s - 8.2s: "Như bạn thấy..."  │ │
│  │                                    │ │
│  │ Slide 2 (18.3s)                    │ │
│  │ • 0.0s - 5.1s: "Sản phẩm..."      │ │
│  │ ...                                │ │
│  └────────────────────────────────────┘ │
│                                          │
│  [Discard]  [Save Only]  [Generate Audio│
└──────────────────────────────────────────┘
```

---

## 🔊 Modal 2: Generate Audio from Subtitles

### Features

- ✅ Chọn narration version từ dropdown
- ✅ Hiển thị preview tất cả subtitles
- ✅ **Edit subtitles** trước khi generate audio
- ✅ Voice configuration (tham khảo modal trong book)
- ✅ Generate audio (2 points)
- ✅ Download audio files after generation

### UI Components

```typescript
interface AudioGenerateModal {
  // Step 1: Select Version
  versions: NarrationVersion[];
  selectedVersion: string;  // narration_id

  // Step 2: Preview & Edit Subtitles
  narration: NarrationDetailResponse;
  isEditing: boolean;
  editedSubtitles: SlideSubtitleData[];
  hasChanges: boolean;

  // Step 3: Voice Configuration
  voiceProvider: 'google' | 'openai' | 'elevenlabs';
  selectedVoice: string;
  speakingRate: number;     // 0.5 - 2.0
  pitch: number;            // -20.0 to 20.0
  useProModel: boolean;

  // Step 4: Audio Generation
  isGenerating: boolean;
  audioFiles: AudioFile[];

  actions: {
    onSaveEdits: () => void;
    onGenerate: () => void;
    onDownload: (slideIndex: number) => void;
  };
}
```

### API Call Flow

```typescript
async function generateAudioFromSubtitles() {
  // 1. Save edits if any (no cost)
  if (hasChanges) {
    await fetch(
      `/api/presentations/${presentationId}/narration/${narrationId}`,
      {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          slides: editedSubtitles
        })
      }
    );
  }

  // 2. Generate audio (2 points)
  setIsGenerating(true);

  try {
    const response = await fetch(
      `/api/presentations/${presentationId}/narration/${narrationId}/generate-audio`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          narration_id: narrationId,
          voice_config: {
            provider: voiceProvider,
            voices: [{
              voice_name: selectedVoice,
              language: selectedLanguage,
              speaking_rate: speakingRate,
              pitch: pitch
            }],
            use_pro_model: useProModel
          }
        })
      }
    );

    if (!response.ok) {
      if (response.status === 402) {
        throw new Error('Không đủ điểm. Cần 2 điểm để generate audio.');
      }
      throw new Error('Failed to generate audio');
    }

    const data = await response.json();

    // 3. Show audio files
    setIsGenerating(false);
    setAudioFiles(data.audio_files);
    setShowSuccess(true);

  } catch (error) {
    setIsGenerating(false);
    handleError(error);
  }
}
```

### UI Layout

```
┌────────────────────────────────────────────────┐
│  🔊 Generate Audio from Subtitles             │
├────────────────────────────────────────────────┤
│                                                │
│  Version:                                      │
│  [Version 1 - 45.8s (Presentation, Vi) ▼]    │
│                                                │
│  ┌──────────────────────────────────────────┐ │
│  │ Subtitles Preview (Click to edit)       │ │
│  │                                          │ │
│  │ Slide 1 (15.5s)                         │ │
│  │ ├─ 0.0s - 3.5s                          │ │
│  │ │  "Chào mừng đến với bài thuyết..."   │ │
│  │ │  [Edit] [🗑️]                         │ │
│  │ ├─ 4.0s - 8.2s                          │ │
│  │ │  "Như bạn thấy trong biểu đồ..."     │ │
│  │ │  [Edit] [🗑️]                         │ │
│  │                                          │ │
│  │ Slide 2 (18.3s)                         │ │
│  │ ├─ 0.0s - 5.1s                          │ │
│  │ │  "Sản phẩm của chúng tôi..."         │ │
│  │ │  [Edit] [🗑️]                         │ │
│  │ ...                                      │ │
│  └──────────────────────────────────────────┘ │
│                                                │
│  Voice Settings:                              │
│  Provider: [Google TTS ▼]                     │
│  Voice: [vi-VN-Neural2-A (Female) ▼]         │
│  Speaking Rate: [1.0] ──────●────── (0.5-2.0) │
│  Pitch: [0.0] ──────●────── (-20 to +20)     │
│  □ Use Premium Voice Model (+quality)         │
│                                                │
│  Cost: 2 points (Your balance: 48 pts)       │
│                                                │
│  [Cancel]              [Generate Audio (2⭐)] │
└────────────────────────────────────────────────┘

// Edit Subtitle Modal:

┌────────────────────────────────────────────────┐
│  ✏️ Edit Subtitle                              │
├────────────────────────────────────────────────┤
│                                                │
│  Slide 1 - Subtitle 1                         │
│                                                │
│  Start Time: [0.0] seconds                    │
│  End Time: [3.5] seconds                      │
│  Duration: 3.5s (auto-calculated)             │
│                                                │
│  Text:                                         │
│  ┌────────────────────────────────────────┐   │
│  │ Chào mừng đến với bài thuyết trình    │   │
│  │ này về sản phẩm mới của chúng tôi.    │   │
│  └────────────────────────────────────────┘   │
│                                                │
│  Speaker: [Narrator (0) ▼]                   │
│                                                │
│  Element References:                          │
│  [+ Add Element]                              │
│                                                │
│  [Cancel]                        [Save Changes]│
└────────────────────────────────────────────────┘

// After generation:

┌────────────────────────────────────────────────┐
│  ✅ Audio Generated Successfully               │
├────────────────────────────────────────────────┤
│                                                │
│  Total Duration: 45.8s                        │
│  Files: 5 slides                              │
│                                                │
│  Audio Files:                                 │
│  ┌────────────────────────────────────────┐   │
│  │ Slide 1 - 15.5s                        │   │
│  │ [▶️ Play] [⬇️ Download]                │   │
│  │                                        │   │
│  │ Slide 2 - 18.3s                        │   │
│  │ [▶️ Play] [⬇️ Download]                │   │
│  │                                        │   │
│  │ ...                                    │   │
│  └────────────────────────────────────────┘   │
│                                                │
│  [Close]                      [Download All]  │
└────────────────────────────────────────────────┘
```

---

## 🔌 API Integration Reference

### 1. Generate Subtitles (Modal 1)

```typescript
POST /api/presentations/{id}/narration/generate-subtitles

Request:
{
  "presentation_id": "507f1f77bcf86cd799439011",
  "mode": "presentation",  // or "academy"
  "language": "vi",        // or "en", "zh"
  "user_query": "Focus on key benefits"  // optional
}

Response:
{
  "success": true,
  "narration_id": "507f1f77bcf86cd799439099",
  "version": 1,
  "slides": [...],
  "total_duration": 45.8,
  "processing_time_ms": 3200,
  "points_deducted": 2
}
```

### 2. List Versions (Modal 2 - Dropdown)

```typescript
GET /api/presentations/{id}/narrations

Response:
{
  "success": true,
  "narrations": [
    {
      "narration_id": "507f...",
      "version": 2,
      "status": "completed",
      "mode": "presentation",
      "language": "vi",
      "total_duration": 45.8,
      "created_at": "2025-01-15T10:30:00Z",
      "audio_ready": true
    },
    {
      "narration_id": "507f...",
      "version": 1,
      "status": "subtitles_only",
      "mode": "academy",
      "language": "en",
      "total_duration": 120.5,
      "created_at": "2025-01-14T15:20:00Z",
      "audio_ready": false
    }
  ],
  "total_count": 2
}
```

### 3. Get Narration Details (Modal 2 - Preview)

```typescript
GET /api/presentations/{id}/narration/{narration_id}

Response:
{
  "success": true,
  "narration_id": "507f...",
  "presentation_id": "507f...",
  "version": 1,
  "status": "subtitles_only",
  "mode": "presentation",
  "language": "vi",
  "user_query": "",
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
          "text": "Chào mừng...",
          "speaker_index": 0,
          "element_references": []
        }
      ],
      "auto_advance": true,
      "transition_delay": 2.0
    }
  ],
  "audio_files": [],
  "voice_config": null,
  "total_duration": 45.8,
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

### 4. Update Subtitles (Modal 2 - Edit)

```typescript
PUT /api/presentations/{id}/narration/{narration_id}

Request:
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
          "text": "EDITED TEXT...",  // Changed
          "speaker_index": 0,
          "element_references": []
        }
      ],
      "auto_advance": true,
      "transition_delay": 2.0
    }
  ]
}

Response:
{
  "success": true,
  "narration_id": "507f...",
  "slides": [...],  // Updated slides
  "total_duration": 45.8,  // Recalculated
  "updated_at": "2025-01-15T10:35:00Z"
}
```

### 5. Generate Audio (Modal 2)

```typescript
POST /api/presentations/{id}/narration/{narration_id}/generate-audio

Request:
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
  }
}

Response:
{
  "success": true,
  "narration_id": "507f...",
  "audio_files": [
    {
      "slide_index": 0,
      "audio_url": "https://cdn.r2.com/narr_507f_slide_0.mp3",
      "library_audio_id": "507f...",
      "file_size": 245678,
      "format": "mp3",
      "duration": 15.5,
      "speaker_count": 1
    }
  ],
  "total_duration": 45.8,
  "processing_time_ms": 8500,
  "points_deducted": 2
}
```

### 6. Delete Narration (Version Management)

```typescript
DELETE /api/presentations/{id}/narration/{narration_id}

Response:
{
  "success": true,
  "narration_id": "507f...",
  "message": "Narration version 1 deleted successfully"
}
```

---

## 📚 Voice Configuration Reference

### Google TTS Voices (Recommended)

**Vietnamese:**
- `vi-VN-Neural2-A` - Female (Natural, professional)
- `vi-VN-Neural2-D` - Male (Clear, authoritative)
- `vi-VN-Wavenet-A` - Female (Premium, expressive)
- `vi-VN-Wavenet-D` - Male (Premium, warm)

**English:**
- `en-US-Neural2-A` - Female (Professional)
- `en-US-Neural2-D` - Male (Authoritative)
- `en-GB-Neural2-A` - Female British (Elegant)
- `en-GB-Neural2-D` - Male British (Distinguished)

**Chinese:**
- `zh-CN-Neural2-A` - Female (Standard Mandarin)
- `zh-CN-Neural2-D` - Male (Standard Mandarin)

### Voice Settings

```typescript
interface VoiceSettings {
  speaking_rate: number;  // 0.5 - 2.0 (default: 1.0)
  pitch: number;          // -20.0 to 20.0 (default: 0.0)
}

// Examples:
// Slow & Low: { speaking_rate: 0.8, pitch: -5.0 }
// Fast & High: { speaking_rate: 1.3, pitch: 5.0 }
// Normal: { speaking_rate: 1.0, pitch: 0.0 }
```

---

## ✅ Implementation Checklist

### Modal 1: Generate Subtitles

- [ ] Create modal component
- [ ] Add scope selector (current/all slides)
- [ ] Add mode selector (presentation/academy)
- [ ] Add language selector
- [ ] Add optional instructions textarea
- [ ] Implement API call with loading state
- [ ] Add progress bar (4-minute timeout)
- [ ] Create subtitle preview component
- [ ] Add actions: Save, Generate Audio, Discard
- [ ] Handle errors (402, 500, timeout)
- [ ] Update user points balance

### Modal 2: Generate Audio

- [ ] Create modal component
- [ ] Add version dropdown (fetch from API)
- [ ] Create subtitle preview/edit component
- [ ] Implement inline subtitle editing
- [ ] Add validation for timestamps
- [ ] Create voice configuration form
- [ ] Reference book modal for voice settings UI
- [ ] Implement update subtitles API call
- [ ] Implement generate audio API call
- [ ] Create audio player for preview
- [ ] Add download buttons for audio files
- [ ] Handle errors (402, 400, 500)

### State Management

- [ ] Create narration context/store
- [ ] Manage versions list
- [ ] Manage selected narration
- [ ] Manage editing state
- [ ] Sync with presentation state

---

## 🎬 User Flow

```
┌─────────────────────┐
│ User clicks         │
│ "Generate Narration"│
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ Modal 1: Generate   │
│ Subtitles           │
│ - Select scope      │
│ - Select mode       │
│ - Select language   │
│ - Add instructions  │
└──────┬──────────────┘
       │ Click "Generate (2⭐)"
       ▼
┌─────────────────────┐
│ Loading...          │
│ Progress: 60%       │
│ Elapsed: 25s        │
│ Max: 4 minutes      │
└──────┬──────────────┘
       │ Success
       ▼
┌─────────────────────┐
│ Preview Subtitles   │
│ - Show all slides   │
│ - Show timings      │
│ - Total duration    │
└──────┬──────────────┘
       │
       ├─ "Save Only" ──> Close modal
       ├─ "Discard" ────> Close modal
       └─ "Generate Audio"
              ▼
       ┌─────────────────────┐
       │ Modal 2: Generate   │
       │ Audio               │
       │ - Select version    │
       │ - Preview subtitles │
       │ - Edit if needed    │
       └──────┬──────────────┘
              │ Edit subtitles?
              ├─ Yes ──> Edit modal ──> Save edits
              └─ No
              ▼
       ┌─────────────────────┐
       │ Voice Configuration │
       │ - Select provider   │
       │ - Select voice      │
       │ - Adjust rate/pitch │
       └──────┬──────────────┘
              │ Click "Generate Audio (2⭐)"
              ▼
       ┌─────────────────────┐
       │ Loading...          │
       │ Generating audio... │
       └──────┬──────────────┘
              │ Success
              ▼
       ┌─────────────────────┐
       │ Audio Files Ready   │
       │ - Play each file    │
       │ - Download files    │
       │ - Download all      │
       └─────────────────────┘
```

**Alternative Flow (Library Audio):**

```
       ┌─────────────────────┐
       │ Modal 2: Audio      │
       │ Options             │
       └──────┬──────────────┘
              │
              ├─ "Generate with TTS" ──> Voice config ──> Generate (2⭐)
              └─ "Select from Library"
                     ▼
              ┌─────────────────────┐
              │ Modal 3: Library    │
              │ Audio Browser       │
              │ - Search/filter     │
              │ - Preview audio     │
              │ - Select for slides │
              └──────┬──────────────┘
                     │ Assign audio
                     ▼
              ┌─────────────────────┐
              │ Audio Assigned      │
              │ - No points cost    │
              │ - Ready to use      │
              └─────────────────────┘
```

---

## 📚 Modal 3: Library Audio Browser

### Features

- ✅ Browse all library audio files
- ✅ Filter by source_type (slide_narration, listening_test, upload)
- ✅ Search by file name
- ✅ Preview audio before assigning
- ✅ Assign to **individual slides** or **all slides**
- ✅ Replace existing audio assignments
- ✅ **No points cost** (free to assign)

### UI Components

```typescript
interface LibraryAudioBrowser {
  // Filters
  sourceType: 'all' | 'slide_narration' | 'listening_test' | 'upload';
  searchQuery: string;

  // Pagination
  currentPage: number;
  limit: number;
  totalCount: number;
  hasMore: boolean;

  // Audio list
  audioFiles: LibraryAudioItem[];
  selectedAudio: Map<number, string>;  // slide_index -> audio_id

  // Preview
  previewingAudio: LibraryAudioItem | null;
  isPlaying: boolean;

  // Assignment mode
  assignmentMode: 'individual' | 'all_slides';
  targetSlides: number[];  // For individual mode

  actions: {
    onSearch: (query: string) => void;
    onFilter: (sourceType: string) => void;
    onPreview: (audioId: string) => void;
    onSelectAudio: (slideIndex: number, audioId: string) => void;
    onAssign: () => void;
  };
}
```

### API Integration

```typescript
// 1. List library audio files
async function fetchLibraryAudio(filters: {
  sourceType?: string;
  searchQuery?: string;
  limit?: number;
  offset?: number;
}) {
  const params = new URLSearchParams();
  if (filters.sourceType) params.append('source_type', filters.sourceType);
  if (filters.searchQuery) params.append('search_query', filters.searchQuery);
  params.append('limit', String(filters.limit || 50));
  params.append('offset', String(filters.offset || 0));

  const response = await fetch(
    `/api/library-audio?${params.toString()}`,
    {
      headers: { 'Authorization': `Bearer ${token}` }
    }
  );

  const data = await response.json();
  return {
    audioFiles: data.audio_files,
    totalCount: data.total_count,
    hasMore: data.has_more
  };
}

// 2. Assign audio to slides
async function assignLibraryAudio(
  presentationId: string,
  narrationId: string,
  assignments: { slide_index: number; library_audio_id: string }[]
) {
  const response = await fetch(
    `/api/presentations/${presentationId}/narration/${narrationId}/assign-audio`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        audio_assignments: assignments
      })
    }
  );

  if (!response.ok) {
    throw new Error('Failed to assign audio');
  }

  return await response.json();
}

// 3. Remove audio from specific slide
async function removeSlideAudio(
  presentationId: string,
  narrationId: string,
  slideIndex: number
) {
  const response = await fetch(
    `/api/presentations/${presentationId}/narration/${narrationId}/audio/${slideIndex}`,
    {
      method: 'DELETE',
      headers: { 'Authorization': `Bearer ${token}` }
    }
  );

  return await response.json();
}
```

### UI Layout

```
┌────────────────────────────────────────────────┐
│  📚 Select Audio from Library                 │
├────────────────────────────────────────────────┤
│                                                │
│  Assignment Mode:                             │
│  ○ Individual slides (Select for each)        │
│  ● All slides (Use same audio)                │
│                                                │
│  ┌──────────────────────────────────────────┐ │
│  │ 🔍 Search: [intro narration...      ] [X]│ │
│  │ Filter: [All Sources ▼]                  │ │
│  │                                          │ │
│  │ Results: 15 files                        │ │
│  └──────────────────────────────────────────┘ │
│                                                │
│  ┌──────────────────────────────────────────┐ │
│  │ Audio Files:                             │ │
│  │                                          │ │
│  │ ☑ intro_narration.mp3                   │ │
│  │   15.5s • 245 KB • TTS Generated        │ │
│  │   [▶️ Preview] [ℹ️ Info]                │ │
│  │                                          │ │
│  │ ☐ slide_1_audio.mp3                     │ │
│  │   18.3s • 298 KB • Uploaded             │ │
│  │   [▶️ Preview] [ℹ️ Info]                │ │
│  │                                          │ │
│  │ ☐ professional_voice.mp3                │ │
│  │   22.1s • 356 KB • Listening Test       │ │
│  │   [▶️ Preview] [ℹ️ Info]                │ │
│  │                                          │ │
│  │ ...                                      │ │
│  │                                          │ │
│  │ [Load More (15/50)]                     │ │
│  └──────────────────────────────────────────┘ │
│                                                │
│  Individual Slides Assignment:                │
│  Slide 0: [intro_narration.mp3        ] [🗑️] │
│  Slide 1: [Not assigned               ] [📂] │
│  Slide 2: [Not assigned               ] [📂] │
│  ...                                           │
│                                                │
│  [Cancel]              [Assign to Slides (0⭐)]│
└────────────────────────────────────────────────┘

// Audio Preview Modal:

┌────────────────────────────────────────────────┐
│  🎵 Preview: intro_narration.mp3              │
├────────────────────────────────────────────────┤
│                                                │
│  ──────●─────────────────────── 5.2s / 15.5s  │
│  [⏸️ Pause] [⏹️ Stop] [🔊 100%]               │
│                                                │
│  File Info:                                   │
│  • Duration: 15.5 seconds                     │
│  • Size: 245 KB                               │
│  • Format: MP3                                │
│  • Source: TTS Generated                      │
│  • Created: 2025-01-15 10:30                  │
│                                                │
│  Voice Settings:                              │
│  • Provider: Google TTS                       │
│  • Voice: vi-VN-Neural2-A (Female)           │
│  • Speaking Rate: 1.0                         │
│                                                │
│  [Close]                  [Use This Audio]    │
└────────────────────────────────────────────────┘
```

### Assignment Modes

**Mode 1: Individual Slides**
- Select different audio for each slide
- Flexible per-slide customization
- Mix TTS with custom audio

**Mode 2: All Slides (Same Audio)**
- Use same audio file for all slides
- Quick assignment
- Useful for background music or intro/outro

### Implementation Example

```typescript
function LibraryAudioBrowserModal({
  narrationId,
  presentationId,
  totalSlides,
  onAssigned,
  onClose
}) {
  const [audioFiles, setAudioFiles] = useState([]);
  const [selectedAudio, setSelectedAudio] = useState(new Map());
  const [assignmentMode, setAssignmentMode] = useState('individual');
  const [searchQuery, setSearchQuery] = useState('');
  const [sourceFilter, setSourceFilter] = useState('all');

  // Fetch audio files
  useEffect(() => {
    fetchLibraryAudio({
      sourceType: sourceFilter === 'all' ? undefined : sourceFilter,
      searchQuery: searchQuery || undefined,
      limit: 50,
      offset: 0
    }).then(data => {
      setAudioFiles(data.audioFiles);
    });
  }, [searchQuery, sourceFilter]);

  // Handle audio selection for slide
  const handleSelectAudio = (slideIndex: number, audioId: string) => {
    const newSelection = new Map(selectedAudio);
    newSelection.set(slideIndex, audioId);
    setSelectedAudio(newSelection);
  };

  // Handle assignment
  const handleAssign = async () => {
    const assignments = [];

    if (assignmentMode === 'all_slides') {
      // Assign same audio to all slides
      const audioId = selectedAudio.get(0); // Get selected audio
      if (!audioId) return;

      for (let i = 0; i < totalSlides; i++) {
        assignments.push({
          slide_index: i,
          library_audio_id: audioId
        });
      }
    } else {
      // Individual assignments
      selectedAudio.forEach((audioId, slideIndex) => {
        assignments.push({
          slide_index: slideIndex,
          library_audio_id: audioId
        });
      });
    }

    try {
      await assignLibraryAudio(presentationId, narrationId, assignments);
      onAssigned();
      onClose();
    } catch (error) {
      console.error('Failed to assign audio:', error);
    }
  };

  return (
    <Modal>
      {/* Filter & Search UI */}
      {/* Audio list with preview */}
      {/* Assignment UI based on mode */}
      {/* Assign button */}
    </Modal>
  );
}
```

---

## 🔗 Backend Endpoints Available

✅ **All endpoints implemented:**

| Endpoint | Method | Cost | Description |
|----------|--------|------|-------------|
| `/presentations/{id}/narration/generate-subtitles` | POST | 2 pts | Generate subtitles with AI |
| `/presentations/{id}/narration/{narration_id}/generate-audio` | POST | 2 pts | Generate audio from subtitles |
| `/presentations/{id}/narrations` | GET | Free | List all versions |
| `/presentations/{id}/narration/{narration_id}` | GET | Free | Get narration details |
| `/presentations/{id}/narration/{narration_id}` | PUT | Free | Update subtitles |
| `/presentations/{id}/narration/{narration_id}` | DELETE | Free | Delete narration |
| **`/library-audio`** | **GET** | **Free** | **Browse library audio files** |
| **`/presentations/{id}/narration/{narration_id}/assign-audio`** | **POST** | **Free** | **Assign library audio to slides** |
| **`/presentations/{id}/narration/{narration_id}/audio/{slide_index}`** | **DELETE** | **Free** | **Remove audio from slide** |

**Backend ready for frontend implementation!** ✅
