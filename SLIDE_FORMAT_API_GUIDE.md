# Slide AI Format API - 3 Modes Guide

## Overview

Endpoint `/api/slides/ai-format` giờ hỗ trợ **3 phương án xử lý** linh hoạt:

1. **Single Slide**: Format 1 slide cụ thể (backward compatible)
2. **Multiple Slides**: Format nhiều slides cụ thể
3. **Entire Document**: Format toàn bộ document (all slides)

## Authentication

Tất cả request cần Bearer token trong header:
```
Authorization: Bearer <firebase_id_token>
```

## Points Cost

- **Format mode** (improve layout/design): **2 points per slide**
- **Edit mode** (rewrite content): **2 points per slide**
- **Batch**: Total cost = `số slides × 2 points`

Ví dụ: Format 10 slides = 20 points

---

## Mode 1: Single Slide (Backward Compatible)

**Use case**: Format 1 slide cụ thể (slide hiện tại đang edit)

### Request

```http
POST /api/slides/ai-format
Content-Type: application/json
Authorization: Bearer <token>
```

```json
{
  "slide_index": 2,
  "current_html": "<h1>My Title</h1><p>Content here</p>",
  "elements": [
    {
      "type": "shape",
      "position": {"x": 100, "y": 200, "width": 300, "height": 50},
      "properties": {"color": "#667eea", "borderRadius": 12}
    }
  ],
  "background": {
    "type": "gradient",
    "gradient": {
      "type": "linear",
      "colors": ["#667eea", "#764ba2"]
    },
    "overlayOpacity": 0.15
  },
  "user_instruction": "Make it more professional",
  "format_type": "format"
}
```

### Response

```json
{
  "job_id": "abc123-def456-ghi789",
  "status": "pending",
  "message": "Slide format job queued. Poll /api/slides/jobs/abc123-def456-ghi789 for status.",
  "estimated_time": "30-120 seconds"
}
```

---

## Mode 2: Multiple Specific Slides

**Use case**: Format nhiều slides cụ thể (user chọn slides 0, 3, 7)

### Request

```json
{
  "slides_data": [
    {
      "slide_index": 0,
      "current_html": "<h1>Slide 1</h1>",
      "elements": [],
      "background": null
    },
    {
      "slide_index": 3,
      "current_html": "<h1>Slide 4</h1><ul><li>Point 1</li></ul>",
      "elements": [],
      "background": {"type": "color", "value": "#ffffff"}
    },
    {
      "slide_index": 7,
      "current_html": "<h1>Slide 8</h1>",
      "elements": [],
      "background": null
    }
  ],
  "user_instruction": "Make all slides consistent",
  "format_type": "format"
}
```

**Note**: Mỗi slide trong `slides_data` ĐÃ có HTML riêng (không cần split ở backend)

### Response

```json
{
  "job_id": "batch-xyz-123",
  "status": "pending",
  "message": "Batch job queued: 3 slide(s). Poll /api/slides/jobs/batch-xyz-123 for status.",
  "estimated_time": "90-360 seconds"
}
```

---

## Mode 3: Entire Document (All Slides)

**Use case**: Format toàn bộ presentation (scope === 'document')

### Request

```json
{
  "process_all_slides": true,
  "slides_data": [
    {
      "slide_index": 0,
      "current_html": "<h1>Slide 1</h1>",
      "elements": [],
      "background": null
    },
    {
      "slide_index": 1,
      "current_html": "<h1>Slide 2</h1>",
      "elements": [],
      "background": null
    },
    {
      "slide_index": 2,
      "current_html": "<h1>Slide 3</h1>",
      "elements": [],
      "background": null
    }
    // ... all slides
  ],
  "user_instruction": "Apply modern design to entire presentation",
  "format_type": "format"
}
```

**Important**:
- `process_all_slides: true` là marker cho Mode 3
- `slides_data` phải chứa **TẤT CẢ slides** trong document
- Mỗi slide ĐÃ có HTML riêng (backend không cần split)

---

## Polling Job Status

### Single Slide Job

```http
GET /api/slides/jobs/{job_id}
Authorization: Bearer <token>
```

**Response (Completed)**:
```json
{
  "job_id": "abc123",
  "status": "completed",
  "created_at": "2024-01-15T10:00:00Z",
  "started_at": "2024-01-15T10:00:02Z",
  "completed_at": "2024-01-15T10:00:45Z",
  "processing_time_seconds": 43.2,
  "is_batch": false,
  "formatted_html": "<h1 style=\"font-size: 48px; font-weight: 700; margin-bottom: 24px;\">My Title</h1>...",
  "suggested_elements": [
    {
      "type": "shape",
      "position": {"x": 100, "y": 200, "width": 300, "height": 50},
      "properties": {"color": "#667eea"}
    }
  ],
  "suggested_background": {
    "type": "gradient",
    "gradient": {"type": "linear", "colors": ["#667eea", "#764ba2"]}
  },
  "ai_explanation": "Improved typography hierarchy by increasing h1 size to 48px...",
  "error": null
}
```

### Batch Job

**Response (Processing)**:
```json
{
  "job_id": "batch-xyz-123",
  "status": "processing",
  "created_at": "2024-01-15T10:00:00Z",
  "started_at": "2024-01-15T10:00:05Z",
  "is_batch": true,
  "total_slides": 10,
  "completed_slides": 7,
  "failed_slides": 0,
  "slides_results": [
    {
      "slide_index": 0,
      "formatted_html": "<h1>...</h1>",
      "suggested_elements": [],
      "suggested_background": null,
      "ai_explanation": "...",
      "error": null
    },
    {
      "slide_index": 1,
      "formatted_html": "<h1>...</h1>",
      "suggested_elements": [],
      "suggested_background": null,
      "ai_explanation": "...",
      "error": null
    }
    // ... 7 results so far, 3 still processing
  ]
}
```

**Response (Completed)**:
```json
{
  "job_id": "batch-xyz-123",
  "status": "completed",
  "created_at": "2024-01-15T10:00:00Z",
  "started_at": "2024-01-15T10:00:05Z",
  "completed_at": "2024-01-15T10:03:20Z",
  "processing_time_seconds": 195.0,
  "is_batch": true,
  "total_slides": 10,
  "completed_slides": 9,
  "failed_slides": 1,
  "slides_results": [
    {
      "slide_index": 0,
      "formatted_html": "<h1>...</h1>",
      "suggested_elements": [],
      "ai_explanation": "...",
      "error": null
    },
    // ... 8 more successful results
    {
      "slide_index": 5,
      "formatted_html": null,
      "suggested_elements": null,
      "ai_explanation": null,
      "error": "AI service timeout"
    }
  ]
}
```

---

## Frontend Implementation Examples

### Example 1: Format Current Slide (Mode 1)

```typescript
async function formatCurrentSlide(slideIndex: number, html: string) {
  const response = await fetch('/api/slides/ai-format', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${firebaseToken}`
    },
    body: JSON.stringify({
      slide_index: slideIndex,
      current_html: html,
      elements: currentSlideElements,
      background: currentSlideBackground,
      user_instruction: userPrompt,
      format_type: 'format'
    })
  });

  const { job_id } = await response.json();

  // Poll for result
  const result = await pollJobStatus(job_id);

  // Apply result
  updateSlideHTML(slideIndex, result.formatted_html);
}
```

### Example 2: Format Selected Slides (Mode 2)

```typescript
async function formatSelectedSlides(selectedIndices: number[], allSlides: Slide[]) {
  const slides_data = selectedIndices.map(index => ({
    slide_index: index,
    current_html: allSlides[index].html,
    elements: allSlides[index].elements || [],
    background: allSlides[index].background || null
  }));

  const response = await fetch('/api/slides/ai-format', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${firebaseToken}`
    },
    body: JSON.stringify({
      slides_data,
      user_instruction: userPrompt,
      format_type: 'format'
    })
  });

  const { job_id } = await response.json();

  // Poll for batch result
  const result = await pollJobStatus(job_id);

  // Apply results
  result.slides_results.forEach(slideResult => {
    if (slideResult.formatted_html) {
      updateSlideHTML(slideResult.slide_index, slideResult.formatted_html);
    }
  });
}
```

### Example 3: Format Entire Document (Mode 3)

```typescript
async function formatEntireDocument(allSlides: Slide[]) {
  const slides_data = allSlides.map((slide, index) => ({
    slide_index: index,
    current_html: slide.html,
    elements: slide.elements || [],
    background: slide.background || null
  }));

  const response = await fetch('/api/slides/ai-format', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${firebaseToken}`
    },
    body: JSON.stringify({
      process_all_slides: true,
      slides_data,
      user_instruction: userPrompt,
      format_type: 'format'
    })
  });

  const { job_id } = await response.json();

  // Poll with progress tracking
  let lastCompletedCount = 0;
  const intervalId = setInterval(async () => {
    const status = await fetch(`/api/slides/jobs/${job_id}`, {
      headers: { 'Authorization': `Bearer ${firebaseToken}` }
    }).then(r => r.json());

    // Update progress
    if (status.completed_slides > lastCompletedCount) {
      console.log(`Progress: ${status.completed_slides}/${status.total_slides}`);
      lastCompletedCount = status.completed_slides;
    }

    if (status.status === 'completed') {
      clearInterval(intervalId);

      // Apply all results
      status.slides_results.forEach(result => {
        if (result.formatted_html) {
          updateSlideHTML(result.slide_index, result.formatted_html);
        }
      });
    }
  }, 3000); // Poll every 3 seconds
}
```

---

## Error Handling

### Insufficient Points

```json
{
  "detail": {
    "error": "INSUFFICIENT_POINTS",
    "message": "Không đủ điểm để format 10 slide(s). Cần: 20, Còn: 5",
    "points_needed": 20,
    "points_available": 5,
    "slides_count": 10
  }
}
```

### Invalid Request

```json
{
  "detail": "Invalid request. Provide either: (slide_index + current_html) OR slides_data array"
}
```

### Job Failed

```json
{
  "job_id": "abc123",
  "status": "failed",
  "error": "AI service timeout after 120 seconds"
}
```

---

## Performance Notes

- **Single slide**: 30-120 seconds
- **Batch processing**: Slides xử lý **song song** (parallel)
  - 10 slides ~ 30-120 seconds (not 300-1200!)
  - Workers pull tasks từ Redis queue concurrently
- **Rate limiting**: 4 worker containers, mỗi worker 1 task/time = 4 slides parallel max

---

## Migration Guide (Old → New)

### Old Code (Chỉ hỗ trợ 1 slide)

```typescript
// ❌ Old: scope === 'document' nhưng chỉ gửi slide_index: 1
const response = await fetch('/api/slides/ai-format', {
  body: JSON.stringify({
    slide_index: 1, // Chỉ slide đầu tiên!
    current_html: allSlidesHTML, // HTML của tất cả slides ghép lại
    format_type: 'format'
  })
});
```

### New Code (Hỗ trợ 3 modes)

```typescript
// ✅ New: Phân biệt scope
if (scope === 'current') {
  // Mode 1: Single slide
  await formatCurrentSlide(currentSlideIndex, currentSlideHTML);

} else if (scope === 'selection') {
  // Mode 2: Multiple specific slides
  await formatSelectedSlides(selectedIndices, allSlides);

} else if (scope === 'document') {
  // Mode 3: Entire document
  await formatEntireDocument(allSlides);
}
```

---

## FAQ

**Q: Frontend cần split HTML cho từng slide không?**

A: KHÔNG! Backend giả định mỗi slide trong `slides_data` ĐÃ có HTML riêng. Frontend đã lưu từng slide với HTML riêng trong database/state rồi.

**Q: Có thể format 100 slides cùng lúc không?**

A: Có thể, nhưng:
- Cost = 200 points
- Time ~ 30-120 seconds (parallel processing)
- Giới hạn 4 workers = max 4 slides xử lý cùng lúc

**Q: Batch job fail 1 slide thì các slide khác sao?**

A: Các slide khác vẫn xử lý bình thường. Response có:
- `completed_slides`: Số slides thành công
- `failed_slides`: Số slides lỗi
- `slides_results[]`: Mỗi slide có field `error` nếu fail

**Q: Có cần thay đổi database schema không?**

A: KHÔNG. Backend chỉ nhận HTML từ frontend, xử lý, trả về HTML formatted. Frontend tự quyết định lưu như nào.
