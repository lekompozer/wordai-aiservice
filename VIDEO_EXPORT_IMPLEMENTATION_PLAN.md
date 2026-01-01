# Video Export Implementation Plan - WordAI Presentation to MP4

**Status:** 🚧 Phase 1 Implementation
**Last Updated:** January 1, 2026
**Target:** Q1 2026

---

## 🎯 Overview

Export WordAI presentations to MP4 video with:
- ✅ Static slideshow with fade transitions (1 screenshot per slide)
- ✅ Multi-language audio support
- ✅ Slide durations from audio timestamps
- ✅ Optimized file size: 50-100 MB for 15-20 min video (H.264, CRF 28)

## 📊 Current State Analysis

### Frontend Approach (Current - Limited)
```typescript
// src: frontend code using MediaRecorder API
MediaRecorder(canvas.captureStream(30), {
  mimeType: 'video/webm;codecs=vp9',
  videoBitsPerSecond: 2500000
})
```

**Issues:**
- ❌ Canvas render chưa capture HTML thực (chỉ fillRect placeholder)
- ❌ MediaRecorder không stable như FFmpeg
- ❌ User phải giữ tab mở
- ❌ Không hỗ trợ H.264 codec tốt
- ❌ RAM/CPU client cao
- ❌ File size quá lớn (280-560 MB cho 15-20 phút)

### Backend Approach (Implemented) ✅
**Tech Stack:**
- **Puppeteer** - Headless Chrome capture screenshots (1 per slide)
- **FFmpeg** - Slideshow video + audio merge
- **Redis Queue** - Job queue (using existing QueueManager)
- **MongoDB** - Job status (using DBManager pattern)
- **S3/R2** - Video storage

**Benefits:**
- ✅ Accurate HTML/CSS screenshot per slide
- ✅ Background processing
- ✅ Optimized file size: 50-100 MB (vs 280-560 MB)
- ✅ Faster rendering (30 screenshots vs 27,000 frames @ 30 FPS)
- ✅ Lower bandwidth costs (73% reduction)
- ✅ Queue multiple exports
- ✅ Scalable workers

---

## 🏗️ Architecture Design

```
┌─────────────────────────────────────────────────────────────┐
│                    Client Request                            │
│  POST /api/presentations/{id}/export/video                  │
│  { language: "vi", resolution: "1080p", fps: 30 }          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              API Endpoint (FastAPI)                          │
│  1. Validate presentation exists                             │
│  2. Check user permissions                                   │
│  3. Create export job in Redis                               │
│  4. Enqueue job to Bull queue                                │
│  5. Return job_id to client                                  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Redis Queue (Bull)                              │
│  - Job: { presentation_id, language, settings }             │
│  - Status: pending → processing → completed/failed          │
│  - Priority: normal/high                                     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│           Video Export Worker (Node.js + Puppeteer)         │
│                                                              │
│  Phase 1: Load Presentation (5-10s)                         │
│    - Load presentation HTML                                  │
│    - Load subtitles + audio for language                     │
│    - Parse slide_timestamps                                  │
│                                                              │
│  Phase 2: Puppeteer Screenshots (10-15s)                    │
│    - Launch headless Chrome                                  │
│    - Set viewport 1920x1080                                  │
│    - Load presentation page                                  │
│    - For each slide:                                         │
│       * Navigate to slide index                              │
│       * Wait 500ms for CSS/animations to settle             │
│       * Take 1 screenshot (PNG)                              │
│       * Save to temp folder                                  │
│    - Extract slide durations from slide_timestamps          │
│                                                              │
│  Phase 3: FFmpeg Slideshow (15-25s)                         │
│    - Create concat file with slide durations                 │
│    - Generate video from static images:                      │
│       * FFmpeg concat demuxer                                │
│       * 24 FPS, H.264 CRF 28                                 │
│       * 0.5s fade transitions between slides                 │
│    - Download audio chunks from R2                           │
│    - Concat audio chunks → single WAV                        │
│    - Merge video + audio → final MP4                         │
│    - File size: 50-100 MB (optimized)                        │
│                                                              │
│  Phase 4: Upload & Cleanup (10-20s)                         │
│    - Upload MP4 to S3/R2                                     │
│    - Generate signed download URL                            │
│    - Update job status → completed                           │
│    - Cleanup temp files                                      │
│    - Send notification to user                               │
└─────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Client Polling                                  │
│  GET /api/export-jobs/{job_id}                              │
│  → { status: "completed", download_url: "..." }             │
└─────────────────────────────────────────────────────────────┘
```

---

## 📋 Implementation Phases

### **Phase 1: Foundation Setup** (Week 1)
**Goal:** Setup infrastructure

**Tasks:**
- [ ] Create `video_export_worker.js` Node.js service
- [ ] Install dependencies: `puppeteer`, `fluent-ffmpeg`, `bull`
- [ ] Setup Bull queue connection to existing Redis
- [ ] Create export jobs collection in MongoDB
- [ ] Add API endpoint: `POST /api/presentations/{id}/export/video`
- [ ] Add polling endpoint: `GET /api/export-jobs/{job_id}`

**Database Schema:**
```javascript
// Collection: video_export_jobs
{
  _id: ObjectId,
  job_id: "export_12345",
  presentation_id: "doc_abc123",
  user_id: "user_xyz",
  language: "vi",
  settings: {
    resolution: "1080p",  // 1080p | 720p | 4k
    fps: 30,              // 24 | 30 | 60
    quality: "high"       // low | medium | high
  },
  status: "pending",      // pending | processing | completed | failed
  progress: 0,            // 0-100
  current_phase: null,    // load | render | encode | upload
  output_url: null,       // S3 download URL
  file_size: null,        // bytes
  duration: null,         // seconds
  error_message: null,
  created_at: ISODate,
  started_at: null,
  completed_at: null
}
```

**API Models:**
```python
# src/models/video_export_models.py
class VideoExportRequest(BaseModel):
    language: str = "vi"
    resolution: str = "1080p"  # 1080p | 720p | 4k
    fps: int = 30
    quality: str = "high"

class VideoExportJobResponse(BaseModel):
    job_id: str
    status: str
    progress: int
    current_phase: Optional[str]
    download_url: Optional[str]
    file_size: Optional[int]
    estimated_time_remaining: Optional[int]  # seconds
```

---

### **Phase 2: Puppeteer Render Engine** (Week 2)
**Goal:** Render presentation frames

**Worker Logic:**
```javascript
// video_export_worker.js
const puppeteer = require('puppeteer');
const fs = require('fs').promises;

async function renderPresentation(job) {
  const { presentation_id, language, settings } = job.data;

  // 1. Load presentation data
  const presentation = await fetchPresentation(presentation_id);
  const subtitles = presentation.languages.find(l => l.language === language);
  const audioFiles = subtitles.audio_files;

  // 2. Launch browser
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  await page.setViewport({
    width: 1920,
    height: 1080,
    deviceScaleFactor: 1
  });

  // 3. Load presentation page
  const presentationUrl = `${process.env.FRONTEND_URL}/public/presentations/${presentation.public_token}`;
  await page.goto(presentationUrl, { waitUntil: 'networkidle0' });

  // 4. Capture frames for each slide
  const frames = [];
  for (const timestamp of audioFiles[0].slide_timestamps) {
    const { slide_index, duration } = timestamp;

    // Navigate to slide
    await page.evaluate((idx) => {
      window.goToSlide(idx);  // Frontend function
    }, slide_index);

    // Wait for animations
    await page.waitForTimeout(500);

    // Capture frames at 30 FPS
    const frameCount = Math.ceil(duration * settings.fps);
    for (let i = 0; i < frameCount; i++) {
      const screenshot = await page.screenshot({ type: 'png' });
      frames.push(screenshot);

      // Advance animation time (if applicable)
      await page.waitForTimeout(1000 / settings.fps);
    }
  }

  await browser.close();

  // 5. Save frames to temp folder
  const tempDir = `/tmp/export_${job.id}`;
  await fs.mkdir(tempDir, { recursive: true });

  for (let i = 0; i < frames.length; i++) {
    await fs.writeFile(`${tempDir}/frame_${i.toString().padStart(6, '0')}.png`, frames[i]);
  }

  return tempDir;
}
```

**Progress Updates:**
```javascript
// Update job progress in real-time
async function updateProgress(jobId, progress, phase) {
  await redis.hset(`export_job:${jobId}`, {
    progress,
    current_phase: phase,
    updated_at: new Date().toISOString()
  });

  // Emit Socket.io event
  io.to(`export_${jobId}`).emit('progress', { progress, phase });
}
```

---

### **Phase 3: FFmpeg Video Processing** (Week 3)
**Goal:** Encode video with audio

**FFmpeg Pipeline:**
```javascript
const ffmpeg = require('fluent-ffmpeg');
const path = require('path');

async function processVideo(job, framesDir) {
  const { language, settings } = job.data;
  const outputPath = `/tmp/output_${job.id}.mp4`;

  // 1. Create video from frames
  await new Promise((resolve, reject) => {
    ffmpeg()
      .input(path.join(framesDir, 'frame_%06d.png'))
      .inputFPS(settings.fps)
      .videoCodec('libx264')
      .outputOptions([
        '-pix_fmt yuv420p',
        '-preset medium',
        '-crf 23'  // Quality: 18 (high) to 28 (low)
      ])
      .output('/tmp/video_temp.mp4')
      .on('progress', (progress) => {
        updateProgress(job.id, progress.percent * 0.5, 'encode_video');
      })
      .on('end', resolve)
      .on('error', reject)
      .run();
  });

  // 2. Download and concat audio chunks
  const audioFiles = await downloadAudioChunks(job.data.presentation_id, language);
  const audioListPath = '/tmp/audio_list.txt';
  await fs.writeFile(
    audioListPath,
    audioFiles.map(f => `file '${f}'`).join('\n')
  );

  await new Promise((resolve, reject) => {
    ffmpeg()
      .input(audioListPath)
      .inputOptions('-f concat', '-safe 0')
      .audioCodec('copy')
      .output('/tmp/audio_merged.wav')
      .on('end', resolve)
      .on('error', reject)
      .run();
  });

  // 3. Merge video + audio
  await new Promise((resolve, reject) => {
    ffmpeg()
      .input('/tmp/video_temp.mp4')
      .input('/tmp/audio_merged.wav')
      .videoCodec('copy')
      .audioCodec('aac')
      .audioBitrate('192k')
      .output(outputPath)
      .on('progress', (progress) => {
        updateProgress(job.id, 50 + progress.percent * 0.5, 'merge_audio');
      })
      .on('end', resolve)
      .on('error', reject)
      .run();
  });

  return outputPath;
}
```

**Quality Presets:**
```javascript
const QUALITY_PRESETS = {
  low: { crf: 28, preset: 'fast', audioBitrate: '96k' },
  medium: { crf: 23, preset: 'medium', audioBitrate: '128k' },
  high: { crf: 18, preset: 'slow', audioBitrate: '192k' }
};
```

---

### **Phase 4: Storage & Delivery** (Week 4)
**Goal:** Upload and serve videos

**S3 Upload:**
```javascript
const { S3Client, PutObjectCommand } = require('@aws-sdk/client-s3');
const { getSignedUrl } = require('@aws-sdk/s3-request-presigner');

async function uploadVideo(job, videoPath) {
  const s3 = new S3Client({ region: process.env.AWS_REGION });

  const key = `exports/${job.data.user_id}/${job.data.presentation_id}/${job.id}.mp4`;

  // Upload
  await s3.send(new PutObjectCommand({
    Bucket: process.env.S3_BUCKET,
    Key: key,
    Body: await fs.readFile(videoPath),
    ContentType: 'video/mp4',
    Metadata: {
      'presentation-id': job.data.presentation_id,
      'language': job.data.language,
      'resolution': job.data.settings.resolution
    }
  }));

  // Generate signed download URL (expires in 24h)
  const url = await getSignedUrl(s3, new GetObjectCommand({
    Bucket: process.env.S3_BUCKET,
    Key: key
  }), { expiresIn: 86400 });

  // Update job
  await db.collection('video_export_jobs').updateOne(
    { job_id: job.id },
    {
      $set: {
        status: 'completed',
        output_url: url,
        file_size: (await fs.stat(videoPath)).size,
        completed_at: new Date()
      }
    }
  );

  // Cleanup
  await fs.rm(`/tmp/export_${job.id}`, { recursive: true });
  await fs.rm(videoPath);

  return url;
}
```

---

### **Phase 5: Frontend Integration** (Week 5)
**Goal:** UI for export feature

**Export Button:**
```typescript
// components/PresentationExport.tsx
async function handleExport() {
  // 1. Create export job
  const res = await fetch(`/api/presentations/${presentationId}/export/video`, {
    method: 'POST',
    body: JSON.stringify({
      language: selectedLanguage,
      resolution: '1080p',
      fps: 30,
      quality: 'high'
    })
  });

  const { job_id } = await res.json();

  // 2. Poll for progress
  const pollInterval = setInterval(async () => {
    const job = await fetch(`/api/export-jobs/${job_id}`).then(r => r.json());

    setProgress(job.progress);
    setCurrentPhase(job.current_phase);

    if (job.status === 'completed') {
      clearInterval(pollInterval);
      window.open(job.download_url, '_blank');
    } else if (job.status === 'failed') {
      clearInterval(pollInterval);
      showError(job.error_message);
    }
  }, 2000);
}
```

**Progress Modal:**
```tsx
<Modal open={isExporting}>
  <ProgressBar value={progress} />
  <div>
    {currentPhase === 'render' && 'Rendering slides...'}
    {currentPhase === 'encode_video' && 'Encoding video...'}
    {currentPhase === 'merge_audio' && 'Adding audio...'}
    {currentPhase === 'upload' && 'Uploading...'}
  </div>
  <div>{progress}% complete</div>
</Modal>
```

---

## 🔧 Technical Specifications

### Video Output
- **Resolution:** 1920x1080 (1080p), 1280x720 (720p), 3840x2160 (4K)
- **Frame Rate:** 24/30/60 FPS
- **Video Codec:** H.264 (libx264)
- **Audio Codec:** AAC
- **Container:** MP4
- **Bitrate:**
  - Video: 5 Mbps (high), 2.5 Mbps (medium), 1 Mbps (low)
  - Audio: 192 kbps (high), 128 kbps (medium), 96 kbps (low)

### Performance Targets
- **30-slide presentation:** 2-3 minutes export time
- **Worker concurrency:** 3-5 concurrent exports
- **Storage:** Auto-delete exports after 7 days
- **Queue priority:** Premium users get priority

### Error Handling
- **Timeout:** 10 minutes max per export
- **Retry:** 3 attempts for failed jobs
- **Fallback:** If Puppeteer fails, use static screenshots
- **Notifications:** Email when export completes

---

## 📊 Cost Estimation

**Per Export (30 slides, 15 min video):**
- Puppeteer render: 1-2 min @ $0.01 compute
- FFmpeg processing: 30-60 sec @ $0.005 compute
- S3 storage: 500 MB @ $0.023/GB/month = $0.012
- S3 bandwidth: 500 MB download @ $0.09/GB = $0.045
- **Total:** ~$0.07 per export

**Monthly (100 exports):**
- $7 compute + storage + bandwidth
- **Break-even:** Charge $0.10 per export or premium feature

---

## 🚀 Rollout Plan

### Week 1-2: Development
- ✅ Setup infrastructure
- ✅ Puppeteer render engine
- ✅ FFmpeg pipeline

### Week 3: Testing
- ✅ Test with sample presentations
- ✅ Load testing (10 concurrent exports)
- ✅ Quality assurance

### Week 4: Beta Release
- ✅ Release to 50 beta users
- ✅ Collect feedback
- ✅ Fix bugs

### Week 5: Public Launch
- ✅ Full rollout
- ✅ Marketing campaign
- ✅ Documentation

---

## 📝 Notes

**Alternative: Client-Side Export (Current)**
- Keep for quick preview/demo
- Backend for production-quality exports
- Offer both options: "Quick Export" vs "Professional Export"

**Future Enhancements:**
- Custom branding (watermark, intro/outro)
- Multi-language exports (all languages in one video with chapters)
- Live streaming integration
- AI video enhancement (upscaling, de-noise)
