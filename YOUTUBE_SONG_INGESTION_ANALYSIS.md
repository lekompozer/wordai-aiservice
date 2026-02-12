# YouTube Song Ingestion - Technical Analysis & Implementation Plan

**Document Type:** Technical Analysis  
**Date:** February 12, 2026  
**Status:** Proposed Implementation  
**Author:** WordAI Development Team

---

## Executive Summary

This document analyzes the feasibility and implementation approach for allowing users to submit YouTube links for English songs not yet in the WordAI database. The system will automatically extract lyrics, generate gap exercises, and make the song available for learning.

**Current Database:** 23,203 songs with English/Vietnamese lyrics and gap exercises.

**User Request:** "User gửi 1 link Youtube bài hát tiếng Anh hoàn toàn không có trong database thì có cách nào tạo ra dữ liệu tương tự được không?"

**Answer:** **Yes, technically feasible** with multi-step automated pipeline and manual review.

---

## Table of Contents

1. [Problem Statement](#problem-statement)
2. [Technical Challenges](#technical-challenges)
3. [Proposed Solution](#proposed-solution)
4. [User Flow & UX](#user-flow--ux)
5. [Technical Architecture](#technical-architecture)
6. [API Specification](#api-specification)
7. [Data Quality & Validation](#data-quality--validation)
8. [Cost Analysis](#cost-analysis)
9. [Timeline & Phases](#timeline--phases)
10. [Risks & Mitigations](#risks--mitigations)

---

## Problem Statement

### Current Limitation

Users can only learn from 23,203 pre-crawled songs from loidichvn.com. If a user wants to learn from a song not in the database, they cannot.

### User Need

- User finds an English song on YouTube they want to learn
- Song may be new release, obscure artist, or not on loidichvn.com
- User wants to practice with gap-fill exercises for this song
- User expects similar quality to existing songs

### Business Value

- **Increased user engagement:** Users can learn from their favorite songs
- **Database growth:** Organic expansion of song library
- **Competitive advantage:** Unique feature (user-requested content)
- **Reduced dependency:** Less reliance on loidichvn.com crawler

---

## Technical Challenges

### 1. Lyrics Extraction

**Challenge:** YouTube videos don't contain structured lyrics.

**Options:**

| Method | Accuracy | Cost | Implementation |
|--------|----------|------|----------------|
| YouTube Auto-Captions | 60-80% | Free | Easy (YouTube API) |
| Speech-to-Text (Whisper AI) | 85-95% | $0.006/min | Medium |
| Lyrics APIs (Genius, Musixmatch) | 95-99% | Varies | Easy |
| Manual Transcription | 100% | High | Hard (requires humans) |

**Recommended:** **Lyrics APIs (Genius/Musixmatch)** for best accuracy, fallback to Whisper AI.

### 2. Vietnamese Translation

**Challenge:** Need Vietnamese lyrics for dual-language display.

**Options:**

| Method | Quality | Cost | Speed |
|--------|---------|------|-------|
| Google Translate API | 70-80% | $20/1M chars | Fast |
| Claude Sonnet 4.5 | 90-95% | $3/1M tokens | Medium |
| DeepL API | 85-90% | $25/1M chars | Fast |
| Human Translation | 100% | Very High | Slow |

**Recommended:** **Claude Sonnet 4.5** for best quality at reasonable cost.

### 3. Gap Generation

**Challenge:** Automated word selection for exercises.

**Status:** **Already solved!** Existing pipeline:
- spaCy NLP for POS tagging
- wordfreq for difficulty scoring
- Automatic gap selection (NOUN, VERB, ADJ)
- 3 difficulty levels (easy, medium, hard)

**No additional work needed.**

### 4. Quality Assurance

**Challenge:** Ensure generated content meets quality standards.

**Risks:**
- Incorrect lyrics (lyrics don't match audio)
- Poor translation quality
- Profanity or inappropriate content
- Copyright issues

**Solution:** Multi-stage validation + admin review queue.

---

## Proposed Solution

### Architecture: 6-Step Pipeline

```
User Submit YouTube Link
    ↓
1. Video Validation
    ↓
2. Lyrics Extraction (API)
    ↓
3. Vietnamese Translation (Claude)
    ↓
4. Gap Generation (Existing Pipeline)
    ↓
5. Quality Checks & Validation
    ↓
6. Admin Review Queue → Approve/Reject
    ↓
Song Available for Learning
```

### Technology Stack

| Component | Technology | Reason |
|-----------|------------|--------|
| Video metadata | YouTube Data API v3 | Free, reliable |
| Lyrics extraction | Genius API + Musixmatch | High accuracy |
| Translation | Claude Sonnet 4.5 | Best quality |
| Gap generation | spaCy + wordfreq | Already implemented |
| Profanity check | better-profanity | Already implemented |
| Storage | MongoDB | Existing database |
| Queue | Redis | Background processing |

---

## User Flow & UX

### Frontend User Journey

**Step 1: Submit Request**

*User on "Browse Songs" page*

- User clicks **"Request New Song"** button
- Modal opens with input field
- User pastes YouTube URL: `https://www.youtube.com/watch?v=dQw4w9WgXcQ`
- System validates URL format
- User clicks **"Submit Request"**

**Step 2: Processing (Real-time Feedback)**

```
✓ Validating YouTube video...
✓ Checking if song already exists...
✓ Extracting song information...
⏳ Finding lyrics... (this may take 30-60 seconds)
```

**Step 3: Success Response**

```
✅ Song Request Submitted!

Song: "Never Gonna Give You Up"
Artist: Rick Astley

Status: ⏳ Pending Review

Your request has been queued for processing. 
We'll generate the exercise and notify you when it's ready!

Estimated time: 5-10 minutes
```

**Step 4: Notification (Email/Push)**

```
🎵 Your Song is Ready!

"Never Gonna Give You Up" by Rick Astley is now available for learning!

[Start Learning] [View Song]
```

### Alternative Flow: Immediate Availability (No Review)

For **premium users** or **trusted users**, skip admin review:

```
✅ Song Added Successfully!

"Never Gonna Give You Up" by Rick Astley

[Start Learning Now] [View Exercise]
```

---

## Technical Architecture

### Database Schema

**New Collection: `user_song_requests`**

```javascript
{
  request_id: "UUID",
  user_id: "firebase_uid",
  user_email: "user@example.com",
  
  // Input
  youtube_url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  youtube_id: "dQw4w9WgXcQ",
  
  // Extracted metadata
  video_title: "Rick Astley - Never Gonna Give You Up",
  video_duration: 213, // seconds
  
  // Processing status
  status: "pending" | "processing" | "completed" | "failed" | "rejected",
  current_step: "lyrics_extraction",
  progress_percentage: 45,
  
  // Generated data
  song_id: "auto_generated_uuid", // Links to song_lyrics
  english_lyrics: "We're no strangers to love...",
  vietnamese_lyrics: "Chúng ta không xa lạ với tình yêu...",
  word_count: 780,
  has_profanity: false,
  
  // Quality metrics
  lyrics_confidence: 0.95, // API confidence score
  translation_quality: "high",
  gap_coverage: {
    easy: 15,
    medium: 25,
    hard: 35
  },
  
  // Review
  requires_review: true,
  reviewed_by: null, // Admin email
  reviewed_at: null,
  review_notes: null,
  
  // Metadata
  requested_at: ISODate("2026-02-12T10:00:00Z"),
  completed_at: null,
  error_message: null,
  processing_time_seconds: null,
}
```

### Worker Architecture

**New Worker: `song_request_worker.py`**

```python
# Async background job processing
async def process_song_request(request_id: str):
    """
    Process user song request through full pipeline.
    
    Steps:
    1. Validate YouTube video (exists, not private, English)
    2. Extract lyrics from Genius/Musixmatch APIs
    3. Translate to Vietnamese using Claude
    4. Generate gaps using existing pipeline
    5. Run quality checks (profanity, completeness)
    6. Queue for admin review OR auto-approve
    7. Notify user
    """
    
    # Update status to "processing"
    await update_request_status(request_id, "processing", step="validation")
    
    # Step 1: Validate video
    video_info = await validate_youtube_video(youtube_id)
    
    # Step 2: Extract lyrics (60s timeout)
    await update_request_status(request_id, "processing", step="lyrics")
    lyrics = await extract_lyrics(video_info)
    
    # Step 3: Translate (30s)
    await update_request_status(request_id, "processing", step="translation")
    vietnamese = await translate_to_vietnamese(lyrics)
    
    # Step 4: Generate gaps (20s)
    await update_request_status(request_id, "processing", step="gaps")
    gaps = await generate_song_gaps(lyrics, song_id)
    
    # Step 5: Quality checks
    await update_request_status(request_id, "processing", step="validation")
    quality = await validate_quality(lyrics, vietnamese, gaps)
    
    # Step 6: Review decision
    if quality.score >= 0.9 and user.is_trusted:
        # Auto-approve
        await create_song_in_database(...)
        await notify_user(request_id, status="approved")
    else:
        # Queue for admin review
        await queue_for_review(request_id)
        await notify_user(request_id, status="pending_review")
    
    await update_request_status(request_id, "completed")
```

---

## API Specification

### 1. Submit Song Request

**Endpoint:** `POST /api/v1/songs/requests`

**Request:**
```json
{
  "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
}
```

**Response:** `202 Accepted`
```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "message": "Your song request is being processed",
  "estimated_time_minutes": 5,
  "song_info": {
    "title": "Rick Astley - Never Gonna Give You Up",
    "youtube_id": "dQw4w9WgXcQ",
    "duration": 213
  }
}
```

**Errors:**
- `400` - Invalid YouTube URL
- `409` - Song already exists in database
- `429` - Too many requests (rate limit: 5/day for free users)

### 2. Check Request Status

**Endpoint:** `GET /api/v1/songs/requests/{request_id}`

**Response:** `200 OK`
```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "current_step": "translation",
  "progress_percentage": 60,
  "estimated_remaining_seconds": 45,
  "song_info": {
    "title": "Never Gonna Give You Up",
    "artist": "Rick Astley"
  }
}
```

**Possible statuses:**
- `pending` - In queue
- `processing` - Currently being processed
- `pending_review` - Waiting for admin approval
- `completed` - Song available for learning
- `failed` - Processing error
- `rejected` - Admin rejected request

### 3. Get User Requests

**Endpoint:** `GET /api/v1/songs/requests`

**Response:** `200 OK`
```json
{
  "requests": [
    {
      "request_id": "...",
      "status": "completed",
      "song_id": "auto_123",
      "title": "Never Gonna Give You Up",
      "requested_at": "2026-02-12T10:00:00Z",
      "completed_at": "2026-02-12T10:05:30Z"
    }
  ],
  "total": 3,
  "pending": 1,
  "completed": 2
}
```

### 4. Admin Review Queue

**Endpoint:** `GET /api/v1/songs/admin/review-queue`

**Response:** `200 OK`
```json
{
  "queue": [
    {
      "request_id": "...",
      "requested_by": "user@example.com",
      "song_title": "Never Gonna Give You Up",
      "lyrics_confidence": 0.95,
      "quality_score": 0.88,
      "requested_at": "2026-02-12T10:00:00Z",
      "preview_url": "/api/v1/songs/requests/.../preview"
    }
  ],
  "total_pending": 15
}
```

### 5. Admin Approve/Reject

**Endpoint:** `POST /api/v1/songs/admin/review-queue/{request_id}/approve`

**Request:**
```json
{
  "notes": "Good quality, approved"
}
```

**Response:** `200 OK`
```json
{
  "message": "Song approved and published",
  "song_id": "auto_123"
}
```

---

## Data Quality & Validation

### Automated Quality Checks

**Pre-Review Validations:**

1. **Lyrics Quality**
   - Minimum 100 words
   - Maximum 2000 words (not an epic poem)
   - Contains English words (wordfreq check)
   - No profanity (better-profanity)
   - Proper formatting (lines, verses)

2. **Translation Quality**
   - Claude returns quality assessment
   - Length ratio check (Vietnamese ~1.2x English)
   - No "untranslated" markers

3. **Gap Generation**
   - Minimum gaps: 10 (easy), 15 (medium), 20 (hard)
   - Coverage: At least 5% of words
   - Balanced POS distribution (nouns + verbs + adjectives)

4. **Video Validation**
   - YouTube video exists and is public
   - Video language is English (metadata check)
   - Not age-restricted or blocked
   - Duration: 1-10 minutes (reasonable song length)

### Quality Scoring

**Automated Quality Score (0-1):**

```python
quality_score = (
    lyrics_confidence * 0.4 +      # API confidence
    translation_quality * 0.3 +    # Claude assessment
    gap_coverage_score * 0.2 +     # Exercise quality
    metadata_completeness * 0.1    # Title, artist extracted
)

# Auto-approve threshold: 0.90
# Manual review: < 0.90
```

### Admin Review Interface

**Display to admin:**

- ✅ Quality score: 0.88 / 1.00
- ✅ Lyrics confidence: 95%
- ⚠️ Translation quality: Medium (Claude flagged 2 phrases)
- ✅ Gaps generated: 15 easy, 25 medium, 35 hard
- ⚠️ Profanity: None detected
- **Preview:** Show side-by-side English/Vietnamese with gaps

**Admin actions:**
- ✅ Approve (publish immediately)
- ✏️ Edit (correct lyrics/translation before publishing)
- ❌ Reject (notify user with reason)

---

## Cost Analysis

### Per-Song Processing Cost

| Step | Service | Cost | Notes |
|------|---------|------|-------|
| YouTube validation | YouTube Data API | $0 | Free quota: 10,000/day |
| Lyrics extraction | Genius API | $0 | Free tier |
| Translation (800 words) | Claude Sonnet 4.5 | ~$0.003 | $3/1M tokens |
| Gap generation | Local (spaCy) | $0 | CPU only |
| Storage (MongoDB) | Included | $0 | Existing DB |
| **Total per song** | | **~$0.003** | **Less than 1 cent!** |

### Monthly Cost Estimates

**Scenario: 1,000 user requests/month**

- Processing: $3
- Storage (100MB new data): $0.10
- Bandwidth: $1
- **Total: ~$5/month**

**Scenario: 10,000 requests/month**

- Processing: $30
- Storage (1GB): $1
- Bandwidth: $10
- **Total: ~$40/month**

### Cost Savings vs. Manual Work

**Manual song addition (current process):**
- Find lyrics: 10 minutes
- Translate: 20 minutes
- Format & upload: 10 minutes
- Generate gaps: 5 minutes
- **Total: 45 minutes @ $20/hour = $15/song**

**Automated pipeline:**
- Processing: $0.003
- Admin review (if needed): 2 minutes @ $20/hour = $0.67
- **Total: $0.67/song**

**Savings: 95% cost reduction!**

---

## Timeline & Phases

### Phase 1: MVP (2 weeks)

**Goal:** Basic pipeline with manual review

**Deliverables:**
- YouTube URL validation
- Lyrics extraction (Genius API integration)
- Claude translation integration
- Gap generation (reuse existing code)
- Admin review queue UI
- Basic user notification (email)

**Limitations:**
- All requests require admin review
- No real-time status updates
- Limited error handling

### Phase 2: Enhanced UX (1 week)

**Deliverables:**
- Real-time status polling (WebSocket or SSE)
- In-app notifications
- User request history page
- Better error messages
- Rate limiting (5 requests/day for free users)

### Phase 3: Auto-Approval (1 week)

**Deliverables:**
- Quality scoring algorithm
- Auto-approve high-quality songs (score >= 0.90)
- Trusted user system (users with 10+ approved requests)
- Premium users: Unlimited requests + auto-approve

### Phase 4: Advanced Features (2 weeks)

**Deliverables:**
- Fallback to Whisper AI if lyrics APIs fail
- Manual lyrics input option (user pastes lyrics)
- Batch processing (admin can approve multiple at once)
- Analytics dashboard (request success rate, processing times)
- Community voting (users upvote requested songs)

**Total Timeline: 6 weeks**

---

## Risks & Mitigations

### Risk 1: Lyrics Extraction Accuracy

**Risk:** Lyrics APIs may not have all songs, especially new releases.

**Impact:** User frustration, failed requests.

**Mitigation:**
- Try multiple APIs in sequence (Genius → Musixmatch → Fallback)
- Implement Whisper AI fallback (transcribe from audio)
- Allow user to paste lyrics manually
- Show clear error message: "Lyrics not found. Try again in a few days."

**Likelihood:** Medium  
**Severity:** Medium

### Risk 2: Translation Quality

**Risk:** Claude may produce poor Vietnamese translations.

**Impact:** Bad learning experience, user complaints.

**Mitigation:**
- Admin review catches bad translations
- Quality scoring flags low-confidence translations
- Allow users to report translation issues
- Build feedback loop to improve prompts

**Likelihood:** Low (Claude is very good)  
**Severity:** Medium

### Risk 3: Copyright Issues

**Risk:** Publishing copyrighted lyrics without permission.

**Impact:** Legal liability, takedown notices.

**Mitigation:**
- **Fair Use Defense:** Educational purpose, transformative use (gap exercises)
- Display attribution (song title, artist)
- Implement DMCA takedown process
- Don't monetize user-requested songs
- Consider licensing deal with lyrics providers

**Likelihood:** Low  
**Severity:** High

**Legal Consultation Required.**

### Risk 4: Spam & Abuse

**Risk:** Users spam requests, inappropriate content.

**Impact:** Wasted resources, admin burden.

**Mitigation:**
- Rate limiting (5/day for free, 50/day for premium)
- Profanity detection (auto-reject)
- User reputation system (trusted users)
- Admin can ban abusive users
- CAPTCHA on request form

**Likelihood:** Medium  
**Severity:** Low

### Risk 5: Processing Failures

**Risk:** Pipeline crashes, APIs timeout, bugs.

**Impact:** Failed requests, user frustration.

**Mitigation:**
- Comprehensive error handling
- Retry logic (3 attempts)
- Timeout handling (90s max per step)
- Error notifications to user
- Failed request queue for manual debugging
- Monitoring & alerts (Sentry)

**Likelihood:** Medium  
**Severity:** Medium

---

## Recommendations

### Immediate Next Steps

1. **Build MVP (Phase 1)** - 2 weeks
   - Start with manual review for all requests
   - Validate user demand and quality

2. **Legal Review** - Parallel to MVP
   - Consult lawyer about copyright implications
   - Review fair use policy
   - Implement DMCA process

3. **User Testing** - After MVP
   - Beta test with 50 users
   - Gather feedback on UX and quality
   - Iterate based on learnings

### Long-Term Strategy

**Year 1 Goals:**
- 10,000 user-requested songs
- 90% auto-approval rate
- <5 minute average processing time
- Community-driven song library

**Business Model:**
- Free users: 5 requests/day, manual review
- Premium users: Unlimited requests, auto-approve, priority processing
- Gamification: Users earn "curator points" for successful requests

---

## Conclusion

**Is it technically feasible?** **YES.**

**Should we build it?** **YES, with phased approach.**

**Key Success Factors:**
1. ✅ Existing gap generation pipeline (already working)
2. ✅ Low cost per song (~$0.003)
3. ✅ High-quality translation (Claude Sonnet 4.5)
4. ✅ Admin review safety net
5. ⚠️ Legal clearance required

**Recommended Approach:**
- Start with MVP + manual review
- Validate user demand and quality
- Gradually automate based on confidence
- Monitor legal landscape

**Expected Impact:**
- 📈 User engagement +30%
- 📚 Song library growth +50%/year
- 💰 Premium conversion +15%
- 🎯 Unique competitive advantage

---

**Next Action:** Present to stakeholders for approval, then begin Phase 1 development.

