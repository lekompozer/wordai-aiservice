# Test Statistics API - Technical Specifications

**Version:** 1.0
**Base URL:** `/api/v1/tests/statistics`
**Authentication:** Not required (public statistics)

---

## Overview

The Test Statistics API provides analytics and reporting endpoints for online tests and user activities. It enables frontend applications to display popular tests and active users based on submission data.

**Key Features:**
- Get most popular tests by submission count
- Get most active users by test submission count
- Filter by time range and test category
- Aggregate statistics including averages and counts

---

## Endpoints

### 1. GET /popular

Get most popular tests ordered by submission count.

#### Endpoint
```
GET /api/v1/tests/statistics/popular
```

#### Description
Returns a list of tests that have been taken the most, with submission counts. Tests are ordered by `submission_count` in descending order. Can be filtered by test category and time range.

#### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `limit` | integer | No | 10 | Maximum number of tests to return. Min: 1, Max: 100 |
| `test_category` | string | No | - | Filter by test category. Values: `academic`, `diagnostic` |
| `days` | integer | No | - | Only count submissions from last N days. Min: 1, Max: 365 |

#### Response Schema

**Success Response (200 OK)**

```json
{
  "success": boolean,
  "total_tests_with_submissions": integer,
  "popular_tests": [
    {
      "test_id": string,
      "test_title": string,
      "submission_count": integer,
      "test_category": string | null,
      "creator_id": string | null
    }
  ]
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Always `true` for successful requests |
| `total_tests_with_submissions` | integer | Total number of unique tests that have at least one submission (respects filters) |
| `popular_tests` | array | Array of popular test objects, ordered by `submission_count` descending |
| `popular_tests[].test_id` | string | MongoDB ObjectId of the test |
| `popular_tests[].test_title` | string | Title of the test |
| `popular_tests[].submission_count` | integer | Number of times this test was submitted by users |
| `popular_tests[].test_category` | string \| null | Test category: `academic` or `diagnostic`, or `null` if not set |
| `popular_tests[].creator_id` | string \| null | Firebase UID of the test creator, or `null` if not available |

#### Example Response

```json
{
  "success": true,
  "total_tests_with_submissions": 25,
  "popular_tests": [
    {
      "test_id": "692c0ce9eabefddaa798357c",
      "test_title": "Kiểm tra IQ tổng quát cho mọi lứa tuổi",
      "submission_count": 15,
      "test_category": "academic",
      "creator_id": "17BeaeikPBQYk8OWeDUkqm0Ov8e2"
    },
    {
      "test_id": "69293c35d7330f550720a445",
      "test_title": "Test tiếng Anh cơ bản",
      "submission_count": 12,
      "test_category": "academic",
      "creator_id": "KkAfCdSeUOduPYNCRfbvwZbj5Oz1"
    }
  ]
}
```

#### Error Responses

**400 Bad Request** - Invalid query parameters
```json
{
  "detail": "test_category must be 'academic' or 'diagnostic'"
}
```

**500 Internal Server Error** - Server error
```json
{
  "detail": "Failed to retrieve statistics: <error_message>"
}
```

---

### 2. GET /active-users

Get most active users ordered by submission count.

#### Endpoint
```
GET /api/v1/tests/statistics/active-users
```

#### Description
Returns a list of users who have submitted the most tests, with their statistics including submission count, average score, and pass/fail counts. Users are ordered by `submission_count` in descending order.

#### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `limit` | integer | No | 10 | Maximum number of users to return. Min: 1, Max: 100 |
| `days` | integer | No | - | Only count submissions from last N days. Min: 1, Max: 365 |
| `min_submissions` | integer | No | 1 | Minimum number of submissions required. Min: 1 |

#### Response Schema

**Success Response (200 OK)**

```json
{
  "success": boolean,
  "total_active_users": integer,
  "active_users": [
    {
      "user_id": string,
      "user_name": string | null,
      "submission_count": integer,
      "average_score": number | null,
      "passed_count": integer,
      "failed_count": integer
    }
  ]
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Always `true` for successful requests |
| `total_active_users` | integer | Total number of users who meet the criteria (respects filters and min_submissions) |
| `active_users` | array | Array of active user objects, ordered by `submission_count` descending |
| `active_users[].user_id` | string | Firebase UID of the user |
| `active_users[].user_name` | string \| null | Display name of the user, or `null` if not available |
| `active_users[].submission_count` | integer | Total number of test submissions by this user |
| `active_users[].average_score` | number \| null | Average score percentage across all graded submissions (0-100), rounded to 2 decimal places. `null` if no graded submissions |
| `active_users[].passed_count` | integer | Number of tests passed (`is_passed = true`) |
| `active_users[].failed_count` | integer | Number of tests failed (`is_passed = false`) |

#### Example Response

```json
{
  "success": true,
  "total_active_users": 50,
  "active_users": [
    {
      "user_id": "17BeaeikPBQYk8OWeDUkqm0Ov8e2",
      "user_name": "Nguyen Van A",
      "submission_count": 10,
      "average_score": 85.5,
      "passed_count": 8,
      "failed_count": 2
    },
    {
      "user_id": "KkAfCdSeUOduPYNCRfbvwZbj5Oz1",
      "user_name": null,
      "submission_count": 7,
      "average_score": 72.3,
      "passed_count": 5,
      "failed_count": 2
    }
  ]
}
```

#### Error Responses

**500 Internal Server Error** - Server error
```json
{
  "detail": "Failed to retrieve statistics: <error_message>"
}
```

---

## Data Source

Both endpoints aggregate data from the `test_submissions` collection in MongoDB.

### Required Fields in test_submissions Collection

For accurate statistics, submissions should contain:
- `test_id` - MongoDB ObjectId reference to online_tests collection
- `test_title` - String, test title (for display without joining)
- `test_category` - String, "academic" or "diagnostic"
- `user_id` - String, Firebase UID
- `user_name` - String or null, user display name
- `score_percentage` - Number or null, score from 0-100
- `is_passed` - Boolean, whether the test was passed
- `submitted_at` - DateTime, when the test was submitted

---

## Implementation Notes

### Data Consistency
- If `test_title` is `null` in submissions, the endpoint will attempt to fetch it from the `online_tests` collection
- If `user_name` is `null`, it will display as `null` in the response (not fallback to users collection)
- Missing or `null` fields are handled gracefully

### Performance Considerations
- Both endpoints use MongoDB aggregation pipelines for efficient data processing
- Indexes recommended:
  - `test_submissions.test_id` (for grouping)
  - `test_submissions.user_id` (for grouping)
  - `test_submissions.submitted_at` (for time range filtering)
  - `test_submissions.test_category` (for category filtering)

### Caching Recommendations
- Consider caching responses for 5-15 minutes on the frontend
- Statistics data changes relatively slowly
- Use cache invalidation when new submissions are created

---

## Frontend Integration Guidelines

### Displaying "Tests được làm nhiều nhất"
1. Call `GET /api/v1/tests/statistics/popular?limit=10`
2. Display `popular_tests` array in a table or list
3. Show `test_title` and `submission_count`
4. Handle case where `popular_tests` is empty (show "Chưa có dữ liệu")

### Displaying "Người dùng tích cực nhất"
1. Call `GET /api/v1/tests/statistics/active-users?limit=10`
2. Display `active_users` array in a table or list
3. Show `user_name` (or "Anonymous" if null) and `submission_count`
4. Optionally show `average_score`, `passed_count`, `failed_count`
5. Handle case where `active_users` is empty (show "Chưa có dữ liệu")

### Error Handling
- Check `success` field in response
- If response is not 200 OK, show error message from `detail` field
- Show user-friendly message if data is empty: "Chưa có dữ liệu"

### Example Scenarios

**Scenario 1: New system with no submissions**
- Both endpoints return empty arrays: `popular_tests: []`, `active_users: []`
- `total_tests_with_submissions: 0`, `total_active_users: 0`
- Frontend should display: "Chưa có dữ liệu"

**Scenario 2: Filter by last 7 days**
```
GET /api/v1/tests/statistics/popular?days=7&limit=5
```
Returns top 5 most popular tests from the last 7 days only.

**Scenario 3: Only academic tests**
```
GET /api/v1/tests/statistics/popular?test_category=academic&limit=20
```
Returns top 20 most popular academic tests (excludes diagnostic tests).

**Scenario 4: Top performers (min 5 submissions)**
```
GET /api/v1/tests/statistics/active-users?min_submissions=5&limit=10
```
Returns top 10 users who have submitted at least 5 tests.

---

## Version History

- **v1.0** (2025-11-30) - Initial release
  - Added `/popular` endpoint
  - Added `/active-users` endpoint
