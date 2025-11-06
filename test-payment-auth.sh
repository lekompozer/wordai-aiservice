#!/bin/bash
# Test Firebase Authentication on Production
# Get your Firebase token from browser console and test

echo "🧪 Testing Firebase Authentication for Payment Checkout"
echo "=================================================="
echo ""

# Step 1: Get Firebase token from browser
echo "📋 Step 1: Get Firebase ID Token"
echo "Run this in browser console (https://wordai.pro):"
echo ""
echo "firebase.auth().currentUser.getIdToken().then(token => {"
echo "  console.log('🔑 Your Firebase Token:');"
echo "  console.log(token);"
echo "  navigator.clipboard.writeText(token);"
echo "  console.log('✅ Token copied to clipboard!');"
echo "});"
echo ""
read -p "Press Enter after you copied the token... "

# Step 2: Prompt for token
echo ""
echo "📝 Step 2: Paste your Firebase token:"
read -r FIREBASE_TOKEN

if [ -z "$FIREBASE_TOKEN" ]; then
    echo "❌ No token provided. Exiting..."
    exit 1
fi

# Step 3: Test checkout API
echo ""
echo "🚀 Step 3: Testing /api/v1/payments/checkout..."
echo ""

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST https://ai.wordai.pro/api/v1/payments/checkout \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $FIREBASE_TOKEN" \
  -d '{
    "plan": "premium",
    "duration": "3_months"
  }')

HTTP_CODE=$(echo "$RESPONSE" | tail -n 1)
BODY=$(echo "$RESPONSE" | sed '$d')

echo "HTTP Status: $HTTP_CODE"
echo ""
echo "Response Body:"
echo "$BODY" | jq '.' 2>/dev/null || echo "$BODY"

echo ""
echo "=================================================="

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "201" ]; then
    echo "✅ SUCCESS! Checkout endpoint working with Firebase auth"
elif [ "$HTTP_CODE" = "401" ]; then
    echo "❌ 401 Unauthorized - Possible issues:"
    echo "   1. Firebase token expired (tokens expire after 1 hour)"
    echo "   2. Firebase Admin SDK not initialized in payment-service"
    echo "   3. firebase-credentials.json not mounted correctly"
    echo ""
    echo "🔍 Check payment-service logs:"
    echo "   ssh root@104.248.147.155 \"docker logs payment-service | tail -50\""
else
    echo "⚠️  Unexpected status code: $HTTP_CODE"
fi
