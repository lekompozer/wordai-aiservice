# Song Learning API - Technical Specification

**Version:** 1.0
**Base URL:** `https://api.wordai.pro/api/v1/songs`
**Authentication:** Firebase JWT Token (via `Authorization: Bearer <token>`)

---

## Overview

Song Learning API cho phép người dùng học tiếng Anh qua lời bài hát với bài tập điền từ (gap-fill). Hệ thống có 3 mức độ khó (Easy, Medium, Hard) và giới hạn 5 bài/ngày cho user free.

---

## Business Rules

### Daily Limits
- **Free users:** 5 songs/day
- **Premium users:** Unlimited access
- Reset time: 00:00 UTC daily

### Pricing
- **Monthly:** 29,000 VND/month
- **6 Months:** 150,000 VND (25k/month)
- **Yearly:** 250,000 VND (21k/month)

### Completion
- Điểm số ≥80% = Completed
- Track best score across multiple attempts
- Lưu lịch sử học tập (attempts, time spent)

---

## Endpoints

### 1. Browse Songs
**GET** `/api/v1/songs`

**Query Parameters:**
```typescript
{
  category?: string;        // "pop", "rock", "ballad", etc.
  search_query?: string;    // Search by title or artist
  skip?: number;            // Pagination offset (default: 0)
  limit?: number;           // Page size (default: 20, max: 50)
}
```

**Response:**
```typescript
{
  songs: [
    {
      song_id: string;                    // "song_12345"
      title: string;                      // "Imagine"
      artist: string;                     // "John Lennon"
      category: string;                   // "rock"
      youtube_id: string;                 // "YkgkThdzX-8"
      difficulties_available: string[];   // ["easy", "medium", "hard"]
      word_count: number;                 // 326
      view_count: number;                 // 1520
    }
  ],
  total: number;      // Total songs matching filters
  page: number;       // Current page (skip / limit)
  limit: number;      // Page size
}
```

---

### 2. Get Song Details
**GET** `/api/v1/songs/{song_id}`

**Response:**
```typescript
{
  song_id: string;
  title: string;
  artist: string;
  category: string;
  english_lyrics: string;           // Full lyrics
  vietnamese_lyrics: string;        // Translation
  youtube_url: string;              // "https://youtube.com/watch?v=..."
  youtube_id: string;
  view_count: number;
  word_count: number;
  difficulties_available: string[]; // ["easy", "medium", "hard"]
}
```

---

### 3. Get Random Song
**GET** `/api/v1/songs/random/pick`

**Query Parameters:**
```typescript
{
  difficulty?: string;    // "easy" | "medium" | "hard"
  category?: string;      // "pop" | "rock" | etc.
}
```

**Response:**
```typescript
{
  song_id: string;
  title: string;
  artist: string;
  category: string;
  difficulty: string;     // Selected difficulty
  youtube_url: string;
}
```

---

### 4. Start Learning Session
**POST** `/api/v1/songs/{song_id}/start`

**Request Body:**
```typescript
{
  difficulty: "easy" | "medium" | "hard";
}
```

**Response:**
```typescript
{
  session_id: string;         // UUID for this session
  song_id: string;
  difficulty: string;
  gaps: [
    {
      gap_id: string;         // Unique ID for this gap
      position: number;       // Gap position (0-indexed)
      line_number: number;    // Line in lyrics (1-indexed)
      word_index: number;     // Word position in line
      pos_tag: string;        // "NOUN", "VERB", "ADJ", "PROPN"
      difficulty_score: number; // 0-10 (harder = higher score)
      hint_char_count: number;  // Number of characters (e.g., 5 for "world")
    }
  ],
  lyrics_with_gaps: string;   // Lyrics with "___" placeholders
  total_gaps: number;         // 8-20 depending on difficulty
  message: string;            // "Started easy session for 'Imagine'"
}
```

**Errors:**
- `400` - Invalid difficulty
- `403` - Daily limit exceeded (free users)
- `404` - Song not found or no gaps available

---

### 5. Submit Answers
**POST** `/api/v1/songs/{song_id}/submit`

**Request Body:**
```typescript
{
  session_id: string;         // From start session
  difficulty: string;
  answers: [
    {
      gap_id: string;
      user_answer: string;    // User's answer (lowercased, trimmed)
    }
  ],
  time_spent_seconds: number; // Time spent on this attempt
}
```

**Response:**
```typescript
{
  session_id: string;
  score: number;              // 0-100 (percentage correct)
  correct_count: number;
  total_gaps: number;
  is_completed: boolean;      // true if score >= 80
  best_score: number;         // Best score for this song+difficulty
  message: string;            // "Great job! You scored 85%"
  correct_answers: [
    {
      gap_id: string;
      correct_answer: string;
      user_answer: string;
      is_correct: boolean;
    }
  ]
}
```

---

### 6. Get User Progress
**GET** `/api/v1/users/me/progress`

**Response:**
```typescript
{
  user_id: string;
  stats: {
    total_attempts: number;       // Total attempts across all songs
    total_completed: number;      // Songs with score >= 80%
    total_time_spent: number;     // Total seconds
    songs_played_today: number;   // 0-5 for free, unlimited for premium
    daily_limit_reached: boolean; // true if hit 5/day limit
    is_premium: boolean;          // Active subscription status
    completion_rate: number;      // % of attempted songs completed
  },
  recent_songs: [
    {
      song_id: string;
      title: string;
      artist: string;
      difficulty: string;
      best_score: number;         // Best score (0-100)
      attempts: number;           // Number of attempts
      last_played: string;        // ISO 8601 timestamp
    }
  ]
}
```

---

## Data Models

### Difficulty Levels
```typescript
enum Difficulty {
  EASY = "easy",      // 8-10 gaps, high-frequency words, proper nouns
  MEDIUM = "medium",  // 12-15 gaps, medium-frequency words
  HARD = "hard"       // 15-20 gaps, all words including rare
}
```

### Gap Item
```typescript
{
  gap_id: string;
  position: number;           // 0-indexed position in gaps array
  line_number: number;        // 1-indexed line in lyrics
  word_index: number;         // 0-indexed word position in line
  original_word: string;      // Correct answer
  lemma: string;              // Base form of word
  pos_tag: string;            // Part of speech
  difficulty_score: number;   // 0-10
  char_count: number;         // Length of word
  is_end_of_line: boolean;
}
```

### Subscription Status
Check via **GET** `/api/v1/users/me/progress`
- `is_premium: true` → Unlimited access
- `is_premium: false` → 5 songs/day limit

---

## Error Codes

### 400 Bad Request
```json
{
  "detail": "Invalid difficulty level. Must be easy, medium, or hard."
}
```

### 403 Forbidden
```json
{
  "detail": "Daily limit reached (5/5 songs). Upgrade to Premium for unlimited access."
}
```

### 404 Not Found
```json
{
  "detail": "Song not found or no gaps available for this difficulty."
}
```

### 401 Unauthorized
```json
{
  "detail": "Not authenticated"
}
```

---

## Implementation Notes

### Frontend Display
1. **Browse Page:**
   - Show song cards with title, artist, thumbnail
   - Display available difficulties as badges
   - Filter by category/search
   - Pagination with infinite scroll

2. **Song Detail Page:**
   - Embed YouTube player (`youtube_id`)
   - Display full lyrics + translation side-by-side
   - Difficulty selector (Easy/Medium/Hard buttons)
   - "Start Learning" button

3. **Learning Session:**
   - Display `lyrics_with_gaps` with `___` highlighted
   - Input fields for each gap (use `gap_id` as key)
   - Timer to track `time_spent_seconds`
   - Submit button → show results overlay

4. **Results Screen:**
   - Score percentage (color: green ≥80%, yellow 60-79%, red <60%)
   - List correct/incorrect answers
   - "Try Again" or "Next Song" buttons
   - Update progress stats

5. **Progress Dashboard:**
   - Display `stats` (total attempts, completion rate, daily limit)
   - Recent songs list with best scores
   - Premium upsell banner if `is_premium: false`

### Premium Check
```javascript
async function canPlaySong(userId) {
  const progress = await fetch('/api/v1/users/me/progress');
  const data = await progress.json();

  if (data.stats.is_premium) {
    return { allowed: true };
  }

  if (data.stats.songs_played_today >= 5) {
    return {
      allowed: false,
      message: "Daily limit reached. Upgrade to Premium!"
    };
  }

  return { allowed: true, remaining: 5 - data.stats.songs_played_today };
}
```

### Answer Validation (Frontend)
```javascript
function normalizeAnswer(userInput) {
  return userInput
    .toLowerCase()
    .trim()
    .replace(/[^a-z]/g, ''); // Remove non-alphabetic chars
}
```

Backend validates using same normalization + fuzzy matching for common typos.

---

## Testing Checklist

- [ ] Browse songs with filters
- [ ] Get song details
- [ ] Random song selection
- [ ] Start session (all 3 difficulties)
- [ ] Submit answers (correct/incorrect/partial)
- [ ] Daily limit enforcement (free users)
- [ ] Premium access (unlimited)
- [ ] Progress tracking
- [ ] Score calculation (≥80% completion)
- [ ] Edge cases: empty answers, special characters

---

## Next Steps (Phase 6)

1. **Subscription Integration:**
   - MoMo payment gateway
   - VNPay integration
   - Subscription management APIs

2. **Social Features:**
   - Leaderboard (top scores per song)
   - Share progress on social media
   - Challenge friends

3. **Analytics:**
   - Track popular songs
   - Difficulty distribution
   - Common mistakes per gap

---

**Contact:** Backend team ready for frontend integration
**Status:** APIs deployed on `https://api.wordai.pro`
**Documentation:** This spec + OpenAPI docs at `/docs`
