# Save Outline Only Endpoint

## Overview
New FREE endpoint that saves analysis outline as empty document for later AI generation.

## Endpoint
```
POST /api/slides/ai-generate/save-outline-only
```

## Use Case
Users can save outline from Step 1 without immediate HTML generation:
1. Review/edit outline before AI generation
2. Decide later whether to use AI or manual editing
3. No upfront cost (FREE endpoint)
4. Faster initial save (no AI processing delay)

## Request Body
```json
{
  "analysis_id": "67a1234567890abcdef12345",
  "creator_name": "John Doe" // optional
}
```

## Response
```json
{
  "success": true,
  "document_id": "doc_abc123def456",
  "title": "Machine Learning Fundamentals",
  "num_slides": 15,
  "created_at": "2025-01-01T10:30:00",
  "message": "Outline saved successfully. 15 slides ready for AI generation."
}
```

## Flow Comparison

### OLD Flow (2 options):
1. **AI Generation (costs points)**:
   - Step 1: `/analyze` → analysis_id
   - Step 2: `/create` → document_id (AI HTML generated)
   - Cost: 2 points + 5 points/batch

2. **Manual Creation (free)**:
   - Step 1: `/analyze` → analysis_id
   - Step 2: `/create-basic` → document_id (simple HTML structure)
   - Cost: 2 points only

### NEW Flow (3 options):
3. **Save for Later (free)**:
   - Step 1: `/analyze` → analysis_id
   - Step 2: `/save-outline-only` → document_id (NO HTML yet)
   - Step 3: Later trigger AI generation OR edit manually
   - Cost: 2 points only

## Implementation Details

### Document Structure Created
```javascript
{
  document_id: "doc_...",
  user_id: "user_...",
  title: "Title from analysis",
  content_html: "",  // EMPTY - no HTML generated yet
  content_text: "",

  // Analysis metadata
  ai_analysis_id: "67a1234567890abcdef12345",
  ai_slide_type: "presentation",
  ai_language: "en",
  ai_num_slides: 15,

  // Status
  ai_generation_type: "pending",  // Ready for AI generation

  // Outline data
  slides_outline: [
    {
      slide_number: 1,
      title: "Introduction to ML",
      content_points: ["What is ML", "Applications", "Benefits"],
      image_suggestion: "diagram showing ML workflow"
    },
    // ... more slides
  ],

  // Empty slide arrays (to be filled later)
  slide_elements: [],
  slide_backgrounds: [],

  // Creator info
  creator_name: "user@example.com"
}
```

### Key Differences from `/create-basic`

| Feature | `/create-basic` | `/save-outline-only` |
|---------|-----------------|----------------------|
| HTML generated | ✅ Simple structure | ❌ Empty string |
| slide_elements | ✅ Basic elements | ❌ Empty array |
| slide_backgrounds | ✅ Default backgrounds | ❌ Empty array |
| ai_generation_type | `"basic"` | `"pending"` |
| Purpose | Manual editing | Later AI generation |

## Usage Example

```python
# Step 1: Analyze
response = requests.post(
    "http://localhost:8000/api/slides/ai-generate/analyze",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "title": "Python Advanced Topics",
        "target_goal": "Teach advanced Python concepts to developers",
        "slide_type": "presentation",
        "num_slides_range": {"min": 10, "max": 15},
        "language": "en",
        "user_query": "decorators, generators, async/await"
    }
)
analysis_id = response.json()["analysis_id"]

# Poll for completion
# ... (wait for analysis to complete)

# Step 2: Save outline only (FREE)
response = requests.post(
    "http://localhost:8000/api/slides/ai-generate/save-outline-only",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "analysis_id": analysis_id,
        "creator_name": "John Doe"
    }
)
document_id = response.json()["document_id"]

# Later: Trigger AI generation OR edit manually
# Option A: Use /create endpoint with document_id (when implemented)
# Option B: Edit slides manually in slide editor
```

## Benefits

1. **No Upfront Cost**: FREE endpoint (0 points)
2. **Flexibility**: Review outline before committing to AI generation
3. **Fast Response**: No AI processing delay
4. **Reusable**: Can trigger AI generation later when ready
5. **Safe**: Validates analysis status and creator_name

## Error Handling

### Common Errors
```json
// Analysis not found
{
  "detail": "Analysis not found. Please run Step 1 first."
}

// Analysis not ready
{
  "detail": "Analysis not ready (status: processing)"
}

// Invalid creator_name (if provided)
{
  "detail": "Creator name validation failed"
}
```

## Code Location
- **Routes**: `src/api/slide_ai_generation_routes.py` (line 1320)
- **Model**: `src/models/slide_ai_generation_models.py` (line 244)

## Testing Checklist
- [ ] Create analysis via `/analyze`
- [ ] Wait for analysis completion
- [ ] Call `/save-outline-only` with analysis_id
- [ ] Verify document created with empty HTML
- [ ] Verify outline saved correctly
- [ ] Verify no points deducted
- [ ] Verify creator_name validation works
- [ ] Test error cases (invalid analysis_id, pending analysis)

## Future Enhancements
- [ ] Add `/generate-from-document` endpoint to trigger AI generation from saved outline
- [ ] Support partial generation (e.g., generate only slides 1-5)
- [ ] Add outline editing before generation

---

**Created**: December 28, 2025
**Status**: ✅ Implemented
**Cost**: FREE (0 points)
