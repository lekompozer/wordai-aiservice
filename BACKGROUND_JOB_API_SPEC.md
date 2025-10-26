# Background Job API - Technical Specification

## Overview

This API provides asynchronous PDF conversion using Gemini AI to avoid timeout issues. The conversion process runs in the background while the client polls for status updates.

**Smart Flow:**
- **Step 1:** API checks cache first
- **If cached:** Returns result immediately (no job, no polling)
- **If not cached:** Creates background job, client polls for status

**Problem Solved:**
- Cloudflare free tier has 100-second timeout limit
- Gemini AI conversion can take >100 seconds for multi-page PDFs
- Synchronous endpoint causes connection timeout before response returns

**Solution:**
- Check cache before processing (instant response if available)
- Start job in background if needed, return immediately with `job_id`
- Client polls status endpoint every 5 seconds after 15-second wait
- No timeout issues, progress visibility, better UX

---

## 📌 Endpoints

### 1. Start Async Conversion Job

**`POST /api/documents/{document_id}/convert-with-ai-async`**

Starts AI conversion in background and returns immediately with job tracking information.

#### Request

**Headers:**
```
Authorization: Bearer {firebase_jwt_token}
Content-Type: application/json
```

**Path Parameters:**
- `document_id` (string, required): File ID from `/api/simple-files/upload` response

**Body:** `application/json`
```json
{
  "target_type": "doc",
  "chunk_size": 5,
  "force_reprocess": false,
  "page_range": null
}
```

**Body Fields:**
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `target_type` | string | No | `"doc"` | Output type: `"doc"` or `"slide"` |
| `chunk_size` | integer | No | `5` | Pages per AI chunk (1-10) |
| `force_reprocess` | boolean | No | `false` | Skip cache, force reprocess |
| `page_range` | object | No | `null` | Convert specific pages only |
| `page_range.start` | integer | Yes* | - | Starting page (1-indexed) |
| `page_range.end` | integer | Yes* | - | Ending page (inclusive) |

*Required if `page_range` is provided

#### Response

**Status Code:** `200 OK`

**Body (Cache Hit - Instant Response):**
```json
{
  "success": true,
  "job_id": null,
  "file_id": "file_abc123",
  "title": "Annual Report 2024.pdf",
  "message": "Using cached result (instant response, no processing)",
  "estimated_wait_seconds": 0,
  "status_endpoint": "",
  "created_at": "2025-10-26T10:30:00.000000",
  "result": {
    "success": true,
    "document_id": "doc_xyz789",
    "title": "Annual Report 2024.pdf",
    "document_type": "doc",
    "content_html": "<div>...</div>",
    "ai_processed": true,
    "ai_provider": "gemini",
    "chunks_processed": 0,
    "total_pages": 15,
    "pages_converted": "all",
    "processing_time_seconds": 0,
    "reprocessed": false,
    "updated_at": "2025-10-25T15:20:00.000000"
  }
}
```

**Body (No Cache - Background Job Created):**
```json
{
  "success": true,
  "job_id": "convert_file_abc123_1729900000",
  "file_id": "file_abc123",
  "title": "Annual Report 2024.pdf",
  "message": "AI conversion started in background. Check status after 15 seconds.",
  "estimated_wait_seconds": 15,
  "status_endpoint": "/api/documents/jobs/convert_file_abc123_1729900000/status",
  "created_at": "2025-10-26T10:30:00.000000",
  "result": null
}
```

**Response Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Always `true` on successful request |
| `job_id` | string\|null | Job ID for polling (null if cached result) |
| `file_id` | string | Original file ID (same as path param) |
| `title` | string | Original filename |
| `message` | string | Human-readable instruction message |
| `estimated_wait_seconds` | integer | Wait time before polling (0 if cached, 15 if processing) |
| `status_endpoint` | string | URL for status checking (empty if cached) |
| `created_at` | string | ISO 8601 timestamp |
| `result` | object\|null | **Conversion result (populated if cached, null if processing)** |

#### Error Responses

**404 Not Found** - File doesn't exist or doesn't belong to user
```json
{
  "detail": "File file_abc123 not found"
}
```

**401 Unauthorized** - Missing or invalid Firebase token
```json
{
  "detail": "Not authenticated"
}
```

**500 Internal Server Error** - Failed to start job
```json
{
  "detail": "Failed to start job: {error_message}"
}
```

---

### 2. Check Job Status

**`GET /api/documents/jobs/{job_id}/status`**

Check the current status and progress of a background conversion job.

#### Request

**Headers:**
```
Authorization: Bearer {firebase_jwt_token}
```

**Path Parameters:**
- `job_id` (string, required): Job ID from start endpoint response

#### Response

**Status Code:** `200 OK`

**Body (Job Pending/Processing):**
```json
{
  "job_id": "convert_file_abc123_1729900000",
  "status": "processing",
  "progress": 45,
  "message": "Processing with Gemini AI...",
  "result": null,
  "error": null,
  "elapsed_seconds": 32.5,
  "created_at": "2025-10-26T10:30:00.000000",
  "estimated_remaining_seconds": 40
}
```

**Body (Job Completed):**
```json
{
  "job_id": "convert_file_abc123_1729900000",
  "status": "completed",
  "progress": 100,
  "message": "Conversion completed successfully!",
  "result": {
    "success": true,
    "document_id": "doc_xyz789",
    "title": "Annual Report 2024.pdf",
    "document_type": "doc",
    "content_html": "<div>...</div>",
    "ai_processed": true,
    "ai_provider": "gemini",
    "chunks_processed": 3,
    "total_pages": 15,
    "pages_converted": "all",
    "processing_time_seconds": 67.8,
    "reprocessed": true,
    "updated_at": "2025-10-26T10:31:08.000000"
  },
  "error": null,
  "elapsed_seconds": 68.2,
  "created_at": "2025-10-26T10:30:00.000000",
  "estimated_remaining_seconds": null
}
```

**Body (Job Failed):**
```json
{
  "job_id": "convert_file_abc123_1729900000",
  "status": "failed",
  "progress": 45,
  "message": "Conversion failed: Invalid PDF format",
  "result": null,
  "error": "Invalid PDF format",
  "elapsed_seconds": 12.3,
  "created_at": "2025-10-26T10:30:00.000000",
  "estimated_remaining_seconds": null
}
```

**Response Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `job_id` | string | Job identifier |
| `status` | string | Job state: `"pending"`, `"processing"`, `"completed"`, `"failed"` |
| `progress` | integer | Progress percentage (0-100) |
| `message` | string | Human-readable status message |
| `result` | object\|null | Conversion result (only when `status="completed"`) |
| `error` | string\|null | Error message (only when `status="failed"`) |
| `elapsed_seconds` | float | Time elapsed since job started |
| `created_at` | string | ISO 8601 timestamp when job started |
| `estimated_remaining_seconds` | integer\|null | Estimated time until completion (null if unknown) |

**Result Object (when completed):**
| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Always `true` on success |
| `document_id` | string | New document ID in `documents` collection |
| `title` | string | Document title |
| `document_type` | string | `"doc"` or `"slide"` |
| `content_html` | string | Full HTML content |
| `ai_processed` | boolean | Always `true` |
| `ai_provider` | string | `"gemini"` |
| `chunks_processed` | integer | Number of page chunks processed |
| `total_pages` | integer | Total PDF pages |
| `pages_converted` | string | `"all"` or range like `"1-20"` |
| `processing_time_seconds` | float | AI processing time |
| `reprocessed` | boolean | `true` if force reprocessed, `false` if cached |
| `updated_at` | string | ISO 8601 timestamp |

#### Error Responses

**404 Not Found** - Job doesn't exist
```json
{
  "detail": "Job convert_file_abc123_1729900000 not found"
}
```

**403 Forbidden** - Job belongs to different user
```json
{
  "detail": "Access denied"
}
```

**401 Unauthorized** - Missing or invalid Firebase token
```json
{
  "detail": "Not authenticated"
}
```

---

## 🔄 Job Status Flow

```
┌─────────┐
│ Request │ Call /convert-with-ai-async
└────┬────┘
     │
     v
┌─────────────┐
│ Check Cache │
└────┬────┬───┘
     │    │
     │    └─ Cache Hit ──> Return result immediately ✅
     │                     (result field populated, no polling)
     │
     └─ No Cache ──> ┌─────────┐
                     │ pending │ Job created, queued for processing
                     └────┬────┘
                          │
                          v
                     ┌────────────┐
                     │ processing │ AI conversion in progress (20-120s)
                     └────┬───────┘
                          │
                          ├─ Success ──> ┌───────────┐
                          │              │ completed │ Result in "result" field
                          │              └───────────┘
                          │
                          └─ Error ────> ┌────────┐
                                        │ failed │ Error in "error" field
                                        └────────┘
```

---

## 📊 Progress Mapping

| Progress | Status | Description |
|----------|--------|-------------|
| 0-10% | pending/processing | Job queued, starting |
| 10-20% | processing | File retrieved from database |
| 20-30% | processing | Checking cache for existing conversion |
| 30-40% | processing | Downloading PDF from R2 storage |
| 40-80% | processing | **Gemini AI processing** (longest step) |
| 80-95% | processing | Creating document in database |
| 95-100% | processing | Finalizing, about to complete |
| 100% | completed | Done! Result available |

---

## 🎯 Frontend Implementation Guide

### Recommended Polling Strategy

```typescript
interface ConversionJob {
  jobId: string;
  fileId: string;
  startTime: number;
}

async function convertPdfAsync(
  documentId: string,
  config: ConvertConfig
): Promise<ConversionResult> {

  // 1. Start conversion job (or get cached result)
  const startResponse = await fetch(
    `/api/documents/${documentId}/convert-with-ai-async`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${firebaseToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(config)
    }
  );

  if (!startResponse.ok) {
    throw new Error('Failed to start conversion');
  }

  const jobData = await startResponse.json();

  // 2. Check if cached result (instant response)
  if (jobData.result) {
    console.log('✅ Cache hit! Using cached result');
    return jobData.result;  // Return immediately!
  }

  // 3. No cache → Must poll for status
  const { job_id, estimated_wait_seconds } = jobData;

  console.log(`⏳ Job ${job_id} created, waiting ${estimated_wait_seconds}s...`);
  await sleep(estimated_wait_seconds * 1000);

  // 4. Poll status every 5 seconds
  const maxAttempts = 60; // 5 minutes max (60 * 5s)
  let attempts = 0;

  while (attempts < maxAttempts) {
    const statusResponse = await fetch(
      `/api/documents/jobs/${job_id}/status`,
      {
        headers: {
          'Authorization': `Bearer ${firebaseToken}`
        }
      }
    );

    if (!statusResponse.ok) {
      throw new Error('Failed to check status');
    }

    const status = await statusResponse.json();

    // Update UI with progress
    updateProgress(status.progress, status.message);

    // Check if completed
    if (status.status === 'completed') {
      return status.result; // ✅ Success!
    }

    // Check if failed
    if (status.status === 'failed') {
      throw new Error(status.error);
    }

    // Wait 5 seconds before next poll
    await sleep(5000);
    attempts++;
  }

  throw new Error('Conversion timeout - please try again');
}

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function updateProgress(progress: number, message: string): void {
  // Update your UI here
  console.log(`Progress: ${progress}% - ${message}`);
}
```

### React Hook Example

```typescript
import { useState, useEffect } from 'react';

interface UseAsyncConversion {
  startConversion: (documentId: string, config: ConvertConfig) => Promise<void>;
  status: 'idle' | 'waiting' | 'processing' | 'completed' | 'failed';
  progress: number;
  message: string;
  result: ConversionResult | null;
  error: string | null;
}

export function useAsyncConversion(): UseAsyncConversion {
  const [status, setStatus] = useState<'idle' | 'waiting' | 'processing' | 'completed' | 'failed'>('idle');
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState('');
  const [result, setResult] = useState<ConversionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);

  async function startConversion(documentId: string, config: ConvertConfig) {
    try {
      setStatus('waiting');
      setProgress(0);
      setMessage('Starting conversion...');
      setError(null);

      // Start job
      const response = await fetch(
        `/api/documents/${documentId}/convert-with-ai-async`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${await getFirebaseToken()}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(config)
        }
      );

      const data = await response.json();
      setJobId(data.job_id);
      setMessage(`Waiting ${data.estimated_wait_seconds}s before checking...`);

      // Wait before polling
      await new Promise(resolve => setTimeout(resolve, data.estimated_wait_seconds * 1000));

      setStatus('processing');
    } catch (err) {
      setStatus('failed');
      setError(err.message);
    }
  }

  // Auto-poll when job is active
  useEffect(() => {
    if (!jobId || status === 'completed' || status === 'failed') return;

    const pollInterval = setInterval(async () => {
      try {
        const response = await fetch(
          `/api/documents/jobs/${jobId}/status`,
          {
            headers: {
              'Authorization': `Bearer ${await getFirebaseToken()}`
            }
          }
        );

        const data = await response.json();
        setProgress(data.progress);
        setMessage(data.message);

        if (data.status === 'completed') {
          setStatus('completed');
          setResult(data.result);
          clearInterval(pollInterval);
        } else if (data.status === 'failed') {
          setStatus('failed');
          setError(data.error);
          clearInterval(pollInterval);
        }
      } catch (err) {
        setStatus('failed');
        setError(err.message);
        clearInterval(pollInterval);
      }
    }, 5000); // Poll every 5 seconds

    return () => clearInterval(pollInterval);
  }, [jobId, status]);

  return {
    startConversion,
    status,
    progress,
    message,
    result,
    error
  };
}
```

### Usage in Component

```typescript
function PdfConverter({ fileId }: { fileId: string }) {
  const { startConversion, status, progress, message, result, error } = useAsyncConversion();

  const handleConvert = async () => {
    await startConversion(fileId, {
      target_type: 'doc',
      chunk_size: 5,
      force_reprocess: false
    });
  };

  return (
    <div>
      <button
        onClick={handleConvert}
        disabled={status !== 'idle' && status !== 'completed' && status !== 'failed'}
      >
        Convert to Document
      </button>

      {status === 'waiting' && (
        <div>⏳ {message}</div>
      )}

      {status === 'processing' && (
        <div>
          <ProgressBar value={progress} />
          <p>{progress}% - {message}</p>
        </div>
      )}

      {status === 'completed' && result && (
        <div>
          ✅ Conversion complete!
          <p>Document ID: {result.document_id}</p>
          <p>Pages: {result.total_pages}</p>
          <p>Time: {result.processing_time_seconds}s</p>
        </div>
      )}

      {status === 'failed' && (
        <div>
          ❌ Conversion failed: {error}
        </div>
      )}
    </div>
  );
}
```

---

## ⚠️ Important Notes

### Timeout Behavior
- **Cloudflare Free:** 100-second hard limit
- **Nginx:** 300-second timeout (backend configured)
- **Solution:** Use async endpoints to avoid all timeout issues

### Processing Time Estimates
- **Small documents (1-5 pages):** 20-30 seconds
- **Medium documents (10-20 pages):** 40-60 seconds
- **Large documents (50+ pages):** 90-120 seconds
- **Polling strategy:** Wait 15s, then check every 5s

### Cache Behavior
- First conversion: Full AI processing (60-120s)
- Subsequent requests: Instant return from cache
- Use `force_reprocess: true` to bypass cache

### Job Cleanup
- Jobs are stored in memory (not persistent)
- Auto-cleanup after 24 hours
- Server restart will lose all pending jobs

### Rate Limiting
- No explicit rate limits on these endpoints
- Gemini API has its own rate limits
- Multiple jobs for same file will queue sequentially

### Security
- All endpoints require Firebase authentication
- Jobs are user-scoped (can't access other users' jobs)
- File access validated on job creation

---

## 🔗 Related Endpoints

### Upload File First
Before converting, upload the PDF:

```bash
POST /api/simple-files/upload
Content-Type: multipart/form-data

file: <pdf_file>
```

Response:
```json
{
  "file_id": "file_abc123",
  "filename": "report.pdf",
  "file_type": "pdf",
  "file_size": 1048576,
  "r2_url": "https://..."
}
```

Use the `file_id` from this response as the `document_id` parameter in the conversion endpoints.

---

## 📝 Examples

### cURL Examples

**Start conversion:**
```bash
curl -X POST "https://wordai.aicode.vn/api/documents/file_abc123/convert-with-ai-async" \
  -H "Authorization: Bearer YOUR_FIREBASE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "target_type": "doc",
    "chunk_size": 5,
    "force_reprocess": false
  }'
```

**Check status:**
```bash
curl "https://wordai.aicode.vn/api/documents/jobs/convert_file_abc123_1729900000/status" \
  -H "Authorization: Bearer YOUR_FIREBASE_TOKEN"
```

### Python Example

```python
import requests
import time

def convert_pdf_async(document_id: str, token: str) -> dict:
    # Start job
    response = requests.post(
        f"https://wordai.aicode.vn/api/documents/{document_id}/convert-with-ai-async",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json={
            "target_type": "doc",
            "chunk_size": 5,
            "force_reprocess": False
        }
    )
    response.raise_for_status()

    job_data = response.json()
    job_id = job_data["job_id"]

    # Wait recommended time
    print(f"Waiting {job_data['estimated_wait_seconds']}s...")
    time.sleep(job_data["estimated_wait_seconds"])

    # Poll status
    while True:
        status_response = requests.get(
            f"https://wordai.aicode.vn/api/documents/jobs/{job_id}/status",
            headers={"Authorization": f"Bearer {token}"}
        )
        status_response.raise_for_status()

        status = status_response.json()
        print(f"Progress: {status['progress']}% - {status['message']}")

        if status["status"] == "completed":
            return status["result"]
        elif status["status"] == "failed":
            raise Exception(status["error"])

        time.sleep(5)  # Poll every 5 seconds

# Usage
result = convert_pdf_async("file_abc123", "your_firebase_token")
print(f"Document created: {result['document_id']}")
```

---

## 🚀 Deployment Info

- **Production URL:** `https://wordai.aicode.vn`
- **Endpoints Available:** ✅ Deployed and ready
- **Backend Version:** Latest (with background job support)
- **Status:** Production ready

---

## 📞 Support

For issues or questions:
- Check job status regularly during development
- Monitor `elapsed_seconds` to detect stuck jobs
- If job takes >5 minutes, consider it failed
- Server logs available for debugging

---

**Last Updated:** October 26, 2025
**API Version:** v1
**Document Version:** 1.0
