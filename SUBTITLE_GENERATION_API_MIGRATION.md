# Subtitle Generation API Migration Guide

**Date:** December 30, 2025
**Version:** v2.0 - Async Job Queue System
**Status:** ✅ Deployed to Production

---

## 🚨 Breaking Change Overview

Subtitle generation is now **non-blocking** using Redis job queue system.

**Before:** API blocks for 30-90 seconds while generating subtitles
**After:** API returns immediately (<100ms), worker processes in background

---

## 📋 Migration Summary

### Old Endpoint (DEPRECATED)
```http
POST /api/presentations/{presentation_id}/narration/generate-subtitles
```
- ❌ **Blocks API for 30-90 seconds**
- ❌ **Timeout issues with 15+ slides**
- ❌ **Entire server frozen during generation**
- ⚠️ Still available but will be removed in future

### New Endpoint (RECOMMENDED)
```http
POST /api/presentations/{presentation_id}/subtitles/generate
GET /api/subtitle-jobs/{job_id}
```
- ✅ **Returns immediately (<100ms)**
- ✅ **No blocking, no timeouts**
- ✅ **Multiple users can generate simultaneously**
- ✅ **Real-time status updates via polling**

---

## 🔄 New Workflow

### Step 1: Create Job (Non-blocking)

**Request:**
```http
POST /api/presentations/{presentation_id}/subtitles/generate
Authorization: Bearer {firebase_token}
Content-Type: application/json

{
  "mode": "presentation",
  "language": "vi",
  "user_query": "nội dung nói về kiến thức đầu tư chứng khoán"
}
```

**Note:** `presentation_id` is taken from URL path, NOT required in request body.

**Response (Immediate - <100ms):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Subtitle generation job created. Poll /subtitle-jobs/{job_id} for status.",
  "estimated_time": "30-90 seconds",
  "presentation_id": "doc_439ef6a6e297",
  "slide_count": 15
}
```

### Step 2: Poll for Status

**Request:**
```http
GET /api/subtitle-jobs/{job_id}
Authorization: Bearer {firebase_token}
```

**Response (While Processing):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "created_at": "2025-12-30T23:13:28.427Z",
  "started_at": "2025-12-30T23:13:29.100Z",
  "processing_time_seconds": null,
  "presentation_id": "doc_439ef6a6e297",
  "slide_count": 15,
  "subtitle_id": null,
  "version": null,
  "total_duration": null,
  "error": null
}
```

**Response (Completed):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "created_at": "2025-12-30T23:13:28.427Z",
  "started_at": "2025-12-30T23:13:29.100Z",
  "processing_time_seconds": 45.3,
  "presentation_id": "doc_439ef6a6e297",
  "slide_count": 15,
  "subtitle_id": "67731234567890abcdef1234",
  "version": 1,
  "total_duration": 120.5,
  "error": null
}
```

**Response (Failed):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "failed",
  "created_at": "2025-12-30T23:13:28.427Z",
  "started_at": "2025-12-30T23:13:29.100Z",
  "processing_time_seconds": 5.2,
  "presentation_id": "doc_439ef6a6e297",
  "slide_count": 15,
  "subtitle_id": null,
  "version": null,
  "total_duration": null,
  "error": "Failed to generate subtitles: API quota exceeded"
}
```

---

## 💻 Frontend Implementation

### React/TypeScript Example

```typescript
interface SubtitleJob {
  job_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  subtitle_id?: string;
  version?: number;
  total_duration?: number;
  error?: string;
}

async function generateSubtitles(presentationId: string) {
  // 1. Create job
  const createResponse = await fetch(
    `/api/presentations/${presentationId}/subtitles/generate`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${firebaseToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        mode: 'presentation',
        language: 'vi',
        user_query: 'Focus on investment knowledge',
      }),
    }
  );

  const { job_id } = await createResponse.json();

  // 2. Poll for status
  return pollJobStatus(job_id);
}

async function pollJobStatus(jobId: string): Promise<SubtitleJob> {
  const maxAttempts = 60; // 60 attempts × 2s = 2 minutes max
  let attempts = 0;

  while (attempts < maxAttempts) {
    const response = await fetch(`/api/subtitle-jobs/${jobId}`, {
      headers: {
        'Authorization': `Bearer ${firebaseToken}`,
      },
    });

    const job: SubtitleJob = await response.json();

    // Check if job is done
    if (job.status === 'completed') {
      console.log('✅ Subtitles generated:', job.subtitle_id);
      return job;
    }

    if (job.status === 'failed') {
      throw new Error(`Subtitle generation failed: ${job.error}`);
    }

    // Still processing, wait 2 seconds
    await new Promise(resolve => setTimeout(resolve, 2000));
    attempts++;
  }

  throw new Error('Subtitle generation timeout');
}

// Usage in component
function SubtitleGenerateButton({ presentationId }: Props) {
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState('');

  const handleGenerate = async () => {
    try {
      setLoading(true);
      setProgress('Creating job...');

      const job = await generateSubtitles(presentationId);

      setProgress('✅ Subtitles generated!');
      // Use job.subtitle_id to generate audio next

    } catch (error) {
      setProgress(`❌ Error: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <button onClick={handleGenerate} disabled={loading}>
      {loading ? progress : 'Generate Subtitles'}
    </button>
  );
}
```

---

## 🎯 Key Changes for Frontend

### 1. **Two-Step Process**
   - Old: 1 request (blocking)
   - New: 2 requests (create job → poll status)

### 2. **Polling Interval**
   - Recommended: **2-3 seconds**
   - Max timeout: **2 minutes** (60 attempts × 2s)

### 3. **Job Status Values**
   - `pending`: Job queued, waiting for worker
   - `processing`: Worker is generating subtitles
   - `completed`: Success, use `subtitle_id` for next step
   - `failed`: Error occurred, check `error` field

### 4. **Error Handling**
   - Check `status === 'failed'`
   - Display `error` message to user
   - Allow retry by creating new job

### 5. **Next Step Integration**
   - When `status === 'completed'`, use `subtitle_id` to generate audio
   - Existing audio generation endpoints unchanged

---

## 🔧 Backend Architecture

### Components

```
┌─────────────────┐
│  Frontend App   │
└────────┬────────┘
         │ 1. POST /subtitles/generate
         ▼
┌─────────────────┐
│   FastAPI       │──── Returns job_id immediately (<100ms)
│   Endpoint      │
└────────┬────────┘
         │ 2. Enqueue to Redis
         ▼
┌─────────────────┐
│  Redis Queue    │──── job:{job_id} (24h TTL)
│  slide_narration│
│  _subtitle      │
└────────┬────────┘
         │ 3. Worker pulls task
         ▼
┌─────────────────┐
│  Subtitle       │──── Updates Redis status
│  Worker         │──── (pending→processing→completed)
└────────┬────────┘
         │ 4. Generates subtitles
         ▼
┌─────────────────┐
│  MongoDB        │──── Saves to presentation_subtitles
│  Collection     │
└─────────────────┘
         │
         │ 5. Frontend polls
         ▼
┌─────────────────┐
│  GET /subtitle- │──── Returns status + subtitle_id
│  jobs/{job_id}  │
└─────────────────┘
```

### Redis Job Status Pattern

**Key:** `job:{job_id}`
**Type:** Hash
**TTL:** 24 hours

**Fields:**
```
job_id: "550e8400-e29b-41d4-a716-446655440000"
status: "completed"
user_id: "firebase_uid_123"
presentation_id: "doc_439ef6a6e297"
slide_count: 15
subtitle_id: "67731234567890abcdef1234"
version: 1
total_duration: 120.5
created_at: "2025-12-30T23:13:28.427Z"
started_at: "2025-12-30T23:13:29.100Z"
```

### MongoDB Collections

**Collection:** `presentation_subtitles`

**Document Schema:**
```javascript
{
  _id: ObjectId("67731234567890abcdef1234"),
  presentation_id: "doc_439ef6a6e297",
  user_id: "firebase_uid_123",
  version: 1,
  language: "vi",
  mode: "presentation",
  user_query: "nội dung nói về kiến thức đầu tư",
  slides: [
    {
      slide_index: 0,
      slide_duration: 8.5,
      subtitles: [
        {
          subtitle_index: 0,
          start_time: 0,
          end_time: 3.2,
          duration: 3.2,
          text: "Xin chào các bạn...",
          speaker_index: 0,
          element_references: []
        }
      ],
      auto_advance: true,
      transition_delay: 2.0
    }
  ],
  total_duration: 120.5,
  audio_status: "pending",
  created_at: ISODate("2025-12-30T23:13:55.000Z"),
  updated_at: ISODate("2025-12-30T23:13:55.000Z")
}
```

---

## 📊 System Monitoring

### Check Worker Status

```bash
# View worker containers
docker ps --filter name=subtitle-worker

# Check worker logs
docker logs slide-narration-subtitle-worker -f --tail 100

# Check Redis queue size
docker exec redis-server redis-cli LLEN queue:slide_narration_subtitle

# Check active jobs
docker exec redis-server redis-cli KEYS "job:*"

# Get job details
docker exec redis-server redis-cli HGETALL "job:550e8400-e29b-41d4-a716-446655440000"
```

### Monitor Performance

- **API Response Time:** <100ms (create job)
- **Worker Processing Time:** 30-90 seconds (15 slides)
- **Redis TTL:** 24 hours (job status auto-expires)
- **Concurrent Workers:** 1 container (can scale horizontally)

---

## 🐛 Troubleshooting

### Issue: Job stays in "pending" status
**Solution:** Worker container might be down. Check:
```bash
docker ps --filter name=subtitle-worker
docker logs slide-narration-subtitle-worker
```

### Issue: 404 Not Found when polling job
**Possible Causes:**
1. Job expired (>24 hours old)
2. Invalid job_id
3. Job belongs to different user

**Solution:** Check job ownership and TTL

### Issue: Job failed with error
**Solution:** Check error message in response:
```json
{
  "status": "failed",
  "error": "API quota exceeded"
}
```

Common errors:
- "API quota exceeded" → Gemini API limit reached
- "Presentation not found" → Invalid presentation_id
- "Insufficient points" → User needs to purchase points

---

## 📝 Migration Checklist

### Backend (✅ Completed)
- [x] Create SlideNarrationSubtitleTask model
- [x] Create subtitle worker
- [x] Add queue dependency
- [x] Create async API endpoints
- [x] Add job response models
- [x] Deploy worker container to production
- [x] Update docker-compose.yml
- [x] Update SYSTEM_REFERENCE.md

### Frontend (TODO)
- [ ] Update API client to use new endpoints
- [ ] Implement job polling mechanism
- [ ] Add loading states for async generation
- [ ] Update error handling
- [ ] Add retry logic for failed jobs
- [ ] Update documentation/API reference
- [ ] Test with 15+ slide presentations
- [ ] Remove old synchronous endpoint usage

---

## 🔗 Related Endpoints

### Complete Subtitle + Audio Flow

```
1. Generate Subtitles (Async)
   POST /api/presentations/{id}/subtitles/generate
   GET /api/subtitle-jobs/{job_id}

2. Generate Audio (After subtitles complete)
   POST /api/presentations/{id}/subtitles/v2/{subtitle_id}/audio

3. List Subtitles
   GET /api/presentations/{id}/subtitles/v2

4. Get Specific Subtitle
   GET /api/presentations/{id}/subtitles/v2/{subtitle_id}
```

---

## 📞 Support

**Questions?** Contact backend team or check:
- [SYSTEM_REFERENCE.md](./SYSTEM_REFERENCE.md) - Full system documentation
- [REDIS_STATUS_PATTERN.md](./REDIS_STATUS_PATTERN.md) - Redis job pattern details
- API Documentation: `https://ai.wordai.pro/docs`

---

**Last Updated:** December 30, 2025
**Deployment Version:** 824c57d
**Status:** ✅ Production Ready
