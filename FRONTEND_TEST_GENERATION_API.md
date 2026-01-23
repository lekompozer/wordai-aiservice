# Frontend Integration Guide - Test Generation APIs

**Date:** January 23, 2026  
**Version:** 2.0 (Worker Queue Pattern)

## 🎯 Overview

Hệ thống test generation đã được migrate sang **Redis Worker Pattern** với max 5 concurrent tasks.

**Key Changes:**
- ✅ Response giờ trả về `job_id` (tracking trong Redis)
- ✅ Polling vẫn dùng endpoint cũ: `GET /tests/{test_id}/status`
- ✅ Worker xử lý isolated (không block API)
- ✅ Resource control tốt hơn (max 5 concurrent)

---

## 📋 Available Test Generation Endpoints

### 1. Listening Comprehension Test
### 2. Grammar Test (Coming Soon)
### 3. Vocabulary Test (Coming Soon)

---

## 🎙️ 1. LISTENING COMPREHENSION TEST

### Endpoint
```
POST /api/v1/tests/generate/listening
```

### Request Headers
```http
Authorization: Bearer <firebase_token>
Content-Type: application/json
```

### Request Body
```typescript
interface GenerateListeningTestRequest {
  // Basic info
  title: string;                    // "IELTS Listening - Travel Booking"
  description?: string;              // Optional description
  language: string;                  // "en", "vi", "zh", "fr"
  topic: string;                     // "Travel", "Business", "Education"
  difficulty: string;                // "beginner", "intermediate", "advanced"
  
  // Test configuration
  num_questions: number;             // 10, 20, 30, 40
  num_audio_sections: number;        // 1-4 sections
  time_limit_minutes?: number;       // Default: 60
  passing_score?: number;            // Default: 70
  use_pro_model?: boolean;           // Default: false (Gemini Pro vs Flash)
  
  // Audio configuration
  audio_config: {
    num_speakers: number;            // 1 (monologue) or 2 (dialogue)
    voice_names?: string[];          // Optional: ["Aoede", "Charon"]
    speaking_rate?: number;          // 0.5 - 2.0, default: 1.0
  };
  
  // Optional custom query
  user_query?: string;               // "Create a conversation about..."
  
  // Phase 7 & 8 (Advanced)
  user_transcript?: string;          // User-provided transcript
  audio_file_path?: string;          // Uploaded audio file path (R2)
}
```

### Response (Success)
```typescript
interface GenerateListeningTestResponse {
  success: true;
  test_id: string;                  // MongoDB test document ID
  job_id: string;                   // NEW: Redis job ID for tracking
  status: "pending";                // Initial status
  message: string;                  // "Listening test generation queued..."
  estimated_time_seconds: number;   // num_audio_sections * 60
}
```

### Example Request
```javascript
const response = await fetch('/api/v1/tests/generate/listening', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${firebaseToken}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    title: "IELTS Listening Practice - Part 1",
    language: "en",
    topic: "Travel and Tourism",
    difficulty: "intermediate",
    num_questions: 10,
    num_audio_sections: 1,
    audio_config: {
      num_speakers: 2,
      voice_names: ["Aoede", "Charon"],
      speaking_rate: 1.0
    },
    user_query: "Create a conversation between a tourist and a hotel receptionist about room booking."
  })
});

const data = await response.json();
console.log('Test ID:', data.test_id);
console.log('Job ID:', data.job_id);   // NEW field
```

---

## 📊 2. POLLING FOR STATUS

### Endpoint (UNCHANGED)
```
GET /api/v1/tests/{test_id}/status
```

### Request Headers
```http
Authorization: Bearer <firebase_token>
```

### Response
```typescript
interface TestStatusResponse {
  test_id: string;
  status: "pending" | "generating" | "completed" | "failed";
  progress_percent: number;          // 0-100
  message: string;                   // Progress description
  error_message?: string;            // If status = "failed"
  
  // Completed state (status = "completed")
  test?: {
    _id: string;
    title: string;
    test_type: "listening";
    test_category: "academic" | "general";
    language: string;
    topic: string;
    difficulty: string;
    num_questions: number;
    time_limit_minutes: number;
    passing_score: number;
    questions: Question[];
    audio_sections: AudioSection[];
    created_at: string;
    updated_at: string;
  };
}
```

### Polling Pattern (RECOMMENDED)
```javascript
async function pollTestStatus(testId) {
  const maxAttempts = 120;  // 2 minutes (1 section = ~60s)
  const pollInterval = 1000; // 1 second
  
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const response = await fetch(`/api/v1/tests/${testId}/status`, {
      headers: {
        'Authorization': `Bearer ${firebaseToken}`
      }
    });
    
    const data = await response.json();
    
    console.log(`Progress: ${data.progress_percent}% - ${data.message}`);
    
    if (data.status === 'completed') {
      console.log('✅ Test generated successfully!');
      return data.test;
    }
    
    if (data.status === 'failed') {
      console.error('❌ Test generation failed:', data.error_message);
      throw new Error(data.error_message);
    }
    
    // Wait before next poll
    await new Promise(resolve => setTimeout(resolve, pollInterval));
  }
  
  throw new Error('Test generation timeout');
}

// Usage
const test = await pollTestStatus(data.test_id);
console.log('Generated test:', test);
```

---

## 🎯 3. Status Flow

```
┌─────────┐
│ pending │  ← Initial state (job queued in Redis)
└────┬────┘
     │
     ↓
┌────────────┐
│ generating │  ← Worker processing (10% → 100%)
└─────┬──────┘
      │
      ├──────────────┐
      │              │
      ↓              ↓
┌───────────┐  ┌─────────┐
│ completed │  │ failed  │
└───────────┘  └─────────┘
```

### Progress Percent Mapping
- `0%` - Pending (waiting for worker)
- `10%` - AI generating questions
- `20-40%` - Generating audio sections
- `60-80%` - Uploading audio to R2
- `90%` - Finalizing test
- `100%` - Completed

---

## 💰 4. Points Cost

### Formula
```
points_cost = 5 + (num_audio_sections - 1)
```

### Examples
- 1 section: 5 points (1 Gemini + 1 TTS)
- 2 sections: 6 points (1 Gemini + 2 TTS)
- 3 sections: 7 points (1 Gemini + 3 TTS)
- 4 sections: 8 points (1 Gemini + 4 TTS)

### Check Points Before Creation
```javascript
// Frontend should check user points first
const userPoints = await getUserPoints();
const requiredPoints = 5 + (numAudioSections - 1);

if (userPoints < requiredPoints) {
  alert(`Insufficient points. Required: ${requiredPoints}, You have: ${userPoints}`);
  return;
}

// Proceed with test creation
const response = await createListeningTest({...});
```

---

## 📝 5. Question Types in Response

### Multiple Choice
```typescript
{
  question_id: "q1",
  question_type: "multiple_choice",
  question_text: "What is the main topic?",
  options: ["A. Travel", "B. Business", "C. Education", "D. Health"],
  correct_answer: "A",
  audio_section_id: "section_1",
  timestamp_start: 5.2,
  timestamp_end: 12.8
}
```

### Fill in the Blank
```typescript
{
  question_id: "q2",
  question_type: "fill_blank",
  question_text: "The hotel is located in ____.",
  correct_answer: "downtown",
  audio_section_id: "section_1",
  timestamp_start: 15.0,
  timestamp_end: 18.5
}
```

### True/False
```typescript
{
  question_id: "q3",
  question_type: "true_false",
  question_text: "The booking is for 3 nights.",
  correct_answer: "True",
  audio_section_id: "section_1"
}
```

### Matching
```typescript
{
  question_id: "q4",
  question_type: "matching",
  question_text: "Match the facilities with their locations",
  left_items: [
    {"key": "A", "text": "Swimming pool"},
    {"key": "B", "text": "Restaurant"}
  ],
  right_items: [
    {"key": "1", "text": "Ground floor"},
    {"key": "2", "text": "Rooftop"}
  ],
  correct_answers: {"A": "2", "B": "1"}
}
```

---

## 🔊 6. Audio Sections Structure

```typescript
interface AudioSection {
  section_id: string;              // "section_1", "section_2"
  section_number: number;          // 1, 2, 3, 4
  audio_url: string;               // R2 public URL
  transcript: string;              // Full transcript
  duration_seconds: number;        // Audio length
  speaker_config: {
    num_speakers: number;
    speakers: Array<{
      name: string;              // "Speaker A", "Speaker B"
      voice: string;             // "Aoede", "Charon"
      gender: string;            // "female", "male"
    }>;
  };
  questions: string[];             // Question IDs in this section
}
```

---

## ⚠️ 7. Error Handling

### Common Error Responses

#### Insufficient Points (402)
```json
{
  "detail": {
    "error": "Insufficient points",
    "message": "Listening test generation requires 6 points. You have 3 points.",
    "required_points": 6,
    "current_points": 3,
    "upgrade_url": "https://ai.wordai.pro/pricing"
  }
}
```

#### Queue Full (503)
```json
{
  "detail": "Queue is full. Please try again later."
}
```

#### Generation Failed
```typescript
// Status endpoint returns:
{
  test_id: "...",
  status: "failed",
  progress_percent: 0,
  message: "Test generation failed. Please try again.",
  error_message: "Gemini API rate limit exceeded"
}
```

### Frontend Error Handling
```javascript
try {
  const response = await createListeningTest(requestData);
  
  if (response.status === 402) {
    const error = await response.json();
    showUpgradeModal(error.detail);
    return;
  }
  
  if (response.status === 503) {
    showToast('Server busy, please try again later');
    return;
  }
  
  const data = await response.json();
  const test = await pollTestStatus(data.test_id);
  
  navigateToTest(test._id);
  
} catch (error) {
  console.error('Test generation error:', error);
  showToast('Failed to generate test');
}
```

---

## 🚀 8. Best Practices

### 1. Show Progress UI
```javascript
function TestGenerationProgress({ testId }) {
  const [status, setStatus] = useState(null);
  
  useEffect(() => {
    const interval = setInterval(async () => {
      const data = await fetchTestStatus(testId);
      setStatus(data);
      
      if (data.status === 'completed' || data.status === 'failed') {
        clearInterval(interval);
      }
    }, 1000);
    
    return () => clearInterval(interval);
  }, [testId]);
  
  return (
    <div>
      <ProgressBar value={status?.progress_percent || 0} />
      <p>{status?.message}</p>
    </div>
  );
}
```

### 2. Handle Browser Close
```javascript
// Warn user if they try to close during generation
window.addEventListener('beforeunload', (e) => {
  if (isGenerating) {
    e.preventDefault();
    e.returnValue = 'Test generation in progress. Are you sure?';
  }
});
```

### 3. Resume After Refresh
```javascript
// Store test_id in localStorage
localStorage.setItem('generating_test_id', testId);

// On app load, check for pending generation
const pendingTestId = localStorage.getItem('generating_test_id');
if (pendingTestId) {
  const status = await fetchTestStatus(pendingTestId);
  if (status.status === 'generating') {
    resumePolling(pendingTestId);
  } else {
    localStorage.removeItem('generating_test_id');
  }
}
```

---

## 📚 9. Grammar & Vocabulary Tests (Coming Soon)

### Grammar Test
```
POST /api/v1/tests/generate/grammar
```
Status: Not yet implemented

### Vocabulary Test
```
POST /api/v1/tests/generate/vocabulary
```
Status: Not yet implemented

### General Test
```
POST /api/v1/tests/generate/general
```
Status: In development (background task pattern, chưa migrate)

---

## 🔄 10. Migration Notes (For Backend Team)

### What Changed
- ❌ **OLD:** `asyncio.create_task(generate_listening_test_background_job(...))`
- ✅ **NEW:** `await queue.enqueue_generic_task(TestGenerationTask(...))`

### Impact on Frontend
- **No breaking changes** in request/response format
- **New field:** `job_id` in response (can be ignored)
- **Polling endpoint:** Same as before
- **MongoDB structure:** Unchanged

### Worker Architecture
```
API Request → Redis Queue → Worker (max 5) → Update MongoDB → Frontend polls MongoDB
```

---

## 📞 Support

**Issues?** Check:
1. Redis connection (worker logs)
2. MongoDB test record (status field)
3. R2 storage (audio upload errors)
4. Gemini API limits (rate limiting)

**Logs:**
```bash
# Worker logs
docker logs test-generation-worker -f

# API logs
docker logs ai-chatbot-rag -f | grep "listening"
```

---

**Last Updated:** January 23, 2026  
**Backend Version:** Worker Queue Pattern v2.0
