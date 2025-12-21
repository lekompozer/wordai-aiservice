# Slide AI API Documentation

## 📖 Overview

API endpoints cho các tính năng AI cho slides:

1. ✅ **Slide Formatting & Editing**: Cải thiện slide tự động với AI
2. ✅ **Slide Narration**: Tạo subtitles và audio cho presentation

---

## 🤖 AI Models Used

| Feature | Mode | AI Model | Purpose |
|---------|------|----------|---------|
| **Formatting** | Format | **Claude Sonnet 4.5** | Layout & design optimization |
| **Formatting** | Edit | **Gemini 3 Pro Preview** | Content rewriting & creation |
| **Narration** | Subtitles | **Gemini 3 Pro Preview** | Natural narration generation |
| **Narration** | Audio | **Google TTS (Neural2)** | High-quality speech synthesis |

---

## 🎨 SLIDE FORMATTING & EDITING API

### Endpoint

```
POST /api/slides/ai-format
```

### Overview

Cho phép người dùng cải thiện slide tự động với AI, bao gồm:

- ✅ **Format Mode**: Cải thiện layout, typography, visual hierarchy (giữ nguyên nội dung)
- ✅ **Edit Mode**: Viết lại nội dung theo yêu cầu của người dụng
- ✅ **Context-Aware**: AI phân tích toàn bộ slide (HTML + Elements + Background)
- ✅ **Smart Suggestions**: Gợi ý di chuyển elements và thay đổi background (optional)

**Lý do chọn model:**
- **Edit Mode**: Gemini 3 Pro có khả năng creative writing tốt hơn, hiểu context sâu hơn → Phù hợp cho viết lại nội dung
- **Format Mode**: Claude Sonnet 4.5 có khả năng phân tích design, spacing, typography tốt hơn → Phù hợp cho cải thiện layout

**Base URL**: `https://ai.wordai.pro` (Production)

**Authentication**: Required (Firebase JWT Token)

**Content-Type**: `application/json`

---

## 📋 Request Schema

### Headers

```http
Authorization: Bearer <firebase_jwt_token>
Content-Type: application/json
```

### Request Body

```typescript
interface SlideAIFormatRequest {
  slide_index: number;              // Slide index (0-based)
  current_html: string;             // Current slide HTML content
  elements: SlideElement[];         // Current slide elements
  background: SlideBackground;      // Current slide background
  user_instruction?: string;        // Optional user instruction
  format_type: "format" | "edit";  // Format or edit mode
}

interface SlideElement {
  type: "shape" | "image" | "icon" | "text";
  position: {
    x: number;      // X position (px)
    y: number;      // Y position (px)
    width: number;  // Width (px)
    height: number; // Height (px)
  };
  properties: {
    color?: string;           // Element color (hex)
    backgroundColor?: string; // Background color (hex)
    borderRadius?: number;    // Border radius (px)
    opacity?: number;         // Opacity (0-1)
    rotation?: number;        // Rotation (degrees)
    [key: string]: any;       // Other properties
  };
}

interface SlideBackground {
  type: "color" | "gradient" | "image";
  value?: string;              // Color hex or image URL
  gradient?: {
    type: "linear" | "radial";
    colors: string[];          // Array of color hex values
    angle?: number;            // Gradient angle (degrees)
  };
  overlayOpacity?: number;     // Overlay opacity (0-1)
  overlayColor?: string;       // Overlay color (hex)
}
```

### Example Request

#### Format Mode (Layout Improvement)

```json
{
  "slide_index": 0,
  "current_html": "<h1>Product Launch 2024</h1><p>Introducing our revolutionary new product that will change the market.</p>",
  "elements": [
    {
      "type": "shape",
      "position": {
        "x": 100,
        "y": 200,
        "width": 300,
        "height": 80
      },
      "properties": {
        "color": "#667eea",
        "borderRadius": 12,
        "opacity": 0.9
      }
    },
    {
      "type": "icon",
      "position": {
        "x": 50,
        "y": 50,
        "width": 64,
        "height": 64
      },
      "properties": {
        "color": "#764ba2"
      }
    }
  ],
  "background": {
    "type": "gradient",
    "gradient": {
      "type": "linear",
      "colors": ["#667eea", "#764ba2"],
      "angle": 135
    },
    "overlayOpacity": 0.1,
    "overlayColor": "#000000"
  },
  "user_instruction": "Make it more modern and professional for a tech startup presentation",
  "format_type": "format"
}
```

#### Edit Mode (Content Rewriting)

```json
{
  "slide_index": 2,
  "current_html": "<h1>Features</h1><ul><li>Fast</li><li>Secure</li><li>Easy to use</li></ul>",
  "elements": [],
  "background": {
    "type": "color",
    "value": "#ffffff"
  },
  "user_instruction": "Expand each feature with 2-3 sentences explaining the benefits. Make it more compelling and sales-focused.",
  "format_type": "edit"
}
```

---

## 📤 Response Schema

### Success Response (200 OK)

```typescript
interface SlideAIFormatResponse {
  success: boolean;                 // Always true for success
  formatted_html: string;           // AI-improved HTML content
  suggested_elements?: SlideElement[]; // Optional element suggestions
  suggested_background?: SlideBackground; // Optional background suggestions
  ai_explanation: string;           // What AI changed and why
  processing_time_ms: number;       // AI processing time
  points_deducted: number;          // Points cost (1-2)
}
```

### Example Response

#### Format Mode Response

```json
{
  "success": true,
  "formatted_html": "<div class=\"slide-header\">\n  <h1 class=\"hero-title\">Product Launch 2024</h1>\n  <p class=\"hero-subtitle\">Introducing our revolutionary new product<br>that will change the market</p>\n</div>",
  "suggested_elements": [
    {
      "type": "shape",
      "position": {
        "x": 100,
        "y": 180,
        "width": 320,
        "height": 100
      },
      "properties": {
        "color": "#667eea",
        "borderRadius": 16,
        "opacity": 0.85
      }
    }
  ],
  "suggested_background": {
    "type": "gradient",
    "gradient": {
      "type": "linear",
      "colors": ["#667eea", "#764ba2", "#f093fb"],
      "angle": 135
    },
    "overlayOpacity": 0.15,
    "overlayColor": "#000000"
  },
  "ai_explanation": "Improved visual hierarchy by:\n- Added semantic HTML structure with header div\n- Enhanced title with hero-title class for better typography\n- Split long subtitle into two lines for readability\n- Suggested larger shape with more rounded corners for modern look\n- Added third gradient color for depth\n- Increased overlay opacity for better text contrast",
  "processing_time_ms": 1847,
  "points_deducted": 1
}
```

#### Edit Mode Response

```json
{
  "success": true,
  "formatted_html": "<div class=\"features-section\">\n  <h1>Powerful Features That Drive Results</h1>\n  <div class=\"feature-list\">\n    <div class=\"feature-item\">\n      <h3>⚡ Lightning Fast Performance</h3>\n      <p>Experience unparalleled speed with our optimized architecture. Your applications load 10x faster, ensuring users stay engaged and conversions increase dramatically.</p>\n    </div>\n    <div class=\"feature-item\">\n      <h3>🔒 Enterprise-Grade Security</h3>\n      <p>Rest easy knowing your data is protected by military-grade encryption and continuous security monitoring. We maintain SOC 2 compliance and conduct regular third-party audits.</p>\n    </div>\n    <div class=\"feature-item\">\n      <h3>🎯 Intuitive User Experience</h3>\n      <p>Our award-winning interface requires zero training. Users can accomplish tasks in half the time compared to competitors, reducing support costs and boosting productivity.</p>\n    </div>\n  </div>\n</div>",
  "ai_explanation": "Rewrote content to be more sales-focused:\n- Changed generic 'Features' to compelling 'Powerful Features That Drive Results'\n- Expanded each feature from single word to detailed benefit statement\n- Added emojis for visual appeal and quick recognition\n- Included specific metrics (10x faster, SOC 2, half the time)\n- Emphasized business outcomes (conversions, cost reduction, productivity)\n- Used power words (unparalleled, military-grade, award-winning)\n- Maintained clean HTML structure with semantic classes",
  "processing_time_ms": 3124,
  "points_deducted": 2
}
```

---

## ⚠️ Error Responses

### 402 Payment Required - Insufficient Points

```json
{
  "detail": {
    "error": "INSUFFICIENT_POINTS",
    "message": "Không đủ điểm để format slide. Cần: 2, Còn: 0",
    "points_needed": 2,
    "points_available": 0
  }
}
```

### 401 Unauthorized - Missing or Invalid Token

```json
{
  "detail": "Invalid authentication credentials"
}
```

### 422 Unprocessable Entity - Invalid Request

```json
{
  "detail": [
    {
      "loc": ["body", "format_type"],
      "msg": "value is not a valid enumeration member; permitted: 'format', 'edit'",
      "type": "type_error.enum"
    }
  ]
}
```

### 500 Internal Server Error - AI Processing Failed

```json
{
  "detail": "AI formatting failed: Gemini API timeout"
}
```

---

## 💰 Pricing

| Mode | Points Cost | AI Model | Use Case |
|------|-------------|----------|----------|
| **Format** | **2 points** | Claude Sonnet 4.5 | Layout improvement, typography, spacing, visual hierarchy |
| **Edit** | **2 points** | Gemini 3 Pro Preview | Content rewriting, expansion, creative writing |

**Why same cost?**
- Both modes use advanced AI models (Claude Sonnet 4.5 / Gemini 3 Pro)
- Both require significant computational resources
- Unified pricing for simplicity (2 points per request)

---

## 🎯 Use Cases

### Format Mode (2 points)

**When to use:**
- ✅ Cải thiện spacing, margins, padding
- ✅ Fix typography hierarchy (h1, h2, p sizing)
- ✅ Better visual alignment
- ✅ Improve readability (line breaks, color contrast)
- ✅ Modernize design aesthetic
- ✅ **GIỮ NGUYÊN nội dung text**

**Example Instructions:**
- "Make it more professional"
- "Improve spacing and alignment"
- "Better visual hierarchy"
- "Modern minimalist design"
- "Increase readability"

### Edit Mode (2 points)

**When to use:**
- ✅ Rewrite content completely
- ✅ Expand bullet points into paragraphs
- ✅ Make content more persuasive/sales-focused
- ✅ Change tone (formal → casual, technical → simple)
- ✅ Translate to different style
- ✅ **THAY ĐỔI nội dung text**

**Example Instructions:**
- "Expand each point with 2-3 sentences"
- "Make it more casual and friendly"
- "Rewrite for C-level executives"
- "Add statistics and data to support claims"
- "Make it more compelling and action-oriented"

---

## 🧠 How AI Processing Works

### Format Mode (Claude Sonnet 4.5)

```
1️⃣ Analyze current slide context
   ├─ HTML structure and content
   ├─ Elements (positions, colors, types)
   ├─ Background (type, colors, overlay)
   └─ User instruction

2️⃣ Apply design principles
   ├─ Visual hierarchy (headings → paragraphs → details)
   ├─ White space optimization
   ├─ Typography best practices
   ├─ Color contrast and readability
   └─ Consistency with existing elements

3️⃣ Generate improvements
   ├─ Formatted HTML with better structure
   ├─ Optional element position suggestions
   ├─ Optional background adjustments
   └─ Explanation of changes

4️⃣ Return result (Temperature: 0.7)
```

### Edit Mode (Gemini 3 Pro Preview)

```
1️⃣ Analyze current content
   ├─ Current HTML text
   ├─ Slide context (index, purpose)
   └─ User instruction

2️⃣ Creative rewriting
   ├─ Understand user intent
   ├─ Generate new content
   ├─ Maintain HTML structure
   ├─ Match requested tone/style
   └─ Preserve key information

3️⃣ Generate new content
   ├─ Rewritten HTML
   ├─ Enhanced messaging
   └─ Explanation of changes

4️⃣ Return result (Temperature: 0.8)
```

---

## 📊 Performance Metrics

### Expected Response Times

| Mode | Avg Time | P95 Time | P99 Time |
|------|----------|----------|----------|
| Format (Claude 4.5) | 1.5s | 3s | 5s |
| Edit (Gemini 3 Pro) | 2.5s | 5s | 8s |

### Success Rates

- Format mode: 98%+ success rate
- Edit mode: 95%+ success rate
- Points check: 100% (cached)

---

## 🔒 Security & Rate Limiting

### Authentication
- Firebase JWT token required
- Token validated on every request
- User ID extracted from token

### Points System
- Check points availability BEFORE AI call
- Deduct points AFTER successful formatting
- Atomic transaction (prevents double-deduction)

### Rate Limiting (Recommended)
```
- Per user: 30 requests/minute
- Per IP: 100 requests/minute
- Burst allowance: 10 requests
```

---

## 🐛 Troubleshooting

### Common Issues

#### Issue 1: "Insufficient points" error

**Symptom:**
```json
{
  "detail": {
    "error": "INSUFFICIENT_POINTS",
    "points_needed": 2,
    "points_available": 0
  }
}
```

**Solution:**
- Purchase more points via `/api/points/purchase`
- Both format and edit modes now cost 2 points

---

#### Issue 2: AI formatting timeout

**Symptom:**
```json
{
  "detail": "AI formatting failed: Gemini API timeout"
}
```

**Solution:**
- Reduce HTML content length
- Simplify complex slides before formatting
- Retry after a few seconds

---

#### Issue 3: Formatted HTML looks broken

**Possible Causes:**
- AI returned invalid HTML structure
- Missing CSS classes on frontend

**Solution:**
- Validate HTML before applying: `DOMParser().parseFromString(html, 'text/html')`
- Show preview modal before auto-applying
- Keep "Undo" button available

---

## 📚 Best Practices

### For Frontend Developers

1. **Always show preview** before applying formatted HTML
2. **Validate HTML** structure before rendering
3. **Handle errors gracefully** with user-friendly messages
4. **Cache user points** to avoid unnecessary API calls
5. **Show loading state** during AI processing (1-5s)
6. **Implement undo/redo** for safety
7. **Log formatting requests** for debugging

### For Users

1. **Start with Format mode** (cheaper, faster)
2. **Use Edit mode** only when rewriting content
3. **Provide specific instructions** for better results
4. **Preview before applying** to avoid wasting points
5. **Keep slides simple** for faster processing

---

## 🎙️ SLIDE NARRATION API

### Overview

2-step flow cho tạo narration tự động cho presentation:

1. **Step 1**: Generate Subtitles (2 points) - Tạo subtitles với timestamps
2. **Step 2**: Generate Audio (2 points) - Convert subtitles thành MP3 audio

**Total Cost**: 4 points (2 + 2) cho complete narration

### Step 1: Generate Subtitles

#### Endpoint

```
POST /api/presentations/{presentation_id}/narration/generate-subtitles
```

#### Request Schema

```typescript
interface SubtitleGenerateRequest {
  presentation_id: string;  // Presentation ID
  mode: "presentation" | "academy";  // Narration mode
  language: "vi" | "en" | "zh";      // Language
  user_query?: string;               // Optional instructions
}
```

**Modes:**
- **presentation**: Concise narration (30-60s per slide, ~150 words/min)
- **academy**: Detailed teaching (60-180s per slide, ~130 words/min)

#### Response Schema

```typescript
interface SubtitleGenerateResponse {
  success: boolean;
  narration_id: string;          // Save for Step 2
  version: number;               // Version number
  slides: SlideSubtitleData[];   // Slides with subtitles
  total_duration: number;        // Total duration (seconds)
  processing_time_ms: number;
  points_deducted: 2;            // Always 2 points
}

interface SlideSubtitleData {
  slide_index: number;
  slide_duration: number;        // Slide duration (seconds)
  subtitles: SubtitleEntry[];
  auto_advance: boolean;
  transition_delay: number;
}

interface SubtitleEntry {
  subtitle_index: number;
  start_time: number;            // Start time (seconds)
  end_time: number;              // End time (seconds)
  duration: number;
  text: string;                  // Subtitle text
  speaker_index: number;         // Speaker (0 for single voice)
  element_references: string[];  // Element IDs referenced
}
```

#### Example Response

```json
{
  "success": true,
  "narration_id": "507f1f77bcf86cd799439099",
  "version": 1,
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
          "text": "Chào mừng đến với bài thuyết trình này.",
          "speaker_index": 0,
          "element_references": []
        },
        {
          "subtitle_index": 1,
          "start_time": 4.0,
          "end_time": 8.2,
          "duration": 4.2,
          "text": "Như bạn thấy trong biểu đồ, quy trình có ba giai đoạn chính.",
          "speaker_index": 0,
          "element_references": ["elem_0"]
        }
      ],
      "auto_advance": true,
      "transition_delay": 2.0
    }
  ],
  "total_duration": 45.8,
  "processing_time_ms": 3200,
  "points_deducted": 2
}
```

---

### Step 2: Generate Audio

#### Endpoint

```
POST /api/presentations/{presentation_id}/narration/{narration_id}/generate-audio
```

#### Request Schema

```typescript
interface AudioGenerateRequest {
  narration_id: string;        // From Step 1
  voice_config: VoiceConfig;
}

interface VoiceConfig {
  provider: "google" | "openai" | "elevenlabs";
  voices: VoiceSettings[];
  use_pro_model: boolean;      // Use premium voices
}

interface VoiceSettings {
  voice_name: string;          // Voice ID
  language: string;            // Language code
  speaking_rate: number;       // 0.5-2.0
  pitch?: number;              // -20.0 to 20.0 (Google only)
}
```

#### Response Schema

```typescript
interface AudioGenerateResponse {
  success: boolean;
  narration_id: string;
  audio_files: AudioFile[];
  total_duration: number;        // Total audio duration (seconds)
  processing_time_ms: number;
  points_deducted: 2;            // Always 2 points
}

interface AudioFile {
  slide_index: number;
  audio_url: string;             // R2 CDN URL
  library_audio_id: string;      // Library audio ID
  file_size: number;             // Bytes
  format: "mp3";
  duration: number;              // Seconds
  speaker_count: number;
}
```

#### Example Response

```json
{
  "success": true,
  "narration_id": "507f1f77bcf86cd799439099",
  "audio_files": [
    {
      "slide_index": 0,
      "audio_url": "https://cdn.r2.com/narr_507f_slide_0.mp3",
      "library_audio_id": "507f1f77bcf86cd799439088",
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

---

### Step 3: List Narration Versions

#### Endpoint

```
GET /api/presentations/{presentation_id}/narrations
```

#### Response Schema

```typescript
interface NarrationListResponse {
  success: boolean;
  narrations: NarrationVersion[];
  total_count: number;
}

interface NarrationVersion {
  narration_id: string;
  version: number;
  status: "subtitles_only" | "completed" | "failed";
  mode: "presentation" | "academy";
  language: string;
  total_duration: number;
  created_at: string;           // ISO datetime
  audio_ready: boolean;
}
```

---

### Narration Pricing

| Step | Operation | Cost | What You Get |
|------|-----------|------|--------------|
| 1 | Generate Subtitles | **2 points** | Subtitles with timestamps, element references |
| 2 | Generate Audio | **2 points** | MP3 audio files uploaded to R2 CDN |

**Total**: 4 points for complete narration (subtitles + audio)

**Note**: You can skip Step 2 if you only need subtitles (e.g., for custom audio recording)

---

### Error Codes

| Status | Error | Description |
|--------|-------|-------------|
| 402 | Insufficient Points | Need 2 points for generation |
| 404 | Presentation Not Found | Invalid presentation ID |
| 404 | Narration Not Found | Invalid narration ID (Step 2) |
| 403 | Forbidden | Not authorized to access resource |
| 400 | Validation Error | Invalid request parameters |
| 500 | AI Error | AI generation failed |

---

### Best Practices

**Subtitle Generation:**
1. Choose mode carefully (presentation vs academy)
2. Provide clear user_query for specific narration style
3. Review subtitles before generating audio
4. Check element_references for animation sync

**Audio Generation:**
1. Use premium voices (use_pro_model: true) for production
2. Adjust speaking_rate based on presentation speed
3. Test voice settings with short slides first
4. Download audio files from R2 URLs for offline use

---

## 🔄 Changelog

### Version 1.1.0 (January 2025)
- ✅ Added Slide Narration API (2-step flow)
- ✅ Gemini 3 Pro Preview for subtitle generation
- ✅ Google TTS Neural2 for audio generation
- ✅ Version management for multiple narrations
- ✅ Element reference tracking for animations

### Version 1.0.0 (December 2024)
- ✅ Initial release
- ✅ Format mode with Claude Sonnet 4.5
- ✅ Edit mode with Gemini 3 Pro Preview
- ✅ Points system integration
- ✅ Element and background suggestions
- ✅ Comprehensive error handling

---

## 📞 Support

**API Issues:**
- Email: support@wordai.vn
- Discord: #api-support

**Documentation:**
- API Docs: https://docs.wordai.vn
- GitHub: https://github.com/wordai/api-docs

---

## 🎯 Future Enhancements

**Planned Features:**
- [ ] Batch formatting (format multiple slides at once)
- [ ] Style presets (corporate, creative, academic, etc.)
- [ ] Multi-speaker narration support
- [ ] Custom voice cloning
- [ ] Subtitle translation
- [ ] A/B testing (generate 2 variations)
- [ ] History tracking (revert to previous versions)
- [ ] Custom AI instructions templates
- [ ] Multi-language support
- [ ] Image element optimization
- [ ] Animation suggestions

---

**Last Updated:** December 21, 2024
**API Version:** 1.0.0
**Status:** ✅ Production Ready
