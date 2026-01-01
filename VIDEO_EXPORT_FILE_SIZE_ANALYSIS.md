# Video Export File Size Analysis & Optimization

**Date:** January 1, 2026
**Target:** 50-100 MB for 15-20 minute presentation video

---

## 📊 File Size Calculation

### Traditional Approach (30 FPS Recording) - TOO LARGE ❌

**Formula:** `file_size = duration × bitrate / 8`

| Duration | Bitrate | File Size | Status |
|----------|---------|-----------|--------|
| 15 min   | 5 Mbps  | 562 MB    | ❌ Too large |
| 15 min   | 2.5 Mbps| 281 MB    | ❌ Too large |
| 15 min   | 1 Mbps  | 112 MB    | ⚠️ Still large |
| 20 min   | 2.5 Mbps| 375 MB    | ❌ Too large |

**Problems:**
- Recording @ 30 FPS creates massive files
- Constant bitrate for mostly static slides is wasteful
- Animations in slides are minimal (fade-in, slide-in)
- User bandwidth and storage costs too high

---

## ✅ Optimized Approach: Static Slideshow

### Key Insight

**Slides are 95% static images** → Don't need 30 FPS recording!

**New Strategy:**
1. Capture **1 screenshot per slide** (30 images for 30 slides)
2. Use FFmpeg slideshow mode with slide durations from `slide_timestamps`
3. Add 0.5s fade transitions between slides
4. Much lower bitrate (500-800 kbps) - static images compress excellently
5. Use CRF (Constant Rate Factor) instead of CBR

### File Size Breakdown (Optimized)

**Audio Track:**
- 15 minutes @ 192 kbps AAC = `15 × 60 × 192 / 8 / 1024 = ~21 MB`
- 20 minutes @ 192 kbps AAC = `20 × 60 × 192 / 8 / 1024 = ~28 MB`

**Video Track (Static Slideshow):**
- FFmpeg slideshow with H.264 CRF 28-30
- Static images compress to 400-600 kbps average
- 15 minutes @ 500 kbps = `15 × 60 × 500 / 8 / 1024 = ~55 MB`
- 20 minutes @ 500 kbps = `20 × 60 × 500 / 8 / 1024 = ~73 MB`

**Total File Size:**

| Duration | Audio | Video | Total | Status |
|----------|-------|-------|-------|--------|
| 15 min   | 21 MB | 55 MB | **76 MB** | ✅ Target achieved |
| 20 min   | 28 MB | 73 MB | **101 MB** | ✅ Target achieved |

**Quality Settings:**
- Low: CRF 30, ~400 kbps → ~60 MB (15 min)
- Medium: CRF 28, ~500 kbps → ~76 MB (15 min) ← **Default**
- High: CRF 26, ~700 kbps → ~95 MB (15 min)

---

## 🎬 FFmpeg Slideshow Implementation

### Input: Screenshots + Durations

**From Puppeteer:**
```javascript
// Capture 1 screenshot per slide
for (const slide of slides) {
  await page.goto(slideUrl);
  await page.waitForSelector('.slide');
  await page.screenshot({ path: `slide_${slide.index}.png` });
}

// Extract durations from slide_timestamps
const durations = slide_timestamps.map(ts => ts.end_time - ts.start_time);
// [30.5, 42.3, 25.8, ...] seconds per slide
```

### FFmpeg Concat with Durations

**Create concat file:**
```text
# slides.txt
file 'slide_0.png'
duration 30.5
file 'slide_1.png'
duration 42.3
file 'slide_2.png'
duration 25.8
...
file 'slide_29.png'
duration 35.0
file 'slide_29.png'  # Repeat last frame
```

**FFmpeg Command:**
```bash
# 1. Create video from slideshow (with fade transitions)
ffmpeg -f concat -safe 0 -i slides.txt \
  -vf "fade=in:0:15,fade=out:st=duration-0.5:d=0.5" \
  -c:v libx264 \
  -crf 28 \
  -preset medium \
  -pix_fmt yuv420p \
  -r 24 \
  video_slides.mp4

# 2. Merge with audio
ffmpeg -i video_slides.mp4 -i audio_merged.wav \
  -c:v copy \
  -c:a aac -b:a 192k \
  -shortest \
  output.mp4
```

**Optimizations:**
- `-crf 28` - Quality (18=high, 28=medium, 30=low for static slides)
- `-preset medium` - Encoding speed vs compression
- `-r 24` - 24 FPS (enough for static slides, saves space)
- Fade transitions make slideshow smooth

---

## 📉 Alternative Compression Strategies

### Strategy 1: Variable Bitrate (Current)

**CRF Mode:**
- Adjusts bitrate based on complexity
- Static slides → low bitrate
- Transitions → higher bitrate temporarily
- **Best for slides** ✅

### Strategy 2: Two-Pass Encoding

**For target file size:**
```bash
# Calculate target bitrate for 80 MB @ 15 min
target_size_mb=80
duration_sec=900
audio_bitrate_kb=192
video_bitrate=$(( (target_size_mb * 8192 / duration_sec) - audio_bitrate_kb ))
# video_bitrate ≈ 537 kbps

# Pass 1
ffmpeg -i input.mp4 -c:v libx264 -b:v ${video_bitrate}k -pass 1 -f null /dev/null

# Pass 2
ffmpeg -i input.mp4 -c:v libx264 -b:v ${video_bitrate}k -pass 2 output.mp4
```

**Use case:** When exact file size matters (e.g., 100 MB limit)

### Strategy 3: H.265/HEVC (Future)

**50% smaller files:**
- Same quality @ 50% bitrate
- 15 min @ 250 kbps video = ~28 MB video track
- **Total: ~50 MB** for 15 min video
- **Problem:** Compatibility (older devices don't support)

**Implementation:**
```bash
ffmpeg -i input.mp4 \
  -c:v libx265 \
  -crf 28 \
  -preset medium \
  -c:a aac -b:a 192k \
  output_hevc.mp4
```

---

## 🎯 Recommended Settings

### Default Profile (Medium Quality, ~76 MB @ 15 min)

```javascript
const VIDEO_SETTINGS = {
  codec: 'libx264',
  crf: 28,              // Quality (lower = better, 18-30 range)
  preset: 'medium',     // Speed (fast/medium/slow)
  fps: 24,              // Frame rate (24 FPS enough for slides)
  pix_fmt: 'yuv420p',   // Compatibility
  audio_codec: 'aac',
  audio_bitrate: '192k',
  fade_duration: 0.5    // Transition duration (seconds)
};
```

### Quality Profiles

```javascript
const QUALITY_PROFILES = {
  low: {
    crf: 30,
    audio_bitrate: '128k',
    target_size: '60 MB @ 15 min'
  },
  medium: {
    crf: 28,
    audio_bitrate: '192k',
    target_size: '76 MB @ 15 min'  // Default
  },
  high: {
    crf: 26,
    audio_bitrate: '256k',
    target_size: '105 MB @ 15 min'
  }
};
```

---

## 📦 Storage & Bandwidth Costs

### Cost Comparison (100 exports/month)

**Old Approach (2.5 Mbps, 280 MB avg):**
- Storage: 100 × 280 MB × $0.023/GB = $0.64/month
- Bandwidth: 100 × 280 MB × $0.09/GB = $2.52
- **Total: $3.16/month**

**New Approach (500 kbps, 76 MB avg):**
- Storage: 100 × 76 MB × $0.023/GB = $0.17/month
- Bandwidth: 100 × 76 MB × $0.09/GB = $0.68
- **Total: $0.85/month**

**Savings: 73% reduction** ($2.31/month)

---

## 🚀 Implementation Changes

### Phase 2: Puppeteer (Updated)

**OLD:** Capture 30 FPS for entire duration
```javascript
// ❌ OLD: Waste resources
const frameCount = Math.ceil(duration * 30);
for (let i = 0; i < frameCount; i++) {
  await page.screenshot();
  await page.waitForTimeout(33); // 30 FPS
}
```

**NEW:** Capture 1 screenshot per slide
```javascript
// ✅ NEW: Efficient
for (const slide of slides) {
  await page.evaluate(idx => window.goToSlide(idx), slide.index);
  await page.waitForTimeout(500); // Wait for animations
  await page.screenshot({
    path: `${tempDir}/slide_${slide.index}.png`,
    type: 'png'
  });
}
```

### Phase 3: FFmpeg (Updated)

**Create concat manifest with durations:**
```javascript
// Build concat file from slide_timestamps
const concatContent = slides.map((slide, idx) => {
  const duration = slide_timestamps[idx].end_time - slide_timestamps[idx].start_time;
  return `file 'slide_${idx}.png'\nduration ${duration}`;
}).join('\n');

// Add last slide again (FFmpeg concat requirement)
concatContent += `\nfile 'slide_${slides.length - 1}.png'`;

await fs.writeFile('slides.txt', concatContent);

// Generate video with fade transitions
await ffmpeg()
  .input('slides.txt')
  .inputOptions('-f concat', '-safe 0')
  .videoCodec('libx264')
  .outputOptions([
    '-crf 28',
    '-preset medium',
    '-pix_fmt yuv420p',
    '-r 24',
    '-vf fade=in:0:15,fade=out:st=duration-0.5:d=0.5'
  ])
  .output('video.mp4')
  .run();

// Merge with audio
await ffmpeg()
  .input('video.mp4')
  .input('audio.wav')
  .videoCodec('copy')
  .audioCodec('aac')
  .audioBitrate('192k')
  .output('final.mp4')
  .run();
```

---

## 📝 Summary

**Target:** 50-100 MB for 15-20 min video ✅

**Solution:**
- ✅ Static slideshow (1 screenshot/slide) instead of 30 FPS recording
- ✅ FFmpeg concat with slide durations from `slide_timestamps`
- ✅ CRF 28, 24 FPS, H.264 codec
- ✅ 192 kbps AAC audio
- ✅ 0.5s fade transitions

**Results:**
- 15 min video: ~76 MB (medium quality)
- 20 min video: ~101 MB (medium quality)
- 73% cost reduction vs traditional approach
- Much faster rendering (30 screenshots vs 27,000 frames!)

**Quality Trade-offs:**
- No smooth animations (slides are static images)
- Fade transitions between slides only
- **Perfect for presentation slides** (minimal motion anyway)
- Users can still view live presentation for full animations
