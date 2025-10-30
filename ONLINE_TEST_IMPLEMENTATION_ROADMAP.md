# Kế hoạch Triển khai: Tính năng Online Test System

**Tác giả:** GitHub Copilot
**Ngày tạo:** 29/10/2025
**Version:** 1.0
**Tài liệu tham khảo:** `ONLINE_TEST_GENERATION_FEATURE.md`

---

## Tổng quan

Tài liệu này mô tả lộ trình triển khai chi tiết cho hệ thống Online Test, được chia thành 5 phases có thể phát triển độc lập và tích hợp dần. Mỗi phase tập trung vào một nhóm tính năng cụ thể và có thể deploy riêng biệt.

---

## Phase 1: Core Test Generation & Basic Testing (Foundation)

**Mục tiêu:** Xây dựng nền tảng cơ bản cho việc tạo và làm bài thi.

**Thời gian ước tính:** 3-4 tuần

### 1.1. Database Schema Setup

**Collections cần tạo:**

1. **`online_tests`** - Lưu thông tin bài thi
   - Fields: `_id`, `title`, `source_document_id`, `source_file_r2_key`, `creator_id`, `time_limit_minutes`, `questions`, `max_retries`, `created_at`, `updated_at`, `is_active`
   - Index: `creator_id`, `created_at`, `is_active`

2. **`test_submissions`** - Lưu kết quả làm bài
   - Fields: `_id`, `test_id`, `user_id`, `user_answers`, `score`, `total_questions`, `correct_answers`, `time_taken_seconds`, `submitted_at`, `attempt_number`, `is_passed`
   - Index: `test_id + user_id`, `user_id + submitted_at`, `test_id + attempt_number`

3. **`test_progress`** (NEW) - Lưu tiến trình làm bài real-time
   - Fields: `_id`, `test_id`, `user_id`, `session_id`, `current_answers`, `last_saved_at`, `started_at`, `time_remaining_seconds`, `is_completed`
   - Index: `user_id + test_id + is_completed`, `session_id`
   - TTL Index: `last_saved_at` (tự động xóa sau 7 ngày nếu không hoàn thành)

### 1.2. AI Service Integration

**Service cần tạo:** `src/services/test_generator_service.py`

**Chức năng:**
- Kết nối với **Gemini 2.5 Pro** với JSON Mode
- Tải nội dung từ R2 (PDF/DOCX) hoặc MongoDB (documents)
- Parse và validate JSON response từ AI
- Retry logic (3 lần) nếu AI trả về JSON không hợp lệ
- Lưu bài thi vào database với status `generating` -> `ready`

### 1.3. API Endpoints - Phase 1

| Method | Endpoint | Chức năng | Auth | Priority |
|--------|----------|-----------|------|----------|
| **POST** | `/api/v1/tests/generate` | Tạo bài thi từ document/file | Required | HIGH |
| **GET** | `/api/v1/tests/{test_id}` | Lấy thông tin bài thi để làm bài (không có đáp án) | Required | HIGH |
| **POST** | `/api/v1/tests/{test_id}/start` | Bắt đầu một session làm bài mới | Required | HIGH |
| **POST** | `/api/v1/tests/{test_id}/submit` | Nộp bài và nhận kết quả chấm điểm | Required | HIGH |
| **GET** | `/api/v1/me/tests` | Danh sách bài thi đã tạo của user | Required | MEDIUM |
| **GET** | `/api/v1/me/submissions` | Lịch sử làm bài của user | Required | MEDIUM |

### 1.4. Business Logic

**Test Generation Flow:**
1. Validate request (num_questions 1-100, time_limit 1-300 phút)
2. Fetch document content từ MongoDB hoặc R2
3. Truncate content nếu quá dài (max 1M tokens)
4. Gọi Gemini với JSON Mode prompt
5. Validate JSON structure và content quality
6. Lưu vào `online_tests` collection
7. Return test_id + metadata (không có đáp án)

**Test Submission Flow:**
1. Validate test_id và user có quyền làm bài
2. Kiểm tra số lần retry (attempt_number < max_retries)
3. Tính điểm dựa trên đáp án đúng
4. Lưu vào `test_submissions` với attempt_number
5. Return kết quả chi tiết (điểm, đáp án đúng, giải thích)

---

## Phase 2: Real-time Progress Sync & Auto-save (Reliability)

**Mục tiêu:** Đảm bảo không mất dữ liệu khi làm bài, hỗ trợ mất kết nối.

**Thời gian ước tính:** 2-3 tuần

### 2.1. WebSocket Integration

**Technology:** Socket.IO (Python: `python-socketio`, Frontend: `socket.io-client`)

**Events cần implement:**

**Client -> Server:**
- `join_test_session` - Tham gia session làm bài
- `save_answer` - Lưu câu trả lời ngay lập tức (debounce 2s)
- `heartbeat` - Ping mỗi 30s để maintain connection
- `leave_test_session` - Rời khỏi session

**Server -> Client:**
- `answer_saved` - Xác nhận đã lưu thành công
- `sync_progress` - Đồng bộ tiến trình từ server (sau reconnect)
- `time_warning` - Cảnh báo khi còn 5 phút
- `session_expired` - Thông báo hết giờ, tự động nộp bài

### 2.2. Auto-save Mechanism

**Luồng hoạt động:**
1. User chọn/thay đổi đáp án -> Frontend emit `save_answer` event
2. Backend nhận event -> Validate -> Update `test_progress` collection
3. Backend emit `answer_saved` confirmation
4. Frontend hiển thị indicator "Đã lưu" hoặc "Đang lưu..."

**Retry Logic (Frontend):**
- Nếu không nhận `answer_saved` sau 5s -> retry (max 3 lần)
- Nếu 3 lần đều fail -> Lưu vào localStorage tạm thời
- Khi reconnect -> Sync từ localStorage lên server

### 2.3. Reconnection Handling

**Khi mất kết nối:**
1. Frontend detect disconnect event
2. Hiển thị banner: "Mất kết nối. Đang thử kết nối lại..."
3. Auto-retry connect mỗi 2s, 5s, 10s, 20s (exponential backoff)
4. Khi reconnect thành công:
   - Emit `join_test_session` với session_id
   - Server gửi lại `sync_progress` (last saved state)
   - Frontend merge với localStorage (nếu có)
   - Hiển thị: "Đã khôi phục kết nối!"

### 2.4. API Endpoints - Phase 2

| Method | Endpoint | Chức năng | Auth | Priority |
|--------|----------|-----------|------|----------|
| **POST** | `/api/v1/tests/{test_id}/progress/save` | HTTP fallback để lưu tiến trình | Required | HIGH |
| **GET** | `/api/v1/tests/{test_id}/progress` | Lấy tiến trình hiện tại (restore session) | Required | HIGH |
| **POST** | `/api/v1/tests/{test_id}/resume` | Tiếp tục bài thi đã bắt đầu nhưng chưa nộp | Required | MEDIUM |

### 2.5. Database Changes

**Update `test_progress` schema:**
- Add `connection_status`: "active" | "disconnected" | "completed"
- Add `last_heartbeat_at`: ISODate
- Add `reconnect_count`: int

---

## Phase 3: Retry Limits & Test Editing (Flexibility)

**Mục tiêu:** Cho phép làm lại bài thi và chỉnh sửa nội dung đề thi.

**Thời gian ước tính:** 2 tuần

### 3.1. Retry Limits Configuration

**Update `online_tests` schema:**
- `max_retries`: int | "unlimited" (default: 1)
  - `0` = không cho làm lại
  - `1` = được làm 1 lần duy nhất
  - `2-99` = được làm lại tối đa N lần
  - `"unlimited"` = không giới hạn

**Business Rules:**
- Chỉ owner (creator_id) mới được thay đổi `max_retries`
- User có thể xem số lần đã làm và còn lại
- Mỗi lần làm lưu riêng biệt với `attempt_number`
- Điểm cao nhất được tính là kết quả chính thức

### 3.2. Test Editing Integration

**Chiến lược:** Tích hợp với Document Editor hiện có

**Luồng hoạt động:**
1. Owner click "Edit Test" -> Backend convert `online_tests` thành document format
2. Mở Document Editor với nội dung questions (HTML format)
3. Owner chỉnh sửa câu hỏi, đáp án, giải thích
4. Khi save -> Parse HTML về JSON format và update `online_tests`
5. Validate: Mỗi câu hỏi phải có ít nhất 2 options, 1 đáp án đúng

**HTML Format cho Document Editor:**
```
<div class="test-question" data-question-id="1">
  <h3>Question 1: What is AI?</h3>
  <div class="options">
    <div class="option" data-key="A">Artificial Intelligence</div>
    <div class="option" data-key="B" data-correct="true">Artificial Intelligence ✓</div>
  </div>
  <div class="explanation">Explanation: AI stands for...</div>
</div>
```

### 3.3. API Endpoints - Phase 3

| Method | Endpoint | Chức năng | Auth | Priority |
|--------|----------|-----------|------|----------|
| **PATCH** | `/api/v1/tests/{test_id}/config` | Cập nhật cấu hình (max_retries, time_limit) | Owner only | HIGH |
| **GET** | `/api/v1/tests/{test_id}/edit` | Lấy nội dung để chỉnh sửa (format HTML) | Owner only | HIGH |
| **PUT** | `/api/v1/tests/{test_id}/content` | Lưu nội dung đã chỉnh sửa | Owner only | HIGH |
| **GET** | `/api/v1/tests/{test_id}/attempts` | Danh sách các lần làm bài của user | Required | MEDIUM |
| **DELETE** | `/api/v1/tests/{test_id}` | Xóa bài thi (soft delete) | Owner only | LOW |

### 3.4. Validation Rules

**Khi chỉnh sửa:**
- Mỗi câu hỏi phải có `question_text` (min 10 chars)
- Phải có ít nhất 2 options, tối đa 6 options
- Chỉ được có 1 đáp án đúng duy nhất
- `explanation` không được để trống (min 20 chars)
- Không được thay đổi `question_id` của câu đã tồn tại

**Khi thay đổi max_retries:**
- Nếu giảm `max_retries` xuống thấp hơn số lần user đã làm -> không áp dụng cho user đó

---

## Phase 4: Sharing & Collaboration (Social Features)

**Mục tiêu:** Chia sẻ bài thi với người khác, quản lý deadline.

**Thời gian ước tính:** 2-3 tuần

### 4.1. Test Sharing System

**New Collection:** `test_shares`

```
{
  "_id": ObjectId,
  "test_id": ObjectId,
  "sharer_id": ObjectId,
  "sharee_email": "user@example.com",
  "sharee_id": ObjectId | null,
  "access_granted_at": ISODate,
  "deadline": ISODate | null,
  "status": "pending" | "accepted" | "completed" | "expired" | "declined",
  "shared_at": ISODate,
  "invitation_token": "uuid-v4"
}
```

**Access Control:**
- `pending`: Đã gửi email, chưa accept
- `accepted`: User đã accept và có thể làm bài
- `completed`: User đã hoàn thành bài thi
- `expired`: Quá deadline chưa làm
- `declined`: User từ chối làm bài

### 4.2. Email & Notification Integration

**Email Service:** Sử dụng Brevo (đã có sẵn trong hệ thống)

**Email Templates:**
1. **Test Invitation Email:**
   - Subject: `{sharer_name} invited you to take a test: {test_title}`
   - Content: Test details, deadline, CTA button "Take Test"
   - Link: `https://wordai.com/tests/invitation/{invitation_token}`

2. **Test Deadline Reminder:**
   - Gửi trước deadline 24h
   - Subject: `Reminder: Test "{test_title}" due in 24 hours`

3. **Test Completion Notification (to Owner):**
   - Subject: `{user_name} completed your test: {test_title}`
   - Content: Score, completion time

**In-app Notifications:**
- Notification type: `online_test_invitation`
- Hiển thị trong notification center
- Real-time notification qua WebSocket (nếu user đang online)

### 4.3. Deadline Management

**Cron Job:** Chạy mỗi giờ để kiểm tra deadline

**Logic:**
1. Query `test_shares` với `status = "accepted"` và `deadline < now()`
2. Update status thành `"expired"`
3. Gửi notification cho sharee: "Bạn đã quá hạn làm bài"
4. Gửi notification cho sharer: "User X chưa hoàn thành bài thi đúng hạn"

### 4.4. API Endpoints - Phase 4

| Method | Endpoint | Chức năng | Auth | Priority |
|--------|----------|-----------|------|----------|
| **POST** | `/api/v1/tests/{test_id}/share` | Chia sẻ bài thi với danh sách emails | Owner only | HIGH |
| **GET** | `/api/v1/tests/invitations` | Danh sách bài thi được mời làm | Required | HIGH |
| **POST** | `/api/v1/tests/invitations/{token}/accept` | Accept lời mời làm bài | Public | HIGH |
| **POST** | `/api/v1/tests/invitations/{token}/decline` | Từ chối lời mời | Public | MEDIUM |
| **GET** | `/api/v1/tests/{test_id}/shares` | Danh sách người được share | Owner only | MEDIUM |
| **DELETE** | `/api/v1/tests/{test_id}/shares/{share_id}` | Thu hồi quyền truy cập | Owner only | MEDIUM |
| **PATCH** | `/api/v1/tests/{test_id}/shares/{share_id}/deadline` | Thay đổi deadline | Owner only | LOW |

### 4.5. Business Logic

**Sharing Flow:**
1. Owner nhập danh sách emails + optional deadline
2. Backend validate emails (format, không trùng)
3. Tạo records trong `test_shares` với `invitation_token`
4. Gửi email mời cho từng user
5. Nếu email đã là user trong hệ thống -> tạo in-app notification
6. Return danh sách share_id đã tạo

**Invitation Flow:**
1. User click link trong email -> redirect đến `/tests/invitation/{token}`
2. Frontend gọi API để validate token
3. Hiển thị preview bài thi (title, số câu hỏi, thời gian, deadline)
4. User click "Accept" hoặc "Decline"
5. Nếu Accept -> redirect đến trang làm bài

---

## Phase 5: Analytics & Reporting (Insights)

**Mục tiêu:** Cung cấp thống kê chi tiết cho owner về kết quả làm bài.

**Thời gian ước tính:** 2 tuần

### 5.1. Analytics Data Structure

**Metrics cần thu thập:**

**Test-level Metrics:**
- Tổng số người được share
- Tổng số người đã làm bài
- Tổng số người đã hoàn thành đúng hạn
- Tổng số người quá hạn chưa làm
- Điểm trung bình (average score)
- Điểm cao nhất/thấp nhất
- Thời gian làm bài trung bình

**Question-level Metrics:**
- Tỷ lệ trả lời đúng cho từng câu hỏi (difficulty analysis)
- Phân bố lựa chọn đáp án (option distribution)
- Câu hỏi dễ nhất/khó nhất

**User-level Metrics:**
- Danh sách user và điểm số
- Thời gian hoàn thành
- Số lần làm lại
- Status (completed, in_progress, expired, not_started)

### 5.2. Analytics Aggregation

**Strategy:** Pre-compute analytics khi có submission mới

**New Collection:** `test_analytics` (cached)

```
{
  "_id": ObjectId,
  "test_id": ObjectId,
  "total_shares": 10,
  "total_completed": 7,
  "total_on_time": 5,
  "total_expired": 2,
  "average_score": 75.5,
  "highest_score": 95.0,
  "lowest_score": 50.0,
  "average_time_seconds": 1200,
  "question_stats": [
    {
      "question_id": ObjectId,
      "correct_count": 8,
      "total_attempts": 10,
      "accuracy_rate": 0.8,
      "option_distribution": {"A": 2, "B": 8, "C": 0, "D": 0}
    }
  ],
  "last_updated": ISODate
}
```

**Update Trigger:** Khi có submission mới hoặc test share mới

### 5.3. Leaderboard System

**Public vs Private:**
- Owner có thể set bài thi là `public_leaderboard: true/false`
- Nếu public: Tất cả người làm bài thấy được leaderboard
- Nếu private: Chỉ owner thấy

**Leaderboard Data:**
- Rank (1, 2, 3...)
- User name (hoặc anonymous nếu user chọn)
- Score
- Time taken
- Attempt number (hiển thị nếu làm lại)

### 5.4. API Endpoints - Phase 5

| Method | Endpoint | Chức năng | Auth | Priority |
|--------|----------|-----------|------|----------|
| **GET** | `/api/v1/tests/{test_id}/analytics` | Tổng quan thống kê bài thi | Owner only | HIGH |
| **GET** | `/api/v1/tests/{test_id}/analytics/users` | Danh sách user và điểm số chi tiết | Owner only | HIGH |
| **GET** | `/api/v1/tests/{test_id}/analytics/questions` | Phân tích độ khó từng câu hỏi | Owner only | MEDIUM |
| **GET** | `/api/v1/tests/{test_id}/leaderboard` | Bảng xếp hạng (public hoặc owner) | Conditional | MEDIUM |
| **POST** | `/api/v1/tests/{test_id}/export` | Export kết quả ra CSV/Excel | Owner only | LOW |
| **GET** | `/api/v1/tests/{test_id}/report/{user_id}` | Báo cáo chi tiết của 1 user cụ thể | Owner only | MEDIUM |

### 5.5. Data Privacy & Permissions

**Rules:**
1. **Owner (creator_id):**
   - Xem tất cả analytics
   - Xem chi tiết kết quả từng user
   - Export dữ liệu
   - Chỉnh sửa leaderboard visibility

2. **Sharee (người được mời):**
   - Chỉ xem kết quả của chính mình
   - Xem leaderboard nếu owner cho phép
   - Không xem được kết quả của người khác

3. **Public:**
   - Không có quyền truy cập bất kỳ analytics nào

### 5.6. Export Functionality

**Supported Formats:**
- **CSV:** Dữ liệu thô, dễ import vào Excel
- **PDF:** Báo cáo đẹp với charts (dùng library như WeasyPrint)

**CSV Structure:**
```
User Email, User Name, Score, Total Questions, Correct Answers, Time Taken, Submitted At, Attempt Number, Status
user1@example.com, John Doe, 85.0, 10, 8, 1200, 2025-10-29T10:30:00, 1, completed
```

**PDF Report:** Bao gồm:
- Test metadata (title, creator, created date)
- Summary statistics (table)
- Score distribution (bar chart)
- Question difficulty analysis (table)
- User results (table with pagination)

---

## Phase 6: Advanced Features (Optional Enhancements)

**Mục tiêu:** Các tính năng nâng cao, không bắt buộc trong MVP.

**Thời gian ước tính:** 3-4 tuần

### 6.1. Question Bank & Reusability

- Tạo question bank để reuse câu hỏi cho nhiều bài thi
- Tag và categorize câu hỏi theo chủ đề
- AI suggestions dựa trên question bank

### 6.2. Adaptive Testing

- AI điều chỉnh độ khó câu hỏi dựa trên performance
- Câu trả lời đúng -> câu tiếp theo khó hơn
- Câu trả lời sai -> câu tiếp theo dễ hơn

### 6.3. Certificate Generation

- Tự động tạo certificate cho user đạt điểm cao
- Template customizable cho owner
- Download PDF certificate

### 6.4. Proctoring Features

- Webcam monitoring (optional)
- Tab switching detection
- Copy/paste prevention
- Randomize question order

### 6.5. Group Testing

- Tạo nhóm user để chia sẻ hàng loạt
- Batch invitations
- Group analytics

---

## Phase 7: Test Marketplace (Monetization - Public Tests)

**Mục tiêu:** Tạo marketplace công khai để owner publish bài thi và bất kỳ user nào cũng có thể tham gia.

**Thời gian ước tính:** 3-4 tuần

### 7.1. Marketplace Architecture

**New Collection:** `marketplace_tests`

```json
{
  "_id": ObjectId,
  "test_id": ObjectId,  // Reference to online_tests
  "owner_id": ObjectId,
  "title": "Bài test về JavaScript cơ bản",
  "description": "Kiểm tra kiến thức JS cho người mới bắt đầu",
  "category": "Programming",  // Programming, Language, Math, Science, etc.
  "tags": ["javascript", "beginner", "web-development"],
  "difficulty_level": "beginner",  // beginner, intermediate, advanced
  "thumbnail_url": "https://r2.../test-thumbnail.jpg",
  "price_points": 10,  // Giá bằng điểm
  "total_enrollments": 150,  // Số người đã tham gia
  "average_rating": 4.5,  // Đánh giá trung bình
  "total_reviews": 45,
  "is_featured": false,  // Featured tests hiển thị ở trang chủ
  "published_at": ISODate,
  "status": "published",  // draft, published, archived
  "preview_questions": 2,  // Số câu hỏi preview miễn phí
}
```

**Update `online_tests` schema:**
- Add `is_marketplace`: boolean (false by default)
- Add `marketplace_id`: ObjectId | null

### 7.2. Publishing Flow

**Owner Workflow:**
1. Owner tạo bài thi như bình thường (Phase 1)
2. Click "Publish to Marketplace"
3. Điền form:
   - Title & Description (marketing copy)
   - Category & Tags
   - Difficulty level
   - **Price (points)**: Owner set giá từ 1-100 điểm
   - Thumbnail image upload
   - Preview questions (2-3 câu miễn phí)
4. Submit for review (optional moderation)
5. Auto-publish hoặc manual approve bởi admin
6. Test xuất hiện trên marketplace

**Validation Rules:**
- Test phải có ít nhất 5 câu hỏi
- Owner phải verified account (email confirmed)
- Không được duplicate content (AI check similarity)

### 7.3. Discovery & Search

**Marketplace Features:**

**Homepage Sections:**
- Featured Tests (admin curated)
- Popular Tests (by enrollments)
- New Arrivals (recently published)
- Recommended for You (AI personalization)

**Search & Filters:**
- Full-text search (title, description, tags)
- Filter by category
- Filter by difficulty level
- Filter by price range (0-10, 11-20, 21-50, 51-100 điểm)
- Sort by: Popular, Newest, Rating, Price (Low to High)

**Test Detail Page:**
- Test overview (title, description, difficulty)
- Owner profile (name, rating, total tests)
- Preview questions (2-3 câu miễn phí để try)
- Reviews & Ratings
- Related tests
- CTA: "Enroll Now" (với giá points)

### 7.4. Enrollment System

**New Collection:** `test_enrollments`

```json
{
  "_id": ObjectId,
  "marketplace_test_id": ObjectId,
  "test_id": ObjectId,
  "user_id": ObjectId,
  "points_paid": 10,
  "enrolled_at": ISODate,
  "status": "active",  // active, completed, refunded
  "attempts_used": 1,
  "max_attempts": 3  // Inherit từ test config
}
```

**Enrollment Flow:**
1. User click "Enroll Now" trên marketplace
2. Hiển thị modal confirm:
   - Test title
   - Price: 10 điểm
   - Current balance: 85 điểm
   - After enrollment: 75 điểm
3. User confirm -> Deduct points -> Create enrollment
4. Redirect đến test taking page

**Access Control:**
- Chỉ enrolled users mới làm được bài
- Enrollment không có deadline (làm bất cứ lúc nào)
- Enrollment lifetime: Unlimited (1 lần mua, làm mãi)

### 7.5. Review & Rating System

**New Collection:** `test_reviews`

```json
{
  "_id": ObjectId,
  "marketplace_test_id": ObjectId,
  "user_id": ObjectId,
  "rating": 5,  // 1-5 stars
  "review_text": "Bài test rất hữu ích cho người mới bắt đầu!",
  "helpful_count": 12,  // Số người click "helpful"
  "created_at": ISODate,
  "updated_at": ISODate
}
```

**Review Rules:**
- Chỉ enrolled users mới được review
- User phải hoàn thành ít nhất 1 lần làm bài
- 1 user chỉ review 1 lần (có thể edit)
- Owner không thể review bài test của chính mình

**Rating Calculation:**
- Average rating = Σ(ratings) / total_reviews
- Update real-time khi có review mới
- Display rating distribution (5★: 30, 4★: 10, 3★: 5...)

### 7.6. API Endpoints - Phase 7

| Method | Endpoint | Chức năng | Auth | Priority |
|--------|----------|-----------|------|----------|
| **POST** | `/api/v1/marketplace/tests/publish` | Publish bài thi lên marketplace | Owner only | HIGH |
| **GET** | `/api/v1/marketplace/tests` | Danh sách bài thi trên marketplace (với filters) | Public | HIGH |
| **GET** | `/api/v1/marketplace/tests/{id}` | Chi tiết bài thi marketplace | Public | HIGH |
| **GET** | `/api/v1/marketplace/tests/{id}/preview` | Lấy preview questions miễn phí | Public | HIGH |
| **POST** | `/api/v1/marketplace/tests/{id}/enroll` | Mua và enroll vào bài thi | Required | HIGH |
| **GET** | `/api/v1/me/enrollments` | Danh sách bài thi đã mua | Required | MEDIUM |
| **POST** | `/api/v1/marketplace/tests/{id}/reviews` | Viết review cho bài thi | Required | MEDIUM |
| **GET** | `/api/v1/marketplace/tests/{id}/reviews` | Lấy danh sách reviews | Public | MEDIUM |
| **PATCH** | `/api/v1/marketplace/tests/{id}` | Cập nhật thông tin marketplace test | Owner only | MEDIUM |
| **DELETE** | `/api/v1/marketplace/tests/{id}` | Unpublish bài thi khỏi marketplace | Owner only | LOW |
| **POST** | `/api/v1/marketplace/reviews/{id}/helpful` | Mark review as helpful | Required | LOW |

### 7.7. Content Moderation

**Auto-moderation (AI):**
- Scan title & description for inappropriate content
- Check for spam keywords
- Detect plagiarism (compare với existing tests)

**Manual moderation (Admin):**
- Review queue for newly published tests
- Flag system: Users report inappropriate tests
- Admin dashboard to approve/reject/archive tests

**Moderation Actions:**
- Approve: Test goes live immediately
- Reject: Owner receives reason, can resubmit
- Archive: Remove từ marketplace (spam/violation)

### 7.8. Owner Dashboard Enhancements

**Marketplace Analytics (for Owners):**
- Total enrollments
- Revenue earned (points)
- Views vs Enrollments conversion rate
- Average rating & review highlights
- Top-performing tests
- Revenue trends (daily/weekly/monthly)

**New Metrics:**
- Impression count (test views)
- Click-through rate (CTR)
- Enrollment rate
- Refund rate (if applicable)

---

## Phase 8: Payment & Point System (Monetization - Real Money)

**Mục tiêu:** Tích hợp hệ thống nạp tiền, quản lý điểm, và chia sẻ doanh thu giữa platform và content creator.

**Thời gian ước tính:** 4-5 tuần

### 8.1. Point System Architecture

**Conversion Rate:**
- **1 USD = 25 điểm** (ví dụ: nạp $4 = 100 điểm)
- Gói khuyến mãi:
  - $4 → 100 điểm (giá gốc)
  - $10 → 260 điểm (bonus 4%)
  - $20 → 540 điểm (bonus 8%)
  - $50 → 1,400 điểm (bonus 12%)

**Revenue Share Model:**
- **Owner nhận: 80%** của giá test (ví dụ: test 10 điểm → owner +8 điểm)
- **Platform phí: 20%** (ví dụ: test 10 điểm → platform +2 điểm)

**New Collection:** `user_wallets`

```json
{
  "_id": ObjectId,
  "user_id": ObjectId,
  "balance_points": 100,
  "total_earned": 50,  // Tổng điểm kiếm được (cho owners)
  "total_spent": 30,   // Tổng điểm tiêu (cho users)
  "total_purchased": 80,  // Tổng điểm đã mua bằng tiền thật
  "created_at": ISODate,
  "updated_at": ISODate
}
```

**New Collection:** `point_transactions`

```json
{
  "_id": ObjectId,
  "user_id": ObjectId,
  "transaction_type": "purchase" | "earn" | "spend" | "refund" | "withdrawal",
  "amount": 10,  // Positive for credit, negative for debit
  "balance_after": 90,
  "related_entity_type": "test_enrollment" | "topup" | "marketplace_sale",
  "related_entity_id": ObjectId,
  "description": "Enrolled in 'JavaScript Basics' test",
  "created_at": ISODate
}
```

### 8.2. Payment Gateway Integration

**Recommended Gateway:** Stripe (Global) hoặc VNPay (Vietnam)

**Stripe Benefits:**
- International payment support (cards, wallets)
- Strong fraud detection
- Easy integration với Python SDK
- Supports subscriptions (future)

**Payment Flow:**
1. User click "Top Up Points"
2. Chọn gói: $4, $10, $20, $50
3. Redirect to Stripe Checkout
4. User nhập thông tin card, thanh toán
5. Stripe webhook notify backend
6. Backend verify payment, add points to wallet
7. Redirect user về dashboard với success message

**New Collection:** `payment_transactions`

```json
{
  "_id": ObjectId,
  "user_id": ObjectId,
  "payment_gateway": "stripe",
  "gateway_transaction_id": "pi_123456789",
  "amount_usd": 4.0,
  "points_purchased": 100,
  "status": "succeeded" | "pending" | "failed" | "refunded",
  "payment_method": "card",  // card, paypal, etc.
  "created_at": ISODate,
  "completed_at": ISODate
}
```

### 8.3. Enrollment Transaction Logic

**When User Enrolls in Paid Test:**

**Transaction Steps:**
1. Validate user balance ≥ test price
2. Create atomic transaction:
   ```python
   # Deduct từ user wallet
   user_wallet.balance_points -= test_price

   # Credit cho owner (80%)
   owner_earning = test_price * 0.8
   owner_wallet.balance_points += owner_earning

   # Credit cho platform (20%)
   platform_earning = test_price * 0.2
   platform_wallet.balance_points += platform_earning
   ```
3. Create 3 point_transactions records:
   - User: `spend`, amount = -10
   - Owner: `earn`, amount = +8
   - Platform: `earn`, amount = +2
4. Create enrollment record
5. Send email confirmation

**Atomicity:** Sử dụng MongoDB transactions để đảm bảo tất cả updates thành công hoặc rollback.

### 8.4. Withdrawal System (Cashout)

**Owner Withdrawal Rules:**
- Minimum withdrawal: 250 điểm (= $10)
- Withdrawal fee: 5% (để cover transaction costs)
- Processing time: 3-5 business days

**Withdrawal Methods:**
- Bank transfer (require bank account info)
- PayPal (require PayPal email)
- Stripe payout (automatic)

**New Collection:** `withdrawal_requests`

```json
{
  "_id": ObjectId,
  "user_id": ObjectId,
  "points_requested": 250,
  "amount_usd": 9.5,  // After 5% fee
  "withdrawal_method": "bank_transfer",
  "bank_account_info": {...},  // Encrypted
  "status": "pending" | "processing" | "completed" | "rejected",
  "requested_at": ISODate,
  "completed_at": ISODate,
  "rejection_reason": null
}
```

**Withdrawal Flow:**
1. Owner request withdrawal từ dashboard
2. Backend validates: balance ≥ 250, không có pending withdrawal
3. Create withdrawal_request với status `pending`
4. Admin review request (fraud check)
5. Admin approve → Initiate payout via Stripe/PayPal
6. Update status thành `completed`, deduct points
7. Send confirmation email

### 8.5. Refund Policy

**Refund Rules:**
- User có thể refund trong 7 ngày nếu:
  - Chưa hoàn thành bài thi
  - Hoặc hoàn thành nhưng score < 30% (bài thi quá khó/sai)
- Refund rate: 100% points trả lại
- Owner và Platform phải hoàn lại phần earning tương ứng

**Refund Flow:**
1. User request refund từ enrollment page
2. Backend validate điều kiện refund
3. Reverse transaction:
   - User: +10 điểm
   - Owner: -8 điểm
   - Platform: -2 điểm
4. Update enrollment status thành `refunded`
5. Notify owner về refund

### 8.6. API Endpoints - Phase 8

| Method | Endpoint | Chức năng | Auth | Priority |
|--------|----------|-----------|------|----------|
| **GET** | `/api/v1/wallet` | Lấy thông tin ví (balance, history) | Required | HIGH |
| **GET** | `/api/v1/wallet/transactions` | Lịch sử giao dịch điểm | Required | HIGH |
| **POST** | `/api/v1/payments/topup` | Tạo Stripe checkout session để nạp tiền | Required | HIGH |
| **POST** | `/api/v1/payments/webhook` | Stripe webhook để xử lý payment events | Public (Stripe) | HIGH |
| **POST** | `/api/v1/wallet/withdraw` | Request rút tiền | Required | MEDIUM |
| **GET** | `/api/v1/wallet/withdrawals` | Lịch sử rút tiền | Required | MEDIUM |
| **POST** | `/api/v1/enrollments/{id}/refund` | Yêu cầu hoàn tiền | Required | MEDIUM |
| **GET** | `/api/v1/admin/withdrawals` | Admin xem pending withdrawals | Admin only | MEDIUM |
| **POST** | `/api/v1/admin/withdrawals/{id}/approve` | Admin approve withdrawal | Admin only | MEDIUM |
| **POST** | `/api/v1/admin/withdrawals/{id}/reject` | Admin reject withdrawal | Admin only | LOW |

### 8.7. Pricing Strategy Recommendations

**Test Pricing Guidelines (for Owners):**
- **Free Preview:** 2-3 câu hỏi miễn phí
- **Beginner tests (5-10 questions):** 5-10 điểm
- **Intermediate tests (10-20 questions):** 10-20 điểm
- **Advanced tests (20-50 questions):** 20-50 điểm
- **Certification tests (50+ questions):** 50-100 điểm

**Dynamic Pricing Suggestions:**
- AI suggests price based on:
  - Number of questions
  - Difficulty level
  - Category average price
  - Owner's reputation

### 8.8. Fraud Prevention

**Bot Protection:**
- reCAPTCHA on payment pages
- Rate limit topup requests (max 5/day)
- Detect suspicious enrollment patterns

**Payment Fraud:**
- Stripe Radar (built-in fraud detection)
- Block stolen cards
- Velocity checks (too many cards from 1 IP)

**Content Fraud:**
- Monitor refund rates per test
- Auto-flag tests với refund rate > 30%
- Suspend owner accounts với repeated violations

**Withdrawal Fraud:**
- KYC verification for withdrawals > $100
- Manual review for first withdrawal
- Blacklist suspicious bank accounts

### 8.9. Financial Reporting

**Platform Revenue Dashboard (Admin):**
- Total revenue (USD & points)
- Revenue by category
- Top-earning tests
- Owner payouts pending
- Refund rate trends

**Owner Earnings Dashboard:**
- Total earnings (points & USD equivalent)
- Earnings by test
- Enrollment trends
- Conversion rate (views → enrollments)
- Projected earnings (based on trends)

**Export Reports:**
- Financial reports (CSV, PDF)
- Tax documents (for compliance)
- Invoice generation for withdrawals

### 8.10. Compliance & Legal

**Terms of Service:**
- Revenue share terms (80/20 split)
- Refund policy clearly stated
- Withdrawal terms and fees
- Content ownership rights

**Tax Compliance:**
- Issue 1099 forms (US creators earning > $600/year)
- VAT handling (EU creators)
- Store tax info for each user (W-9 forms)

**Payment Security:**
- PCI DSS compliance (handled by Stripe)
- Encrypt sensitive financial data
- Regular security audits

**Data Privacy:**
- GDPR compliance for EU users
- Secure storage of payment methods
- Right to data deletion

---

## Technical Considerations

### 7.1. Performance Optimization

**Caching Strategy:**
- Cache `online_tests` metadata với TTL 5 phút
- Cache `test_analytics` với TTL 10 phút
- Cache `marketplace_tests` với TTL 15 phút (ít thay đổi hơn)
- Cache test reviews và ratings với TTL 10 phút
- Invalidate cache khi có submission mới hoặc review mới

**Database Indexes:**
- Composite index: `(test_id, user_id, attempt_number)` cho queries nhanh
- Index `creator_id` cho owner dashboard
- Index `deadline` cho cron job
- Index `(category, published_at)` cho marketplace filtering
- Index `(average_rating, total_enrollments)` cho sorting
- Index `user_id` trong `user_wallets` và `point_transactions`
- Index `status` trong `withdrawal_requests`

**API Rate Limiting:**
- `/tests/generate`: 5 requests/hour/user (AI costs)
- `/tests/{id}/submit`: 10 requests/minute/user
- `/tests/{id}/progress/save`: 100 requests/minute/user
- `/payments/topup`: 5 requests/day/user (prevent fraud)
- `/marketplace/tests`: 100 requests/minute/user (public access)
- `/wallet/withdraw`: 3 requests/day/user

### 7.2. Error Handling

**Common Errors:**
- `TEST_NOT_FOUND`: 404
- `TEST_EXPIRED`: 410 Gone
- `MAX_RETRIES_EXCEEDED`: 429 Too Many Requests
- `INVALID_ANSWERS_FORMAT`: 400 Bad Request
- `DEADLINE_PASSED`: 403 Forbidden
- `AI_GENERATION_FAILED`: 503 Service Unavailable
- `INSUFFICIENT_BALANCE`: 402 Payment Required (không đủ điểm)
- `PAYMENT_FAILED`: 402 Payment Required (thanh toán thất bại)
- `ALREADY_ENROLLED`: 409 Conflict (đã mua test này rồi)
- `WITHDRAWAL_MINIMUM_NOT_MET`: 400 Bad Request (chưa đủ 250 điểm)
- `REFUND_NOT_ELIGIBLE`: 403 Forbidden (không đủ điều kiện refund)

**Retry Strategy:**
- AI generation failures: 3 retries với exponential backoff
- WebSocket reconnect: Infinite retries với max delay 30s
- Progress save failures: Queue trong localStorage, retry khi online
- Payment webhook retries: Stripe tự động retry với exponential backoff (1h, 2h, 4h...)
- Withdrawal processing: Manual retry by admin nếu payout fails

### 7.3. Security Considerations

**Authentication & Authorization:**
- JWT token validation cho tất cả endpoints
- Owner-only endpoints: Check `creator_id === user_id`
- Share access: Validate invitation token hoặc `test_shares` record
- Enrollment access: Validate user đã mua test (check `test_enrollments`)
- Admin endpoints: Validate `is_admin` flag trong user JWT

**Data Validation:**
- Sanitize HTML content khi edit test
- Validate JSON structure từ AI
- Rate limit để prevent abuse
- Validate payment amounts (prevent negative/zero amounts)
- Validate withdrawal amounts (minimum thresholds)

**Financial Security:**
- Use Stripe webhook signatures để verify requests
- Never trust client-side payment amounts
- Double-entry bookkeeping cho point transactions
- Audit logs cho tất cả financial transactions
- Encrypt bank account information (AES-256)

**Privacy:**
- Encrypt sensitive data (bank accounts, tax info)
- GDPR compliance: Export personal data, delete account
- PCI DSS compliance for payment data (handled by Stripe)
- Separate sensitive data vào encrypted collections

### 7.4. Monitoring & Logging

**Key Metrics:**
- AI generation success rate
- Average generation time
- WebSocket connection stability
- API response times
- Error rates per endpoint
- **Payment success rate** (Stripe payments)
- **Enrollment conversion rate** (views → enrollments)
- **Revenue metrics** (daily/weekly/monthly)
- **Refund rate** per test and platform-wide
- **Withdrawal processing time**

**Logging:**
- Log mọi test generation request với outcome
- Log submission attempts với score
- Log sharing actions với target users
- Log WebSocket disconnect/reconnect events
- **Log tất cả payment transactions** với full details
- **Log point transactions** (earn, spend, refund)
- **Log withdrawal requests** và approval/rejection
- **Log marketplace events** (publish, enroll, review)

---

## Deployment Strategy

### 8.1. Feature Flags

Sử dụng feature flags để enable/disable từng phase:

```python
FEATURE_FLAGS = {
    "online_test_generation": True,   # Phase 1
    "real_time_sync": True,            # Phase 2
    "test_retry_limits": True,         # Phase 3
    "test_editing": False,             # Phase 3 (chưa release)
    "test_sharing": True,              # Phase 4
    "test_analytics": True,            # Phase 5
    "test_marketplace": False,         # Phase 7 (beta)
    "payment_system": False,           # Phase 8 (beta)
    "point_wallet": False,             # Phase 8
    "withdrawal_system": False,        # Phase 8 (admin only)
}
```

### 8.2. Database Migration

- Dùng `pymongo` migration scripts trong `scripts/migrations/`
- Mỗi phase có 1 migration file riêng
- Rollback strategy cho mỗi migration

### 8.3. Backward Compatibility

- API versioning: `/api/v1/tests`, `/api/v2/tests` nếu cần breaking changes
- Soft delete thay vì hard delete
- Maintain old schema fields khi migrate

### 8.4. Testing Strategy

**Unit Tests:**
- Test AI response parsing
- Test scoring logic
- Test retry limit calculations

**Integration Tests:**
- Test end-to-end flow từ generation đến submission
- Test WebSocket events và reconnection
- Test sharing flow và email delivery

**Load Tests:**
- Simulate 100 concurrent users làm bài
- Test WebSocket scalability
- Test database query performance

---

## Success Metrics (KPIs)

### 9.1. Technical KPIs

- **AI Generation Success Rate:** ≥ 98%
- **API Response Time (p95):** < 500ms
- **WebSocket Uptime:** ≥ 99.5%
- **Data Loss Rate:** 0% (với auto-save)

### 9.2. Business KPIs

- **Test Generation Rate:** Số bài thi tạo/tháng
- **Test Completion Rate:** (Completed / Total Started) ≥ 80%
- **Share Engagement Rate:** (Accepted / Total Shares) ≥ 60%
- **User Retention:** User quay lại làm bài thi thứ 2 ≥ 40%
- **Marketplace Metrics (Phase 7):**
  - **Monthly Active Tests:** Số bài thi published và active
  - **Enrollment Rate:** (Enrollments / Test Views) ≥ 15%
  - **Average Test Price:** Giá trung bình của tests
  - **Creator Earnings:** Tổng điểm owners kiếm được/tháng
- **Payment Metrics (Phase 8):**
  - **Monthly Revenue (MRR):** Doanh thu từ topup/tháng
  - **ARPU:** Average Revenue Per User
  - **Payment Success Rate:** ≥ 98%
  - **Refund Rate:** < 5% platform-wide
  - **Withdrawal Processing Time:** < 3 days average

---

## Risks & Mitigation

### 10.1. Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| AI tạo câu hỏi kém chất lượng | HIGH | MEDIUM | Validation layer, human review option |
| WebSocket scaling issues | HIGH | LOW | Use Redis pub/sub, load balancer |
| Data loss khi mất kết nối | HIGH | MEDIUM | Auto-save + localStorage backup |
| Cheating (screen share, copy) | MEDIUM | HIGH | Proctoring features (Phase 6), randomize questions |
| High AI costs | MEDIUM | MEDIUM | Cache similar requests, rate limiting |
| **Payment fraud** | **HIGH** | **MEDIUM** | Stripe Radar, velocity checks, KYC for withdrawals |
| **Chargebacks** | **MEDIUM** | **LOW** | Clear refund policy, fraud detection |
| **Marketplace spam/low quality** | **MEDIUM** | **HIGH** | AI moderation, manual review, rating system |
| **Revenue share disputes** | **MEDIUM** | **LOW** | Clear ToS, transparent analytics, audit logs |
| **Withdrawal fraud** | **HIGH** | **LOW** | KYC verification, manual review, blacklist |

### 10.2. Contingency Plans

- **AI Service Down:** Fallback sang Claude nếu Gemini fail
- **Database Overload:** Implement read replicas, query optimization
- **Email Service Down:** Queue emails, retry sau
- **WebSocket Issues:** HTTP fallback cho progress save
- **Stripe Outage:** Queue topup requests, process khi service restored
- **High Refund Rate:** Auto-flag suspicious tests, contact owner, temporary suspend
- **Withdrawal Backlog:** Scale admin team, automate approvals với ML fraud detection

---

## Conclusion

Lộ trình này cung cấp một kế hoạch chi tiết, có thể thực hiện từng bước để xây dựng hệ thống Online Test hoàn chỉnh với marketplace và payment integration. Mỗi phase độc lập và có thể deploy riêng biệt, cho phép team phát triển linh hoạt và minimize risks.

**Recommended Implementation Order:**
1. **Phase 1 (Foundation)** - MUST HAVE - 3-4 tuần
2. **Phase 2 (Real-time Sync)** - MUST HAVE - 2-3 tuần
3. **Phase 4 (Sharing)** - SHOULD HAVE - 2-3 tuần
4. **Phase 3 (Retry & Editing)** - SHOULD HAVE - 2 tuần
5. **Phase 5 (Analytics)** - NICE TO HAVE - 2 tuần
6. **Phase 7 (Marketplace)** - MONETIZATION - 3-4 tuần
7. **Phase 8 (Payment System)** - MONETIZATION - 4-5 tuần
8. **Phase 6 (Advanced Features)** - FUTURE - 3-4 tuần

**Timeline Breakdown:**

**MVP (Phase 1-5):** 11-16 tuần (3-4 tháng)
- Core functionality cho private test creation và sharing

**Monetization Release (Phase 7-8):** 7-9 tuần (2 tháng)
- Public marketplace với payment integration
- Revenue sharing system

**Full Feature Release (Phase 6):** 3-4 tuần (1 tháng)
- Advanced features như proctoring, certificates

**Total Estimated Timeline:** 21-29 tuần (5-7 tháng) cho full system.

**Phased Rollout Strategy:**
- **Month 1-3:** MVP (Phase 1-5) - Private tests only
- **Month 4-5:** Marketplace beta (Phase 7) - Invited creators only
- **Month 5-6:** Payment integration (Phase 8) - Limited beta
- **Month 6-7:** Public launch với full monetization
- **Month 7+:** Advanced features và optimization

**Revenue Projections (Optimistic):**
- **Month 1-3:** $0 (MVP, no monetization)
- **Month 4:** $500 (Beta marketplace, 20 creators)
- **Month 5:** $2,000 (Payment beta, 50 active tests)
- **Month 6:** $5,000 (Public launch)
- **Month 12:** $20,000-50,000 (Target với 500+ creators)
