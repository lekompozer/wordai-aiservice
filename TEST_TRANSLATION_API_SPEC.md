# 🌍 Test Translation API - Technical Specification

## 📋 Overview

API endpoint để dịch các bài test hiện có sang ngôn ngữ khác sử dụng Gemini 2.0 Flash Exp. Tạo bản sao mới của test với nội dung đã được dịch, giữ nguyên cấu trúc và logic của test gốc.

---

## 🔗 Endpoint

### **POST /api/v1/tests/{test_id}/translate**

Dịch một bài test sang ngôn ngữ khác

**Authentication:** Required (Bearer Token)

**Path Parameters:**
- `test_id` (string, required): ID của test cần dịch

**Request Body:**
```json
{
  "target_language": "en",
  "new_title": "Optional Custom Title"
}
```

**Request Body Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `target_language` | string | ✅ Yes | Mã ngôn ngữ đích (xem danh sách bên dưới) |
| `new_title` | string | ❌ No | Tiêu đề tùy chỉnh cho test đã dịch. Nếu không cung cấp sẽ tự động thêm suffix "({language_code})" |

**Response (200 OK):**
```json
{
  "success": true,
  "test_id": "6756abc123def456789",
  "status": "pending",
  "original_test_id": "6756abc123def456000",
  "target_language": "en",
  "message": "Test translation to en started. Poll /tests/{test_id}/status for progress.",
  "created_at": "2025-12-02T10:30:00.000Z"
}
```

---

## 🌐 Supported Languages

API hỗ trợ 17 ngôn ngữ:

| Language Code | Language Name | Flag |
|--------------|---------------|------|
| `en` | English | 🇬🇧 |
| `vi` | Tiếng Việt | 🇻🇳 |
| `zh-CN` | Chinese (Simplified) | 🇨🇳 |
| `zh-TW` | Chinese (Traditional) | 🇹🇼 |
| `ja` | Japanese | 🇯🇵 |
| `ko` | Korean | 🇰🇷 |
| `th` | Thai | 🇹🇭 |
| `id` | Indonesian | 🇮🇩 |
| `km` | Khmer | 🇰🇭 |
| `lo` | Lao | 🇱🇦 |
| `hi` | Hindi | 🇮🇳 |
| `ms` | Malay | 🇲🇾 |
| `pt` | Portuguese | 🇵🇹 |
| `ru` | Russian | 🇷🇺 |
| `fr` | French | 🇫🇷 |
| `de` | German | 🇩🇪 |
| `es` | Spanish | 🇪🇸 |

**Lưu ý:**
- Frontend nên validate `target_language` trước khi gọi API
- Nếu gửi language code không được hỗ trợ sẽ nhận lỗi `400 Bad Request`

---

## 🔄 Translation Process Flow

### **1. Initial Request**
User gọi `POST /tests/{test_id}/translate` với target language

**What Happens:**
- Backend kiểm tra quyền sở hữu (chỉ owner mới dịch được)
- Kiểm tra test có questions chưa (không thể dịch test rỗng)
- Validate target language có được hỗ trợ không
- Kiểm tra ngôn ngữ hiện tại có khác target language không
- Tạo test record mới với `status: "pending"`
- Trả về `test_id` mới ngay lập tức (< 500ms)

### **2. Background Translation**
Background job xử lý translation bằng Gemini

**Status Progression:**
```
pending (0%) → translating (10-80%) → ready (100%)
                                    ↓
                                  failed
```

**Translation Steps:**
1. Update status → `"translating"` (10%)
2. Extract questions và text content
3. Build comprehensive translation prompt
4. Call Gemini 2.0 Flash Exp (30%)
5. Parse JSON response (80%)
6. Merge translated content với original structure
7. Save questions → Update status → `"ready"` (100%)

### **3. Status Polling**
Frontend poll status endpoint để check tiến độ

**Endpoint:** `GET /api/v1/tests/{new_test_id}/status`

**Polling Strategy:**
```javascript
// Recommended polling pattern
const pollInterval = 2000; // 2 seconds
const maxAttempts = 90; // 3 minutes max

let attempts = 0;
const interval = setInterval(async () => {
  attempts++;

  const response = await fetch(`/api/v1/tests/${testId}/status`);
  const data = await response.json();

  if (data.status === 'ready') {
    clearInterval(interval);
    // Redirect to test or show success
  } else if (data.status === 'failed') {
    clearInterval(interval);
    // Show error message
  } else if (attempts >= maxAttempts) {
    clearInterval(interval);
    // Timeout - show message to try again later
  }

  // Update progress bar
  updateProgress(data.progress_percent);
}, pollInterval);
```

**Status Response:**
```json
{
  "test_id": "6756abc123def456789",
  "status": "translating",
  "progress_percent": 45,
  "message": "Translating test content...",
  "title": "Test Title (en)",
  "num_questions": 20
}
```

---

## 📊 What Gets Translated

### ✅ **Text Content (Translated)**

| Field | Description | Example |
|-------|-------------|---------|
| `title` | Test title | "Kiểm tra IQ" → "IQ Test" |
| `description` | Test description | Full description text |
| `questions[].question_text` | Question text | "Câu hỏi 1" → "Question 1" |
| `questions[].options[].option_text` | MCQ option text | "Đáp án A" → "Answer A" |
| `questions[].explanation` | Answer explanation | Full explanation |
| `questions[].grading_rubric` | Essay rubric | Grading criteria |

### ⚠️ **Preserved (NOT Translated)**

| Field | Description | Why Not Translated |
|-------|-------------|-------------------|
| `question_id` | Question identifier | Technical field |
| `option_key` | Option key (A, B, C, D) | Universal identifier |
| `correct_answer_key` | Correct answer | Must match option keys |
| `media_type` | Media type (image/audio) | Technical field |
| `media_url` | Media URL | External resource |
| `media_description` | Media description | Optional - could translate in future |
| `time_limit_minutes` | Time limit | Numeric value |
| `max_retries` | Max attempts | Numeric value |
| `passing_score` | Passing score | Numeric value |
| `attachments[]` | PDF attachments | File references |

---

## 🗄️ Database Schema

### **New Test Document Structure**

Khi dịch, tạo document mới trong collection `online_tests`:

**Key Fields:**
```json
{
  "_id": ObjectId("new_test_id"),
  "title": "Translated Title",
  "description": "Translated description",
  "test_language": "en",
  "source_type": "translation",
  "original_test_id": "original_test_id",
  "creation_type": "translated",
  "status": "pending",
  "progress_percent": 0,
  "creator_id": "user_uid",
  "questions": [],
  "is_active": true,
  "created_at": ISODate("2025-12-02T10:30:00Z"),
  "updated_at": ISODate("2025-12-02T10:30:00Z"),
  "translated_at": ISODate("2025-12-02T10:32:15Z")
}
```

**Important Fields for Translation:**
- `source_type: "translation"` - Đánh dấu test này là bản dịch
- `original_test_id` - Reference đến test gốc
- `test_language` - Ngôn ngữ MỚI của test
- `translated_at` - Timestamp khi hoàn thành dịch

---

## ⚡ Performance & Timing

### **Response Times:**

| Stage | Expected Time | Notes |
|-------|--------------|-------|
| Initial API call | < 500ms | Tạo record và return test_id |
| Translation process | 30-90 seconds | Depends on test length |
| Status polling | 2s intervals | Recommended |

### **Translation Duration Factors:**

**Fast (20-30s):**
- 5-10 questions
- MCQ only
- Short text content

**Medium (40-60s):**
- 10-20 questions
- Mix MCQ and Essay
- Medium text length

**Slow (60-90s):**
- 20+ questions
- Lots of Essay questions
- Long explanations/rubrics

### **Optimization Tips:**
- Poll mỗi 2 giây (không nên < 1s để tránh overload)
- Show progress bar based on `progress_percent`
- Timeout sau 3 phút nếu vẫn không xong
- Cache translation results (test đã dịch có thể reuse)

---

## 🔒 Authentication & Authorization

### **Required:**
- Firebase Authentication token trong header
- User phải là owner của test gốc

### **Access Control:**
```
✅ CAN Translate:
- Test owner (creator_id == user_id)

❌ CANNOT Translate:
- Non-owners
- Shared users
- Public viewers
```

### **Error Response (403 Forbidden):**
```json
{
  "detail": "Only test owner can translate test"
}
```

---

## 🚨 Error Handling

### **Common Errors:**

| Status Code | Error | Cause | Solution |
|-------------|-------|-------|----------|
| `400` | Invalid target_language | Unsupported language code | Use supported language codes |
| `400` | Cannot translate empty test | Test has no questions | Add questions first |
| `400` | Already in target language | test_language == target_language | Choose different language |
| `403` | Access denied | User is not owner | Only owner can translate |
| `404` | Test not found | Invalid test_id | Check test_id |
| `500` | Translation failed | AI service error | Retry or contact support |

### **Error Response Format:**
```json
{
  "detail": "Error message here"
}
```

### **Failed Translation:**
Nếu background job fail, status sẽ là `"failed"`:

```json
{
  "test_id": "6756abc123def456789",
  "status": "failed",
  "progress_percent": 0,
  "message": "Translation failed",
  "error_message": "Invalid JSON response from AI: ..."
}
```

**Frontend nên:**
- Show error message to user
- Provide "Retry" button
- Log error for debugging
- Suggest contacting support if persists

---

## 🎯 Use Cases

### **1. Teacher Creating Multilingual Tests**
**Scenario:** Teacher tạo test tiếng Việt, muốn version tiếng Anh cho học sinh quốc tế

**Flow:**
1. Tạo test tiếng Việt như bình thường
2. Click "Translate" button
3. Chọn "English" từ dropdown
4. Wait for translation (show progress)
5. Review translated test
6. Publish hoặc edit thêm nếu cần

### **2. Student Practicing in Different Languages**
**Scenario:** Học sinh muốn làm cùng bài test bằng ngôn ngữ khác để practice

**Flow:**
1. Browse marketplace tests
2. Find interesting test
3. See "Available in: VI, EN, JA" badges
4. Click language switcher
5. Take test in preferred language

### **3. Content Creator Building Language Learning Tests**
**Scenario:** Creator tạo test vocabulary, cần versions cho nhiều ngôn ngữ

**Flow:**
1. Create master test in English
2. Translate to Vietnamese, Chinese, Japanese
3. Review all versions for accuracy
4. Publish all versions to marketplace
5. Users can choose their learning language

### **4. International Test Bank**
**Scenario:** Organization building multilingual test database

**Flow:**
1. Bulk translate existing tests
2. Quality check translations
3. Build language-specific test collections
4. Enable users to switch languages anytime

---

## 💡 Frontend Implementation Guide

### **UI Components Needed:**

**1. Translation Button**
- Location: Test detail page (owner view)
- Label: "🌍 Translate" hoặc "Dịch sang ngôn ngữ khác"
- Click → Open translation modal

**2. Translation Modal**
```
┌─────────────────────────────────────────┐
│  🌍 Translate Test                      │
├─────────────────────────────────────────┤
│                                         │
│  Target Language: [Dropdown ▼]         │
│                                         │
│  New Title (optional):                  │
│  [________________________]             │
│                                         │
│  ⚠️ This will create a new copy of     │
│     the test in the selected language  │
│                                         │
│     [Cancel]  [Translate →]            │
└─────────────────────────────────────────┘
```

**3. Translation Progress Modal**
```
┌─────────────────────────────────────────┐
│  🔄 Translating to English...           │
├─────────────────────────────────────────┤
│                                         │
│  Progress: 45%                          │
│  [████████░░░░░░░░░░]                   │
│                                         │
│  Status: Translating question 9/20     │
│                                         │
│  This may take 1-2 minutes...          │
│                                         │
└─────────────────────────────────────────┘
```

**4. Language Selector (Existing Tests)**
- Show available translations as badges
- Quick switch between language versions
- Example: `[🇻🇳 VI] [🇬🇧 EN] [🇯🇵 JA]`

### **State Management:**

**Translation State:**
```typescript
interface TranslationState {
  isTranslating: boolean;
  testId: string | null;
  originalTestId: string;
  targetLanguage: string;
  progress: number;
  status: 'idle' | 'pending' | 'translating' | 'ready' | 'failed';
  error: string | null;
}
```

**Actions:**
- `startTranslation(testId, targetLanguage, newTitle?)`
- `pollTranslationStatus(testId)`
- `handleTranslationComplete(testId)`
- `handleTranslationError(error)`

### **Validation:**

**Before API Call:**
```typescript
// Check current language
if (test.test_language === targetLanguage) {
  showError('Test is already in this language');
  return;
}

// Check supported languages
const SUPPORTED_LANGUAGES = ['en', 'vi', 'zh-CN', ...];
if (!SUPPORTED_LANGUAGES.includes(targetLanguage)) {
  showError('Language not supported');
  return;
}

// Check ownership
if (test.creator_id !== currentUser.uid) {
  showError('Only test owner can translate');
  return;
}
```

### **Error Messages (User-Friendly):**

| Technical Error | User Message (Vietnamese) | User Message (English) |
|----------------|--------------------------|----------------------|
| `403 Forbidden` | "Chỉ người tạo test mới có thể dịch" | "Only test owner can translate" |
| `400 Empty test` | "Test chưa có câu hỏi. Vui lòng thêm câu hỏi trước khi dịch" | "Test has no questions. Add questions before translating" |
| `400 Same language` | "Test đã ở ngôn ngữ này rồi" | "Test is already in this language" |
| `500 Translation failed` | "Dịch thất bại. Vui lòng thử lại" | "Translation failed. Please try again" |
| Timeout (3 min) | "Dịch test quá lâu. Vui lòng thử lại sau" | "Translation is taking too long. Please try again later" |

---

## 🔍 Testing Checklist

### **Functional Tests:**
- [ ] ✅ Translate test with MCQ questions only
- [ ] ✅ Translate test with Essay questions only
- [ ] ✅ Translate test with Mixed (MCQ + Essay)
- [ ] ✅ Translate test with media attachments
- [ ] ✅ Translate test with PDF attachments
- [ ] ✅ Verify option keys stay unchanged (A, B, C, D)
- [ ] ✅ Verify correct_answer_key stays unchanged
- [ ] ✅ Verify new test is independent copy
- [ ] ✅ Verify original test unchanged
- [ ] ✅ Test all 17 supported languages
- [ ] ✅ Test translation quality for each language

### **Error Cases:**
- [ ] ❌ Try to translate without authentication
- [ ] ❌ Try to translate test you don't own
- [ ] ❌ Try to translate empty test (no questions)
- [ ] ❌ Try to translate to same language
- [ ] ❌ Try to translate with unsupported language
- [ ] ❌ Test Gemini API failure handling
- [ ] ❌ Test timeout scenario (> 3 minutes)

### **Edge Cases:**
- [ ] 🔸 Translate test with 100 questions (max)
- [ ] 🔸 Translate test with very long explanations
- [ ] 🔸 Translate test with special characters
- [ ] 🔸 Translate test with code snippets in questions
- [ ] 🔸 Translate test with mathematical formulas
- [ ] 🔸 Translate already translated test (chain translation)
- [ ] 🔸 Multiple users translating same test simultaneously

### **Performance Tests:**
- [ ] ⚡ Measure response time for initial API call (should be < 500ms)
- [ ] ⚡ Measure translation time for different test sizes
- [ ] ⚡ Test with concurrent translation requests
- [ ] ⚡ Monitor Gemini API rate limits

---

## 📈 Monitoring & Analytics

### **Metrics to Track:**

**Usage Metrics:**
- Total translations per day/week/month
- Popular language pairs (e.g., VI → EN)
- Success rate (completed vs failed)
- Average translation duration by test size

**Quality Metrics:**
- User edits after translation (indicates quality issues)
- Tests deleted immediately after translation (low quality)
- User satisfaction ratings for translated tests

**Performance Metrics:**
- Average API response time
- Average translation duration
- Gemini API call success rate
- Status polling frequency

### **Alerts:**
- Translation failure rate > 5%
- Average translation time > 2 minutes
- Gemini API errors spike
- Unusual number of translations from single user (abuse detection)

---

## 🔮 Future Enhancements

### **Phase 2 (Planned):**
- **Batch Translation:** Translate multiple tests at once
- **Language Detection:** Auto-detect source language
- **Translation Memory:** Cache common phrases for consistency
- **Glossary Support:** User-defined terminology translations
- **Quality Check:** AI review of translation quality
- **Edit Translations:** Allow manual edits to translated text

### **Phase 3 (Ideas):**
- **Real-time Translation:** Translate as user types
- **Voice Translation:** Translate audio questions
- **Image Text Translation:** OCR + translate for image-based questions
- **Collaborative Translation:** Multiple users can review/edit
- **Translation API for 3rd party:** Allow external services to translate

---

## 📞 Support & Resources

**API Documentation:**
- Full API reference: `/docs` (Swagger UI)
- Interactive testing: `/docs#/Test%20Translation`

**Related Endpoints:**
- `GET /api/v1/tests/{test_id}` - Get test details
- `GET /api/v1/tests/{test_id}/status` - Check generation/translation status
- `POST /api/v1/tests/{test_id}/duplicate` - Duplicate test (alternative to translation)

**Contact:**
- Technical support: support@wordai.pro
- Report translation quality issues: feedback@wordai.pro

---

**Last Updated:** December 2, 2025
**API Version:** v1.0
**Status:** ✅ Production Ready
