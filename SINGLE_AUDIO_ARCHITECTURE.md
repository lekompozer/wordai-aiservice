# Single Audio File Architecture for Slide Narration

## Problem
- **OLD**: Generated separate audio file for EACH slide
- 4 slides = 4 TTS API calls = 4× cost + 4× time (2-4 minutes)
- 100 slides = 100 API calls = 50-100 minutes + massive cost
- Gemini rate limiting caused failures (Slide 4 failed with 500 INTERNAL)

## Solution
- **NEW**: Generate ONE audio file for entire presentation
- Use timestamps to mark slide boundaries
- Frontend slices audio using `audioPlayer.currentTime = start_time`

## Architecture

### Before (Multi-file):
```python
for slide in slides:  # N iterations
    audio = await tts.generate_audio(slide_text)  # N API calls
    upload(f"slide_{i}.mp3")  # N files
    db.insert({slide_index, audio_url})  # N documents
```
**Cost**: 4 slides = 4 calls, 100 slides = 100 calls

### After (Single-file):
```python
# 1. Combine all slides
combined_text = "Slide 1. Speaker: text...\n\nSlide 2. Speaker: text..."
slide_markers = [{slide_index, start_char, end_char, text_length}, ...]

# 2. ONE TTS call
audio = await tts.generate_audio(combined_text)  # 1 API call

# 3. Upload single file
upload("presentation_full.mp3")

# 4. Calculate timestamps proportionally
slide_timestamps = []
for marker in slide_markers:
    char_ratio = marker["text_length"] / len(combined_text)
    slide_duration = total_duration × char_ratio
    start_time = Σ(previous_durations)
    
    slide_timestamps.append({
        "slide_index": marker["slide_index"],
        "start_time": start_time,
        "duration": slide_duration,
        "end_time": start_time + slide_duration
    })

# 5. Store single document with timestamps
db.insert({
    "audio_type": "full_presentation",
    "audio_url": "full.mp3",
    "slide_timestamps": [...]  # Frontend uses this
})
```
**Cost**: 1 call regardless of slide count

## Savings
- **Time**: 30-60s total (instead of 30-60s × N)
- **Cost**: 1 API call (instead of N calls)
- **Reliability**: No rate limiting issues
- **Examples**:
  - 4 slides: 75% savings
  - 10 slides: 90% savings
  - 100 slides: 99% savings

## Database Schema

### presentation_audio collection:
```javascript
{
  "presentation_id": "...",
  "audio_type": "full_presentation",  // Marker
  "audio_url": "https://.../presentation_full.mp3",
  "slide_count": 4,
  "slide_timestamps": [
    {
      "slide_index": 0,
      "start_time": 0,
      "duration": 45.5,
      "end_time": 45.5
    },
    {
      "slide_index": 1,
      "start_time": 45.5,
      "duration": 38.2,
      "end_time": 83.7
    },
    // ... more slides
  ],
  "audio_metadata": {
    "duration_seconds": 120,
    "file_size_bytes": 1234567,
    "format": "mp3",
    "sample_rate": 24000
  }
}
```

### library_audio collection:
```javascript
{
  "filename": "narration_{presentation_id}_{language}_v{version}_full.mp3",
  "metadata": {
    "source_type": "slide_narration",
    "total_slides": 4,
    "total_duration_seconds": 120,
    "slide_timestamps": [...]  // Same as above
  }
}
```

## Frontend Integration

### Playing specific slide:
```javascript
const audioPlayer = new Audio(presentation.audio_url);
const slideTimestamps = presentation.slide_timestamps;

function playSlide(slideIndex) {
  const timestamp = slideTimestamps.find(t => t.slide_index === slideIndex);
  audioPlayer.currentTime = timestamp.start_time;
  audioPlayer.play();
}

// Auto-highlight current slide
audioPlayer.ontimeupdate = () => {
  const currentTime = audioPlayer.currentTime;
  const currentSlide = slideTimestamps.find(
    t => currentTime >= t.start_time && currentTime < t.end_time
  );
  if (currentSlide) {
    highlightSlide(currentSlide.slide_index);
  }
};
```

### Progress bar for specific slide:
```javascript
function getSlideProgress(slideIndex) {
  const timestamp = slideTimestamps[slideIndex];
  const elapsed = audioPlayer.currentTime - timestamp.start_time;
  return (elapsed / timestamp.duration) * 100;
}
```

## Timestamp Calculation Method

**Proportional to character count:**
```python
# Each slide gets duration proportional to its text length
char_ratio = slide_text_length / total_text_length
slide_duration = total_audio_duration × char_ratio
start_time = sum(previous_slide_durations)
end_time = start_time + slide_duration
```

**Example:**
- Total text: 1000 characters, 120 seconds
- Slide 1: 250 chars → 30s (0-30s)
- Slide 2: 500 chars → 60s (30-90s)
- Slide 3: 250 chars → 30s (90-120s)

**Accuracy:**
- Should be ±5 seconds accurate for most cases
- TTS speaks at relatively consistent pace
- May need refinement for very uneven slide lengths

## Files Modified

### src/services/slide_narration_service.py (Lines 678-820):
- **OLD**: Loop through slides, generate per slide
- **NEW**: 
  1. Combine all slides into single text (lines 678-710)
  2. ONE TTS call for entire presentation (lines 725-729)
  3. Upload single file to R2 (lines 732-740)
  4. Calculate timestamps proportionally (lines 745-760)
  5. Save to library with timestamps (lines 762-780)
  6. Create single presentation_audio document (lines 783-815)

## Testing Checklist

- [ ] Generate audio for 4-slide presentation
- [ ] Verify only 1 TTS API call made
- [ ] Verify single audio file uploaded to R2
- [ ] Verify timestamps calculated correctly
- [ ] Test frontend can play specific slides
- [ ] Test progress tracking within slides
- [ ] Test edge case: 1-slide presentation
- [ ] Test edge case: 100-slide presentation
- [ ] Verify cost savings (check Gemini API usage)
- [ ] Verify time savings (should be ~30-60s total)

## Deployment

```bash
# Commit changes
git add src/services/slide_narration_service.py
git commit -m "Refactor: Single audio file with timestamps for slide narration

- Combine all slides into one TTS call
- Calculate proportional timestamps for each slide
- Saves 99% cost for 100-slide presentations
- Reduces generation time from minutes to seconds
- Eliminates Gemini rate limiting issues"

# Deploy to production
./deploy-fresh-start.sh

# Monitor worker logs
docker logs -f slide-narration-audio-worker
```

## Breaking Changes

**API Response:**
- **OLD**: Array of audio objects (one per slide)
- **NEW**: Single audio object with `slide_timestamps` array

**Frontend must:**
1. Use single `audio_url` for entire presentation
2. Use `slide_timestamps` array to slice audio
3. Update UI to show slide progress within single audio

## Rollback Plan

If timestamps are inaccurate or frontend issues:
1. Keep new code but add feature flag
2. If `generate_per_slide=true`, use old loop method
3. Default to `generate_per_slide=false` for cost savings
4. Users can opt-in to per-slide generation if needed

## Future Enhancements

1. **Word-level timestamps**: Use TTS metadata for exact timing
2. **Silence detection**: Adjust timestamps based on actual pauses
3. **Preview mode**: Generate only first 3 slides for quick preview
4. **Progressive loading**: Stream audio while generating
5. **Caching**: Cache combined audio for popular presentations
