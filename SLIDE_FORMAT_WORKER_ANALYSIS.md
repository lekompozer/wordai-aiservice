# SLIDE FORMAT WORKER - PHÂN TÍCH NGUYÊN NHÂN THẤT BẠI

## 🔍 TÓM TẮT VẤN ĐỀ

**Job ID:** `769accf2-f7ef-4208-92fb-c703fc0cfc65`
**User Request:** Format 3 slides (9, 10, 11)
**Kết quả:** Chỉ 1/3 slides hoàn thành, worker bị stuck rồi die

### Triệu chứng quan sát được:
1. ✅ Batch job status = `completed` trong Redis
2. ❌ Chỉ có 1 slide trong `slides_results` (thay vì 3)
3. ❌ Chunk task `_chunk_0` vẫn status = `processing` sau 2 giờ
4. ❌ Worker container `unhealthy` và không log gì trong 10 phút
5. ⚠️ Warning log: "Mode 2 but missing document_id or user_id, cannot update MongoDB"
6. ❌ Task data bị mất khi worker crash (Redis chỉ còn status, không có HTML)

---

## 🐛 ROOT CAUSES - CÁC NGUYÊN NHÂN GỐC RỄ

### **1. WORKER DIE/CRASH KHÔNG ROLLBACK TASK STATUS** ⚠️ CRITICAL
**Vị trí:** Worker main loop không có cleanup khi shutdown

**Vấn đề:**
```python
# Worker set status = "processing"
await set_job_status(
    job_id=job_id,
    status="processing",  # ✅ Set trước khi xử lý
    ...
)

# Nếu worker crash GIỮA CHỪNG → status vẫn là "processing"
# → Worker khác KHÔNG nhặt lại task (tránh duplicate)
# → Task BỊ STUCK MÃI MÃI
```

**Nguyên nhân worker die:**
- TimeoutError sau 5 phút (line 95)
- Exception không catch được (line 108)
- SIGTERM/SIGINT từ Docker restart
- OOM (Out of Memory)
- Redis connection lost
- Claude API timeout quá lâu

**Impact:** Task bị stuck, user không thấy kết quả, không auto-retry

---

### **2. TASK DATA KHÔNG PERSISTENT - CHỈ LƯU STATUS** ⚠️ CRITICAL
**Vị trí:** `queue_manager.dequeue_generic_task()` và task storage

**Vấn đề:**
```python
# API routes tạo task với đầy đủ data
task = SlideFormatTask(
    document_id=request.document_id,  # ✅ Có
    current_html=combined_html,       # ✅ Có (lớn 10KB+)
    ...
)

# Enqueue vào Redis
await queue.enqueue_generic_task(task)  # Lưu vào queue + status key

# Khi worker crash:
# - Queue item bị LPOP (xóa khỏi queue)
# - Status key CHỈ CÒN basic fields (job_id, status, user_id)
# - KHÔNG CÒN current_html, document_id chi tiết!

# Khi re-enqueue:
redis-cli RPUSH queue:slide_format "task_id"  # ❌ CHỈ CÓ ID!
# Worker nhặt lên parse → FAIL: thiếu current_html
```

**Evidence từ Redis:**
```json
{
  "task_id": "..._chunk_0",
  "status": "pending",
  "user_id": "...",
  "document_id": null,  // ❌ LOST!
  "created_at": "...",
  "error_message": null
  // ❌ KHÔNG CÓ: current_html, elements, background, format_type!
}
```

**Impact:** Không thể retry task sau khi crash, data bị mất vĩnh viễn

---

### **3. MODE 2 WARNING: THIẾU DOCUMENT_ID** ⚠️ HIGH
**Vị trí:** `_merge_chunk_results()` line 629

**Vấn đề:**
```python
# Worker check document_id trước khi update MongoDB
if document_id and user_id:
    # Update slide_backgrounds trong MongoDB
    ...
else:
    logger.warning(
        "⚠️ Mode 2 but missing document_id or user_id, cannot update MongoDB"
    )
    # ❌ SKIP UPDATE → Frontend không thấy kết quả!
```

**Nguyên nhân document_id = None:**
1. **API không truyền document_id** (Mode 2 không require)
2. **Task data bị mất** khi worker crash (như #2)
3. **Frontend không gửi** document_id trong request

**Frontend request cần check:**
```typescript
// ❌ SAI - Thiếu document_id cho Mode 2
{
  slides_data: [{slide_index: 9, current_html: "..."}],
  process_all_slides: false,
  // ❌ THIẾU: document_id
}

// ✅ ĐÚNG - Có document_id
{
  document_id: "doc_06de72fea3d7",  // ✅ BẮT BUỘC cho Mode 2
  slides_data: [...],
  process_all_slides: false
}
```

**Impact:**
- Worker xử lý xong nhưng KHÔNG LƯU VÀO MONGODB
- Frontend polling MongoDB không thấy formatted_html
- User thấy job "completed" nhưng không có kết quả

---

### **4. BATCH JOB LOGIC SAI: TÍNH TOTAL_SLIDES TỪ CHUNK** ⚠️ MEDIUM
**Vị trí:** API `slide_ai_routes.py` line 280

**Vấn đề:**
```python
# API tạo batch job với 3 slides
await set_job_status(
    batch_job_id=batch_job_id,
    total_slides=num_slides,  # ✅ = 3
    ...
)

# Nhưng khi tạo chunk task:
task = SlideFormatTask(
    batch_job_id=batch_job_id,
    total_slides=len(chunk_slides),  # ❌ = 1 (slides trong chunk này)
    ...
)

# Worker có thể nhầm lẫn:
# - Batch job có total_slides = 3
# - Chunk task có total_slides = 1
# - Nếu logic sai → đếm sai completed
```

**Tuy nhiên:** Code worker hiện tại ĐÚNG - không dùng `task.total_slides` để update batch job, mà dùng `batch_job.get("total_slides")` từ Redis.

**Impact:** Nhầm lẫn logic, nhưng không gây lỗi trực tiếp

---

### **5. REDIS CONNECTION ERRORS KHÔNG RETRY** ⚠️ MEDIUM
**Vị trí:** Worker main loop line 723

**Vấn đề:**
```python
except Exception as e:
    logger.error(f"❌ Worker: Error in main loop: {e}", exc_info=True)
    await asyncio.sleep(5)  # Sleep 5s rồi tiếp tục

# ✅ CÓ retry logic
# ❌ NHƯNG: Nếu Redis connection lost lâu > 5s
#          → Worker retry liên tục → Spam logs → Có thể OOM
```

**Cần thêm:**
- Exponential backoff (5s → 10s → 20s → 60s)
- Max retry count
- Circuit breaker pattern

---

### **6. TIMEOUT 5 PHÚT QUÁ NGẮN CHO BATCH LỚN** ⚠️ MEDIUM
**Vị trí:** `process_task()` line 92

**Vấn đề:**
```python
timeout_seconds = 300  # 5 phút

# Với batch 12 slides:
# - Claude API: 30-120s per slide
# - Total: 360-1440s (6-24 phút)
# → TIMEOUT chắc chắn!

# Nếu timeout → Task fail
# → Batch job fail
# → User mất points nhưng không có kết quả
```

**Cần:**
- Timeout động dựa vào `total_slides`: `timeout = 60 + (total_slides * 30)`
- Hoặc tăng lên 15-30 phút cho batch lớn

---

### **7. CHUNK DELAY 90S KHI WORKER RESTART** ⚠️ LOW
**Vị trí:** Worker `_process_task_internal()` line 157

**Vấn đề:**
```python
if task.chunk_index and task.chunk_index > 0:
    delay_seconds = 90 * task.chunk_index
    await asyncio.sleep(delay_seconds)
    # Chunk 1: sleep 90s
    # Chunk 2: sleep 180s
    # ...
```

**Nếu worker restart:**
- Chunk đã delay rồi nhưng restart → delay lại từ đầu
- User chờ lâu gấp đôi

**Cần:** Lưu `chunk_started_at` trong Redis, check xem đã delay chưa

---

## 📊 FRONTEND REQUEST FLOW - PHÂN TÍCH

### **Cần check frontend gửi gì:**

```typescript
// Frontend call POST /api/slides/format

// ❌ REQUEST SAI (thiếu document_id):
{
  "slides_data": [
    {
      "slide_index": 8,
      "current_html": "<div>...</div>",
      "elements": [],
      "background": null
    },
    {
      "slide_index": 9,
      "current_html": "<div>...</div>",
      "elements": [],
      "background": null
    },
    {
      "slide_index": 10,
      "current_html": "<div>...</div>",
      "elements": [],
      "background": null
    }
  ],
  "user_instruction": null,
  "format_type": "format",
  "process_all_slides": false
  // ❌ THIẾU: document_id!
}

// ✅ REQUEST ĐÚNG:
{
  "document_id": "doc_06de72fea3d7",  // ✅ BẮT BUỘC!
  "slides_data": [...],
  "user_instruction": null,
  "format_type": "format",
  "process_all_slides": false
}
```

**Hậu quả khi thiếu document_id:**
1. API vẫn accept (vì `document_id` là Optional)
2. Task được tạo với `document_id=None`
3. Worker xử lý xong nhưng SKIP MongoDB update (warning log)
4. Redis có kết quả nhưng MongoDB KHÔNG CÓ
5. Frontend polling MongoDB → không thấy gì
6. User thấy loading mãi

---

## 🔧 GIẢI PHÁP - PRIORITY ORDER

### **🚨 P0 - CRITICAL (Deploy ngay)**

#### **1. BẮT BUỘC document_id CHO MODE 2**
```python
# File: src/models/slide_ai_models.py
class SlideAIFormatRequest(BaseModel):
    document_id: str = Field(  # ❌ Xóa Optional
        ...,  # ✅ Required
        description="Document ID - REQUIRED for all modes to save results"
    )
```

#### **2. CLEANUP STUCK TASKS KHI WORKER START**
```python
# File: src/workers/slide_format_worker.py
async def initialize(self):
    await self.queue_manager.connect()

    # ✅ Reset stuck tasks
    await self._cleanup_stuck_tasks()

async def _cleanup_stuck_tasks(self):
    """Reset tasks stuck in 'processing' > 10 minutes"""
    stuck_keys = await self.redis_client.keys("job:*")
    for key in stuck_keys:
        job = await get_job_status(self.redis_client, key)
        if job.get("status") == "processing":
            started_at = job.get("started_at")
            if started_at:
                elapsed = (datetime.utcnow() - datetime.fromisoformat(started_at)).total_seconds()
                if elapsed > 600:  # 10 phút
                    logger.warning(f"🔄 Resetting stuck job {key}")
                    await set_job_status(
                        self.redis_client,
                        job_id=key,
                        status="failed",
                        error="Worker crashed, task reset"
                    )
```

#### **3. LƯU TASK DATA VÀO REDIS HASH (cho retry)**
```python
# File: src/queue/queue_manager.py
async def enqueue_generic_task(self, task: BaseModel) -> bool:
    # ✅ Lưu FULL task data vào hash
    task_key = f"task:{task.task_id}"
    await self.redis_client.hset(task_key, mapping={
        "task_json": task.json(),  # Full data
        "created_at": datetime.utcnow().isoformat()
    })
    await self.redis_client.expire(task_key, 86400)  # 24h TTL

    # Enqueue task ID vào queue
    await self.redis_client.rpush(f"queue:{self.queue_name}", task.task_id)
```

```python
# File: src/workers/slide_format_worker.py
async def retry_failed_task(self, task_id: str):
    """Retry task từ Redis hash"""
    task_key = f"task:{task_id}"
    task_data = await self.redis_client.hget(task_key, "task_json")
    if task_data:
        task = SlideFormatTask.parse_raw(task_data)
        await self.process_task(task)
```

---

### **⚠️ P1 - HIGH (Deploy trong tuần)**

#### **4. TĂNG TIMEOUT CHO BATCH LỚN**
```python
# Dynamic timeout
timeout_seconds = 60 + (task.total_slides or 1) * 30  # 60s base + 30s/slide
```

#### **5. EXPONENTIAL BACKOFF CHO REDIS ERRORS**
```python
retry_count = 0
max_retries = 5
backoff = 5

while retry_count < max_retries:
    try:
        await self.queue_manager.connect()
        break
    except Exception as e:
        retry_count += 1
        wait_time = backoff * (2 ** retry_count)  # 5s, 10s, 20s, 40s, 80s
        logger.warning(f"Redis connection failed, retry {retry_count}/{max_retries} in {wait_time}s")
        await asyncio.sleep(wait_time)
```

#### **6. HEALTH CHECK ENDPOINT CHO WORKER**
```python
# File: src/workers/slide_format_worker.py
from aiohttp import web

async def health_check(request):
    # Check Redis connection
    # Check running tasks
    # Return 200 if healthy
    return web.json_response({"status": "healthy", "active_tasks": len(running_tasks)})

# Docker healthcheck
# HEALTHCHECK CMD curl -f http://localhost:8080/health || exit 1
```

---

### **📌 P2 - MEDIUM (Tuần sau)**

#### **7. MONITORING & ALERTING**
```python
# Prometheus metrics
from prometheus_client import Counter, Gauge

tasks_processed = Counter('worker_tasks_processed_total', 'Total tasks processed')
tasks_failed = Counter('worker_tasks_failed_total', 'Total tasks failed')
active_tasks = Gauge('worker_active_tasks', 'Currently active tasks')
```

#### **8. DEAD LETTER QUEUE**
```python
# Tasks fail > 3 lần → chuyển vào DLQ
if task.retry_count >= 3:
    await self.redis_client.rpush("queue:slide_format:dlq", task.json())
    logger.error(f"Task {task.task_id} moved to DLQ after 3 failures")
```

---

## 📋 SUMMARY - KẾT LUẬN

### **3 VẤN ĐỀ CHÍNH:**

1. **❌ Frontend thiếu `document_id` trong request Mode 2**
   - → Worker không lưu được MongoDB
   - → Frontend không thấy kết quả

2. **❌ Worker crash không reset task status**
   - → Task stuck ở "processing" mãi mãi
   - → User không thấy lỗi, không retry được

3. **❌ Task data không persistent**
   - → Crash mất hết HTML, không retry được
   - → Phải request lại từ đầu

### **ACTION ITEMS:**

**Ngay lập tức:**
1. ✅ Check frontend code - bắt buộc gửi `document_id`
2. ✅ Deploy fix: require `document_id` trong API
3. ✅ Deploy fix: cleanup stuck tasks khi worker start
4. ✅ Deploy fix: lưu full task data vào Redis hash

**Tuần này:**
5. ⏰ Tăng timeout cho batch lớn
6. 🔄 Exponential backoff cho Redis errors
7. ❤️ Health check endpoint

**Sau:**
8. 📊 Monitoring metrics
9. 💀 Dead letter queue
10. 🧪 Integration tests

---

**Ngày phân tích:** 2026-01-06
**Người phân tích:** GitHub Copilot
**Độ ưu tiên:** CRITICAL - Cần deploy fixes trong 24h
