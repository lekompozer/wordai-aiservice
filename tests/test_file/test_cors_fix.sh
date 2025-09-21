#!/bin/bash

# Script to test CORS after fix
# Test CORS sau khi fix

echo "🧪 Testing CORS Configuration After Fix..."
echo "=================================================="

# Test URL
TEST_URL="https://ai.wordai.pro/api/unified/chat-stream"
ORIGIN="https://admin.agent8x.io.vn"

echo "📡 Testing Preflight Request..."
echo "URL: $TEST_URL"
echo "Origin: $ORIGIN"
echo ""

# Test OPTIONS preflight request
echo "🔍 Preflight Request Headers:"
curl -X OPTIONS "$TEST_URL" \
  -H "Origin: $ORIGIN" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Content-Type" \
  -I -s | grep -i access-control | while read line; do
    echo "  $line"
    
    # Check for duplicates
    if echo "$line" | grep -q ",.*," ; then
        echo "  ❌ DUPLICATE DETECTED in: $line"
    fi
done

echo ""
echo "🔍 Complete Response Headers:"
curl -X OPTIONS "$TEST_URL" \
  -H "Origin: $ORIGIN" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Content-Type" \
  -I -s

echo ""
echo "🧪 Testing Actual POST Request..."

# Test actual POST request
curl -X POST "$TEST_URL" \
  -H "Origin: $ORIGIN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Test CORS",
    "user_info": {
      "user_id": "test_user",
      "source": "WEBSITE",
      "name": "Test User"
    },
    "industry": "BANKING",
    "language": "VIETNAMESE"
  }' \
  -I -s | head -20

echo ""
echo "✅ CORS Test Completed!"
echo ""
echo "🔍 What to look for:"
echo "  ✅ Single Access-Control-Allow-Origin header"
echo "  ✅ No comma-separated duplicate values" 
echo "  ✅ Status 200 for OPTIONS request"
echo "  ✅ Status 200 for POST request"
