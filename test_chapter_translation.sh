#!/bin/bash

# Test Chapter Translation Endpoint
# Tests the new async chapter translation endpoint with Redis queue

set -e

echo "🧪 Testing Chapter Translation Async Endpoint"
echo "=============================================="

# Configuration
BASE_URL="http://localhost:8001"
TOKEN="${FIREBASE_TOKEN:-your_token_here}"
BOOK_ID="${TEST_BOOK_ID:-your_book_id}"
CHAPTER_ID="${TEST_CHAPTER_ID:-your_chapter_id}"

if [ "$TOKEN" = "your_token_here" ]; then
    echo "❌ Error: Set environment variables:"
    echo "   export FIREBASE_TOKEN='your_firebase_token'"
    echo "   export TEST_BOOK_ID='your_book_id'"
    echo "   export TEST_CHAPTER_ID='your_chapter_id'"
    exit 1
fi

if [ "$BOOK_ID" = "your_book_id" ] || [ "$CHAPTER_ID" = "your_chapter_id" ]; then
    echo "❌ Error: Set TEST_BOOK_ID and TEST_CHAPTER_ID"
    exit 1
fi

echo ""
echo "📝 Test Configuration:"
echo "  Book ID: $BOOK_ID"
echo "  Chapter ID: $CHAPTER_ID"
echo ""

echo "📝 Test 1: Submit chapter translation job (without new chapter)"
echo "---------------------------------------------------------------"

RESPONSE=$(curl -s -X POST "$BASE_URL/api/books/$BOOK_ID/chapters/$CHAPTER_ID/translate/async" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
        "source_language": "vi",
        "target_language": "en",
        "create_new_chapter": false
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

MAX_ATTEMPTS=60  # 60 * 5s = 300s = 5 minutes
ATTEMPT=0

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    echo -n "Polling ($ATTEMPT/$MAX_ATTEMPTS)... "

    STATUS_RESPONSE=$(curl -s -X GET "$BASE_URL/api/books/$BOOK_ID/chapters/translation-jobs/$JOB_ID" \
        -H "Authorization: Bearer $TOKEN")

    STATUS=$(echo $STATUS_RESPONSE | grep -o '"status":"[^"]*"' | cut -d'"' -f4)

    echo "Status: $STATUS"

    if [ "$STATUS" = "completed" ]; then
        echo ""
        echo "✅ Job completed successfully!"
        echo "Response: $STATUS_RESPONSE"

        # Check if translated_html exists
        if echo "$STATUS_RESPONSE" | grep -q '"translated_html"'; then
            echo "✅ Translated HTML present"
        else
            echo "❌ Translated HTML missing"
            exit 1
        fi

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
echo "📝 Test 3: Submit translation job WITH new chapter creation"
echo "------------------------------------------------------------"

RESPONSE2=$(curl -s -X POST "$BASE_URL/api/books/$BOOK_ID/chapters/$CHAPTER_ID/translate/async" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
        "source_language": "vi",
        "target_language": "en",
        "create_new_chapter": true,
        "new_chapter_title_suffix": " (English Version)"
    }')

echo "Response: $RESPONSE2"

JOB_ID2=$(echo $RESPONSE2 | grep -o '"job_id":"[^"]*"' | cut -d'"' -f4)

if [ -z "$JOB_ID2" ]; then
    echo "❌ Failed to get job_id for second test"
    exit 1
fi

echo "✅ Job created: $JOB_ID2"

echo ""
echo "🔄 Test 4: Poll second job status (with new chapter creation)"
echo "--------------------------------------------------------------"

ATTEMPT=0

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    echo -n "Polling ($ATTEMPT/$MAX_ATTEMPTS)... "

    STATUS_RESPONSE2=$(curl -s -X GET "$BASE_URL/api/books/$BOOK_ID/chapters/translation-jobs/$JOB_ID2" \
        -H "Authorization: Bearer $TOKEN")

    STATUS=$(echo $STATUS_RESPONSE2 | grep -o '"status":"[^"]*"' | cut -d'"' -f4)

    echo "Status: $STATUS"

    if [ "$STATUS" = "completed" ]; then
        echo ""
        echo "✅ Job completed successfully!"
        echo "Response: $STATUS_RESPONSE2"

        # Check for new chapter fields
        if echo "$STATUS_RESPONSE2" | grep -q '"new_chapter_id"'; then
            echo "✅ New chapter ID present"
        else
            echo "❌ New chapter ID missing"
            exit 1
        fi

        if echo "$STATUS_RESPONSE2" | grep -q '"new_chapter_title"'; then
            echo "✅ New chapter title present"
        else
            echo "❌ New chapter title missing"
            exit 1
        fi

        if echo "$STATUS_RESPONSE2" | grep -q '"new_chapter_slug"'; then
            echo "✅ New chapter slug present"
        else
            echo "❌ New chapter slug missing"
            exit 1
        fi

        break
    elif [ "$STATUS" = "failed" ]; then
        echo ""
        echo "❌ Job failed"
        echo "Response: $STATUS_RESPONSE2"
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
echo "  - Job submission (translate only): ✅"
echo "  - Job processing (translate only): ✅"
echo "  - Job submission (create new chapter): ✅"
echo "  - Job processing (create new chapter): ✅"
echo "  - New chapter creation: ✅"
echo ""
echo "💡 Note: You can verify new chapter in MongoDB:"
echo "   db.book_chapters.find({book_id: '$BOOK_ID'}).sort({created_at: -1}).limit(1)"
