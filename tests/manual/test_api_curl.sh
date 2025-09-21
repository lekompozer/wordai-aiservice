#!/bin/bash
"""
Test AI Extraction API với curl commands
"""

echo "🧪 TESTING AI EXTRACTION API WITH CURL"
echo "======================================"

SERVER_URL="http://localhost:8000"
HEALTH_URL="${SERVER_URL}/api/extract/health"
INFO_URL="${SERVER_URL}/api/extract/info"
EXTRACT_URL="${SERVER_URL}/api/extract/process"

echo "🌐 Server: $SERVER_URL"
echo "⏰ Started: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Test 1: Health Check
echo "🏥 TEST 1: Health Check"
echo "----------------------"
echo "📡 Calling: $HEALTH_URL"
curl -s -X GET "$HEALTH_URL" | jq . || echo "❌ Health check failed"
echo ""

# Test 2: Service Info
echo "ℹ️ TEST 2: Service Info"
echo "----------------------"
echo "📡 Calling: $INFO_URL"
curl -s -X GET "$INFO_URL" | jq . || echo "❌ Service info failed"
echo ""

# Test 3: Insurance Text Extraction (DeepSeek)
echo "🛡️ TEST 3: Insurance Text Extraction (DeepSeek)"
echo "----------------------------------------------"
echo "📡 Calling: $EXTRACT_URL"
echo "🤖 Expected AI: DeepSeek (text file)"

curl -s -X POST "$EXTRACT_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "r2_url": "https://agent8x.io.vn/company/5a44b799-4783-448f-b6a8-b9a51ed7ab76/files/Sa%CC%89n%20pha%CC%82%CC%89m%20Ba%CC%89o%20hie%CC%82%CC%89m%20AIA.txt",
    "industry": "insurance",
    "data_type": "products",
    "file_metadata": {
      "original_name": "Sản phẩm Bảo hiểm AIA.txt",
      "file_size": 50000,
      "file_type": "text/plain"
    },
    "company_info": {
      "name": "AIA Insurance",
      "industry": "insurance",
      "description": "Life and health insurance company"
    },
    "language": "vi"
  }' | jq . || echo "❌ Insurance extraction failed"

echo ""

# Test 4: Fashion CSV Extraction (DeepSeek)
echo "👗 TEST 4: Fashion CSV Extraction (DeepSeek)"
echo "-------------------------------------------"
echo "📡 Calling: $EXTRACT_URL"
echo "🤖 Expected AI: DeepSeek (CSV file)"

curl -s -X POST "$EXTRACT_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "r2_url": "https://agent8x.io.vn/companies/ivy-fashion-store/20250714_103032_ivy-fashion-products.csv",
    "industry": "fashion",
    "data_type": "products",
    "file_metadata": {
      "original_name": "20250714_103032_ivy-fashion-products.csv",
      "file_size": 25000,
      "file_type": "text/csv"
    },
    "company_info": {
      "name": "Ivy Fashion Store",
      "industry": "fashion",
      "description": "Fashion retail store"
    },
    "language": "vi"
  }' | jq . || echo "❌ Fashion extraction failed"

echo ""

# Test 5: Restaurant Image Extraction (ChatGPT Vision)
echo "🍜 TEST 5: Restaurant Image Extraction (ChatGPT Vision)"
echo "-----------------------------------------------------"
echo "📡 Calling: $EXTRACT_URL"
echo "🤖 Expected AI: ChatGPT Vision (image file)"

curl -s -X POST "$EXTRACT_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "r2_url": "https://agent8x.io.vn/companies/golden-dragon-restaurant/20250714_131220_golden-dragon-menu.jpg",
    "industry": "restaurant",
    "data_type": "products",
    "file_metadata": {
      "original_name": "20250714_131220_golden-dragon-menu.jpg",
      "file_size": 2048000,
      "file_type": "image/jpeg"
    },
    "company_info": {
      "name": "Golden Dragon Restaurant",
      "industry": "restaurant",
      "description": "Traditional Vietnamese restaurant"
    },
    "language": "vi"
  }' | jq . || echo "❌ Restaurant extraction failed"

echo ""
echo "🏁 API TESTS COMPLETED"
echo "🕒 Finished: $(date '+%Y-%m-%d %H:%M:%S')"
