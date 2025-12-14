# System Reference - Backend Infrastructure

**Last Updated:** December 14, 2025
**Purpose:** Complete reference for AI agents and developers working with the backend system

---

## 🐳 Docker Configuration

### Container Names

| Container Name | Service | Purpose |
|---------------|---------|---------|
| `ai-chatbot-rag` | Backend API | Main FastAPI application |
| `mongodb` | Database | MongoDB 7.0 database server |
| `qdrant` | Vector DB | Qdrant vector search (if used) |
| `redis` | Cache | Redis cache server (if used) |

### Docker Commands

```bash
# List running containers
docker ps

# View logs
docker logs ai-chatbot-rag
docker logs ai-chatbot-rag -f --tail 100

# Execute commands inside container
docker exec ai-chatbot-rag <command>

# Access container shell
docker exec -it ai-chatbot-rag /bin/bash

# Check files inside container
docker exec ai-chatbot-rag ls -lh /tmp/
```

---

## 🗄️ MongoDB Database

### Connection Information

**Database Name:** `ai_service_db`

**Connection String Format:**
```
mongodb://<username>:<password>@mongodb:27017/?authSource=admin
```

**Alternative Connection (from inside Docker network):**
```
mongodb://<username>:<password>@mongodb:27017/ai_service_db?authSource=admin
```

**Environment Variables:**
- `MONGODB_NAME`: Database name (default: `ai_service_db`)
- `MONGODB_URI_AUTH`: Full connection string with authentication (PRODUCTION - REQUIRED on server)
- `MONGODB_URI`: Full connection string without auth (LOCAL DEVELOPMENT ONLY)
- `MONGO_INITDB_ROOT_USERNAME`: Admin username
- `MONGO_INITDB_ROOT_PASSWORD`: Admin password

**Important:**
- Production server MUST use `MONGODB_URI_AUTH`
- Local development uses `MONGODB_URI`
- Backend code checks `MONGODB_URI_AUTH` first, falls back to `MONGODB_URI`

### Collections Structure

#### 1. **online_tests**
Test documents and questions

**Fields:**
- `_id`: ObjectId (test ID)
- `title`: String
- `description`: String
- `creator_id`: String (Firebase UID)
- `creator_name`: String
- `test_type`: String (`mcq`, `listening`, `merged`)
- `test_category`: String (`academic`, `diagnostic`)
- `status`: String (`ready`, `generating`, `failed`)
- `is_active`: Boolean
- `questions`: Array of question objects
  - `question_id`: String
  - `question_type`: String (`mcq`, `mcq_multiple`, `matching`, `completion`, `sentence_completion`, `short_answer`, `essay`)
  - `question_text`: String
  - `correct_answers`: Array (unified field)
  - `explanation`: String
  - `max_points`: Integer
  - `options`: Array (for MCQ)
  - `template`: String (for completion/sentence_completion)
  - `sentences`: Array (for IELTS sentence_completion)
  - `left_items`, `right_options`: Arrays (for matching)
- `audio_sections`: Array (for listening tests)
- `attachments`: Array (for reading comprehension PDFs)
- `time_limit_minutes`: Integer
- `max_retries`: Integer
- `passing_score`: Integer
- `deadline`: DateTime
- `show_answers_timing`: String (`immediate`, `after_deadline`)
- `marketplace_config`: Object (for published tests)
- `evaluation_criteria`: Object (for diagnostic tests)
- `created_at`: DateTime
- `updated_at`: DateTime
- `generated_at`: DateTime

**Indexes:**
- `_id`: Primary key
- `creator_id`: For user's tests
- `status`: For filtering ready tests

#### 2. **test_submissions**
User test submissions and results

**Fields:**
- `_id`: ObjectId (submission ID)
- `test_id`: String
- `user_id`: String (Firebase UID)
- `user_email`: String
- `user_answers`: Array of answer objects
- `grading_status`: String (`auto_graded`, `pending_grading`, `partially_graded`, `fully_graded`)
- `score`: Float (out of 10)
- `score_percentage`: Float (0-100)
- `mcq_score`: Float (MCQ points only)
- `essay_score`: Float (essay points only)
- `mcq_correct_count`: Integer
- `correct_answers`: Integer (total correct)
- `total_questions`: Integer
- `is_passed`: Boolean
- `time_taken_seconds`: Integer
- `attempt_number`: Integer
- `essay_grades`: Array (for essay questions)
- `submitted_at`: DateTime
- `is_diagnostic_test`: Boolean
- `has_ai_evaluation`: Boolean

**Indexes:**
- `_id`: Primary key
- `test_id`: For test results
- `user_id`: For user submissions
- `{test_id, user_id}`: Compound for user's attempts

#### 3. **test_shares**
Test sharing permissions

**Fields:**
- `_id`: ObjectId
- `test_id`: String
- `owner_id`: String (Firebase UID)
- `shared_with`: Array of user objects
  - `user_id`: String
  - `email`: String
  - `shared_at`: DateTime
  - `can_edit`: Boolean
- `created_at`: DateTime

**Indexes:**
- `test_id`: For test sharing
- `shared_with.user_id`: For user's shared tests

#### 4. **users**
User profiles and settings

**Fields:**
- `_id`: ObjectId
- `firebase_uid`: String (unique)
- `email`: String
- `display_name`: String
- `photo_url`: String
- `subscription_tier`: String
- `points_balance`: Integer
- `created_at`: DateTime
- `last_login`: DateTime

**Indexes:**
- `firebase_uid`: Unique, for authentication
- `email`: For lookups

#### 5. **grading_queue**
Essay grading queue

**Fields:**
- `_id`: ObjectId
- `submission_id`: String
- `test_id`: String
- `user_id`: String
- `total_essays`: Integer
- `graded_count`: Integer
- `status`: String (`pending`, `in_progress`, `completed`)
- `created_at`: DateTime

**Indexes:**
- `submission_id`: Unique
- `status`: For queue processing

#### 6. **test_purchases**
Marketplace test purchases

**Fields:**
- `_id`: ObjectId
- `test_id`: String
- `buyer_id`: String (Firebase UID)
- `seller_id`: String (test creator)
- `price_points`: Integer
- `purchased_at`: DateTime

**Indexes:**
- `{test_id, buyer_id}`: Compound, unique
- `buyer_id`: For user purchases
- `seller_id`: For seller earnings

#### 7. **test_ratings**
Test ratings and reviews

**Fields:**
- `_id`: ObjectId
- `test_id`: String
- `user_id`: String
- `rating`: Integer (1-5)
- `review`: String
- `created_at`: DateTime

**Indexes:**
- `{test_id, user_id}`: Compound, unique
- `test_id`: For test ratings

#### 8. **conversations**
Chat conversations

**Fields:**
- `_id`: ObjectId
- `user_id`: String
- `title`: String
- `messages`: Array
- `created_at`: DateTime
- `updated_at`: DateTime

**Indexes:**
- `user_id`: For user conversations

#### 9. **notifications**
User notifications

**Fields:**
- `_id`: ObjectId
- `user_id`: String
- `type`: String
- `title`: String
- `message`: String
- `is_read`: Boolean
- `created_at`: DateTime

**Indexes:**
- `user_id`: For user notifications
- `is_read`: For unread count

---

## 📁 File System Structure

### Temporary Files (Inside Docker Container)

```
/tmp/
├── gemini_test_responses/     # Full Gemini API responses (JSON)
│   └── test_gen_YYYYMMDD_HHMMSS_ffffff.json
├── gemini_parsed_json/        # Parsed JSON before validation
│   └── parsed_YYYYMMDD_HHMMSS_ffffff.json
└── gemini_prompts/            # Prompts sent to Gemini
    └── prompt_YYYYMMDD_HHMMSS_ffffff.txt
```

**Note:** These directories are created dynamically when tests are generated.

### Application Structure

```
/app/                          # Inside Docker container
├── src/
│   ├── api/                   # FastAPI route handlers
│   │   ├── test_creation_routes.py
│   │   ├── test_taking_routes.py
│   │   ├── test_grading_routes.py
│   │   ├── marketplace_routes.py
│   │   └── test_sharing_routes.py
│   ├── services/
│   │   ├── test_generator_service.py
│   │   ├── prompt_builders.py
│   │   └── online_test_utils.py
│   └── models/                # Pydantic models
├── serve.py                   # FastAPI app entry point
└── requirements.txt
```

---

## 🚀 Deployment Process

### Deployment Script

**Location:** `/home/hoile/wordai/deploy-compose-with-rollback.sh`

**Standard Deployment Commands:**

```bash
# 1. SSH to production server
ssh root@<server-ip>

# 2. Switch to deployment user
su - hoile

# 3. Navigate to project directory
cd /home/hoile/wordai

# 4. Pull latest code
git pull origin main

# 5. Deploy with rollback capability
./deploy-compose-with-rollback.sh
```

### Deployment Flow

1. **Pull latest code** from GitHub
2. **Build new Docker image** with latest commit hash as tag
3. **Stop current container** (ai-chatbot-rag)
4. **Start new container** with new image
5. **Health check** (wait for /health endpoint)
6. **Rollback** if health check fails (restore previous image)

### Docker Image Naming

Format: `lekompozer/wordai-aiservice:<commit-hash>`

Example: `lekompozer/wordai-aiservice:7757d9c`

### Check Current Version

```bash
# Check running container image
docker inspect ai-chatbot-rag --format "{{.Config.Image}}"

# Check when container was created
docker inspect ai-chatbot-rag --format "{{.Created}}"
```

---

## 🔧 MongoDB Access

### From Production Server

```bash
# SSH to server
ssh root@<server-ip>

# Access MongoDB shell
docker exec mongodb mongosh -u <username> -p <password> \
  --authenticationDatabase admin ai_service_db
```

### Common MongoDB Operations

```javascript
// Switch to database
use ai_service_db

// List all collections
show collections

// Count documents
db.online_tests.countDocuments()

// Find test by ID (as ObjectId)
db.online_tests.findOne({_id: ObjectId("693eb0d83456aa028c4ee7fe")})

// Find tests by user
db.online_tests.find({creator_id: "firebase-uid"}).limit(10)

// Find submissions for a test
db.test_submissions.find({test_id: "693eb0d83456aa028c4ee7fe"})

// Check test status
db.online_tests.find({status: "ready"}).count()

// Get recent tests
db.online_tests.find().sort({created_at: -1}).limit(5)
```

### Query from Command Line (One-liner)

```bash
# Example: Check test questions
docker exec mongodb mongosh -u <username> -p <password> \
  --authenticationDatabase admin ai_service_db --quiet --eval '
var test = db.online_tests.findOne({_id: ObjectId("test-id-here")});
if (test) {
    print("Title: " + test.title);
    print("Questions: " + test.questions.length);
    test.questions.forEach((q, i) => {
        print((i+1) + ". " + q.question_type + " - " + q.question_text.substring(0, 50));
    });
}
'
```

---

## 🔍 Debugging & Logging

### View Application Logs

```bash
# Real-time logs
docker logs ai-chatbot-rag -f

# Last 100 lines
docker logs ai-chatbot-rag --tail 100

# Search for specific test
docker logs ai-chatbot-rag 2>&1 | grep "test-id-here"

# Filter by timestamp
docker logs ai-chatbot-rag 2>&1 | grep "2025-12-14 19:43"
```

### Log Patterns to Search

```bash
# Test generation
grep "🎯 Starting test generation"
grep "✅ Generated.*questions"
grep "💾 Saved full response"

# Test retrieval
grep "📖 Get test request"
grep "🔑 Owner view"
grep "👥 Shared view"

# Errors
grep "❌"
grep "ERROR"
grep "Exception"
```

### Check Gemini Response Files

```bash
# List saved responses
docker exec ai-chatbot-rag ls -lth /tmp/gemini_test_responses/

# View a response
docker exec ai-chatbot-rag cat /tmp/gemini_test_responses/test_gen_*.json

# Copy response file to local machine
docker cp ai-chatbot-rag:/tmp/gemini_test_responses/test_gen_20251214_194300.json ./
```

---

## 📊 API Endpoints Reference

### Test Creation
- `POST /api/v1/tests/generate` - Generate test from PDF
- `POST /api/v1/tests/generate/general` - Generate general knowledge test
- `GET /api/v1/tests/{test_id}/status` - Check generation status

### Test Taking
- `GET /api/v1/tests/{test_id}` - Get test (owner/shared/public view)
- `POST /api/v1/tests/{test_id}/start` - Start test session
- `POST /api/v1/tests/{test_id}/submit` - Submit test answers

### Test Results
- `GET /api/v1/me/submissions` - List user submissions
- `GET /api/v1/me/submissions/{submission_id}` - Get submission results

### Test Grading
- `GET /api/v1/grading/tests/{test_id}/queue` - Get grading queue
- `POST /api/v1/grading/submissions/{submission_id}/grade-essay` - Grade single essay
- `POST /api/v1/grading/submissions/{submission_id}/grade-all-essays` - Grade all essays

### Marketplace
- `GET /api/marketplace/tests` - Browse marketplace tests
- `GET /api/marketplace/tests/{test_id}` - Get marketplace test details
- `POST /api/marketplace/tests/{test_id}/purchase` - Purchase test

---

## 🔐 Authentication

### Firebase Authentication

All API requests require Firebase ID token in header:

```
Authorization: Bearer <firebase-id-token>
```

### User Context

Backend extracts user info from token:
- `uid`: Firebase user ID (used as `creator_id`, `user_id`)
- `email`: User email
- `name`: Display name

---

## 🐛 Common Issues & Solutions

### Issue: Test not found
**Solution:** Use ObjectId format in MongoDB queries
```javascript
// ✅ Correct
db.online_tests.findOne({_id: ObjectId("693eb0d83456aa028c4ee7fe")})

// ❌ Wrong
db.online_tests.findOne({_id: "693eb0d83456aa028c4ee7fe"})
```

### Issue: correct_answers empty
**Check:**
1. View test in database: `db.online_tests.findOne({_id: ObjectId("test-id")})`
2. Check if questions have `correct_answers` field
3. Verify normalization didn't clear it (fixed in commit 7757d9c)

### Issue: Frontend not showing results
**Check:**
1. User access type (owner/shared/public)
2. GET /api/v1/tests/{test_id} response includes questions
3. Questions include correct_answers for owner view

### Issue: Gemini response files missing
**Check:**
1. Test was created AFTER deployment of logging code
2. Directory exists: `docker exec ai-chatbot-rag ls /tmp/gemini_test_responses/`
3. Permissions: Container has write access to /tmp/

---

## 📝 Code Conventions

### Question Types

All question types use unified `correct_answers` field:

| Type | correct_answers Format |
|------|----------------------|
| `mcq` | `["A"]` |
| `mcq_multiple` | `["A", "C"]` |
| `matching` | `[{"left_key": "1", "right_key": "A"}]` |
| `completion` | `[{"blank_key": "1", "answers": ["text"]}]` |
| `sentence_completion` | `["word", "variation"]` |
| `short_answer` | `["answer", "variation"]` |

### Legacy Fields (Deprecated)

- ❌ `correct_answer_key` (single MCQ)
- ❌ `correct_answer_keys` (multiple MCQ)
- ❌ `correct_matches` (matching)

**Note:** Backend still accepts these for backward compatibility but converts to `correct_answers`.

---

## 🔄 State Machine

### Test Status Flow

```
creating → generating → ready
         ↓
       failed
```

### Grading Status Flow

```
auto_graded (MCQ only)
     ↓
pending_grading (has essays)
     ↓
partially_graded (some graded)
     ↓
fully_graded (all graded)
```

---

## 📚 Related Documentation

- **Question Types:** See `QUESTION_TYPES_JSON_SCHEMA.md`
- **API Docs:** Available at `/docs` endpoint
- **Environment:** See `.env` file (not in repo)

---

## 🆘 Emergency Rollback

If deployment fails:

```bash
# 1. Check previous image
docker images | grep wordai-aiservice

# 2. Stop current container
docker stop ai-chatbot-rag
docker rm ai-chatbot-rag

# 3. Start with previous image
docker run -d --name ai-chatbot-rag \
  --network wordai-network \
  -p 8000:8000 \
  lekompozer/wordai-aiservice:<previous-commit-hash>

# 4. Verify health
curl http://localhost:8000/health
```

---

## 📞 Key Commands Cheat Sheet

```bash
# Quick health check
curl http://localhost:8000/health

# Check container status
docker ps | grep ai-chatbot-rag

# Count tests in database
docker exec mongodb mongosh -u <user> -p <pass> \
  --authenticationDatabase admin ai_service_db --quiet --eval \
  'db.online_tests.countDocuments()'

# Find test by title
docker exec mongodb mongosh -u <user> -p <pass> \
  --authenticationDatabase admin ai_service_db --quiet --eval \
  'db.online_tests.find({title: {$regex: "search-term", $options: "i"}}).limit(5).forEach(t => print(t._id + " - " + t.title))'

# Check recent submissions
docker exec mongodb mongosh -u <user> -p <pass> \
  --authenticationDatabase admin ai_service_db --quiet --eval \
  'db.test_submissions.find().sort({submitted_at: -1}).limit(5).forEach(s => print(s._id + " - " + s.test_id + " - " + s.score))'
```

---

**End of System Reference**
