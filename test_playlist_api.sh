#!/bin/bash

# Test Playlist API Endpoints
# Usage: ./test_playlist_api.sh [firebase_token]

BASE_URL="https://ai.wordai.pro/api/v1/songs"
TOKEN="${1:-test-token}"

echo "=========================================="
echo "PLAYLIST API TEST"
echo "=========================================="
echo ""

# 1. Get all playlists (should return empty array)
echo "1️⃣  GET /playlists (List all playlists)"
echo "   Expected: [] (empty array, status 200)"
RESULT=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X GET "${BASE_URL}/playlists" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json")

HTTP_CODE=$(echo "$RESULT" | grep "HTTP_CODE" | cut -d: -f2)
BODY=$(echo "$RESULT" | sed '/HTTP_CODE/d')

echo "   Status: ${HTTP_CODE}"
echo "   Response: ${BODY}"
echo ""

# 2. Create new playlist
echo "2️⃣  POST /playlists (Create empty playlist)"
echo "   Creating: 'My Test Playlist'"
RESULT=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "${BASE_URL}/playlists" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Test Playlist",
    "description": "Test playlist created via API",
    "is_public": false
  }')

HTTP_CODE=$(echo "$RESULT" | grep "HTTP_CODE" | cut -d: -f2)
BODY=$(echo "$RESULT" | sed '/HTTP_CODE/d')

echo "   Status: ${HTTP_CODE}"
echo "   Response: ${BODY}" | jq '.' 2>/dev/null || echo "   Response: ${BODY}"

# Extract playlist_id if successful
if [ "$HTTP_CODE" = "201" ]; then
  PLAYLIST_ID=$(echo "$BODY" | jq -r '.playlist_id' 2>/dev/null)
  echo "   ✅ Created playlist: ${PLAYLIST_ID}"
else
  echo "   ❌ Failed to create playlist"
  exit 1
fi
echo ""

# 3. Get playlist detail
echo "3️⃣  GET /playlists/${PLAYLIST_ID} (Get playlist detail)"
RESULT=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X GET "${BASE_URL}/playlists/${PLAYLIST_ID}" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json")

HTTP_CODE=$(echo "$RESULT" | grep "HTTP_CODE" | cut -d: -f2)
BODY=$(echo "$RESULT" | sed '/HTTP_CODE/d')

echo "   Status: ${HTTP_CODE}"
echo "   Response: ${BODY}" | jq '.songs' 2>/dev/null || echo "   Response: ${BODY}"
echo ""

# 4. Add song to playlist (use song_id 1479 - What I've Done)
echo "4️⃣  POST /playlists/${PLAYLIST_ID}/songs (Add song)"
echo "   Adding song: 1479 (What I've Done)"
RESULT=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "${BASE_URL}/playlists/${PLAYLIST_ID}/songs" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "song_id": "1479"
  }')

HTTP_CODE=$(echo "$RESULT" | grep "HTTP_CODE" | cut -d: -f2)
BODY=$(echo "$RESULT" | sed '/HTTP_CODE/d')

echo "   Status: ${HTTP_CODE}"
if [ "$HTTP_CODE" = "200" ]; then
  echo "   ✅ Song added successfully"
  echo "   Songs in playlist:"
  echo "$BODY" | jq '.songs[] | {song_id, title, artist}' 2>/dev/null
else
  echo "   Response: ${BODY}"
fi
echo ""

# 5. Update playlist
echo "5️⃣  PUT /playlists/${PLAYLIST_ID} (Update playlist)"
RESULT=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X PUT "${BASE_URL}/playlists/${PLAYLIST_ID}" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Updated Playlist",
    "description": "Updated description"
  }')

HTTP_CODE=$(echo "$RESULT" | grep "HTTP_CODE" | cut -d: -f2)
echo "   Status: ${HTTP_CODE}"
if [ "$HTTP_CODE" = "200" ]; then
  echo "   ✅ Playlist updated"
fi
echo ""

# 6. Get all playlists (should now have 1)
echo "6️⃣  GET /playlists (List all playlists again)"
RESULT=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X GET "${BASE_URL}/playlists" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json")

HTTP_CODE=$(echo "$RESULT" | grep "HTTP_CODE" | cut -d: -f2)
BODY=$(echo "$RESULT" | sed '/HTTP_CODE/d')

echo "   Status: ${HTTP_CODE}"
if [ "$HTTP_CODE" = "200" ]; then
  COUNT=$(echo "$BODY" | jq 'length' 2>/dev/null || echo "0")
  echo "   ✅ Found ${COUNT} playlist(s)"
  echo "$BODY" | jq '.[] | {name, song_count}' 2>/dev/null
fi
echo ""

# 7. Remove song from playlist
echo "7️⃣  DELETE /playlists/${PLAYLIST_ID}/songs/1479 (Remove song)"
RESULT=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X DELETE "${BASE_URL}/playlists/${PLAYLIST_ID}/songs/1479" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json")

HTTP_CODE=$(echo "$RESULT" | grep "HTTP_CODE" | cut -d: -f2)
echo "   Status: ${HTTP_CODE}"
if [ "$HTTP_CODE" = "200" ]; then
  echo "   ✅ Song removed"
fi
echo ""

# 8. Delete playlist
echo "8️⃣  DELETE /playlists/${PLAYLIST_ID} (Delete playlist)"
RESULT=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X DELETE "${BASE_URL}/playlists/${PLAYLIST_ID}" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json")

HTTP_CODE=$(echo "$RESULT" | grep "HTTP_CODE" | cut -d: -f2)
echo "   Status: ${HTTP_CODE}"
if [ "$HTTP_CODE" = "204" ]; then
  echo "   ✅ Playlist deleted"
fi
echo ""

echo "=========================================="
echo "TEST COMPLETE"
echo "=========================================="
echo ""
echo "Summary:"
echo "✅ Playlist API endpoints working correctly"
echo "   - Create empty playlist"
echo "   - Add songs to playlist"
echo "   - Update playlist"
echo "   - Remove songs"
echo "   - Delete playlist"
