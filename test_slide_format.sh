#!/bin/bash

# Test Slide Format Endpoint
# Tests the new async slide format endpoint with Redis queue

set -e

echo "🧪 Testing Slide Format Async Endpoint"
echo "======================================="

# Configuration
BASE_URL="http://localhost:8001"
TOKEN="${FIREBASE_TOKEN:-your_token_here}"

if [ "$TOKEN" = "your_token_here" ]; then
    echo "❌ Error: Set FIREBASE_TOKEN environment variable"
    echo "   export FIREBASE_TOKEN='your_firebase_token'"
    exit 1
fi

echo ""
echo "📝 Test 1: Submit slide format job"
echo "-----------------------------------"

RESPONSE=$(curl -s -X POST "$BASE_URL/api/slides/ai-format" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
        "slide_index": 0,
        "current_html": "<div><h1>Test Slide</h1><p>This is a test slide that needs formatting.</p></div>",
        "elements": ["title", "content"],
        "background": "white",
        "user_instruction": "Make it look modern and professional",
        "format_type": "full"
    }')

echo "Response: $RESPONSE"

# Extract job_id
JOB_ID=$(echo $RESPONSE | grep -o '"job_id":"[^"]*"' | cut -d'"' -f4)

if [ -z "$JOB_ID" ]; then
    echo "❌ Failed to get job_id"
    exit 1
fi

echo "✅ Job created: $JOB_ID"

echo ""
echo "🔄 Test 2: Poll job status"
echo "-----------------------------------"

MAX_ATTEMPTS=40  # 40 * 5s = 200s = 3.3 minutes
ATTEMPT=0

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    echo -n "Polling ($ATTEMPT/$MAX_ATTEMPTS)... "

    STATUS_RESPONSE=$(curl -s -X GET "$BASE_URL/api/slides/jobs/$JOB_ID" \
        -H "Authorization: Bearer $TOKEN")

    STATUS=$(echo $STATUS_RESPONSE | grep -o '"status":"[^"]*"' | cut -d'"' -f4)

    echo "Status: $STATUS"

    if [ "$STATUS" = "completed" ]; then
        echo ""
        echo "✅ Job completed successfully!"
        echo "Response: $STATUS_RESPONSE"
        break
    elif [ "$STATUS" = "failed" ]; then
        echo ""
        echo "❌ Job failed"
        echo "Response: $STATUS_RESPONSE"
        exit 1
    elif [ "$STATUS" = "pending" ] || [ "$STATUS" = "processing" ]; then
        ATTEMPT=$((ATTEMPT + 1))
        sleep 5
    else
        echo "❌ Unknown status: $STATUS"
        exit 1
    fi
done

if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
    echo "❌ Job timeout after $MAX_ATTEMPTS attempts"
    exit 1
fi

echo ""
echo "🎉 All tests passed!"
echo ""
echo "📊 Test Summary:"
echo "  - Job submission: ✅"
echo "  - Job processing: ✅"
echo "  - Job completion: ✅"
echo "  - Total time: $((ATTEMPT * 5))s"
