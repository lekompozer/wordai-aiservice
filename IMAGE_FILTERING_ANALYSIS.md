# Image Filtering System - Phân Tích và Phương Hướng Thực Hiện

## Tổng Quan Hiện Trạng

### Nguồn Dữ Liệu
- **Base URL**: `https://xamvn.bond/attachments/{id}/`
- **ID Range**: 47102 → 634220
- **Tổng số ảnh**: ~587,000 hình
- **Cấu trúc**: Sequential IDs từ server gốc

### Vấn Đề Cần Giải Quyết
1. ❌ **Broken Images**: Một số ID bị lỗi/không tồn tại
2. 🔞 **NSFW Content**: Hình 18+ cần phải lọc ra
3. 📊 **Scale**: Hàng trăm nghìn hình cần xử lý
4. 💾 **Storage**: Quyết định lưu trữ như thế nào (temp/permanent)
5. 🔍 **Metadata**: Cần database để track trạng thái từng hình

---

## Kiến Trúc Đề Xuất

### 1. Background Worker Pattern (Redis Queue)

Sử dụng pattern có sẵn trong hệ thống WordAI:

```
Client API → Redis Queue → Image Processing Worker → MongoDB
```

#### Redis Queue Structure
```python
# Job data structure
{
    "job_id": "img_filter_batch_001",
    "job_type": "image_filter",
    "batch_start_id": 47102,
    "batch_end_id": 47202,  # 100 images per batch
    "status": "pending",    # pending/processing/completed/failed
    "created_at": "2026-02-27T10:00:00Z"
}

# Progress tracking in Redis
HSET job:img_filter_batch_001 status "processing"
HSET job:img_filter_batch_001 processed 45
HSET job:img_filter_batch_001 broken 5
HSET job:img_filter_batch_001 nsfw 12
HSET job:img_filter_batch_001 safe 28
```

#### Batch Size Optimization
```python
IMAGES_PER_BATCH = 100  # Cân bằng giữa speed và memory
CONCURRENT_DOWNLOADS = 10  # Parallel downloads trong 1 batch
TOTAL_BATCHES = 587000 / 100 = ~5870 batches
```

---

### 2. Worker Implementation

#### File Structure
```
src/
  queue/
    image_filter_worker.py     # Main worker
    image_filter_queue.py      # Queue manager
  services/
    image_downloader.py        # Download logic
    nsfw_detector.py           # AI detection
  database/
    image_metadata.py          # MongoDB operations
```

#### Worker Core Logic (`image_filter_worker.py`)
```python
from src.queue.queue_manager import RedisQueue, set_job_status
from src.services.image_downloader import ImageDownloader
from src.services.nsfw_detector import NSFWDetector
from src.database.db_manager import DBManager
import asyncio
import aiohttp
from pathlib import Path

class ImageFilterWorker:
    def __init__(self):
        self.queue_manager = RedisQueue("queue:image_filter")
        self.db_manager = DBManager()
        self.db = self.db_manager.db
        self.nsfw_detector = NSFWDetector()
        self.temp_dir = Path("/tmp/image_filter")
        self.temp_dir.mkdir(exist_ok=True)

    async def run(self):
        """Main worker loop - giống pattern của learning_events_worker"""
        print("🖼️  Image Filter Worker started")
        while True:
            try:
                job = await self.queue_manager.dequeue()
                if not job:
                    await asyncio.sleep(1)
                    continue

                await self.process_batch(job)
            except Exception as e:
                print(f"❌ Worker error: {e}")
                await asyncio.sleep(5)

    async def process_batch(self, job):
        """Process một batch images"""
        job_id = job["job_id"]
        start_id = job["batch_start_id"]
        end_id = job["batch_end_id"]

        # Update status to processing
        await set_job_status(
            redis_client=self.queue_manager.redis_client,
            job_id=job_id,
            status="processing",
            user_id="system",
            progress=0
        )

        results = {
            "processed": 0,
            "broken": [],
            "nsfw": [],
            "safe": []
        }

        # Download và phân tích từng batch
        image_ids = list(range(start_id, end_id + 1))

        # Parallel download 10 ảnh cùng lúc
        async with aiohttp.ClientSession() as session:
            for i in range(0, len(image_ids), 10):
                batch = image_ids[i:i+10]
                tasks = [self.process_single_image(session, img_id, results)
                        for img_id in batch]
                await asyncio.gather(*tasks, return_exceptions=True)

                # Update progress
                results["processed"] = i + len(batch)
                progress = (results["processed"] / len(image_ids)) * 100
                await set_job_status(
                    redis_client=self.queue_manager.redis_client,
                    job_id=job_id,
                    status="processing",
                    user_id="system",
                    progress=int(progress),
                    metadata=results
                )

        # Save batch results to MongoDB
        await self.save_batch_results(start_id, end_id, results)

        # Mark job completed
        await set_job_status(
            redis_client=self.queue_manager.redis_client,
            job_id=job_id,
            status="completed",
            user_id="system",
            progress=100,
            result=results
        )

        print(f"✅ Batch {start_id}-{end_id} done: "
              f"{len(results['safe'])} safe, "
              f"{len(results['nsfw'])} nsfw, "
              f"{len(results['broken'])} broken")

    async def process_single_image(self, session, image_id, results):
        """Download và phân tích 1 ảnh"""
        url = f"https://xamvn.bond/attachments/{image_id}/"
        temp_path = self.temp_dir / f"{image_id}.jpg"

        try:
            # 1. Download image
            async with session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    results["broken"].append(image_id)
                    return

                content = await resp.read()
                temp_path.write_bytes(content)

            # 2. Detect NSFW using AI
            is_nsfw, confidence = await self.nsfw_detector.detect(temp_path)

            # 3. Categorize
            if is_nsfw and confidence > 0.7:  # Threshold 70%
                results["nsfw"].append({
                    "id": image_id,
                    "confidence": confidence
                })
            else:
                results["safe"].append(image_id)

            # 4. Clean up temp file immediately
            temp_path.unlink()

        except asyncio.TimeoutError:
            results["broken"].append(image_id)
        except Exception as e:
            print(f"⚠️  Error processing {image_id}: {e}")
            results["broken"].append(image_id)
            if temp_path.exists():
                temp_path.unlink()

    async def save_batch_results(self, start_id, end_id, results):
        """Lưu kết quả vào MongoDB"""
        # Bulk insert/update vào collection images_metadata
        operations = []

        # Broken images
        for img_id in results["broken"]:
            operations.append({
                "update_one": {
                    "filter": {"image_id": img_id},
                    "update": {
                        "$set": {
                            "image_id": img_id,
                            "status": "broken",
                            "updated_at": "$$NOW"
                        }
                    },
                    "upsert": True
                }
            })

        # NSFW images
        for item in results["nsfw"]:
            operations.append({
                "update_one": {
                    "filter": {"image_id": item["id"]},
                    "update": {
                        "$set": {
                            "image_id": item["id"],
                            "status": "active",
                            "category": "nsfw",
                            "nsfw_confidence": item["confidence"],
                            "updated_at": "$$NOW"
                        }
                    },
                    "upsert": True
                }
            })

        # Safe images
        for img_id in results["safe"]:
            operations.append({
                "update_one": {
                    "filter": {"image_id": img_id},
                    "update": {
                        "$set": {
                            "image_id": img_id,
                            "status": "active",
                            "category": "safe",
                            "updated_at": "$$NOW"
                        }
                    },
                    "upsert": True
                }
            })

        if operations:
            await self.db.images_metadata.bulk_write(operations)
```

---

### 3. NSFW Detection Service

#### Option 1: NudeNet (Lightweight, Fast)
```python
# src/services/nsfw_detector.py
from nudenet import NudeDetector
from pathlib import Path

class NSFWDetector:
    def __init__(self):
        # Model tải về lần đầu ~50MB
        self.detector = NudeDetector()

    async def detect(self, image_path: Path):
        """
        Returns: (is_nsfw: bool, confidence: float)
        """
        results = self.detector.detect(str(image_path))

        # NudeNet trả về list các detected objects với labels
        nsfw_labels = [
            'FEMALE_BREAST_EXPOSED', 'FEMALE_GENITALIA_EXPOSED',
            'MALE_GENITALIA_EXPOSED', 'BUTTOCKS_EXPOSED',
            'ANUS_EXPOSED', 'MALE_BREAST_EXPOSED'
        ]

        nsfw_detections = [
            d for d in results
            if d['class'] in nsfw_labels and d['score'] > 0.6
        ]

        if not nsfw_detections:
            return False, 0.0

        # Max confidence trong các detections
        max_conf = max(d['score'] for d in nsfw_detections)
        return True, max_conf

# Requirements:
# nudenet==3.4
# tensorflow==2.15.0 (or tensorflow-lite for smaller footprint)
```

#### Option 2: OpenNSFW (TensorFlow)
```python
from opennsfw2 import predict_image
import numpy as np

class NSFWDetector:
    async def detect(self, image_path: Path):
        """OpenNSFW returns probability 0.0-1.0"""
        nsfw_prob = predict_image(str(image_path))
        is_nsfw = nsfw_prob > 0.7  # Threshold
        return is_nsfw, float(nsfw_prob)

# Requirements:
# opennsfw2==0.10.0
```

#### Option 3: CLIP-based Detection (Most Accurate)
```python
from transformers import CLIPProcessor, CLIPModel
from PIL import Image
import torch

class NSFWDetector:
    def __init__(self):
        self.model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        self.processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
        self.labels = ["safe content", "explicit content", "nudity", "adult content"]

    async def detect(self, image_path: Path):
        image = Image.open(image_path)
        inputs = self.processor(
            text=self.labels,
            images=image,
            return_tensors="pt",
            padding=True
        )

        with torch.no_grad():
            outputs = self.model(**inputs)
            logits_per_image = outputs.logits_per_image
            probs = logits_per_image.softmax(dim=1)

        # probs[0][0] = safe, probs[0][1:] = nsfw variants
        nsfw_prob = probs[0][1:].sum().item()
        is_nsfw = nsfw_prob > 0.5
        return is_nsfw, nsfw_prob

# Requirements:
# transformers==4.36.0
# torch==2.1.2
# Pillow==10.2.0
```

**Khuyến nghị**: **NudeNet** - balance tốt giữa accuracy và speed, model nhẹ (50MB)

---

### 4. MongoDB Schema

#### Collection: `images_metadata`
```javascript
{
  "_id": ObjectId("..."),
  "image_id": 47102,               // Primary key
  "status": "active",               // active/broken
  "category": "safe",               // safe/nsfw
  "nsfw_confidence": 0.85,          // 0.0-1.0 (null nếu safe)
  "source_url": "https://xamvn.bond/attachments/47102/",
  "processed_at": ISODate("2026-02-27T10:30:00Z"),
  "updated_at": ISODate("2026-02-27T10:30:00Z")
}

// Indexes
db.images_metadata.createIndex({ "image_id": 1 }, { unique: true })
db.images_metadata.createIndex({ "category": 1, "status": 1 })
db.images_metadata.createIndex({ "status": 1 })
db.images_metadata.createIndex({ "processed_at": -1 })
```

#### Collection: `image_filter_jobs`
```javascript
{
  "_id": ObjectId("..."),
  "job_id": "img_filter_batch_001",
  "batch_start_id": 47102,
  "batch_end_id": 47202,
  "status": "completed",           // pending/processing/completed/failed
  "processed": 100,
  "safe_count": 78,
  "nsfw_count": 17,
  "broken_count": 5,
  "started_at": ISODate("..."),
  "completed_at": ISODate("..."),
  "duration_seconds": 245
}
```

---

### 5. API Endpoints

#### Admin API: Quản Lý Filter Jobs

```python
# src/routes/admin/image_filter.py
from fastapi import APIRouter, Depends
from src.middleware.firebase_auth import get_current_user, require_admin
from src.queue.image_filter_queue import get_image_filter_queue
from src.database.db_manager import DBManager

router = APIRouter(prefix="/api/v1/admin/image-filter", tags=["Admin - Image Filter"])

@router.post("/start-batch")
async def start_filter_batch(
    start_id: int,
    end_id: int,
    current_user: dict = Depends(require_admin),
    db = Depends(lambda: DBManager().db)
):
    """Khởi động filter job cho 1 range IDs"""
    queue = await get_image_filter_queue()

    # Chia nhỏ thành các batch 100 ảnh
    batch_size = 100
    job_ids = []

    for batch_start in range(start_id, end_id, batch_size):
        batch_end = min(batch_start + batch_size - 1, end_id)

        job = {
            "job_type": "image_filter",
            "batch_start_id": batch_start,
            "batch_end_id": batch_end,
            "requested_by": current_user["uid"]
        }

        job_id = await queue.enqueue_generic_task(job)
        job_ids.append(job_id)

    return {
        "success": True,
        "total_images": end_id - start_id + 1,
        "total_batches": len(job_ids),
        "job_ids": job_ids
    }

@router.post("/start-full-scan")
async def start_full_scan(
    current_user: dict = Depends(require_admin)
):
    """Scan toàn bộ 587k ảnh - tạo ~5870 jobs"""
    return await start_filter_batch(
        start_id=47102,
        end_id=634220,
        current_user=current_user
    )

@router.get("/job-status/{job_id}")
async def get_job_status(
    job_id: str,
    current_user: dict = Depends(require_admin)
):
    """Kiểm tra trạng thái 1 job"""
    from src.queue.queue_manager import get_job_status
    queue = await get_image_filter_queue()
    job = await get_job_status(queue.redis_client, job_id)
    return job

@router.get("/stats")
async def get_filter_stats(
    current_user: dict = Depends(require_admin),
    db = Depends(lambda: DBManager().db)
):
    """Thống kê tổng quan"""
    total = await db.images_metadata.count_documents({})
    safe = await db.images_metadata.count_documents({"category": "safe"})
    nsfw = await db.images_metadata.count_documents({"category": "nsfw"})
    broken = await db.images_metadata.count_documents({"status": "broken"})

    return {
        "total_processed": total,
        "safe": safe,
        "nsfw": nsfw,
        "broken": broken,
        "pending": 587000 - total
    }
```

#### Public API: Gallery với Filter

```python
# src/routes/gallery.py
from fastapi import APIRouter, Query, Depends
from src.middleware.firebase_auth import get_current_user
from src.database.db_manager import DBManager

router = APIRouter(prefix="/api/v1/gallery", tags=["Gallery"])

@router.get("/images")
async def get_gallery_images(
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    category: str = Query("safe", enum=["safe", "nsfw", "all"]),
    current_user: dict = Depends(get_current_user),
    db = Depends(lambda: DBManager().db)
):
    """
    Lấy danh sách ảnh đã filter
    - category="safe": chỉ ảnh safe (mặc định)
    - category="nsfw": chỉ ảnh 18+ (cần subscription)
    - category="all": tất cả (admin only)
    """
    # Check subscription for NSFW access
    if category == "nsfw":
        subscription = await db.user_gallery_subscription.find_one({
            "user_id": current_user["uid"],
            "status": "active"
        })
        if not subscription:
            return {"error": "NSFW gallery requires subscription", "code": "SUBSCRIPTION_REQUIRED"}

    # Query filter
    query = {"status": "active"}
    if category != "all":
        query["category"] = category

    skip = (page - 1) * limit

    images = await db.images_metadata.find(query)\
        .sort("image_id", 1)\
        .skip(skip)\
        .limit(limit)\
        .to_list(length=limit)

    total = await db.images_metadata.count_documents(query)

    return {
        "images": [
            {
                "id": img["image_id"],
                "url": img["source_url"],
                "category": img["category"]
            }
            for img in images
        ],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit
        }
    }
```

---

### 6. Storage Strategy

#### ❌ **KHÔNG nên**: Lưu ảnh lâu dài trên server
- 587k ảnh × ~500KB trung bình = ~293GB
- Server hiện tại chỉ có HDD giới hạn
- Chi phí storage cao

#### ✅ **Nên**: Temp Download → Analyze → Delete

```
1. Download ảnh vào /tmp/image_filter/{image_id}.jpg
2. Chạy NSFW detection
3. Lưu metadata vào MongoDB
4. XOÁ file ảnh ngay lập tức
5. Frontend vẫn load ảnh trực tiếp từ xamvn.bond
```

#### 🔄 **Cloudflare R2** (Tùy chọn nếu cần cache sau này)

Nếu muốn tối ưu tốc độ load cho user:

```python
# Chỉ cache ảnh SAFE vào R2 để serve nhanh hơn
async def upload_to_r2_if_safe(image_id, temp_path, is_nsfw):
    if is_nsfw:
        return  # NSFW không cache

    # Upload safe image to R2
    s3_client = boto3.client(
        's3',
        endpoint_url='https://your-account.r2.cloudflarestorage.com',
        aws_access_key_id=R2_ACCESS_KEY,
        aws_secret_access_key=R2_SECRET_KEY
    )

    with open(temp_path, 'rb') as f:
        s3_client.upload_fileobj(
            f,
            'xam-gallery',
            f'safe/{image_id}.jpg',
            ExtraArgs={'ContentType': 'image/jpeg'}
        )
```

**Cloudflare R2 Pricing**: $0.015/GB/month storage (rẻ hơn S3 nhiều, bandwidth free)

---

### 7. Deployment Strategy

#### Container Setup (Docker Compose)

```yaml
# docker-compose.yml
services:
  # ... existing services ...

  image-filter-worker:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: image-filter-worker
    command: python -m src.queue.image_filter_worker
    environment:
      - REDIS_HOST=redis-server
      - MONGODB_HOST=mongodb
      - MONGODB_DATABASE=ai_service_db
    volumes:
      - /tmp/image_filter:/tmp/image_filter  # Temp storage
    restart: unless-stopped
    depends_on:
      - redis-server
      - mongodb
    mem_limit: 1g  # Limit memory usage
    cpus: 1.0      # Limit CPU to 1 core
```

#### Resource Requirements

**Worker Memory Profile**:
```
- Base Python process: ~200MB
- NudeNet model loaded: ~150MB
- Processing 10 images concurrently: ~100MB
- Buffer: ~50MB
Total: ~500MB per worker
```

**Khuyến nghị**: Chạy 1 worker duy nhất để tiết kiệm RAM (server chỉ còn ~800MB free)

#### Deployment Commands

```bash
# 1. Thêm worker vào docker-compose.yml
ssh root@104.248.147.155 "su - hoile -c 'cd /home/hoile/wordai && git pull'"

# 2. Deploy với full rebuild
ssh root@104.248.147.155 "su - hoile -c 'cd /home/hoile/wordai && ./deploy-compose-with-rollback.sh'"

# 3. Check worker logs
ssh root@104.248.147.155 "docker logs image-filter-worker --tail=100 -f"
```

---

### 8. Processing Timeline Estimate

#### Assumptions
```
- Trung bình 1 ảnh: 2 giây (download + detect)
- Concurrent: 10 ảnh cùng lúc
- 1 batch 100 ảnh: ~20 giây
- Tổng 5870 batches: 117,400 giây = ~32.6 giờ
```

**Thời gian ước tính**: 1.5-2 ngày để xử lý hết 587k ảnh (chạy 24/7)

#### Optimization Ideas
```python
# Nếu muốn nhanh hơn, có thể:
1. Tăng CONCURRENT_DOWNLOADS = 20 (thay vì 10)
2. Skip download nếu ảnh quá nhỏ (<10KB = likely broken)
3. Batch API gọi xamvn.bond để check existence trước khi download
4. Chạy multiple workers (nếu có thêm RAM)
```

---

### 9. Monitoring & Logging

#### Worker Logs Structure
```python
import logging

logger = logging.getLogger("image_filter_worker")
logger.setLevel(logging.INFO)

# Structured logs
logger.info(f"📦 Batch started: {start_id}-{end_id}")
logger.info(f"✅ Image {img_id}: SAFE (conf: {conf:.2f})")
logger.warning(f"🔞 Image {img_id}: NSFW (conf: {conf:.2f})")
logger.error(f"❌ Image {img_id}: BROKEN (status: {status})")
logger.info(f"🏁 Batch completed: {stats}")
```

#### Redis Monitoring
```bash
# Check queue length
docker exec redis-server redis-cli LLEN queue:image_filter

# Check active jobs
docker exec redis-server redis-cli KEYS "job:img_filter_*"

# Get job details
docker exec redis-server redis-cli HGETALL "job:img_filter_batch_001"
```

#### MongoDB Queries for Stats
```javascript
// Progress tracking
db.images_metadata.aggregate([
  { $group: {
    _id: "$category",
    count: { $sum: 1 }
  }}
])

// Broken images list
db.images_metadata.find({ status: "broken" }).limit(100)

// High confidence NSFW
db.images_metadata.find({
  category: "nsfw",
  nsfw_confidence: { $gt: 0.9 }
}).sort({ nsfw_confidence: -1 })
```

---

### 10. Frontend Integration

#### Update Gallery HTML

```javascript
// Add filter toggle
<div class="controls">
  <select id="category-filter">
    <option value="safe">Safe Content</option>
    <option value="nsfw">🔞 18+ (Subscription)</option>
  </select>
</div>

// API call với filter
async function loadImages(page, category) {
  const token = await getFirebaseToken();
  const response = await fetch(
    `/api/v1/gallery/images?page=${page}&category=${category}`,
    { headers: { 'Authorization': `Bearer ${token}` }}
  );

  if (response.status === 403) {
    // Show subscription modal
    showSubscriptionModal();
    return;
  }

  const data = await response.json();
  renderGallery(data.images);
}
```

---

### 11. Subscription Model (Optional)

#### NSFW Access Pricing
```
Tier 1: $4.99/month  → NSFW gallery access
Tier 2: $9.99/month  → NSFW + HD downloads
```

#### Subscription Collection
```javascript
// user_gallery_subscription
{
  "user_id": "firebase_uid",
  "subscription_tier": "premium",  // basic/premium
  "status": "active",
  "start_date": ISODate("..."),
  "end_date": ISODate("..."),
  "payment_id": "..."
}
```

---

## Implementation Checklist

### Phase 1: Core Infrastructure (Week 1)
- [ ] Tạo MongoDB collection `images_metadata`
- [ ] Tạo indexes cho collection
- [ ] Implement `image_filter_worker.py`
- [ ] Implement `nsfw_detector.py` với NudeNet
- [ ] Implement `image_downloader.py`
- [ ] Tạo queue manager cho image filter
- [ ] Test worker locally với 100 ảnh

### Phase 2: Admin API (Week 1)
- [ ] API endpoint `/admin/image-filter/start-batch`
- [ ] API endpoint `/admin/image-filter/job-status`
- [ ] API endpoint `/admin/image-filter/stats`
- [ ] Admin dashboard để monitor progress

### Phase 3: Deployment (Week 2)
- [ ] Add worker to docker-compose.yml
- [ ] Deploy to production server
- [ ] Start processing first 10k images as test
- [ ] Monitor performance và memory usage
- [ ] Optimize batch size nếu cần

### Phase 4: Public API (Week 2)
- [ ] API endpoint `/gallery/images` với category filter
- [ ] Integration với Firebase Auth
- [ ] Update frontend HTML để call API
- [ ] Test filtering workflow

### Phase 5: Subscription (Week 3 - Optional)
- [ ] Implement subscription collection
- [ ] Payment integration cho NSFW access
- [ ] Subscription validation middleware
- [ ] Frontend subscription modal

### Phase 6: Full Processing (Week 3-4)
- [ ] Kick off full scan 587k images
- [ ] Monitor daily progress
- [ ] Handle errors và retry failed batches
- [ ] Final verification

---

## Cost Analysis

### Server Resources (Current)
```
RAM: 7.8GB total, ~800MB free
CPU: 2 vCPUs, currently 40-60% usage
Disk: HDD with space available

Additional Cost: $0 (use existing worker slot)
```

### External Services
```
NudeNet Model: FREE (open source)
Cloudflare R2 (optional):
  - Storage: ~150GB safe images × $0.015/GB = $2.25/month
  - Bandwidth: FREE (unlimited egress)

Total Additional Cost: $0-3/month
```

### Revenue Potential (NSFW Subscription)
```
Ước tính: 100 users × $4.99 = $499/month
ROI: 166x so với chi phí $3/month
```

---

## Security Considerations

### 1. Worker Security
```python
# Rate limiting to avoid overwhelming source server
RATE_LIMIT_PER_SECOND = 10

# User-Agent để avoid bị block
headers = {
    'User-Agent': 'XAM-Gallery-Bot/1.0 (Image Analysis)'
}
```

### 2. NSFW Content Access Control
```python
# Always require authentication
@require_auth
async def get_nsfw_images(...):
    # Check subscription
    # Check age verification (nếu cần)
    # Log access for compliance
```

### 3. Data Privacy
```
- Không lưu ảnh NSFW trên server
- Metadata không chứa user data
- Tuân thủ GDPR/CCPA nếu có EU/US users
```

---

## Conclusion

### Phương Án Được Khuyến Nghị

✅ **Temp Download + AI Detection + Metadata Storage**

**Lý do**:
1. 💰 Chi phí thấp ($0 additional cost)
2. 🚀 Scalable với Redis queue pattern có sẵn
3. 🔒 Secure (không lưu ảnh NSFW)
4. ⚡ Fast (NudeNet model nhẹ, nhanh)
5. 📊 Flexible metadata cho filtering sau này

**Timeline**: 2-3 weeks implementation + 1.5 days processing

**Next Steps**:
1. Approve kiến trúc này
2. Start Phase 1: Core infrastructure
3. Test với 1000 ảnh đầu tiên
4. Scale to full 587k nếu test OK

---

**Document Version**: 1.0
**Created**: February 27, 2026
**Author**: GitHub Copilot
**Status**: PROPOSAL - Pending Approval
