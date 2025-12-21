# Slide AI Formatting API Documentation

## 📖 Overview

API endpoint cho tính năng **AI-powered slide formatting and editing**. Cho phép người dùng cải thiện slide tự động với AI, bao gồm:

- ✅ **Format Mode**: Cải thiện layout, typography, visual hierarchy (giữ nguyên nội dung)
- ✅ **Edit Mode**: Viết lại nội dung theo yêu cầu của người dùng
- ✅ **Context-Aware**: AI phân tích toàn bộ slide (HTML + Elements + Background)
- ✅ **Smart Suggestions**: Gợi ý di chuyển elements và thay đổi background (optional)

### 🤖 AI Models Used

| Mode | AI Model | Purpose | Strengths |
|------|----------|---------|-----------|
| **Edit** | **Gemini 3 Pro Preview** | Content rewriting & creation | Tốt nhất cho creative writing, rewriting nội dung phức tạp |
| **Format** | **Claude Sonnet 4.5** | Layout & design optimization | Tốt nhất cho design thinking, visual hierarchy, formatting |

**Lý do chọn model:**
- **Edit Mode**: Gemini 3 Pro có khả năng creative writing tốt hơn, hiểu context sâu hơn → Phù hợp cho viết lại nội dung
- **Format Mode**: Claude Sonnet 4.5 có khả năng phân tích design, spacing, typography tốt hơn → Phù hợp cho cải thiện layout

---

## 🔗 Endpoint

```
POST /api/slides/ai-format
```

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

## 🔄 Changelog

### Version 1.0.0 (December 2024)
- ✅ Initial release
- ✅ Format mode with Claude 3.5 Sonnet
- ✅ Edit mode with Gemini 2.0 Pro 3 Preview
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
