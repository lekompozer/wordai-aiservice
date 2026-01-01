# Frontend Integration Guide - Video Export System

**Last Updated:** January 1, 2026  
**Status:** Phase 1-4 Complete, Ready for Frontend Integration  
**Backend Endpoints:** Fully implemented and tested

---

## Overview

The video export system allows users to export presentations as MP4 videos with two quality modes:

- **Optimized Mode** (Default): Static slideshow, ~48 MB for 15 min, 2.5 min generation
- **Animated Mode** (Premium): 5s animation per slide, ~61 MB for 15 min, 8 min generation

Videos are generated asynchronously via background worker, uploaded to Cloudflare R2 CDN, and saved to user's library.

---

## API Endpoints

### 1. Create Export Job

**Endpoint:** `POST /api/presentations/{presentation_id}/export/video`

**Authentication:** Required (Firebase token)

**Request Body:**
```json
{
  "language": "vi",
  "export_mode": "optimized",
  "resolution": "1080p",
  "quality": "medium"
}
```

**Request Parameters:**
- `language`: Language code (vi, en) - must match existing audio/subtitle version
- `export_mode`: "optimized" (default) or "animated"
- `resolution`: "1080p" (default) or "720p"
- `quality`: "low" | "medium" | "high" (affects CRF encoding)

**Success Response (202 Accepted):**
```json
{
  "job_id": "export_abc123xyz",
  "status": "pending",
  "message": "Video export job created successfully",
  "polling_url": "/api/export-jobs/export_abc123xyz",
  "estimated_size_mb": 48,
  "estimated_time_seconds": 150
}
```

**Error Responses:**
- `400 Bad Request`: Missing required data (audio/subtitle not found for language)
- `401 Unauthorized`: Invalid or missing authentication token
- `403 Forbidden`: User doesn't have access to presentation
- `404 Not Found`: Presentation not found
- `422 Unprocessable Entity`: Invalid parameters
- `500 Internal Server Error`: Server error

---

### 2. Get Job Status

**Endpoint:** `GET /api/export-jobs/{job_id}`

**Authentication:** Required (must be job owner)

**Success Response:**
```json
{
  "job_id": "export_abc123xyz",
  "status": "processing",
  "progress": 65,
  "current_phase": "encode",
  "download_url": null,
  "library_video_id": null,
  "file_size": null,
  "duration": null,
  "error": null,
  "presentation_id": "doc_xyz789",
  "language": "vi",
  "export_mode": "optimized",
  "estimated_size_mb": 48,
  "created_at": "2026-01-01T10:00:00Z",
  "estimated_time_remaining": 45
}
```

**Job Status Values:**
- `pending`: Job queued, waiting for worker
- `processing`: Worker is actively processing
- `completed`: Video ready for download
- `failed`: Export failed (see error field)

**Current Phase Values:**
- `load`: Loading presentation data
- `screenshot`: Capturing screenshots with Playwright
- `encode`: FFmpeg video encoding
- `merge`: Audio merging
- `upload`: Uploading to R2 storage
- `completed`: All phases complete

**Progress Values:**
- 0-10%: Loading data
- 10-50%: Screenshot capture
- 50-80%: Video encoding
- 80-90%: Audio merge
- 90-100%: R2 upload and finalize

**Completed Job Response:**
```json
{
  "job_id": "export_abc123xyz",
  "status": "completed",
  "progress": 100,
  "current_phase": "completed",
  "download_url": "https://cdn.wordai.vn/videos/exports/user123/doc_xyz/20260101_120000_abc123.mp4",
  "library_video_id": "lib_def456",
  "file_size": 48,
  "duration": 125.5,
  "presentation_id": "doc_xyz789",
  "language": "vi",
  "export_mode": "optimized",
  "estimated_size_mb": 48,
  "created_at": "2026-01-01T10:00:00Z",
  "estimated_time_remaining": null
}
```

**Error Responses:**
- `403 Forbidden`: User doesn't own this job
- `404 Not Found`: Job not found

---

## Integration Flow

### Step 1: Initiate Export

User clicks "Export Video" button → Frontend shows mode selection dialog:

**Dialog Options:**
1. **Export Mode Selection**
   - Optimized (Recommended): Faster, smaller file
   - Animated (Premium): Higher quality, longer generation

2. **Language Selection**
   - Dropdown with available audio/subtitle languages
   - Only show languages where both audio AND subtitle exist

3. **Quality Settings** (Optional, can hide in "Advanced")
   - Resolution: 1080p / 720p
   - Quality preset: Low / Medium / High

### Step 2: Submit Request

Frontend calls POST endpoint → Backend validates → Returns job_id

**Validation Checks (Backend):**
- Presentation exists and user has access
- Audio version exists for selected language
- Subtitle version exists for selected language
- Presentation is shared publicly (required for screenshot capture)

**If validation fails:**
- Show error message to user
- If public sharing required: prompt user to enable public sharing first

### Step 3: Show Progress Modal

Display modal with:
- Progress bar (0-100%)
- Current phase text
- Estimated time remaining
- Cancel button (optional - job continues in background)

**Progress Updates:**
Poll GET endpoint every 2-3 seconds until status is "completed" or "failed"

### Step 4: Handle Completion

**On Success:**
- Show success message with download button
- Display file size and duration
- Optionally show in user's video library
- Auto-download option

**On Failure:**
- Show error message from job.error field
- Provide retry button
- Common errors:
  - "Presentation not shared publicly"
  - "Audio not found for language"
  - "FFmpeg encoding failed"

### Step 5: Download Video

User clicks download → Open download_url in new tab or trigger download

**Download URL Characteristics:**
- Permanent CDN link (no expiration)
- Direct MP4 download
- Can be shared publicly
- Hosted on Cloudflare R2

---

## UI/UX Recommendations

### Export Button Placement

**Location Options:**
1. **Presentation Editor Toolbar**
   - Icon: Download/Export icon
   - Label: "Export Video"
   - Position: Near "Share" button

2. **Presentation Settings Menu**
   - Under "Advanced" or "Export" section

3. **Presentation List** (Bulk)
   - Action menu for each presentation

### Mode Selection Dialog

**Recommended Layout:**

**Title:** Export Presentation as Video

**Mode Selection:**
- Radio buttons or toggle switch
- Clear visual distinction between modes
- Show estimated file size and time for each

**Optimized Mode:**
- Icon: Lightning/Fast icon
- Description: "Static slideshow, faster generation"
- File size: ~48 MB for 15 min
- Time: ~2-3 minutes

**Animated Mode:**
- Icon: Play/Animation icon
- Description: "Animated slides with transitions"
- File size: ~61 MB for 15 min
- Time: ~8-10 minutes
- Badge: "Premium" or "Pro" (if applicable)

**Language Selector:**
- Dropdown with flag icons
- Only enabled languages (with audio + subtitle)
- Default: Current editor language

**Advanced Settings** (Collapsible):
- Resolution dropdown
- Quality preset selector

### Progress Modal

**Header:**
- Title: "Generating Video..."
- Close button (X) - closes modal but job continues

**Progress Bar:**
- Animated, shows 0-100%
- Color changes: Blue (processing) → Green (completed)

**Status Text:**
- Current phase in plain language:
  - "Loading presentation..." (0-10%)
  - "Capturing screenshots..." (10-50%)
  - "Encoding video..." (50-80%)
  - "Merging audio..." (80-90%)
  - "Uploading to cloud..." (90-100%)

**Time Remaining:**
- "Estimated time: 2 minutes remaining"
- Updates based on estimated_time_remaining

**Actions:**
- "Run in Background" button - closes modal, shows notification when done
- "Cancel" button (optional) - note: job continues in background

### Completion States

**Success Modal:**
- Icon: Checkmark ✓
- Title: "Video Ready!"
- File info: "48 MB • 2:05 duration"
- Primary button: "Download Video"
- Secondary button: "View in Library"

**Error Modal:**
- Icon: Error X
- Title: "Export Failed"
- Error message from API
- Primary button: "Try Again"
- Secondary button: "Close"

### Video Library Integration

**Add to Library Tab:**
- New section: "Exported Videos"
- List view with thumbnails
- Show: Title, duration, file size, export date
- Actions: Download, Delete, Share

**List Item:**
- Thumbnail: First slide screenshot (optional)
- Title: Presentation name + language
- Metadata: "Optimized • 48 MB • 2:05"
- Export date: "Jan 1, 2026"
- Download icon button

---

## Polling Strategy

### Recommended Approach

**Initial Poll:**
- Start polling immediately after job creation
- Interval: Every 2 seconds

**Progressive Backoff:**
- After 30 seconds: Every 3 seconds
- After 2 minutes: Every 5 seconds
- Maximum: 10 minutes timeout

**Stop Conditions:**
- Status = "completed" → Show success
- Status = "failed" → Show error
- Timeout reached → Show timeout error with refresh option
- User closes modal → Store job_id, check on page refresh

### Background Polling

**When user closes progress modal:**
- Continue polling in background
- Show notification badge/icon
- On completion: Browser notification (if permitted)
- On page refresh: Check pending jobs and show status

### Example Polling Logic (Conceptual)

**Initial Request:**
1. Call POST /api/presentations/{id}/export/video
2. Receive job_id
3. Start polling GET /api/export-jobs/{job_id}

**Polling Loop:**
1. Get status every 2-3 seconds
2. Update progress bar and phase text
3. Calculate estimated time remaining
4. If completed/failed → Stop polling
5. If timeout → Stop and show timeout message

**State Management:**
- Store current export jobs in local storage
- On app load: Check for pending jobs
- Resume polling if jobs in progress

---

## Error Handling

### Common Errors and Solutions

**1. "Presentation not found"**
- **Cause:** Invalid presentation_id
- **Action:** Show error, redirect to presentation list

**2. "Audio version not found for language 'en'"**
- **Cause:** No audio generated for selected language
- **Action:** Prompt user to generate audio first
- **UI:** Show "Generate Audio" button

**3. "Subtitle version not found for language 'en'"**
- **Cause:** No subtitles for selected language
- **Action:** Prompt user to generate subtitles first

**4. "Presentation not shared publicly"**
- **Cause:** Public sharing required for screenshot capture
- **Action:** Prompt user to enable public sharing
- **UI:** Show "Enable Sharing" button → Auto-enable → Retry export

**5. "FFmpeg encoding failed"**
- **Cause:** Server-side encoding error
- **Action:** Retry button with exponential backoff
- **Escalation:** Contact support after 3 failed attempts

**6. "Worker timeout"**
- **Cause:** Worker crashed or overloaded
- **Action:** Automatic retry (backend handles this)
- **UI:** Show "Processing delayed, please wait..."

### Error Display

**Error Modal Structure:**
- Clear error title
- User-friendly message (translate technical errors)
- Actionable next steps
- Support contact info (for persistent errors)

**Error Messages Translation:**

Technical errors should be translated to user-friendly language:

| Backend Error | User Message |
|--------------|--------------|
| "Audio version not found" | "Please generate audio for this language first" |
| "Presentation not shared publicly" | "This presentation needs to be shared to export video" |
| "FFmpeg encoding failed" | "Video processing error. Please try again." |
| "Worker timeout" | "Export is taking longer than expected. We'll notify you when ready." |

---

## Performance Considerations

### File Size Expectations

**Optimized Mode:**
- 5 min presentation: ~16 MB
- 10 min presentation: ~32 MB
- 15 min presentation: ~48 MB
- 20 min presentation: ~64 MB

**Animated Mode:**
- 5 min presentation: ~20 MB
- 10 min presentation: ~40 MB
- 15 min presentation: ~61 MB
- 20 min presentation: ~81 MB

### Generation Time Expectations

**Optimized Mode:**
- 10 slides: ~1.5 minutes
- 20 slides: ~2 minutes
- 30 slides: ~2.5 minutes
- 50 slides: ~3.5 minutes

**Animated Mode:**
- 10 slides: ~5 minutes
- 20 slides: ~7 minutes
- 30 slides: ~8 minutes
- 50 slides: ~10 minutes

**Factors affecting time:**
- Slide count (more slides = longer)
- Audio duration (longer audio = larger file)
- Server load (workers may queue)

### Browser Compatibility

**Required Features:**
- Fetch API for HTTP requests
- Promise/async support
- File download capability
- Local storage (for job tracking)

**Recommended:**
- Notification API (for background completion alerts)
- Service Workers (for offline job status check)

---

## Data Storage

### Local Storage Keys

**Suggested structure for tracking export jobs:**

**Key Format:** `video_export_jobs`

**Value Structure:**
```json
{
  "export_abc123": {
    "job_id": "export_abc123",
    "presentation_id": "doc_xyz",
    "presentation_name": "Product Launch 2026",
    "status": "processing",
    "progress": 45,
    "created_at": "2026-01-01T10:00:00Z",
    "export_mode": "optimized",
    "language": "vi"
  }
}
```

**Cleanup Strategy:**
- Remove completed jobs after 24 hours
- Remove failed jobs after 7 days
- Remove jobs if presentation deleted

---

## Security Considerations

### Authentication

**All endpoints require:**
- Firebase authentication token
- User must own presentation to export
- User must own job to check status

**Token Handling:**
- Include in Authorization header: `Bearer {token}`
- Token refresh on expiry
- Graceful handling of 401/403 errors

### Download URLs

**CDN URLs are public:**
- Anyone with URL can download
- No authentication required on CDN
- URLs don't expire (permanent storage)

**Privacy Implications:**
- Inform users that videos are publicly accessible via URL
- Provide "Delete Video" option to remove from library
- Deletion removes from library but CDN may cache for 24h

---

## Testing Checklist

### Functional Tests

- [ ] Create export with optimized mode
- [ ] Create export with animated mode
- [ ] Poll job status successfully
- [ ] Download completed video
- [ ] Handle missing audio error
- [ ] Handle missing subtitle error
- [ ] Handle public sharing requirement
- [ ] Handle concurrent exports (multiple presentations)
- [ ] Resume polling after page refresh
- [ ] Background completion notification

### UI/UX Tests

- [ ] Export button is visible and accessible
- [ ] Mode selection dialog is clear
- [ ] Progress bar animates smoothly
- [ ] Phase text updates correctly
- [ ] Time remaining updates
- [ ] Success modal shows download button
- [ ] Error modal shows retry button
- [ ] Video appears in library after completion

### Edge Cases

- [ ] User closes browser during export
- [ ] User logs out during export
- [ ] Network disconnection during polling
- [ ] Very large presentations (100+ slides)
- [ ] Multiple language exports simultaneously
- [ ] Export same presentation twice (concurrent jobs)

### Performance Tests

- [ ] Polling doesn't cause memory leaks
- [ ] Modal is responsive during long exports
- [ ] Download works on slow connections
- [ ] Large files (>100 MB) download correctly

---

## Monitoring and Analytics

### Recommended Event Tracking

**Export Initiated:**
- Presentation ID
- Export mode (optimized/animated)
- Language
- User ID

**Export Completed:**
- Job ID
- Duration (time to complete)
- File size (actual vs estimated)
- Export mode

**Export Failed:**
- Job ID
- Error type
- Error message
- Retry count

**Download Triggered:**
- Video ID
- Source (completion modal / library)

### Metrics to Track

**User Behavior:**
- Export mode preference (optimized vs animated)
- Language distribution
- Average time from initiate to download
- Abandonment rate (closed modal before completion)

**System Performance:**
- Average export time by mode
- Success rate (completed / total)
- Common error types
- Peak usage hours

---

## Support and Troubleshooting

### User Support Guide

**Common User Issues:**

1. **"My export is stuck at 50%"**
   - Solution: Refresh page and check status again
   - Typically: Encoding phase takes longest
   - Wait time: Up to 5 minutes for large presentations

2. **"Download link doesn't work"**
   - Solution: Try opening in new tab
   - Check: Browser popup blocker settings
   - Alternative: Copy URL and paste in new tab

3. **"Video quality is low"**
   - Solution: Use "Animated" mode with "High" quality
   - Note: Optimized mode intentionally compresses for smaller file

4. **"Can't find my exported video"**
   - Solution: Check video library section
   - Check: Email for completion notification (if implemented)
   - Check: Browser downloads folder

### Developer Debug Info

**Debug Mode Response (if implemented):**

Add `?debug=true` to status endpoint for additional info:
```json
{
  "job_id": "export_abc123",
  "status": "processing",
  "debug": {
    "worker_id": "video_export_worker_12345",
    "queue_position": 2,
    "started_at": "2026-01-01T10:00:30Z",
    "temp_dir": "/tmp/export_abc123",
    "screenshot_count": 25,
    "current_operation": "ffmpeg_encode"
  }
}
```

---

## Migration Notes

### Existing Presentation Data

**Requirements:**
- Presentation must have audio for selected language
- Presentation must have subtitles for selected language
- Presentation must be publicly shared

**If missing requirements:**
- Backend returns 400 Bad Request with clear error message
- Frontend should guide user to complete requirements first

### Backward Compatibility

**API versioning:**
- Current version: v1 (implicit)
- Future versions: Add /v2/ prefix to endpoints
- Support old endpoints for 6 months minimum

---

## Roadmap and Future Features

### Phase 5 (Current Phase)
- Frontend UI implementation
- Progress tracking
- Download handling
- Library integration

### Future Enhancements
- **Batch Export**: Export multiple presentations at once
- **Scheduled Export**: Schedule export for later time
- **Custom Branding**: Add logo watermark to videos
- **Quality Presets**: Custom encoding profiles
- **Webhook Notifications**: Alert external systems on completion
- **Video Editing**: Trim, crop, add intro/outro
- **Subtitle Embedding**: Burn subtitles into video
- **Multi-language Export**: Single job for all languages
- **Preview**: Preview before export
- **Templates**: Save export settings as templates

---

## Backend Status

### Completed Components

✅ **Phase 1**: API endpoints, models, queue setup  
✅ **Phase 2**: Playwright screenshot capture  
✅ **Phase 3**: FFmpeg encoding + audio merge  
✅ **Phase 4**: R2 upload + library integration  

**All backend features are production-ready.**

### Testing Status

- ✅ Unit tests: Core functions tested
- ✅ Integration tests: API endpoints validated
- ⏳ Load tests: Pending (planned for 100 concurrent jobs)
- ⏳ E2E tests: Waiting for frontend integration

### Production Readiness

**Ready for:**
- Development/staging environment testing
- Limited beta release (10-20 users)
- Gradual rollout with monitoring

**Before full production:**
- Load testing with realistic traffic
- CDN caching optimization
- Worker scaling strategy
- Cost analysis (storage + bandwidth)

---

## Contact and Support

**Backend API Issues:**
- Check API documentation: `/docs` endpoint
- Review error responses for debugging info
- Check job status for detailed error messages

**Integration Questions:**
- This document covers all API contracts
- Response formats are fixed and versioned
- Breaking changes will be announced 30 days in advance

**Feature Requests:**
- Submit via GitHub issues or team communication channel
- Include use case and expected behavior
- Priority will be assessed based on user impact

---

**Document Version:** 1.0  
**Last Updated:** January 1, 2026  
**Next Review:** After Phase 5 completion
