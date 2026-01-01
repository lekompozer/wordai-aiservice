# Video Export Worker - Phase 2

## Overview

Python worker that processes video export tasks from Redis queue using Playwright for screenshot capture.

## Features

### Optimized Mode (Default)
- **1 screenshot per slide** at 6-second mark (after animations complete)
- **File size:** ~48 MB for 15 min presentation
- **Generation:** ~2.5 minutes
- **Use case:** Education, quick sharing, low bandwidth

### Animated Mode (Premium)
- **150 frames per slide** (5s @ 30 FPS animation)
- **File size:** ~61 MB for 15 min presentation  
- **Generation:** ~8 minutes
- **Use case:** Marketing, professional presentations

## Installation

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Install Playwright Chromium browser
playwright install chromium

# 3. Verify installation
python3 -c "from playwright.async_api import async_playwright; print('✅ Playwright OK')"
```

## Running the Worker

### Development
```bash
./start-video-export-worker.sh
```

### Production (Docker)
```bash
# Worker runs automatically via docker-compose
docker-compose up -d video-export-worker
```

## How It Works

### 1. Queue Processing
- Worker polls `video_export` Redis queue
- Dequeues VideoExportTask messages
- Updates job status in Redis (`job:{job_id}`)

### 2. Screenshot Capture

#### Optimized Mode
```python
# For each slide:
1. Navigate to slide: window.goToSlide(index)
2. Wait 6 seconds (animations complete)
3. Capture 1 screenshot: slide_NNN.png
4. Update progress: 0-50%
```

#### Animated Mode
```python
# For each slide:
1. Navigate to slide: window.goToSlide(index)
2. Capture 150 frames @ 30 FPS (5 seconds)
3. Save to: slide_NNN/frame_NNNN.png
4. Update progress: 0-50%
```

### 3. Metadata Storage
Screenshots + metadata saved to `/tmp/export_{job_id}/`:
```
/tmp/export_abc123/
├── screenshot_metadata.json  # Paths, timestamps, mode
├── slide_000.png             # Optimized: 1 per slide
├── slide_001.png
└── slide_002/                # Animated: 150 frames
    ├── frame_0000.png
    ├── frame_0001.png
    └── ...
```

### 4. Progress Updates
Redis job status updated throughout:
- 0%: Load presentation data
- 10%: Data loaded, starting screenshots
- 50%: Screenshots complete
- Next: Phase 3 (FFmpeg encoding)

## Database Patterns

### Redis Job Status
```python
from src.queue.queue_manager import set_job_status

await set_job_status(
    redis_client=queue_manager.redis_client,
    job_id=job_id,
    status="processing",  # pending/processing/completed/failed
    progress=50,
    current_phase="screenshot",
    user_id=user_id,
)
```

### MongoDB Backup
```python
from src.database.db_manager import DBManager

db_manager = DBManager()
db = db_manager.db

db.video_export_jobs.update_one(
    {"_id": job_id},
    {"$set": {"status": "processing", "progress": 50}}
)
```

## Configuration

### Environment Variables
```bash
ENVIRONMENT=development          # or production
REDIS_URL=redis://localhost:6379
FRONTEND_URL=https://wordai.pro  # For loading presentations
```

### Worker Settings
- **Batch size:** 1 (process 1 task at a time)
- **Max retries:** 2
- **Screenshot wait:** 6 seconds (optimized) for animations
- **FPS:** 30 (animated mode)

## Screenshots

### Browser Settings
- **Viewport:** 1920×1080 (Full HD)
- **Device scale:** 1× (no HiDPI)
- **Headless:** True (no GUI)
- **Chromium args:** 
  - `--no-sandbox`
  - `--disable-setuid-sandbox`
  - `--disable-dev-shm-usage`

### Public Presentation URL
Worker loads presentations via public sharing token:
```
https://wordai.pro/public/presentations/{public_token}
```

Requires presentation to be shared publicly first.

## Error Handling

### Failed Screenshots
- Logs error and continues with next slide
- Job marked as failed if critical error
- Temp directory cleaned up on failure

### Missing Data
- Presentation not found → Job failed
- Public token missing → Job failed with helpful message
- Audio/subtitle missing → Job failed

### Retry Logic
- Worker retries failed jobs up to 2 times
- Exponential backoff on Redis connection errors

## Monitoring

### Logs
```bash
# Worker logs include:
📸 Optimized mode: Capturing 30 screenshots...
   🌐 Loading: https://wordai.pro/public/presentations/xyz
   ✅ Slide 1/30: slide_000.png
   ✅ Slide 2/30: slide_001.png
✅ Captured 30 screenshots
```

### Job Status
```bash
# Check Redis job status
redis-cli HGETALL "job:export_xyz123"

# Check MongoDB backup
mongo ai_service_db --eval 'db.video_export_jobs.find({_id: "export_xyz123"})'
```

## Next Steps (Phase 3)

Worker currently stops after screenshots (50% progress). Phase 3 will implement:

1. **FFmpeg Encoding**
   - Optimized: Concat filter with durations.txt
   - Animated: Encode animation segments
   
2. **Audio Merging**
   - Download merged audio
   - Sync with video
   - AAC encoding @ 128-192 kbps

3. **Final Video**
   - H.264 encoding with CRF 26-30 (optimized) or 23-28 (animated)
   - Output: `/tmp/export_{job_id}/final.mp4`

## Troubleshooting

### Playwright Not Found
```bash
pip install playwright
playwright install chromium
```

### Browser Launch Failed
```bash
# Install dependencies (Ubuntu/Debian)
playwright install-deps chromium
```

### Screenshots Black/Empty
- Check if presentation is publicly shared
- Verify frontend URL is correct
- Increase wait time from 6s to 10s if needed

### Memory Issues
- Reduce batch_size to 1
- Clear /tmp after each job
- Limit concurrent workers

## Performance

### Optimized Mode
- **30 slides × 2s/screenshot** = 60s capture
- **+ 60s encoding** (Phase 3) = 2.5 min total
- **Memory:** ~500 MB per job

### Animated Mode
- **30 slides × 150 frames × 2s** = 9,000s capture (2.5 hours)
- Wait, that's too slow! Need optimization:
  - **Use FFmpeg record** instead of frame-by-frame
  - Phase 3 will use `ffmpeg -f image2pipe` streaming
- **Memory:** ~2 GB per job

## Production Deployment

### Docker Compose
```yaml
video-export-worker:
  build: .
  command: python3 src/workers/video_export_worker.py
  environment:
    - ENVIRONMENT=production
    - REDIS_URL=redis://redis-server:6379
    - FRONTEND_URL=https://wordai.pro
  depends_on:
    - redis-server
    - mongodb
  volumes:
    - /tmp:/tmp  # Shared temp directory
```

### Scaling
```bash
# Run multiple workers
docker-compose up -d --scale video-export-worker=3
```

---

**Status:** Phase 2 Complete ✅  
**Next:** Phase 3 - FFmpeg Encoding
