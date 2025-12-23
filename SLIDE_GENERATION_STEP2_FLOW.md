# Slide Generation Step 2 - Complete Flow Documentation

**Last Updated:** December 23, 2025
**Purpose:** Document Step 2 workflow with outline management, retry mechanism, and style consistency

---

## 📋 Overview

Step 2 generates HTML slides from the outline created in Step 1. Key features:
- **Batch processing**: 8 slides per batch to avoid Claude token limits
- **Streaming**: Real-time Claude API streaming for progress updates
- **Style consistency**: First slide passed as reference to subsequent batches
- **Outline storage**: Saved in MongoDB for retry and editing
- **Partial save**: Failed generations save partial slides + outline for retry

---

## 🔄 Complete Workflow

### Step 1: Analysis (Gemini)
```
User Input → Gemini API → Slide Outline (25 slides)
                        ↓
                MongoDB: slides_analysis collection
                        ↓
                Return: analysis_id
```

### Step 2: HTML Generation (Claude)

```
1. User submits analysis_id
   ↓
2. Check points (4 points for 25 slides)
   ↓
3. Create document in MongoDB (status: pending)
   ↓
4. Enqueue task to Redis (slide_generation_queue)
   ↓
5. Worker picks up task
   ↓
6. Load outline from analysis
   ↓
7. Generate in batches:

   Batch 1 (slides 0-7):
   - Claude generates with streaming
   - Save slide 1 as style reference
   - Update Redis: 33% progress

   Batch 2 (slides 8-15):
   - Pass slide 1 sample for style consistency
   - Claude generates matching style
   - Update Redis: 66% progress

   Batch 3 (slides 16-23):
   - Same style reference
   - Update Redis: 100% progress

   ↓
8. Success: Save all slides + outline to MongoDB
   OR
   Failed: Save partial slides + outline to MongoDB
   ↓
9. Update Redis status (completed/failed)
   ↓
10. Deduct points (only if successful)
```

---

## 🗄️ MongoDB Schema

### Document Structure

```javascript
{
  _id: ObjectId("..."),
  document_id: "doc_124bf7056e8e",
  user_id: "17BeaeikPBQYk8OWeDUkqm0Ov8e2",
  title: "Giới thiệu về Ethereum",
  document_type: "slide",

  // ✅ NEW: Slide-specific fields
  content_html: "<div class=\"slide\">...</div>\n\n<div class=\"slide\">...</div>",  // All slides concatenated
  slide_backgrounds: [...],  // Background info
  slides_outline: [  // ⭐ NEW: Saved outline for retry/editing
    {
      slide_number: 1,
      title: "Slide Title",
      content_points: ["Point 1", "Point 2"],
      visual_suggestions: "Charts, icons",
      image_suggestion: "Blockchain diagram",
      duration_seconds: 60
    },
    // ... 24 more slides
  ],
  outline_id: "694a82b00cca6c6ded5df372",  // ⭐ NEW: Reference to original analysis (optional)

  // Status tracking (in Redis, not MongoDB)
  // generation_status: "pending" | "processing" | "completed" | "failed"

  created_at: ISODate("2025-12-23T11:53:43.000Z"),
  last_saved_at: ISODate("2025-12-23T11:58:12.000Z"),
  is_deleted: false
}
```

### Redis Job Status

```javascript
{
  job_id: "doc_124bf7056e8e",
  document_id: "doc_124bf7056e8e",
  user_id: "17BeaeikPBQYk8OWeDUkqm0Ov8e2",
  status: "completed" | "processing" | "pending" | "failed",
  title: "Presentation Title",

  // Progress tracking
  progress_percent: 66,
  batches_completed: 2,
  total_batches: 3,

  // ⭐ NEW: Retry information
  slides_generated: 13,  // Actual slides saved
  slides_expected: 25,   // Total slides from outline
  can_retry: true,       // Flag for frontend to show retry button

  // Timestamps
  started_at: "2025-12-23T11:53:43Z",
  updated_at: "2025-12-23T11:55:30Z",
  completed_at: "2025-12-23T11:58:12Z",

  // Error info (if failed)
  error: "Generated 13/25 slides. Claude timeout..."
}
```

---

## 🔌 API Endpoints

### 1. Create Slides (Step 2)

**POST** `/api/slides/ai-generate/create`

```json
{
  "analysis_id": "694a82b00cca6c6ded5df372",
  "logo_url": "https://example.com/logo.png",  // optional
  "slide_images": [  // optional
    {
      "slide_number": 5,
      "image_url": "https://example.com/image.png"
    }
  ]
}
```

**Response:**
```json
{
  "document_id": "doc_124bf7056e8e",
  "poll_url": "/api/slides/ai-generate/status/doc_124bf7056e8e",
  "title": "Giới thiệu về Ethereum",
  "num_slides": 25,
  "points_deducted": 4,
  "message": "Slide generation started. Poll status endpoint."
}
```

---

### 2. Poll Status (Real-time Progress)

**GET** `/api/slides/ai-generate/status/{document_id}`

**Response (Processing):**
```json
{
  "document_id": "doc_124bf7056e8e",
  "status": "processing",
  "progress_percent": 66,
  "message": "Generating slides... (66% complete, batch 2/3)",
  "num_slides": 25,
  "title": "Giới thiệu về Ethereum",
  "created_at": "2025-12-23T11:53:43Z",
  "updated_at": "2025-12-23T11:55:30Z"
}
```

**Response (Failed - Partial):**
```json
{
  "document_id": "doc_124bf7056e8e",
  "status": "failed",
  "progress_percent": 52,
  "error_message": "Generated 13/25 slides. Claude timeout...",
  "message": "Slide generation failed: Generated 13/25 slides...",
  "slides_generated": 13,
  "slides_expected": 25,
  "can_retry": true,  // ⭐ Show retry button
  "num_slides": 13,
  "title": "Giới thiệu về Ethereum"
}
```

**Response (Completed):**
```json
{
  "document_id": "doc_124bf7056e8e",
  "status": "completed",
  "progress_percent": 100,
  "message": "Successfully generated 25 slides!",
  "num_slides": 25,
  "title": "Giới thiệu về Ethereum",
  "completed_at": "2025-12-23T11:58:12Z"
}
```

---

### 3. ⭐ NEW: Get Slide with Outline Reference

**GET** `/api/documents/{document_id}`

**Response:**
```json
{
  "document_id": "doc_124bf7056e8e",
  "title": "Giới thiệu về Ethereum",
  "document_type": "slide",
  "content_html": "<div class=\"slide\">...</div>...",
  "version": 1,
  "last_saved_at": "2025-12-23T11:58:12Z",
  "file_size_bytes": 245678,
  "auto_save_count": 0,
  "manual_save_count": 1,
  "source_type": "created",
  "file_id": null,
  "slide_elements": [...],
  "slide_backgrounds": [...],
  "slides_outline": [  // ⭐ Outline array (only for slide documents)
    {
      "slide_number": 1,
      "title": "Mục lục",
      "content_points": ["Point 1", "Point 2"],
      "suggested_visuals": ["Icons", "List"],
      "image_suggestion": "Ethereum logo",
      "estimated_duration": 60,
      "image_url": null
    },
    // ... 24 more slides
  ],
  "outline_id": "694a82b00cca6c6ded5df372",  // ⭐ Reference to analysis
  "has_outline": true  // ⭐ Frontend shows "View Outline" button if true
}
```

**Frontend Usage:**
```javascript
const doc = await fetch('/api/documents/doc_124bf7056e8e').then(r => r.json());

if (doc.has_outline) {
  // Show "View Outline" or "Edit Outline" button
  showOutlineButton(doc.document_id);
}
```

---

### 4. ⭐ NEW: Get Outline for Viewing/Retry

**GET** `/api/slides/ai-generate/documents/{document_id}/outline`

**Purpose:**
- View outline that was used to generate slides
- Check if can retry (partial generation)
- Display outline to user before editing

**Response:**
```json
{
  "document_id": "doc_124bf7056e8e",
  "title": "Giới thiệu về Ethereum",
  "slides_outline": [
    {
      "slide_number": 1,
      "title": "Mục lục",
      "content_points": [
        "Blockchain là gì?",
        "Smart Contract hoạt động thế nào?",
        "Ứng dụng thực tế"
      ],
      "visual_suggestions": "List with icons",
      "image_suggestion": "Ethereum logo",
      "duration_seconds": 60
    },
    // ... 24 more slides
  ],
  "slides_generated": 25,  // Current slides in document
  "slides_expected": 25,   // Total from outline
  "can_retry": false,      // All slides generated
  "can_edit": true,        // User can edit outline
  "outline_id": "694a82b00cca6c6ded5df372"
}
```

**Use Cases:**
1. **View outline**: Frontend displays in modal/panel
2. **Check retry**: If `can_retry=true`, show "Retry Generation" button
3. **Edit outline**: Frontend enables edit mode → PUT endpoint

---

### 5. ⭐ IMPLEMENTED: Edit Outline

**PUT** `/api/slides/ai-generate/documents/{document_id}/outline`

**Purpose:**
- Allow user to edit outline before regenerating
- Useful when partial generation failed
- User can adjust content/structure

**Request Body:**
```json
{
  "slides_outline": [
    {
      "slide_number": 1,
      "title": "Updated Title",  // User edited
      "content_points": [
        "New point 1",
        "New point 2"
      ],
      "suggested_visuals": ["Updated visuals"],
      "image_suggestion": "New image idea",
      "estimated_duration": 90,  // User changed
      "image_url": null
    },
    // ... rest of slides (must maintain same count)
  ]
}
```

**Response:**
```json
{
  "success": true,
  "message": "Outline updated successfully (25 slides)",
  "document_id": "doc_124bf7056e8e",
  "slides_count": 25,
  "updated_at": "2025-12-23T12:05:00Z"
}
```

**Validation:**
- ✅ User must own document
- ✅ Cannot edit if generation is in progress (status=processing)
- ✅ Must maintain slide count (can't change from 25 to 10)
- ✅ Slide numbers must be sequential (1, 2, 3, ...)

**Error Responses:**
```json
// Document not found or no access
{
  "detail": "Document not found or you don't have access"
}

// Generation in progress
{
  "detail": "Cannot edit outline while generation is in progress. Please wait for completion or cancellation."
}

// Slide count mismatch
{
  "detail": "Slide count mismatch. Current: 25, New: 20. Cannot add or remove slides."
}

// Invalid slide numbers
{
  "detail": "Slide numbers must be sequential 1-25, got [1, 2, 5, 6, ...]"
}
```

---

### 6. ⭐ NEW: Retry Generation from Outline

**POST** `/api/slides/ai-generate/documents/{document_id}/retry`

**Purpose:**
- Retry failed generation using saved outline
- Use edited outline if user modified it
- Don't deduct points again (already paid)

**Request Body:**
```json
{
  "use_edited_outline": true,  // Use current outline or original?
  "regenerate_all": false      // false = continue from partial, true = start over
}
```

**Response:**
```json
{
  "success": true,
  "message": "Retry started. Continue from slide 14.",
  "document_id": "doc_124bf7056e8e",
  "poll_url": "/api/slides/ai-generate/status/doc_124bf7056e8e",
  "slides_to_generate": 12,    // Remaining slides
  "total_slides": 25,
  "points_deducted": 0         // No additional charge for retry
}
```

**Flow:**
1. Load outline from document
2. If `regenerate_all=false`: Start from slide 14 (after last successful)
3. If `regenerate_all=true`: Delete all slides, start from slide 0
4. Enqueue to Redis queue
5. Worker continues batch generation

---

## 🎨 Style Consistency Mechanism

### Problem
When generating 25 slides in 3 batches, each batch is independent. Batch 2 doesn't know what Batch 1 looks like → inconsistent styles (different backgrounds, colors, fonts).

### Solution: Pass First Slide as Style Reference

**Step 1: Batch 1 Generates Slides 0-7**
```python
batch_1_html = claude.generate([slide_0, slide_1, ..., slide_7])
first_slide_sample = batch_1_html[1]  # Save slide 1 (TOC) as reference
```

**Step 2: Batch 2 Uses Style Reference**
```python
batch_2_html = claude.generate(
    slides=[slide_8, ..., slide_15],
    first_slide_sample=first_slide_sample  # ⭐ Pass slide 1 HTML
)
```

**Prompt Injection:**
```
CRITICAL - STYLE CONSISTENCY:
This is batch 2 of 3. You MUST maintain the EXACT SAME visual style as the previous batch.

Here is a sample slide from batch 1 for reference:
```html
<div class="slide" style="background: #0f172a; ...">
  <h2 style="color: #ffffff; font-size: 48px; ...">Mục lục</h2>
  ...
</div>
```

EXTRACT AND REPLICATE:
- Background color: #0f172a (MUST be identical)
- Text colors: #ffffff, #f7fafc
- Font sizes: h2=48px, p=32px
- Layout spacing: padding: 4rem
- Slide number: top-right, opacity 0.6

DO NOT change the visual style - only the content should be different!
```

**Result:**
- ✅ All 25 slides have same background (#0f172a)
- ✅ Same text colors (#ffffff)
- ✅ Same font sizes
- ✅ Consistent layout spacing
- ✅ Professional, unified presentation

---

## ⚡ Streaming & Performance

### Claude Streaming API

**Before (No Streaming):**
```python
response = claude.messages.create(...)
html_output = response.content[0].text  # Wait for full response (10+ minutes)
```

**Problem:** 10-minute timeout, no progress updates, frontend shows nothing

**After (With Streaming):**
```python
html_output = ""
with claude.messages.stream(...) as stream:
    for text in stream.text_stream:
        html_output += text  # Receive real-time chunks
        # Can update Redis here for real-time progress
```

**Benefits:**
- ✅ No 10-minute timeout (connection stays alive)
- ✅ Real-time text streaming
- ✅ Can update progress more frequently
- ✅ Better user experience

### Configuration

```python
max_tokens = 36864  # 36K tokens (reduced from 64K)
# 1 slide ≈ 2000-3000 tokens
# 8 slides ≈ 16000-24000 tokens
# 36K gives buffer + faster than 64K

temperature = 0.8   # Creative but consistent
timeout = 1800.0    # 30 minutes (no rush)
```

**Why 8 slides per batch?**
- 15 slides = ~45K tokens → risk hitting limit
- 10 slides = ~30K tokens → safer but still risky
- 8 slides = ~24K tokens → safe margin + faster

---

## 🔄 Retry Workflow Example

### Scenario: Partial Generation Failure

**Initial Generation:**
```
Step 1: Analyze → 25 slides outline ✅
Step 2: Create slides
  Batch 1 (slides 0-7): ✅ Success
  Batch 2 (slides 8-15): ❌ Failed (Claude timeout)

Result: 8 slides saved, outline saved
Status: Failed, can_retry=true
```

**Frontend Display:**
```
┌────────────────────────────────────────┐
│ ⚠️ Generation Partially Failed        │
│                                        │
│ 8 of 25 slides generated               │
│                                        │
│ [View Partial Slides] [Retry]         │
└────────────────────────────────────────┘
```

**User Clicks "Retry":**
```
1. GET /documents/{id}/outline
   → Shows outline (user can edit if needed)

2. User optionally edits outline
   PUT /documents/{id}/outline
   → Save changes

3. User clicks "Retry Generation"
   POST /documents/{id}/retry
   {
     "use_edited_outline": true,
     "regenerate_all": false
   }

4. Worker resumes:
   - Loads outline (edited or original)
   - Starts from Batch 2 (slides 8-15)
   - Uses slide 1 style reference
   - Generates remaining slides

5. Success: All 25 slides complete ✅
   No additional points charged
```

---

## 🎯 Frontend Integration Guide

### 1. Create Slides Flow

```javascript
// Step 1: Submit analysis_id
const response = await fetch('/api/slides/ai-generate/create', {
  method: 'POST',
  body: JSON.stringify({
    analysis_id: '694a82b00cca6c6ded5df372',
    logo_url: 'https://...',
    slide_images: []
  })
});

const { document_id, poll_url } = await response.json();

// Step 2: Poll status every 3 seconds
const pollInterval = setInterval(async () => {
  const statusRes = await fetch(`/api/slides/ai-generate/status/${document_id}`);
  const status = await statusRes.json();

  // Update progress bar
  updateProgress(status.progress_percent);
  updateMessage(status.message);

  if (status.status === 'completed') {
    clearInterval(pollInterval);
    showSuccess('Slides generated!');
    loadSlides(document_id);
  }

  if (status.status === 'failed') {
    clearInterval(pollInterval);

    if (status.can_retry) {
      showRetryOption(document_id, status.slides_generated, status.slides_expected);
    } else {
      showError(status.error_message);
    }
  }
}, 3000);
```

### 2. View Outline Button

```javascript
// When displaying document
async function loadDocument(documentId) {
  const res = await fetch(`/api/documents/${documentId}`);
  const doc = await res.json();

  // Show outline button if available
  if (doc.has_outline) {
    showOutlineButton(documentId);
  }
}

// When user clicks "View Outline"
async function viewOutline(documentId) {
  const res = await fetch(`/api/slides/ai-generate/documents/${documentId}/outline`);
  const data = await res.json();

  showOutlineModal({
    title: data.title,
    slides: data.slides_outline,
    canEdit: data.can_edit,
    canRetry: data.can_retry
  });
}
```

### 3. Edit Outline Modal

```javascript
function OutlineEditor({ documentId, outline }) {
  const [editedOutline, setEditedOutline] = useState(outline);

  async function saveOutline() {
    await fetch(`/api/slides/ai-generate/documents/${documentId}/outline`, {
      method: 'PUT',
      body: JSON.stringify({
        slides_outline: editedOutline
      })
    });

    showSuccess('Outline updated!');
  }

  return (
    <div>
      {editedOutline.map((slide, index) => (
        <SlideOutlineEditor
          key={index}
          slide={slide}
          onChange={(updated) => updateSlide(index, updated)}
        />
      ))}
      <button onClick={saveOutline}>Save Changes</button>
    </div>
  );
}
```

### 4. Retry Failed Generation

```javascript
async function retryGeneration(documentId) {
  // Option 1: Show edit outline first
  const edited = await showEditOutlineModal(documentId);

  // Option 2: Retry with current outline
  const res = await fetch(`/api/slides/ai-generate/documents/${documentId}/retry`, {
    method: 'POST',
    body: JSON.stringify({
      use_edited_outline: edited,
      regenerate_all: false  // Continue from partial
    })
  });

  const { poll_url } = await res.json();

  // Start polling again
  pollStatus(documentId);
}
```

---

## 📊 Error Handling

### Common Errors

**1. Claude Timeout (10-minute default)**
```
Error: "Streaming is required for operations that may take longer than 10 minutes"
Solution: ✅ Streaming enabled, timeout=1800s (30min)
```

**2. Token Limit Exceeded**
```
Error: "Claude generated 5/8 slides"
Cause: max_tokens too low or batch too large
Solution: ✅ Reduced batch size to 8, max_tokens=36K
```

**3. Inconsistent Styles**
```
Error: Each batch has different background colors
Cause: No style reference between batches
Solution: ✅ Pass first_slide_sample to subsequent batches
```

**4. Lost Outline on Failure**
```
Error: Can't retry - outline not saved
Solution: ✅ Save outline to MongoDB on every generation
```

### Partial Save Logic

```python
try:
    # Generate batch
    batch_html = await generate_batch(...)
    all_slides.extend(batch_html)

except Exception as error:
    # Save partial slides instead of discarding
    if all_slides:
        save_partial_slides(
            document_id=document_id,
            slides_html=all_slides,
            slides_outline=full_outline,  # Save for retry
            error=str(error)
        )

    # Update Redis: failed but can retry
    update_status(
        status='failed',
        can_retry=True,
        slides_generated=len(all_slides),
        slides_expected=len(full_outline)
    )
```

---

## 🔐 Security & Permissions

### Outline Access Control

```python
@router.get("/documents/{document_id}/outline")
async def get_outline(document_id: str, user_info: dict = Depends(require_auth)):
    doc = db.documents.find_one({
        "document_id": document_id,
        "user_id": user_info["uid"],  # ✅ User must own document
        "is_deleted": False
    })

    if not doc:
        raise HTTPException(status_code=404, detail="Not found or no access")

    return doc["slides_outline"]
```

### Outline Edit Validation

```python
@router.put("/documents/{document_id}/outline")
async def update_outline(
    document_id: str,
    request: UpdateOutlineRequest,
    user_info: dict = Depends(require_auth)
):
    # 1. Check ownership
    doc = db.documents.find_one({
        "document_id": document_id,
        "user_id": user_info["uid"]
    })

    # 2. Check not in progress
    status = redis.hget(f"job:{document_id}", "status")
    if status == "processing":
        raise HTTPException(400, detail="Cannot edit during generation")

    # 3. Validate slide count
    if len(request.slides_outline) != len(doc["slides_outline"]):
        raise HTTPException(400, detail="Cannot change slide count")

    # 4. Update outline
    db.documents.update_one(
        {"document_id": document_id},
        {"$set": {"slides_outline": request.slides_outline}}
    )

    return {"success": True}
```

---

## 📈 Monitoring & Logging

### Worker Logs

```
🔄 Batch 1/3: slides 1-8
🌊 Starting Claude streaming for batch 1/3...
✅ HTML streaming completed: 18542 chars
✅ Parsed 8 slides from batch
📌 Saved slide 1 as style reference for subsequent batches
✅ Batch 1/3 completed (33%)

🔄 Batch 2/3: slides 9-16
🎨 Using style reference from batch 1
🌊 Starting Claude streaming for batch 2/3...
✅ HTML streaming completed: 17893 chars
✅ Parsed 8 slides from batch
✅ Batch 2/3 completed (66%)

🔄 Batch 3/3: slides 17-25
🎨 Using style reference from batch 1
🌊 Starting Claude streaming for batch 3/3...
✅ HTML streaming completed: 15234 chars
✅ Parsed 9 slides from batch
✅ Batch 3/3 completed (100%)

✅ All slides generated. Total: 25
💾 Saved outline to MongoDB for retry/editing
💰 Deducted 4 points from user
```

### Redis Status Updates

```
11:53:43 - Status: pending (0%)
11:53:50 - Status: processing (5%) - "Starting batch 1..."
11:55:20 - Status: processing (33%) - "Batch 1/3 completed"
11:56:45 - Status: processing (66%) - "Batch 2/3 completed"
11:58:10 - Status: processing (95%) - "Batch 3/3 completed"
11:58:12 - Status: completed (100%) - "Successfully generated 25 slides!"
```

---

## 🧪 Testing Scenarios

### Test Case 1: Full Success
```
Input: 25 slides outline
Expected: All 25 slides generated, outline saved, status=completed
Points: 4 deducted
```

### Test Case 2: Partial Failure
```
Input: 25 slides outline
Batch 1: Success (8 slides)
Batch 2: Failed (timeout)
Expected: 8 slides saved, outline saved, status=failed, can_retry=true
Points: 0 deducted (failed before completion)
```

### Test Case 3: Retry After Edit
```
1. Generate 25 slides → Partial failure (8 slides)
2. User edits outline (fixes content)
3. Retry generation
Expected: Continues from slide 9, uses edited outline, completes 25 slides
Points: 0 additional (already paid)
```

### Test Case 4: Style Consistency
```
Input: 25 slides (3 batches)
Expected:
  - Batch 1: Dark theme (#0f172a)
  - Batch 2: Same dark theme (via style reference)
  - Batch 3: Same dark theme
Result: All slides visually consistent
```

---

## 📚 Related Documentation

- **Question Types**: See `QUESTION_TYPES_JSON_SCHEMA.md`
- **System Reference**: See `SYSTEM_REFERENCE.md`
- **Step 1 Analysis**: See API docs `/docs#/Slide AI Generation/analyze_slide_requirements`
- **Redis Queue**: See `src/queue/queue_manager.py`
- **Worker Logic**: See `src/workers/slide_generation_worker.py`

---

**End of Documentation**
