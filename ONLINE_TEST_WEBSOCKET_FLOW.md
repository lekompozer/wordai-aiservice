# Online Test WebSocket Flow - Frontend Integration Guide

## Overview

Hệ thống làm bài test online với WebSocket real-time sync và khả năng reconnect sau khi mất kết nối.

**Đặc điểm chính:**
- Backend tự động tính thời gian dựa trên `started_at` (không phụ thuộc frontend)
- Frontend gửi FULL answers mỗi lần để đề phòng mất kết nối
- Có thể reconnect và tiếp tục làm bài nếu chưa hết giờ
- Submit bị reject nếu quá thời gian → trả về submission gần nhất (nếu có)

---

---

## Media Upload for Essay Answers

### Generate Presigned URL for Media Upload

**Endpoint:** `POST /api/v1/tests/submissions/answer-media/presigned-url`

**Headers:**
```
Authorization: Bearer {firebase_token}
Content-Type: application/json
```

**Request Body:**
```json
{
  "filename": "diagram.png",
  "file_size_mb": 2.5,
  "content_type": "image/png"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "presigned_url": "https://...",
  "file_url": "https://static.wordai.pro/answer-media/user123/diagram.png",
  "file_size_mb": 2.5,
  "expires_in": 300
}
```

**Supported Media Types:**
- **Images**: JPG, PNG, GIF (`image/jpeg`, `image/png`, `image/gif`)
- **Audio**: MP3, WAV, M4A (`audio/mpeg`, `audio/wav`, `audio/x-m4a`)
- **Documents**: PDF, DOCX (`application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`)

**Upload Flow:**
```javascript
// Step 1: Get presigned URL
const { presigned_url, file_url } = await fetch('/api/v1/tests/submissions/answer-media/presigned-url', {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
  body: JSON.stringify({
    filename: file.name,
    file_size_mb: file.size / (1024 * 1024),
    content_type: file.type
  })
}).then(r => r.json());

// Step 2: Upload file directly to R2
await fetch(presigned_url, {
  method: 'PUT',
  body: file,
  headers: { 'Content-Type': file.type }
});

// Step 3: Add to essay answer
const mediaAttachment = {
  media_type: getMediaType(file.type), // 'image', 'audio', 'document'
  media_url: file_url,
  filename: file.name,
  file_size_mb: file.size / (1024 * 1024),
  description: userDescription || ''
};

// Step 4: Save with WebSocket
socket.emit('save_answers_batch', {
  session_id: sessionId,
  answers: {
    [questionId]: {
      question_type: 'essay',
      essay_answer: essayText,
      media_attachments: [mediaAttachment]
    }
  }
});
```

**Storage Limits:**
- Max file size: **20MB** per attachment
- Multiple attachments per question: **Yes**
- Storage counted toward user's quota: **Yes**

---

## API Endpoints

### 1. Start Test Session

**Endpoint:** `POST /api/v1/tests/{test_id}/start`

**Headers:**
```
Authorization: Bearer {firebase_token}
```

**Response (200 OK):**
```json
{
  "success": true,
  "session_id": "uuid-string",
  "test": {
    "test_id": "test_id",
    "title": "Đề thi Toán",
    "num_questions": 20,
    "time_limit_minutes": 30,
    "questions": [
      {
        "question_id": "q1",
        "question_text": "Câu 1...",
        "options": [
          {"key": "A", "text": "..."},
          {"key": "B", "text": "..."}
        ]
      }
    ]
  },
  "current_attempt": 1,
  "max_attempts": 3,
  "attempts_remaining": 2,
  "is_creator": false,
  "time_limit_seconds": 1800,
  "time_remaining_seconds": 1800,
  "is_completed": false
}
```

**Response (429 Too Many Requests) - Hết lượt:**
```json
{
  "detail": "Maximum attempts (3) exceeded. You have used 3 attempts."
}
```

**Lưu ý:**
- `session_id`: Dùng để join WebSocket và sync answers
- `started_at`: Backend tự lưu, không trả về cho frontend
- Frontend nhận `time_remaining_seconds` = `time_limit_seconds` ban đầu

---

### 2. Sync Answers (HTTP Endpoint - Backup)

**Endpoint:** `POST /api/v1/tests/{test_id}/sync-answers`

**Headers:**
```
Authorization: Bearer {firebase_token}
Content-Type: application/json
```

**Request Body:**
```json
{
  "session_id": "uuid-string",
  "answers": {
    "q1": "A",
    "q2": "B",
    "q3": "C"
  }
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "session_id": "uuid-string",
  "answers_count": 3,
  "saved_at": "2025-11-15T10:30:00Z"
}
```

**Response (422 Unprocessable Entity) - Hết giờ:**
```json
{
  "detail": {
    "error": "time_expired",
    "message": "Thời gian làm bài đã hết. Không thể sync answers.",
    "elapsed_seconds": 2000,
    "time_limit_seconds": 1800
  }
}
```

**Response (410 Gone) - Session đã completed:**
```json
{
  "detail": "Session already completed"
}
```

**Use case:**
- Reconnect sau khi mất WebSocket connection
- Backup sync trước khi submit
- Periodic sync mỗi 30-60s (optional)

---

### 3. Submit Test

**Endpoint:** `POST /api/v1/tests/{test_id}/submit`

**Headers:**
```
Authorization: Bearer {firebase_token}
Content-Type: application/json
```

**Request Body:**
```json
{
  "user_answers": [
    {
      "question_id": "q1",
      "selected_answer_key": "A"
    },
    {
      "question_id": "q2",
      "selected_answer_key": "B"
    }
  ]
}
```

**Response (200 OK) - Trong thời gian:**
```json
{
  "success": true,
  "submission_id": "submission_id",
  "score": 8.5,
  "score_percentage": 85,
  "total_questions": 20,
  "correct_answers": 17,
  "attempt_number": 1,
  "is_passed": true,
  "results": [
    {
      "question_id": "q1",
      "question_text": "Câu 1...",
      "your_answer": "A",
      "correct_answer": "A",
      "is_correct": true,
      "explanation": "..."
    }
  ]
}
```

**Response (200 OK) - Quá thời gian, có submission cũ:**
```json
{
  "success": false,
  "error": "time_limit_exceeded",
  "message": "Thời gian làm bài đã hết (30 phút). Kết quả được lấy từ lần nộp gần nhất.",
  "time_taken_seconds": 2000,
  "time_limit_seconds": 1800,
  "latest_submission": {
    "submission_id": "old_submission_id",
    "score": 7.5,
    "score_percentage": 75,
    "is_passed": true,
    "submitted_at": "2025-11-15T10:20:00Z"
  }
}
```

**Response (422 Unprocessable Entity) - Quá thời gian, không có submission cũ:**
```json
{
  "detail": {
    "error": "time_limit_exceeded",
    "message": "Thời gian làm bài đã hết (30 phút) và không có lần nộp bài nào trước đó.",
    "time_taken_seconds": 2000,
    "time_limit_seconds": 1800
  }
}
```

**Lưu ý:**
- Backend tính `time_taken_seconds` từ `started_at` đến `submitted_at`
- Nếu quá `time_limit_seconds` → reject và trả về submission gần nhất
- Frontend không cần gửi `time_taken` (backend tự tính)

---

## WebSocket Events

### Connection

**URL:** `wss://ai.wordai.pro/ws/socket.io/`

**Library:** Socket.IO Client

**Connection options:**
```javascript
{
  transports: ['websocket', 'polling'],
  autoConnect: true,
  reconnection: true,
  reconnectionAttempts: 5,
  reconnectionDelay: 1000
}
```

---

### 1. Join Session

**Event:** `join_test_session`

**Emit:**
```json
{
  "session_id": "uuid-string",
  "user_id": "firebase_uid",
  "test_id": "test_id"
}
```

**Listen: `session_joined`**
```json
{
  "session_id": "uuid-string",
  "current_answers": {
    "q1": "A",
    "q2": "B"
  },
  "time_remaining_seconds": 1500,
  "started_at": "2025-11-15T10:00:00Z"
}
```

**Listen: `error` (Hết giờ - không thể join lại):**
```json
{
  "message": "Thời gian làm bài đã hết. Không thể kết nối lại.",
  "error_code": "TIME_EXPIRED",
  "started_at": "2025-11-15T10:00:00Z",
  "elapsed_minutes": 35,
  "time_limit_minutes": 30
}
```

**Validation:**
- Backend tính `time_remaining = time_limit - (now - started_at)`
- Nếu `time_remaining <= 0` → reject join, trả về error
- Nếu OK → trả về `current_answers` (để restore state)

---

### 2. Save Answers (Batch) - **RECOMMENDED**

**Event:** `save_answers_batch`

**Emit:** (Gửi FULL answers mỗi lần)

**NEW FORMAT** - Hỗ trợ MCQ và Essay với media attachments:
```json
{
  "session_id": "uuid-string",
  "answers": {
    "q1": {
      "question_type": "mcq",
      "selected_answer_key": "A"
    },
    "q2": {
      "question_type": "essay",
      "essay_answer": "Câu trả lời của tôi...",
      "media_attachments": [
        {
          "media_type": "image",
          "media_url": "https://static.wordai.pro/answer-media/user123/diagram.png",
          "filename": "diagram.png",
          "file_size_mb": 2.5,
          "description": "Biểu đồ minh họa"
        }
      ]
    },
    "q3": {
      "question_type": "essay",
      "essay_answer": "Text only, no media"
    }
  }
}
```

**LEGACY FORMAT** (vẫn hỗ trợ backward compatibility):
```json
{
  "session_id": "uuid-string",
  "answers": {
    "q1": "A",
    "q2": "B",
    "q3": "C"
  }
}
```

**Listen: `answers_saved_batch`**
```json
{
  "session_id": "uuid-string",
  "answers_count": 4,
  "saved_at": "2025-11-15T10:15:00Z"
}
```

**Listen: `error`**
```json
{
  "message": "Session not active. Please rejoin."
}
```

**Khuyến nghị:**
- Gửi FULL answers mỗi khi user trả lời 1 câu (không chỉ câu vừa làm)
- Backend sẽ overwrite toàn bộ `current_answers`
- Đảm bảo không mất data nếu đứt kết nối

---

### 3. Save Single Answer - **LEGACY (Optional)**

**Event:** `save_answer`

**NEW FORMAT** - MCQ:
```json
{
  "session_id": "uuid-string",
  "question_id": "q1",
  "question_type": "mcq",
  "selected_answer_key": "A"
}
```

**NEW FORMAT** - Essay with media:
```json
{
  "session_id": "uuid-string",
  "question_id": "q2",
  "question_type": "essay",
  "essay_answer": "Câu trả lời của tôi...",
  "media_attachments": [
    {
      "media_type": "image",
      "media_url": "https://static.wordai.pro/answer-media/...",
      "filename": "diagram.png",
      "file_size_mb": 2.5,
      "description": "Biểu đồ minh họa"
    }
  ]
}
```

**LEGACY FORMAT** (vẫn hỗ trợ):
```json
{
  "session_id": "uuid-string",
  "question_id": "q1",
  "answer_key": "A"
}
```

**Listen: `answer_saved`**
```json
{
  "session_id": "uuid-string",
  "question_id": "q1",
  "answer_data": {
    "question_type": "mcq",
    "selected_answer_key": "A"
  },
  "saved_at": "2025-11-15T10:15:00Z"
}
```

**Lưu ý:**
- Khuyến nghị dùng `save_answers_batch` để gửi FULL answers
- Single answer chỉ nên dùng khi cần immediate feedback

---

### 4. Heartbeat (Keep Connection Alive)

**Event:** `heartbeat`

**Emit:** (Mỗi 5-10 giây)
```json
{
  "session_id": "uuid-string"
}
```

**Listen: `heartbeat_ack`**
```json
{
  "session_id": "uuid-string",
  "timestamp": "2025-11-15T10:15:00Z",
  "time_remaining_seconds": 1200
}
```

**Listen: `time_warning` (< 5 phút còn lại)**
```json
{
  "session_id": "uuid-string",
  "time_remaining_seconds": 180,
  "message": "Chỉ còn 3 phút!"
}
```

**Lưu ý:**
- Frontend KHÔNG cần gửi `time_remaining_seconds` (backend tự tính)
- Backend trả về `time_remaining_seconds` trong `heartbeat_ack` để frontend có thể sync
- Frontend có thể dùng giá trị này để điều chỉnh countdown timer (optional)

---

## User Flows

### Flow 1: Làm bài bình thường (MCQ và Essay với media)

```
1. User click "Bắt đầu làm bài"
   → POST /api/v1/tests/{test_id}/start
   ← Nhận: session_id, questions (có question_type), time_limit_seconds

2. Frontend khởi tạo:
   - Countdown timer: time_limit_seconds
   - WebSocket connection
   - Empty answers state: {}

3. Connect WebSocket:
   → emit: join_test_session { session_id, user_id, test_id }
   ← listen: session_joined { current_answers, time_remaining_seconds }

4. Bắt đầu countdown timer:
   - Timer đếm ngược từ time_limit_seconds
   - Hiển thị thời gian còn lại

5. User trả lời câu hỏi:

   A. MCQ (câu 1):
   - User chọn A
   - Update local: answers = {
       q1: {question_type: "mcq", selected_answer_key: "A"}
     }
   - emit: save_answers_batch { session_id, answers }

   B. Essay không có media (câu 2):
   - User gõ text
   - Update local: answers = {
       q1: {...},
       q2: {question_type: "essay", essay_answer: "text..."}
     }
   - emit: save_answers_batch { session_id, answers }

   C. Essay có media (câu 3):
   - User gõ text: "Đây là câu trả lời..."
   - User click "Upload image"
   
   → POST /api/v1/tests/submissions/answer-media/presigned-url
   Body: {filename: "diagram.png", file_size_mb: 2.5, content_type: "image/png"}
   ← {presigned_url, file_url}
   
   → PUT presigned_url (upload file to R2)
   
   - Update local: answers = {
       q1: {...}, q2: {...},
       q3: {
         question_type: "essay",
         essay_answer: "Đây là câu trả lời...",
         media_attachments: [
           {media_type: "image", media_url: file_url, filename: "diagram.png", file_size_mb: 2.5}
         ]
       }
     }
   - emit: save_answers_batch { session_id, answers }

6. Heartbeat tự động (mỗi 5-10s):
   → emit: heartbeat { session_id }
   ← listen: heartbeat_ack { time_remaining_seconds }

7. User click "Nộp bài":
   → POST /api/v1/tests/{test_id}/submit
   Body: {
     user_answers: [
       {question_id: "q1", question_type: "mcq", selected_answer_key: "A"},
       {question_id: "q2", question_type: "essay", essay_answer: "...", media_attachments: [...]},
       {question_id: "q3", question_type: "essay", essay_answer: "..."}
     ]
   }
   ← Nhận: score (MCQ auto-graded), essay grading_status: "pending_grading"

8. Hiển thị kết quả
   - MCQ: Điểm ngay lập tức
   - Essay: "Đang chờ chấm điểm"
```

---

### Flow 2: Mất kết nối giữa chừng (Reconnect)

```
1. User đang làm bài (đã trả lời câu 1 MCQ, câu 2 Essay)
   - Local state: answers = {
       q1: {question_type: "mcq", selected_answer_key: "A"},
       q2: {question_type: "essay", essay_answer: "...", media_attachments: [...]}
     }
   - Timer đang chạy: còn 20 phút

2. Mất kết nối Internet/WiFi:
   ← listen: disconnect
   - Frontend phát hiện mất kết nối
   - Hiển thị warning: "Mất kết nối, đang thử kết nối lại..."
   - Timer vẫn tiếp tục đếm (frontend)

3. User tiếp tục làm bài offline:
   - User trả lời câu 3 (Essay)
   - Update local state: answers = { q1: {...}, q2: {...}, q3: {...} }
   - emit: save_answers_batch → FAIL (no connection)
   - Lưu vào localStorage/memory

4. Kết nối lại sau 2 phút:
   ← listen: connect
   - WebSocket reconnected

5. Rejoin session:
   → emit: join_test_session { session_id, user_id, test_id }

   Case A: Còn trong thời gian (18 phút còn lại)
   ← listen: session_joined {
       current_answers: {
         q1: {question_type: "mcq", selected_answer_key: "A"},
         q2: {question_type: "essay", essay_answer: "...", media_attachments: [...]}
       },
       time_remaining_seconds: 1080
     }

   - Merge local state với server state:
     answers = { q1: {...}, q2: {...}, q3: {...} }  // q3 từ local

   - Sync lại với server:
     → POST /api/v1/tests/{test_id}/sync-answers
     Body: { session_id, answers: { q1: {...}, q2: {...}, q3: {...} } }
     ← { success: true, answers_count: 3 }

   - Sync timer: Frontend timer = 1080s (từ backend)
   - Tiếp tục làm bài bình thường

   Case B: Hết thời gian (31 phút đã qua)
   ← listen: error {
       message: "Thời gian làm bài đã hết. Không thể kết nối lại.",
       error_code: "TIME_EXPIRED",
       elapsed_minutes: 31,
       time_limit_minutes: 30
     }

   - Hiển thị thông báo: "Hết giờ làm bài"
   - Tự động navigate to results hoặc home
   - KHÔNG cho phép submit
```

---

### Flow 3: Submit khi hết giờ

```
Scenario A: Submit đúng lúc hết giờ (trong vài giây)

1. Timer đếm về 0:
   - Frontend hiển thị "Hết giờ!"
   - Tự động submit

2. Submit ngay lập tức:
   → POST /api/v1/tests/{test_id}/submit
   Body: { user_answers: [...] }

3. Backend check:
   - started_at = 10:00:00
   - submitted_at = 10:30:02 (2 giây sau khi hết giờ)
   - time_taken = 1802s
   - time_limit = 1800s
   - Difference = 2s → CÒN CHẤP NHẬN (tolerance ~5s)

4. Response:
   ← 200 OK { score, results, is_passed }
   - Chấp nhận submission
   - Tính điểm bình thường

---

Scenario B: Submit muộn hơn (sau 1-2 phút hết giờ)

1. User làm bài chậm, click Submit sau khi hết giờ

2. Submit:
   → POST /api/v1/tests/{test_id}/submit
   Body: { user_answers: [...] }

3. Backend check:
   - started_at = 10:00:00
   - submitted_at = 10:32:00
   - time_taken = 1920s
   - time_limit = 1800s
   - Quá 120s → REJECT

4. Response (Có submission cũ):
   ← 200 OK {
       success: false,
       error: "time_limit_exceeded",
       message: "Thời gian làm bài đã hết (30 phút). Kết quả được lấy từ lần nộp gần nhất.",
       latest_submission: {
         submission_id: "old_id",
         score: 7.5,
         submitted_at: "10:25:00"
       }
     }

   - Frontend hiển thị submission cũ
   - "Bạn đã nộp bài lúc 10:25, điểm: 7.5"

5. Response (KHÔNG có submission cũ):
   ← 422 Unprocessable Entity {
       detail: {
         error: "time_limit_exceeded",
         message: "Thời gian làm bài đã hết (30 phút) và không có lần nộp bài nào trước đó.",
         time_taken_seconds: 1920,
         time_limit_seconds: 1800
       }
     }

   - Frontend hiển thị lỗi
   - "Hết thời gian làm bài, không thể nộp bài"
```

---

### Flow 4: Refresh/Close browser giữa chừng

```
1. User đang làm bài:
   - session_id: "abc-123"
   - answers: { q1: "A", q2: "B", q3: "C" }
   - Timer: còn 20 phút

2. User refresh browser hoặc đóng tab:
   - WebSocket disconnect
   - localStorage vẫn lưu:
     * session_id
     * test_id
     * answers
     * started_at (optional)

3. User quay lại (trong vòng 20 phút):
   - Load localStorage
   - Check: có session_id + test_id đang active?

4. Nếu có session active:
   - Không cần POST /start lại (đã có session_id)
   - Connect WebSocket ngay

   → emit: join_test_session { session_id, user_id, test_id }

   ← listen: session_joined {
       current_answers: { q1: "A", q2: "B", q3: "C" },
       time_remaining_seconds: 1200  // Còn 20 phút
     }

   - Restore UI state:
     * Questions
     * Answers đã chọn
     * Timer = 1200s

   - Sync local answers nếu khác server:
     → POST /api/v1/tests/{test_id}/sync-answers

   - Tiếp tục làm bài

5. Nếu hết giờ (quay lại sau 35 phút):
   → emit: join_test_session
   ← listen: error { error_code: "TIME_EXPIRED" }

   - Clear localStorage
   - Navigate to home hoặc results
```

---

## Best Practices cho Frontend

### 1. State Management

```
Recommended state structure:

{
  // Test info
  testId: string,
  sessionId: string,
  questions: Array,

  // Timer
  timeLimit: number,        // seconds (từ start response)
  timeRemaining: number,    // seconds (countdown local)
  serverTimeRemaining: number, // seconds (từ heartbeat_ack)
  startedAt: string,        // ISO 8601 (optional, để debug)

  // Answers
  answers: {
    "q1": "A",
    "q2": "B",
    ...
  },

  // Connection
  isConnected: boolean,
  isReconnecting: boolean,
  lastSyncAt: string,       // ISO 8601

  // UI
  currentQuestionIndex: number,
  showTimeWarning: boolean
}
```

### 2. Timer Logic

```
Frontend countdown timer (independent):

1. Nhận time_limit_seconds từ start response
2. Đếm ngược từ time_limit_seconds về 0
3. Update UI mỗi giây

Sync với backend (optional):
- Nhận server_time_remaining từ heartbeat_ack
- Nếu lệch > 5s → điều chỉnh local timer
- Ví dụ:
  * Local timer: 1200s
  * Server timer: 1180s
  * Lệch 20s → set local = 1180s

Lợi ích:
- Timer vẫn chạy khi mất kết nối
- Tự động sync khi reconnect
- Không bị lag do network
```

### 3. Auto-save Strategy

```
Recommended: Gửi FULL answers mỗi khi thay đổi

Option A: Immediate save
- User chọn answer → emit ngay lập tức
- Pros: Real-time sync
- Cons: Nhiều requests nếu user đổi ý

Option B: Debounced save
- User chọn answer → đợi 500ms → emit
- Nếu user đổi ý trong 500ms → reset timer
- Pros: Giảm số requests
- Cons: Delay 500ms

Option C: Hybrid
- Immediate emit save_answers_batch
- + Backup HTTP POST /sync-answers mỗi 30-60s
- Pros: Tốt nhất, đảm bảo data safety
- Cons: Phức tạp hơn
```

### 4. Error Handling

```
WebSocket errors:

1. disconnect:
   - Hiển thị warning: "Mất kết nối..."
   - Set isReconnecting = true
   - Timer vẫn chạy
   - Queue answers locally

2. connect:
   - Ẩn warning
   - Rejoin session
   - Sync queued answers

3. error (TIME_EXPIRED):
   - Stop timer
   - Hiển thị: "Hết giờ làm bài"
   - Disable tất cả inputs
   - Navigate to results/home

4. error (other):
   - Log error
   - Retry hoặc show toast

HTTP errors:

1. 422 (time_expired):
   - Parse detail.error
   - Hiển thị message phù hợp

2. 429 (too many attempts):
   - "Bạn đã hết lượt làm bài"
   - Navigate to home

3. 500 (server error):
   - "Lỗi server, vui lòng thử lại"
   - Retry hoặc navigate to home
```

### 5. LocalStorage Strategy

```
Save to localStorage:

1. Sau khi start:
   localStorage.setItem('active_test', JSON.stringify({
     testId,
     sessionId,
     startedAt: new Date().toISOString(),
     answers: {}
   }))

2. Mỗi khi update answers:
   const state = JSON.parse(localStorage.getItem('active_test'))
   state.answers = newAnswers
   localStorage.setItem('active_test', JSON.stringify(state))

3. Khi submit thành công:
   localStorage.removeItem('active_test')

4. Khi hết giờ:
   localStorage.removeItem('active_test')

5. Check on app load:
   const activeTest = localStorage.getItem('active_test')
   if (activeTest) {
     // Có test đang làm dở
     // Check time_remaining via rejoin
     // Restore nếu còn thời gian
   }
```

### 6. UX Recommendations

```
1. Connection status indicator:
   - Green dot: Connected
   - Yellow dot: Reconnecting...
   - Red dot: Disconnected

2. Auto-save indicator:
   - "Đã lưu tự động" sau mỗi lần save
   - Show timestamp: "Lưu lúc 10:15:30"

3. Time warning levels:
   - < 5 min: Yellow background
   - < 2 min: Red background + blink
   - < 30s: Play sound alert

4. Confirm before leave:
   - window.onbeforeunload = "Bài làm chưa nộp, bạn có chắc muốn thoát?"
   - Chỉ khi có answers chưa submit

5. Submit confirmation:
   - Modal: "Bạn có chắc muốn nộp bài?"
   - Hiển thị: answered/total questions
   - Confirm → Submit

6. Offline mode:
   - Continue countdown
   - Queue answers in memory
   - Show "Offline, sẽ tự động sync khi online"
   - Auto-sync khi reconnect
```

---

## Testing Checklist

### Connection Tests

- [ ] Làm bài bình thường (không mất kết nối)
- [ ] Mất kết nối giữa chừng → reconnect trong thời gian
- [ ] Mất kết nối → reconnect sau khi hết giờ
- [ ] Refresh browser giữa chừng → continue
- [ ] Close tab → reopen trong thời gian
- [ ] Multiple tabs cùng session (test race conditions)

### Timer Tests

- [ ] Countdown chính xác
- [ ] Time warning hiển thị đúng (< 5 min)
- [ ] Auto-submit khi hết giờ
- [ ] Sync timer sau reconnect

### Answer Sync Tests

- [ ] Save single answer
- [ ] Save multiple answers liên tiếp
- [ ] Answer được restore sau reconnect
- [ ] LocalStorage sync chính xác
- [ ] Conflict resolution (local vs server)

### Submit Tests

- [ ] Submit trong thời gian → 200 OK
- [ ] Submit đúng lúc hết giờ (tolerance ~5s) → 200 OK
- [ ] Submit sau hết giờ, có submission cũ → 200 với latest_submission
- [ ] Submit sau hết giờ, không có submission cũ → 422
- [ ] Submit khi hết lượt → 429

### Edge Cases

- [ ] Start 2 sessions song song (multiple tabs)
- [ ] Submit 2 lần liên tiếp (double click)
- [ ] Mất kết nối lâu (> 10 min) → reconnect
- [ ] Server restart giữa chừng
- [ ] Network flaky (on/off nhiều lần)

---

## Troubleshooting

### Issue: "Session not active" khi save answer

**Nguyên nhân:**
- WebSocket chưa join session
- Session đã expired/completed

**Giải pháp:**
1. Check WebSocket connected
2. Emit join_test_session trước
3. Đợi session_joined response
4. Sau đó mới emit save_answer

---

### Issue: Timer lệch so với server

**Nguyên nhân:**
- Frontend countdown độc lập
- Network delay
- Client clock không chính xác

**Giải pháp:**
- Sync với server_time_remaining từ heartbeat_ack
- Adjust local timer nếu lệch > 5s
- Trust backend time khi submit

---

### Issue: Answers bị mất sau reconnect

**Nguyên nhân:**
- Chưa emit save_answers_batch trước khi disconnect
- Không restore từ server khi rejoin

**Giải pháp:**
- Gửi FULL answers mỗi khi thay đổi
- Restore từ session_joined.current_answers
- Merge với localStorage nếu có conflict
- POST /sync-answers để backup

---

### Issue: Submit bị reject mặc dù timer chưa hết

**Nguyên nhân:**
- Frontend timer lag/delay
- Server time chính xác hơn
- Network delay khi submit

**Giải pháp:**
- Trust server time
- Submit trước 5-10s để có buffer
- Show warning khi < 1 min
- Auto-submit ở 0s (đừng đợi user click)

---

## FAQ

**Q: Frontend có cần gửi time_remaining trong heartbeat không?**

A: KHÔNG. Backend tự tính từ `started_at` và `time_limit`. Frontend chỉ gửi `session_id`.

**Q: Nếu user làm bài offline (không WebSocket) thì sao?**

A:
- Timer vẫn chạy local
- Answers lưu trong memory/localStorage
- Khi online lại → POST /sync-answers để sync
- Submit vẫn hoạt động (qua HTTP)

**Q: Có thể start lại session đã hết giờ không?**

A: KHÔNG. Mỗi lần start tạo session mới. Session cũ hết giờ → không thể join lại.

**Q: Làm sao biết session còn valid không?**

A: Emit join_test_session → nếu nhận error TIME_EXPIRED → session đã hết giờ.

**Q: Submit có cần session_id không?**

A: KHÔNG. Submit chỉ cần `test_id` và `user_answers`. Backend tự tìm session để tính `time_taken`.

**Q: Có thể submit nhiều lần không?**

A: CÓ, trong giới hạn `max_attempts`. Mỗi lần submit tạo submission mới với `attempt_number` tăng dần.

**Q: Answers được lưu ở đâu?**

A:
- WebSocket: `test_progress.current_answers` (real-time)
- Submit: `test_submissions.user_answers` (final)
- Submit không dùng `current_answers`, chỉ dùng data từ request body

---

## Summary

**Key Points:**

1. **Backend là nguồn chân lý về thời gian** - Frontend chỉ hiển thị countdown
2. **Gửi FULL answers mỗi lần** - Để đề phòng mất kết nối
3. **Có thể reconnect** - Nếu còn trong thời gian làm bài
4. **Submit có validation** - Reject nếu quá thời gian, trả về submission cũ nếu có
5. **LocalStorage để restore** - Khi refresh/close browser
6. **Heartbeat để keep-alive** - Và sync time (optional)

**Best Flow:**

```
START → JOIN WEBSOCKET → AUTO-SAVE (FULL) → HEARTBEAT → SUBMIT
         ↓                     ↓                ↓           ↓
    session_joined    save_answers_batch  heartbeat_ack   score
         ↓                     ↓
   restore state      backend sync
```

---

*Document version: 1.0*
*Last updated: 2025-11-15*
