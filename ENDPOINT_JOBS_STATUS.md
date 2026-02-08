# Endpoint: GET /api/v1/books/jobs/{job_id}

## 📌 Mục đích
Polling trạng thái job tạo PDF chapter (async processing)

---

## 🔐 Request Format

### URL
```
GET https://ai.wordai.pro/api/v1/books/jobs/{job_id}
```

### Headers (BẮT BUỘC)
```http
Authorization: Bearer <firebase_token>
Origin: https://wordai.pro
```

### Path Parameters
- `job_id` (string, UUID): Job ID được trả về khi enqueue job

### Query Parameters
Không có

---

## ✅ Response Format - SUCCESS CASES

### 1️⃣ Status: PENDING (Job vừa tạo)
**HTTP 200 OK**
```json
{
  "job_id": "db67a850-1efd-41f7-88ed-b434ef108bc5",
  "user_id": "17BeaeikPBQYk8OWeDUkqm0Ov8e2",
  "status": "pending",
  "progress": 0,
  "message": "PDF chapter creation job enqueued",
  "created_at": "2026-02-08T00:10:28.325Z",
  "updated_at": "2026-02-08T00:10:28.325Z"
}
```

### 2️⃣ Status: PROCESSING (Đang xử lý)
**HTTP 200 OK**

**Phase 1: Download PDF (0-10%)**
```json
{
  "job_id": "db67a850-1efd-41f7-88ed-b434ef108bc5",
  "user_id": "17BeaeikPBQYk8OWeDUkqm0Ov8e2",
  "status": "processing",
  "progress": 10,
  "message": "Downloading PDF: document.pdf",
  "created_at": "2026-02-08T00:10:28.325Z",
  "updated_at": "2026-02-08T00:10:35.123Z"
}
```

**Phase 2: Extract Pages (30-70%)**
```json
{
  "job_id": "db67a850-1efd-41f7-88ed-b434ef108bc5",
  "user_id": "17BeaeikPBQYk8OWeDUkqm0Ov8e2",
  "status": "processing",
  "progress": 45,
  "message": "Processed 120/283 pages...",
  "created_at": "2026-02-08T00:10:28.325Z",
  "updated_at": "2026-02-08T00:12:15.456Z"
}
```

**Phase 3: Create Chapter (70-100%)**
```json
{
  "job_id": "db67a850-1efd-41f7-88ed-b434ef108bc5",
  "user_id": "17BeaeikPBQYk8OWeDUkqm0Ov8e2",
  "status": "processing",
  "progress": 70,
  "message": "Processed 283 pages. Creating chapter...",
  "created_at": "2026-02-08T00:10:28.325Z",
  "updated_at": "2026-02-08T00:15:30.789Z"
}
```

### 3️⃣ Status: COMPLETED (Thành công)
**HTTP 200 OK**
```json
{
  "job_id": "db67a850-1efd-41f7-88ed-b434ef108bc5",
  "user_id": "17BeaeikPBQYk8OWeDUkqm0Ov8e2",
  "status": "completed",
  "progress": 100,
  "message": "Chapter created successfully with 283 pages",
  "result": {
    "chapter_id": "3939f17c-a8ea-4000-be89-9e7e6f5ca4e9",
    "total_pages": 283
  },
  "created_at": "2026-02-08T00:10:28.325Z",
  "updated_at": "2026-02-08T00:16:45.123Z",
  "completed_at": "2026-02-08T00:16:45.123Z"
}
```

### 4️⃣ Status: FAILED (Thất bại)
**HTTP 200 OK** (không phải 500!)
```json
{
  "job_id": "db67a850-1efd-41f7-88ed-b434ef108bc5",
  "user_id": "17BeaeikPBQYk8OWeDUkqm0Ov8e2",
  "status": "failed",
  "progress": 35,
  "message": "PDF processing failed: Out of memory",
  "error": "Out of memory",
  "created_at": "2026-02-08T00:10:28.325Z",
  "updated_at": "2026-02-08T00:12:30.456Z",
  "failed_at": "2026-02-08T00:12:30.456Z"
}
```

---

## ❌ Error Responses

### 1️⃣ Job Not Found
**HTTP 404 Not Found**
```json
{
  "detail": "Job db67a850-1efd-41f7-88ed-b434ef108bc5 not found"
}
```

### 2️⃣ Access Denied (Wrong User)
**HTTP 403 Forbidden**
```json
{
  "detail": "Access denied to this job"
}
```

### 3️⃣ Authentication Required
**HTTP 401 Unauthorized**
```json
{
  "detail": "Could not validate credentials"
}
```

### 4️⃣ Internal Server Error
**HTTP 500 Internal Server Error**
```json
{
  "detail": "Failed to get job status: <error message>"
}
```

### 5️⃣ Bad Gateway (NGINX)
**HTTP 502 Bad Gateway**
```html
<html>
<head><title>502 Bad Gateway</title></head>
<body>
<center><h1>502 Bad Gateway</h1></center>
<center>nginx</center>
</body>
</html>
```

**Nguyên nhân:**
- Backend không chạy hoặc restart
- Backend quá tải, không accept connection
- MongoDB connection timeout
- Gunicorn/Uvicorn workers đã hết (tất cả busy)

---

## 🔄 Frontend Polling Strategy

### Recommended
```javascript
const pollInterval = 2000; // 2 seconds
const maxPolls = 900; // 30 minutes (900 * 2s = 1800s)
let pollCount = 0;

async function pollJobStatus(jobId) {
  try {
    const response = await fetch(
      `https://ai.wordai.pro/api/v1/books/jobs/${jobId}`,
      {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${firebaseToken}`,
          'Content-Type': 'application/json',
        },
        credentials: 'include',
      }
    );

    if (!response.ok) {
      // Handle HTTP errors
      if (response.status === 502) {
        console.error('Backend unavailable (502)');
        // Retry with backoff
        return;
      }
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const job = await response.json();
    
    // Update UI with progress
    updateProgress(job.progress, job.message);

    // Check status
    if (job.status === 'completed') {
      // Success! Redirect to chapter
      window.location.href = `/books/${bookId}/chapters/${job.result.chapter_id}`;
      return;
    }

    if (job.status === 'failed') {
      // Show error
      showError(`Failed: ${job.error}`);
      return;
    }

    // Continue polling
    pollCount++;
    if (pollCount < maxPolls) {
      setTimeout(() => pollJobStatus(jobId), pollInterval);
    } else {
      showError('Timeout: Job took too long (30 minutes)');
    }

  } catch (error) {
    console.error('Poll failed:', error);
    // Retry with exponential backoff
    const backoff = Math.min(pollInterval * Math.pow(2, pollCount), 10000);
    setTimeout(() => pollJobStatus(jobId), backoff);
  }
}
```

---

## 🐛 Debugging CORS + 502 Error

### Vấn đề hiện tại
```
Access to fetch at 'https://ai.wordai.pro/api/v1/books/jobs/...' 
from origin 'https://wordai.pro' has been blocked by CORS policy: 
No 'Access-Control-Allow-Origin' header is present on the requested resource.

GET https://ai.wordai.pro/api/v1/books/jobs/... 
net::ERR_FAILED 502 (Bad Gateway)
```

### Nguyên nhân
**502 Bad Gateway xảy ra TRƯỚC khi CORS headers được thêm vào**

Flow:
1. Frontend gửi GET request
2. NGINX forward tới Python backend (`http://python_backend`)
3. ❌ **Backend không trả lời** (crashed/busy/timeout)
4. NGINX trả về 502 Bad Gateway (HTML response)
5. ❌ **CORS headers KHÔNG được thêm vào** vì response không phải từ backend
6. Browser block request vì missing CORS header

### Giải pháp

#### Option 1: Add CORS to 502 error page (NGINX)
```nginx
# In nginx.conf
error_page 502 /502.html;
location = /502.html {
    add_header 'Access-Control-Allow-Origin' $cors_origin always;
    root /usr/share/nginx/html;
    internal;
}
```

#### Option 2: Check backend health
```bash
# SSH to server
ssh root@104.248.147.155

# Check if backend is running
su - hoile -c 'cd /home/hoile/wordai && docker ps | grep ai-chatbot-rag'

# Check backend logs
su - hoile -c 'cd /home/hoile/wordai && docker logs --tail 100 ai-chatbot-rag'

# Check if backend accepts connections
su - hoile -c 'curl -I http://localhost:8000/health'
```

#### Option 3: Increase Gunicorn workers
```python
# In serve.py or docker-compose.yml
# Increase workers to handle more concurrent requests
workers = cpu_count() * 2 + 1  # e.g., 9 workers on 4-core server
```

---

## 📊 Database Schema

### Collection: `pdf_chapter_jobs`

```javascript
{
  _id: ObjectId("..."),
  job_id: "db67a850-1efd-41f7-88ed-b434ef108bc5", // UUID
  user_id: "17BeaeikPBQYk8OWeDUkqm0Ov8e2",
  book_id: "book_19127824bb26",
  file_id: "file_122e249f76bf",
  
  // Job state
  status: "pending" | "processing" | "completed" | "failed",
  progress: 45, // 0-100
  message: "Processed 120/283 pages...",
  
  // Result (when completed)
  result: {
    chapter_id: "3939f17c-a8ea-4000-be89-9e7e6f5ca4e9",
    total_pages: 283
  },
  
  // Error (when failed)
  error: "Out of memory",
  
  // Timestamps
  created_at: ISODate("2026-02-08T00:10:28.325Z"),
  updated_at: ISODate("2026-02-08T00:12:15.456Z"),
  completed_at: ISODate("2026-02-08T00:16:45.123Z"), // optional
  failed_at: ISODate("2026-02-08T00:12:30.456Z"), // optional
}
```

### Indexes
```javascript
db.pdf_chapter_jobs.createIndex({ job_id: 1 }, { unique: true });
db.pdf_chapter_jobs.createIndex({ user_id: 1, status: 1 });
db.pdf_chapter_jobs.createIndex({ created_at: 1 }, { expireAfterSeconds: 604800 }); // TTL 7 days
db.pdf_chapter_jobs.createIndex({ updated_at: 1 });
```

---

## 🚀 Next Steps

1. **Deploy code với logging mới**
   ```bash
   ssh root@104.248.147.155 "su - hoile -c 'cd /home/hoile/wordai && git pull && ./deploy-compose-with-rollback.sh'"
   ```

2. **Check logs khi polling**
   ```bash
   # Xem logs real-time
   ssh root@104.248.147.155 "su - hoile -c 'docker logs -f ai-chatbot-rag | grep \"JOB STATUS\"'"
   ```

3. **Test endpoint trực tiếp**
   ```bash
   curl -H "Authorization: Bearer $TOKEN" \
        https://ai.wordai.pro/api/v1/books/jobs/db67a850-1efd-41f7-88ed-b434ef108bc5
   ```
