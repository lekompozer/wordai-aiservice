# Show Answers Timing Feature - Anti-Cheating for Tests

**Date:** November 12, 2025
**Version:** 1.0
**Feature:** Control when test answers are revealed to prevent cheating

---

## 📋 Overview

This feature adds control over **when test takers can see correct answers and explanations** after submitting a test. This prevents users from:
- Taking screenshots of answers during the test
- Sharing answers with friends before the deadline
- Cheating on timed assessments or exams

### Use Cases

1. **Timed Exams**: Teacher sets deadline, students can't see answers until exam period ends
2. **Recruitment Tests**: Candidates only see pass/fail until hiring deadline
3. **Training Assessments**: Learners get scores immediately but explanations after deadline
4. **Public Marketplace Tests**: Prevent buyers from sharing answers with non-buyers

---

## 🎯 Feature Behavior

### Option 1: `immediate` (Default)
**Current behavior - no changes needed**

- User submits test → immediately sees:
  - ✅ Score and percentage
  - ✅ Pass/fail status
  - ✅ Correct answers for each question
  - ✅ Their selected answers
  - ✅ Explanations

**Best for:** Practice tests, self-study, casual quizzes

---

### Option 2: `after_deadline`
**NEW - Anti-cheating mode**

#### Before Deadline Passes:
When user submits test, they only see:
- ✅ Score and percentage
- ✅ Pass/fail status
- ✅ Total correct answers count
- ❌ **HIDDEN**: Detailed results list (no questions shown)
- ❌ **HIDDEN**: Which questions they got right/wrong
- ❌ **HIDDEN**: Correct answer keys
- ❌ **HIDDEN**: User's selected answers
- ❌ **HIDDEN**: Explanations

**Response includes:**
```json
{
  "success": true,
  "score": 7.5,
  "score_percentage": 75,
  "is_passed": true,
  "correct_answers": 15,
  "total_questions": 20,
  "submission_id": "sub_789",

  // ❌ NO "results" array at all
  "results_hidden_until_deadline": "2025-11-15T23:59:59Z",
  "message": "Detailed answers will be revealed after the deadline"
}
```

#### After Deadline Passes:
User can view full details:
- ✅ All correct answers
- ✅ Their selected answers
- ✅ Full explanations
- ✅ Complete review experience

**Best for:** Exams, assessments, certification tests, competitive tests

---

## 📡 API Changes

### 1. Test Creation & Update

#### New Field: `show_answers_timing`

**Values:**
- `"immediate"` - Show answers right after submit (default)
- `"after_deadline"` - Hide answers until deadline passes

**Applies to:**
- `POST /api/v1/tests/generate` - AI-generated tests
- `POST /api/v1/tests/manual` - Manual tests
- `PATCH /api/v1/tests/{test_id}/config` - Update existing test

---

#### POST /api/v1/tests/generate

**Request - Added field:**
```json
{
  "title": "English Final Exam",
  "description": "End of semester assessment",
  "source_type": "document",
  "source_id": "doc_123",
  "num_questions": 50,
  "time_limit_minutes": 90,
  "deadline": "2025-11-20T23:59:59Z",
  "show_answers_timing": "after_deadline"  // ← NEW
}
```

**Database - Stored in test document:**
```javascript
{
  "_id": ObjectId("..."),
  "title": "English Final Exam",
  "deadline": ISODate("2025-11-20T23:59:59Z"),
  "show_answers_timing": "after_deadline",  // ← NEW FIELD
  // ... other fields
}
```

---

#### POST /api/v1/tests/manual

**Request:**
```json
{
  "title": "Math Quiz",
  "time_limit_minutes": 30,
  "deadline": "2025-11-15T18:00:00Z",
  "show_answers_timing": "after_deadline",  // ← NEW
  "questions": [...]
}
```

---

#### PATCH /api/v1/tests/{test_id}/config

**Request - Update existing test:**
```json
{
  "deadline": "2025-11-25T23:59:59Z",
  "show_answers_timing": "after_deadline"  // ← Can update later
}
```

**Validation:**
- Must be `"immediate"` or `"after_deadline"`
- Returns 400 if invalid value

---

### 2. Test Submission - Modified Response

#### POST /api/v1/tests/{test_id}/submit

**Behavior:**
1. Check `show_answers_timing` setting from test document
2. If `"immediate"` → return full results (current behavior)
3. If `"after_deadline"`:
   - Check if `deadline` has passed
   - If deadline **not passed** → hide detailed answers
   - If deadline **passed** → show full results

---

**Response - Before Deadline (Limited):**
```json
{
  "success": true,
  "submission_id": "sub_789",
  "score": 8.2,
  "score_percentage": 82,
  "total_questions": 20,
  "correct_answers": 16,
  "is_passed": true,

  // ❌ NO "results" array - completely hidden
  // ❌ NO "attempt_number" shown
  "results_hidden_until_deadline": "2025-11-20T23:59:59Z",
  "message": "Detailed answers will be revealed after the deadline"
}
```

**Response - After Deadline (Full):**
```json
{
  "success": true,
  "submission_id": "sub_789",
  "score": 8.2,
  "score_percentage": 82,
  "total_questions": 20,
  "correct_answers": 16,
  "attempt_number": 1,
  "is_passed": true,

  // ✅ Full results with answers
  "results": [
    {
      "question_id": "q1",
      "question_text": "What is 2+2?",
      "your_answer": "D",
      "correct_answer": "D",
      "is_correct": true,
      "explanation": "Basic arithmetic: 2+2 equals 4"
    }
    // ... more questions
  ]
}
```

---

### 3. View Submission Details - Modified Response

#### GET /api/v1/me/submissions/{submission_id}

**Behavior:**
- Same logic as submit endpoint
- Check test's `show_answers_timing` and `deadline`
- Return limited or full results based on current time

---

**Response - Before Deadline (Limited):**
```json
{
  "submission_id": "sub_789",
  "test_title": "English Final Exam",
  "score": 7.5,
  "score_percentage": 75,
  "total_questions": 20,
  "correct_answers": 15,
  "is_passed": true,
  "submitted_at": "2025-11-15T10:30:00Z",

  // ❌ NO "results" array at all
  // ❌ NO "attempt_number" or "time_taken_seconds"
  "results_hidden_until_deadline": "2025-11-20T23:59:59Z",
  "message": "Detailed answers and explanations will be revealed after the deadline"
}
```

**Response - After Deadline (Full):**
```json
{
  "submission_id": "sub_789",
  "test_title": "English Final Exam",
  "score": 7.5,
  "score_percentage": 75,
  "total_questions": 20,
  "correct_answers": 15,
  "is_passed": true,
  "submitted_at": "2025-11-15T10:30:00Z",

  // ✅ Full results with all details
  "results": [
    {
      "question_id": "q1",
      "question_text": "Choose the correct answer:",
      "options": [{"key": "A", "text": "..."}, ...],
      "your_answer": "B",
      "correct_answer": "B",
      "is_correct": true,
      "explanation": "Detailed explanation here..."
    }
    // ... all questions with full details
  ]
}
```

---

## 🎨 Frontend Integration Guide

### Test Creation UI

```typescript
interface TestSettings {
  title: string;
  deadline?: string; // ISO 8601
  show_answers_timing: 'immediate' | 'after_deadline';
}

function TestSettingsForm() {
  const [settings, setSettings] = useState<TestSettings>({
    title: '',
    show_answers_timing: 'immediate'
  });

  return (
    <div>
      <h3>Answer Reveal Settings</h3>

      {/* Deadline input */}
      <label>
        Deadline (optional):
        <input
          type="datetime-local"
          value={settings.deadline}
          onChange={e => setSettings({...settings, deadline: e.target.value})}
        />
      </label>

      {/* Show answers timing */}
      <label>
        When to show answers:
        <select
          value={settings.show_answers_timing}
          onChange={e => setSettings({
            ...settings,
            show_answers_timing: e.target.value as any
          })}
        >
          <option value="immediate">
            Immediately after submission
          </option>
          <option value="after_deadline" disabled={!settings.deadline}>
            After deadline (requires deadline)
          </option>
        </select>
      </label>

      {/* Warning if after_deadline selected */}
      {settings.show_answers_timing === 'after_deadline' && (
        <div className="warning">
          ⚠️ Students will only see their score until {settings.deadline}
        </div>
      )}
    </div>
  );
}
```

---

### Test Submission Result Display

```typescript
interface SubmissionResult {
  success: boolean;
  score: number;
  score_percentage: number;
  is_passed: boolean;
  correct_answers: number;
  total_questions: number;
  results?: Array<{
    question_id: string;
    question_text: string;
    your_answer?: string;
    correct_answer?: string;
    is_correct: boolean;
    explanation?: string;
  }>;
  results_limited?: boolean;
  answers_hidden_until_deadline?: string;
  message?: string;
}

function SubmissionResultDisplay({ result }: { result: SubmissionResult }) {
  return (
    <div className="submission-result">
      {/* Always show score */}
      <div className="score-section">
        <h2>Score: {result.score}/10 ({result.score_percentage}%)</h2>
        <p className={result.is_passed ? 'passed' : 'failed'}>
          {result.is_passed ? '✅ PASSED' : '❌ FAILED'}
        </p>
        <p>Correct: {result.correct_answers}/{result.total_questions}</p>
      </div>

      {/* Check if answers are hidden */}
      {result.results_hidden_until_deadline ? (
        <div className="answers-locked">
          <h3>🔒 Answers Hidden Until Deadline</h3>
          <p>{result.message}</p>
          <p>
            Deadline: {new Date(result.results_hidden_until_deadline).toLocaleString()}
          </p>

          <div className="info-box">
            💡 You can review detailed answers and explanations after the deadline
          </div>
        </div>
      ) : (
        <div className="full-results">
          {/* Show full results with answers */}
          <h3>Detailed Results</h3>
          {result.results?.map((q, i) => (
            <div key={q.question_id} className="question-result">
              <h4>Question {i + 1}</h4>
              <p>{q.question_text}</p>
              <p>Your answer: <strong>{q.your_answer}</strong></p>
              <p>Correct answer: <strong>{q.correct_answer}</strong></p>
              <p className={q.is_correct ? 'correct' : 'incorrect'}>
                {q.is_correct ? '✅ Correct' : '❌ Incorrect'}
              </p>
              {q.explanation && (
                <div className="explanation">
                  <strong>Explanation:</strong> {q.explanation}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

---

### Checking Past Submissions

```typescript
async function viewSubmission(submissionId: string) {
  const response = await fetch(
    `/api/v1/me/submissions/${submissionId}`,
    {
      headers: { 'Authorization': `Bearer ${token}` }
    }
  );

  const data: SubmissionResult = await response.json();

  // Check if still locked (no results array present)
  if (data.results_hidden_until_deadline) {
    showMessage(
      'Answers are still hidden until deadline: ' +
      new Date(data.results_hidden_until_deadline).toLocaleString()
    );
  } else {
    showFullResults(data.results);
  }
}
```

---

## 🔒 Security Considerations

### What This Feature Prevents:
✅ Users can't screenshot answers during deadline period
✅ Users can't share correct answers with friends
✅ Fair assessment for all participants
✅ Maintains exam integrity

### What This Feature Does NOT Prevent:
❌ Users can still see their score immediately
❌ Users know total correct answers count
❌ Browser back button (frontend must handle)
❌ Network request inspection (backend doesn't send results before deadline)### Best Practices:
1. **Always set a deadline** when using `"after_deadline"` mode
2. **Communicate clearly** to users when answers will be revealed
3. **Frontend validation**: Disable "after_deadline" option if no deadline set
4. **Time zone handling**: Backend uses UTC, frontend should display in user's timezone

---

## 🗄️ Database Schema

### Test Document (online_tests collection)

```javascript
{
  "_id": ObjectId("..."),
  "title": "Final Exam",
  "creator_id": "user123",
  "deadline": ISODate("2025-11-20T23:59:59Z"),

  // NEW FIELD
  "show_answers_timing": "after_deadline",  // or "immediate"

  "questions": [...],
  "time_limit_minutes": 90,
  "passing_score": 70,
  // ... other fields
}
```

**Field Details:**
- **Type:** `string`
- **Values:** `"immediate"` | `"after_deadline"`
- **Default:** `"immediate"` (if not specified)
- **Required:** No (optional)

---

## ✅ Testing Checklist

### Backend Testing

- [ ] **Create test with immediate mode**
  - [ ] Submit test → should see full results
  - [ ] View submission → should see full results

- [ ] **Create test with after_deadline mode + deadline in future**
  - [ ] Submit test → should see limited results
  - [ ] Check `results_hidden_until_deadline` field present
  - [ ] View submission → should see limited results

- [ ] **Create test with after_deadline mode + deadline in past**
  - [ ] Submit test → should see full results
  - [ ] View submission → should see full results

- [ ] **Update test show_answers_timing**
  - [ ] Change from immediate to after_deadline
  - [ ] Change from after_deadline to immediate
  - [ ] Invalid value → should return 400 error

- [ ] **Edge cases**
  - [ ] Test with after_deadline but no deadline → treat as immediate
  - [ ] Deadline with no timezone → should handle gracefully
  - [ ] Multiple submissions → each respects deadline

---

### Frontend Testing

- [ ] **Test creation UI**
  - [ ] Dropdown shows both options
  - [ ] after_deadline disabled if no deadline set
  - [ ] Warning message appears when after_deadline selected

- [ ] **Submission result page**
  - [ ] Limited results show only correct/incorrect icons
  - [ ] Deadline countdown/message displayed
  - [ ] No answer keys visible before deadline
  - [ ] Full results visible after deadline

- [ ] **Submission history page**
  - [ ] Old submissions show limited results if deadline not passed
  - [ ] Old submissions show full results if deadline passed
  - [ ] Clear messaging about when answers unlock

---

## 🚀 Migration Notes

### For Existing Tests

**No migration required** - this is a backward-compatible change.

- Existing tests without `show_answers_timing` field → default to `"immediate"`
- All existing tests continue to work as before
- Creators can update tests to use `"after_deadline"` mode

### Breaking Changes

**None.** This is purely additive.

---

## 📝 API Summary

| Endpoint | Changes | New Response Fields |
|----------|---------|-------------------|
| `POST /api/v1/tests/generate` | Added `show_answers_timing` in request body | None |
| `POST /api/v1/tests/manual` | Added `show_answers_timing` in request body | None |
| `PATCH /api/v1/tests/{test_id}/config` | Added `show_answers_timing` in request body | None |
| `POST /api/v1/tests/{test_id}/submit` | Modified response logic | `results_hidden_until_deadline`, `message` (when limited) |
| `GET /api/v1/me/submissions/{submission_id}` | Modified response logic | `results_limited`, `answers_hidden_until_deadline`, `message` |

---

## 💡 Example Scenarios

### Scenario 1: University Final Exam
```json
{
  "title": "Computer Science Final Exam",
  "deadline": "2025-12-15T18:00:00Z",
  "show_answers_timing": "after_deadline",
  "time_limit_minutes": 120
}
```
- Students take exam anytime before Dec 15 6PM
- After submit: see score only
- After Dec 15 6PM: everyone can review answers

---

### Scenario 2: Job Interview Assessment
```json
{
  "title": "Software Engineer Technical Test",
  "deadline": "2025-11-30T23:59:59Z",
  "show_answers_timing": "after_deadline"
}
```
- Candidates submit before Nov 30
- Only see pass/fail score
- After hiring process ends (Nov 30), can review

---

### Scenario 3: Practice Quiz (No Restrictions)
```json
{
  "title": "JavaScript Practice Quiz",
  "show_answers_timing": "immediate"
}
```
- No deadline needed
- Instant feedback with answers
- Great for learning

---

## 📞 Support & Questions

**Common Questions:**

Q: Can I change `show_answers_timing` after test is created?
A: Yes, use `PATCH /api/v1/tests/{test_id}/config`

Q: What if I set `after_deadline` but no deadline?
A: System treats it as `immediate` mode (shows answers right away)

Q: Can users see which questions they got wrong before deadline?
A: No, they only see: score, pass/fail status, and total correct count. No question-level details until deadline passes.Q: Does this work with marketplace tests?
A: Yes, buyers inherit the `show_answers_timing` setting from the original test

Q: Can I have different deadlines for different users?
A: No, this is a global test setting. For per-user deadlines, use the sharing system's individual deadline feature.

---

**Last Updated:** November 12, 2025
**Feature Status:** ✅ Implemented and Ready for Deployment
