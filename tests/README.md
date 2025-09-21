# 🧪 Admin Workflow Testing Guide

Comprehensive testing suite for the AI Service Admin API workflow, including real R2 upload integration.

## 📋 Overview

This testing suite validates the complete data flow:
```
Backend → AI Service → R2 Storage → AI Processing → Qdrant Vector DB → Search
```

## 🔧 Test Files

### 1. `test_complete_admin_workflow.py`
- **Purpose**: Complete workflow test with mock R2 uploads
- **Coverage**: All admin endpoints, file processing, Qdrant integration
- **Use Case**: Development and CI/CD testing

### 2. `test_real_r2_workflow.py`
- **Purpose**: Real R2 upload workflow test
- **Coverage**: Actual R2 file upload, real file processing
- **Use Case**: Integration testing with real cloud storage

### 3. `run_admin_tests.sh`
- **Purpose**: Interactive test runner script
- **Features**: Dependency checking, server validation, test selection

## 🚀 Quick Start

### Prerequisites
1. **Server Running**: AI Service must be running on `http://localhost:8000`
2. **Environment**: `.env` file with R2 credentials configured
3. **Dependencies**: `httpx`, `boto3`, `python-dotenv`

### Run Tests

#### Option 1: Interactive Runner (Recommended)
```bash
./run_admin_tests.sh
```

#### Option 2: Direct Python Execution
```bash
# Complete workflow test (mock R2)
python tests/test_complete_admin_workflow.py

# Real R2 upload test
python tests/test_real_r2_workflow.py
```

## 📊 Test Coverage

### Company Management
- ✅ Company registration
- ✅ Company basic info update (matching Backend spec)
- ✅ Company deletion

### File Management
- ✅ File upload with AI processing
- ✅ Document chunking and Qdrant storage
- ✅ File metadata handling

### Products & Services
- ✅ CSV extraction with industry templates
- ✅ Structured data extraction
- ✅ Products/Services CRUD operations

### Data Flow
- ✅ R2 upload integration
- ✅ AI provider selection (ChatGPT Vision/Gemini)
- ✅ Background Qdrant processing
- ✅ Search and retrieval

## 🔍 Test Data

### Test Company
```json
{
  "company_id": "golden-dragon-test-2025",
  "company_name": "Golden Dragon Restaurant Test",
  "industry": "RESTAURANT"
}
```

### Test Files Generated
1. **Company Info** (`company_info.txt`): Restaurant details, contact info, services
2. **Products Menu** (`menu_products.csv`): Vietnamese restaurant menu with prices

### Backend Spec Compliance
- ✅ Company metadata structure matches Backend-AI-Data-Document.md
- ✅ File upload data format matches specification
- ✅ Products/Services extraction follows industry templates

## 📈 Expected Results

### Successful Test Output
```
🎯 FINAL TEST RESULTS
==============================
company_registration      ✅ PASS
company_update           ✅ PASS
file_upload              ✅ PASS
products_extraction      ✅ PASS
qdrant_search           ✅ PASS
cleanup                 ✅ PASS

Overall: 6/6 tests passed
🎉 ALL TESTS PASSED! Admin workflow is working correctly.
```

## 🛠️ Configuration

### Required Environment Variables (.env)
```bash
# API Configuration
INTERNAL_API_KEY=agent8x-backend-secret-key-2025

# R2 Storage Configuration
R2_ACCESS_KEY_ID=your_access_key
R2_SECRET_ACCESS_KEY=your_secret_key
R2_ENDPOINT=https://your-account.r2.cloudflarestorage.com
R2_BUCKET_NAME=your_bucket
R2_PUBLIC_URL=https://your-domain.com
R2_REGION=auto

# Qdrant Configuration
QDRANT_URL=https://your-qdrant-instance.cloud.qdrant.io
QDRANT_API_KEY=your_qdrant_api_key

# AI Provider Keys
DEEPSEEK_API_KEY=your_deepseek_key
CHATGPT_API_KEY=your_chatgpt_key
GEMINI_API_KEY=your_gemini_key
```

## 🔧 Troubleshooting

### Common Issues

#### 1. Server Not Running
```bash
❌ AI Service is not running!
```
**Solution**: Start the server:
```bash
python -m uvicorn src.app:create_app --host 0.0.0.0 --port 8000
```

#### 2. Missing Dependencies
```bash
❌ Missing dependencies
```
**Solution**: Install required packages:
```bash
pip install httpx boto3 python-dotenv
```

#### 3. R2 Configuration Error
```bash
❌ Missing R2 configuration: ['R2_ACCESS_KEY_ID']
```
**Solution**: Check `.env` file has all required R2 credentials

#### 4. API Key Authentication
```bash
❌ Registration failed: 401
```
**Solution**: Verify `INTERNAL_API_KEY` in `.env` matches server configuration

### Debug Mode
Enable verbose logging by modifying test files:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📝 Test Scenarios

### Scenario 1: Restaurant Chain Setup
1. Register restaurant company
2. Upload company information document
3. Upload menu CSV with products
4. Extract products with AI
5. Search for specific menu items
6. Verify Qdrant storage

### Scenario 2: Real Production Flow
1. Upload actual files to R2
2. Process with appropriate AI providers
3. Store vectors in Qdrant
4. Test search functionality
5. Clean up test data

## 🎯 Success Criteria

### Company Management
- Company registration creates Qdrant collection
- Basic info update preserves all metadata fields
- Deletion removes all associated data

### File Processing
- Files upload successfully to R2
- AI processing extracts content correctly
- Content is chunked and stored in Qdrant
- Background tasks complete without errors

### Products Extraction
- CSV files are parsed correctly
- Industry templates are applied
- Structured data is extracted
- Products are searchable in database

### Data Integrity
- All uploaded data is retrievable
- Search functionality works
- No data loss during processing
- Cleanup removes all test data

## 📞 Support

For issues or questions about the testing suite:
1. Check server logs for detailed error messages
2. Verify all environment variables are set
3. Ensure Qdrant and R2 services are accessible
4. Review API documentation at `/docs` endpoint

## 🔄 Continuous Integration

These tests can be integrated into CI/CD pipelines:
```yaml
# Example GitHub Actions step
- name: Run Admin Workflow Tests
  run: |
    python tests/test_complete_admin_workflow.py
  env:
    INTERNAL_API_KEY: ${{ secrets.INTERNAL_API_KEY }}
    QDRANT_URL: ${{ secrets.QDRANT_URL }}
    QDRANT_API_KEY: ${{ secrets.QDRANT_API_KEY }}
```
