#!/bin/bash

# Admin Workflow Test Runner
# Runs comprehensive tests for the admin API workflow

echo "🧪 Admin Workflow Test Runner"
echo "==============================="

# Check if virtual environment is activated
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "⚠️  Warning: No virtual environment detected"
    echo "   Consider activating your Python virtual environment first"
    echo ""
fi

# Check if required dependencies are installed
echo "📦 Checking dependencies..."
python3 -c "import httpx, boto3" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Missing dependencies. Installing..."
    pip install httpx boto3 python-dotenv
    echo "✅ Dependencies installed"
else
    echo "✅ Dependencies OK"
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found!"
    echo "   Please create .env file with required R2 and API configuration"
    exit 1
fi

echo "✅ Configuration file found"

# Check if server is running
echo ""
echo "🔍 Checking if AI Service is running..."
curl -s http://localhost:8000/api/health > /dev/null
if [ $? -eq 0 ]; then
    echo "✅ AI Service is running at http://localhost:8000"
else
    echo "❌ AI Service is not running!"
    echo "   Please start the server with: python -m uvicorn src.app:create_app --host 0.0.0.0 --port 8000"
    echo "   Or run: python src/app.py"
    exit 1
fi

echo ""
echo "🚀 Starting Admin Workflow Tests..."
echo "==============================="

# Test options
echo "Select test to run:"
echo "1. Complete Admin Workflow Test (Mock R2)"
echo "2. Real R2 Upload Workflow Test"
echo "3. Both tests"
echo ""
read -p "Enter choice (1-3): " choice

case $choice in
    1)
        echo "🧪 Running Complete Admin Workflow Test..."
        python tests/test_complete_admin_workflow.py
        ;;
    2)
        echo "🧪 Running Real R2 Upload Workflow Test..."
        python tests/test_real_r2_workflow.py
        ;;
    3)
        echo "🧪 Running Both Tests..."
        echo ""
        echo "=== Test 1: Complete Admin Workflow ==="
        python tests/test_complete_admin_workflow.py
        echo ""
        echo "=== Test 2: Real R2 Upload Workflow ==="
        python tests/test_real_r2_workflow.py
        ;;
    *)
        echo "❌ Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "🏁 Test execution completed!"
echo ""
echo "📋 Test Summary:"
echo "- Complete Admin Workflow: Tests all admin endpoints with mock R2"
echo "- Real R2 Upload: Tests actual file upload to R2 with credentials from .env"
echo ""
echo "💡 Tips:"
echo "- Check logs above for detailed test results"
echo "- If tests fail, verify .env configuration and server status"
echo "- Use http://localhost:8000/docs to explore API endpoints"
