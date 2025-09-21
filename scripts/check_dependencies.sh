#!/bin/bash

# Script kiểm tra Docker build và dependencies
# Check Docker build and dependencies

echo "🚀 Starting Docker build and dependency check..."
echo "================================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    if [ $2 -eq 0 ]; then
        echo -e "${GREEN}✅ $1${NC}"
    else
        echo -e "${RED}❌ $1${NC}"
    fi
}

# Function to print info
print_info() {
    echo -e "${YELLOW}🔍 $1${NC}"
}

# Step 1: Build Docker image
print_info "Building Docker image..."
docker build -t ai-chatbot-test . --no-cache

if [ $? -eq 0 ]; then
    print_status "Docker build completed successfully" 0
else
    print_status "Docker build failed" 1
    exit 1
fi

# Step 2: Test PyMuPDF import in container
print_info "Testing PyMuPDF import in container..."
docker run --rm ai-chatbot-test python3 -c "
import sys
print('Python version:', sys.version)
print('---')
try:
    # import fitz  # PyMuPDF - REMOVED: Now using Gemini for PDF extraction
    print('❌ PyMuPDF has been removed from this project')
    print('✅ PDF extraction now uses Gemini AI instead')
    # print('PyMuPDF version:', fitz.version[0])  # REMOVED
    # print('PyMuPDF features:', fitz.version[1])  # REMOVED
except ImportError as e:
    print('❌ PyMuPDF import failed:', str(e))
    sys.exit(1)
except Exception as e:
    print('❌ Unexpected error:', str(e))
    sys.exit(1)
"

if [ $? -eq 0 ]; then
    print_status "PyMuPDF test passed" 0
else
    print_status "PyMuPDF test failed" 1
    exit 1
fi

# Step 3: Test other critical imports
print_info "Testing other critical imports..."
docker run --rm ai-chatbot-test python3 -c "
try:
    # Test các imports quan trọng khác
    import fastapi
    print('✅ FastAPI:', fastapi.__version__)
    
    import uvicorn
    print('✅ Uvicorn imported successfully')
    
    import qdrant_client
    print('✅ Qdrant client imported successfully')
    
    import openai
    print('✅ OpenAI:', openai.__version__)
    
    import sentence_transformers
    print('✅ Sentence Transformers imported successfully')
    
    import redis
    print('✅ Redis imported successfully')
    
    print('---')
    print('✅ All critical imports successful')
    
except ImportError as e:
    print('❌ Import failed:', str(e))
    import sys
    sys.exit(1)
"

if [ $? -eq 0 ]; then
    print_status "Critical imports test passed" 0
else
    print_status "Critical imports test failed" 1
    exit 1
fi

# Step 4: Check system libraries
print_info "Checking system libraries in container..."
docker run --rm ai-chatbot-test bash -c "
echo 'System libraries check:'
echo '---'

# Check libcrypt
find /usr/lib /lib -name 'libcrypt*' -type f 2>/dev/null | sort
echo '---'

# Check ldd for PyMuPDF
echo 'PyMuPDF dependencies:'
# PyMuPDF libcrypt check - REMOVED: Now using Gemini for PDF extraction
# python3 -c 'import fitz; print(fitz.__file__)' | xargs dirname | xargs find | grep '_fitz' | head -1 | xargs ldd 2>/dev/null | grep -E '(libcrypt|not found)' || echo 'No libcrypt dependencies found'
echo '---'

echo '✅ System libraries check completed'
"

if [ $? -eq 0 ]; then
    print_status "System libraries check passed" 0
else
    print_status "System libraries check failed" 1
fi

# Step 5: Test application startup (short test)
print_info "Testing application startup..."
docker run --rm -d --name ai-chatbot-startup-test -p 18000:8000 ai-chatbot-test

# Wait for startup
sleep 10

# Check if container is running
if docker ps | grep -q ai-chatbot-startup-test; then
    print_status "Container started successfully" 0
    
    # Test health endpoint
    print_info "Testing health endpoint..."
    if curl -f http://localhost:18000/health > /dev/null 2>&1; then
        print_status "Health endpoint responding" 0
    else
        print_status "Health endpoint not responding" 1
    fi
else
    print_status "Container failed to start" 1
    
    # Show logs
    print_info "Container logs:"
    docker logs ai-chatbot-startup-test
fi

# Cleanup
docker stop ai-chatbot-startup-test > /dev/null 2>&1
docker rm ai-chatbot-startup-test > /dev/null 2>&1

echo ""
echo "================================================"
echo -e "${GREEN}🎉 Docker dependency check completed!${NC}"
echo ""
echo "If all tests passed, your image should work in production."
echo ""
echo "To deploy:"
echo "1. Tag your image: docker tag ai-chatbot-test your-registry/ai-chatbot:latest"
echo "2. Push to registry: docker push your-registry/ai-chatbot:latest"
echo "3. Deploy to production"
echo ""
echo "To run locally:"
echo "docker run -p 8000:8000 ai-chatbot-test"
