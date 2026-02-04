# Audio Timestamp Fix - Slide Narration System

**Issue:** Timestamp dài hơn audio thực tế vì AI tự tính duration từ word count nhưng không add pause giữa slides

**Root Cause:** Formula tính timestamp trong AI prompt không bao gồm slide pause

**Target:** 15-20 phút cho 30 slides (thay vì ~8 phút hiện tại)

---

## 🔍 Current Formula (Broken)

**Prompt trong `_build_subtitle_prompt()`:**

```python
Formula:
1. Count words in subtitle text you just wrote
2. duration = word_count / (speaking_rate / 60)
3. Add pauses: +0.3s between subtitles, +0.5s between slides  # ❌ AI KHÔNG LÀM ĐÚNG
4. start_time = previous subtitle's end_time + pause
5. end_time = start_time + duration
```

**Vấn đề:**
- AI thực tế **KHÔNG** add +0.5s pause giữa slides
- AI chỉ add +0.3s giữa subtitles trong cùng 1 slide
- Code merge audio cũng **KHÔNG** add silence giữa chunks

**Kết quả:**
- 30 slides với 2-3 câu/slide → ~8 phút (quá ngắn)
- Audio chạy xong nhưng timestamp vẫn còn chạy (vì AI tính có pause, nhưng audio thực không có)

---

## ✅ Solution

### Phase 1: Update AI Prompt (Clear Instructions)

**File:** `src/services/slide_narration_service.py`

**Current (lines 325-345):**
```python
if mode == "presentation":
    style_instructions = """
PRESENTATION MODE:
- Concise and engaging narration (30-60 seconds per slide)
- Focus on key points only
- Speaking rate: ~150 words per minute
"""
else:  # academy
    style_instructions = """
ACADEMY MODE:
- Detailed explanatory narration (60-180 seconds per slide)
- Explain concepts thoroughly
- Speaking rate: ~130 words per minute (slower for clarity)
"""
```

**New:**
```python
if mode == "presentation":
    style_instructions = """
PRESENTATION MODE:
- Professional narration (45-60 seconds per slide on average)
- 3-4 complete sentences per slide (increase from 2-3)
- Speaking rate: ~150 words per minute
- Natural pacing with brief pauses between points
- Target: 15-20 minutes for 30 slides (30-40 seconds/slide average)
"""
else:  # academy
    style_instructions = """
ACADEMY MODE:
- Detailed teaching narration (60-120 seconds per slide on average)
- 5-6 complete sentences per slide (increase from 3-4)
- Speaking rate: ~130 words per minute (slower for clarity)
- Include examples and explanations
- Target: 20-30 minutes for 30 slides (40-60 seconds/slide average)
"""
```

**Current Timing Formula (lines 410-435):**
```python
**STEP 2: Calculate TIMING for each subtitle**
After writing text, calculate timing based on:
- Speaking rate: {mode} mode (~150 words/min for presentation, ~130 words/min for academy)
- Word count in subtitle text
- Natural pauses between sentences

Formula:
1. Count words in subtitle text you just wrote
2. duration = word_count / (speaking_rate / 60)
3. Add pauses: +0.3s between subtitles, +0.5s between slides
4. start_time = previous subtitle's end_time + pause
5. end_time = start_time + duration
```

**New Formula:**
```python
**STEP 2: Calculate TIMING for each subtitle**
CRITICAL: Timestamps must match actual audio generation (no slide pauses in audio).

Formula for EACH subtitle:
1. Count words in subtitle text
2. base_duration = word_count / (speaking_rate / 60)
   - Presentation mode: 150 words/min = 2.5 words/sec
   - Academy mode: 130 words/min = 2.17 words/sec

3. Add natural speech pauses:
   - Within same slide: +0.3s between subtitles
   - First subtitle of slide: start immediately (no gap from previous slide)

4. Calculate timestamps:
   - If first subtitle of presentation: start_time = 0
   - If first subtitle of slide (but not first slide):
       start_time = previous_slide_last_subtitle.end_time + 0.3
   - If middle subtitle of slide:
       start_time = previous_subtitle.end_time + 0.3
   - end_time = start_time + base_duration
   - duration = base_duration

⚠️ IMPORTANT: DO NOT add 1.5s or 2s pause between slides in timestamps!
Audio generation does not add silence between slides, so timestamps must be continuous.
The 0.3s pause between subtitles provides natural breathing room.

Example (Presentation mode, 150 wpm):
Slide 0:
  Subtitle 0: "Chào mừng các bạn đến với khóa học AI." (9 words)
    - base_duration = 9 / 2.5 = 3.6s
    - start_time = 0.0
    - end_time = 0.0 + 3.6 = 3.6
    - duration = 3.6

  Subtitle 1: "Hôm nay chúng ta sẽ học về Machine Learning." (10 words)
    - base_duration = 10 / 2.5 = 4.0s
    - start_time = 3.6 + 0.3 = 3.9
    - end_time = 3.9 + 4.0 = 7.9
    - duration = 4.0

Slide 1 (immediately after Slide 0):
  Subtitle 0: "Machine Learning là gì?" (4 words)
    - base_duration = 4 / 2.5 = 1.6s
    - start_time = 7.9 + 0.3 = 8.2 (NOT 9.9!)
    - end_time = 8.2 + 1.6 = 9.8
    - duration = 1.6
```

---

### Phase 2: Add Silence Between Slides in Audio Generation

**File:** `src/services/slide_narration_service.py`

**Current (lines 935-940):**
```python
# Add silence between slides using empty space (Gemini handles naturally)
slide_text += " "  # Natural pause between slides
```

**Problem:** Space (" ") does NOT create 1.5s pause in Gemini TTS!

**Fix Option 1: SSML pause (if Gemini supports)**
```python
# Add 1.5s pause between slides
if slide_index < len(slides) - 1:  # Not last slide
    slide_text += "<break time='1500ms'/>"  # SSML pause
```

**Fix Option 2: Merge audio with silence (RECOMMENDED)**

Update `_merge_audio_chunks()` to add silence between slide boundaries:

```python
# Lines 1350-1420 in _merge_audio_chunks()

combined_audio = AudioSegment.empty()
global_timestamps = []
current_time = 0.0
SLIDE_PAUSE_MS = 1500  # 1.5 seconds pause between slides

for chunk_idx, chunk_doc in enumerate(audio_documents):
    # ... download chunk ...

    # Load audio segment
    audio_segment = AudioSegment.from_wav(io.BytesIO(audio_data))

    # Add chunk timestamps with offset
    chunk_timestamps = chunk_doc.get("slide_timestamps", [])
    prev_slide_index = None

    for ts in chunk_timestamps:
        slide_index = ts["slide_index"]

        # Add pause if transitioning to new slide
        if prev_slide_index is not None and slide_index != prev_slide_index:
            # Add 1.5s silence between slides
            silence = AudioSegment.silent(duration=SLIDE_PAUSE_MS)
            combined_audio += silence
            current_time += SLIDE_PAUSE_MS / 1000.0
            logger.info(f"   ⏸️  Added {SLIDE_PAUSE_MS}ms pause after slide {prev_slide_index}")

        global_timestamps.append({
            "slide_index": slide_index,
            "start_time": current_time + ts["start_time"],
            "end_time": current_time + ts["end_time"],
        })

        prev_slide_index = slide_index

    # Append chunk audio
    combined_audio += audio_segment
    current_time += len(audio_segment) / 1000.0
```

**Problem with Option 2:** Timestamps in chunks are RELATIVE to chunk, not global. Need to recalculate.

**Better Fix: Add silence when generating per-slide audio**

Update `generate_audio_v2()` to add silence after each slide:

```python
# Lines 1000-1100 in generate_audio_v2()

for slide in slides:
    slide_index = slide["slide_index"]
    subtitles = slide.get("subtitles", [])

    # ... generate slide_text ...

    # Join subtitles with natural pauses
    slide_text = ". ".join(slide_text_parts)
    if slide_text and not slide_text.endswith("."):
        slide_text += "."

    # ✅ NEW: Mark slide end for post-processing
    # We'll add silence AFTER audio is generated
    slide_text_parts.append({
        "text": slide_text,
        "needs_pause_after": (slide_index < len(slides) - 1)  # Not last slide
    })
```

**WAIT** - Current code generates audio in CHUNKS, not per-slide. Pause must be in merge step.

---

## 🎯 Recommended Implementation (Simple & Safe)

### Step 1: Fix AI Prompt - More sentences per slide

**File:** `src/services/slide_narration_service.py` (line 325-345)

Change:
```python
if mode == "presentation":
    style_instructions = """
PRESENTATION MODE:
- Professional narration (40-60 seconds per slide)
- 3-4 complete sentences per slide to ensure adequate duration
- Speaking rate: ~150 words per minute
- Clear, engaging delivery
"""
else:  # academy
    style_instructions = """
ACADEMY MODE:
- Detailed explanatory narration (60-100 seconds per slide)
- 5-6 complete sentences per slide with examples
- Speaking rate: ~130 words per minute (slower for clarity)
- Teaching tone with thorough explanations
"""
```

### Step 2: Fix Timestamp Formula - Remove slide pause from calculation

**File:** `src/services/slide_narration_service.py` (line 410-435)

Change prompt to explicitly state **NO pause between slides**:

```python
**CRITICAL TIMING RULES:**

1. Calculate duration from word count ONLY (no artificial pauses):
   - duration = word_count / (speaking_rate / 60)
   - Presentation: 150 wpm = 2.5 words/sec
   - Academy: 130 wpm = 2.17 words/sec

2. Add small gap between subtitles (0.3s for breathing):
   - If first subtitle of presentation: start_time = 0
   - Otherwise: start_time = previous_subtitle.end_time + 0.3
   - end_time = start_time + duration

3. DO NOT add extra pause between slides:
   - Slides flow continuously with only 0.3s subtitle gap
   - No 1.5s or 2s pause between slide boundaries
   - This matches how audio is actually generated

Example calculation:
Slide 0, Subtitle 0: "Chào mừng đến với AI." (5 words)
  duration = 5 / 2.5 = 2.0s
  start = 0, end = 2.0

Slide 0, Subtitle 1: "Hôm nay học Machine Learning." (5 words)
  duration = 5 / 2.5 = 2.0s
  start = 2.0 + 0.3 = 2.3, end = 4.3

Slide 1, Subtitle 0: "ML là gì?" (3 words)  ← Same slide boundary, just +0.3s
  duration = 3 / 2.5 = 1.2s
  start = 4.3 + 0.3 = 4.6, end = 5.8
```

### Step 3: Target Duration via More Content

Instead of adding silence, make AI generate MORE text per slide:

**Presentation mode:**
- Current: 2-3 sentences → ~20-30 words/slide → ~10-12 sec/slide → 5-6 min total
- Target: 3-4 sentences → ~40-50 words/slide → ~20-25 sec/slide → 12-15 min total

**Academy mode:**
- Current: 3-4 sentences → ~40-50 words/slide → ~20-25 sec/slide → 12-15 min total
- Target: 5-6 sentences → ~70-90 words/slide → ~35-45 sec/slide → 20-25 min total

---

## 📊 Expected Results

**Before:**
- 30 slides × 10 sec/slide = 5 minutes (too short)
- Timestamp longer than audio (because AI calculated with pause, but audio has none)

**After:**
- Presentation: 30 slides × 20 sec/slide = 10 minutes
- Academy: 30 slides × 40 sec/slide = 20 minutes
- Timestamp matches audio perfectly (no artificial pauses)

---

## 🚀 Implementation Steps

1. ✅ **Update AI Prompt** - Change sentence count (3-4 for presentation, 5-6 for academy)
2. ✅ **Fix Timestamp Formula** - Remove slide pause instruction
3. ✅ **Test with sample presentation** - Verify timestamp matches audio
4. ⏳ **Deploy to production**

---

## 🔍 Testing Checklist

- [ ] Generate new subtitle for test presentation (30 slides)
- [ ] Check subtitle word count: ~40-50 words/slide (presentation) or ~70-90 (academy)
- [ ] Generate audio and verify duration: ~10-15 min (presentation) or ~20-25 min (academy)
- [ ] Compare timestamp vs audio duration: should be ±5% match
- [ ] Test auto-advance: slides should transition smoothly with audio

---

## 📝 Notes

**Why not add silence between slides?**
- Complicates merge logic
- Harder to debug timing issues
- Better to have continuous audio and let frontend handle auto-advance

**Why increase sentence count instead of slower speech?**
- More content = more value for users
- Slower speech can sound unnatural
- Easier to control via prompt than TTS parameters

**Alternative: Add pause in TTS text**
- Gemini TTS does NOT support SSML `<break>` tags
- Ellipsis "..." adds ~0.5s pause (unreliable)
- Periods "." add ~0.3s pause (more reliable)

**Recommended:** Keep continuous audio, increase content per slide.
