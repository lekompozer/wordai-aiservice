#!/bin/bash
# setup-environment.sh - Tạo cấu trúc thư mục cho production và staging

echo "==== Bắt đầu thiết lập môi trường AI Chatbot RAG ===="
ROOT_DIR=$(pwd)
echo "Thư mục gốc: $ROOT_DIR"

# ===== BƯỚC 2: Tạo cấu trúc thư mục và Docker Compose =====
echo "===== BƯỚC 2: Tạo cấu trúc thư mục và Docker Compose ====="

# Tạo thư mục config
echo "Tạo thư mục config..."
mkdir -p config/production
mkdir -p config/staging
mkdir -p config/development

# Tạo thư mục docker
echo "Tạo thư mục docker..."
mkdir -p docker/production
mkdir -p docker/staging

# Tạo thư mục data và logs
echo "Tạo thư mục data và logs..."
mkdir -p data
mkdir -p data-staging
mkdir -p logs/production
mkdir -p logs/staging

# Tạo file config/__init__.py
echo "Tạo file config/__init__.py..."
cat > config/__init__.py << 'EOF'
import os

# Sử dụng biến môi trường để xác định môi trường
environment = os.getenv("ENVIRONMENT", "development")

if environment == "production":
    from config.production.config import *
    print(f"Loaded PRODUCTION configuration")
elif environment == "staging":
    from config.staging.config import *
    print(f"Loaded STAGING configuration")
else:
    # Fallback cho local development
    try:
        from config.development.config import *
        print(f"Loaded DEVELOPMENT configuration")
    except ImportError:
        print("No specific configuration found, using defaults")
        # Định nghĩa một số config mặc định
        DEBUG = True
        USE_MOCK_EMBEDDING = False
        LOG_LEVEL = "DEBUG"
EOF

# Tạo file config cho production
echo "Tạo file config/production/config.py..."
cat > config/production/config.py << 'EOF'
# Production specific settings
DEBUG = False
USE_MOCK_EMBEDDING = False
LOG_LEVEL = "INFO"
MEMORY_THRESHOLD_MB = 6000  # 6GB threshold for switching to mock embeddings
REQUEST_TIMEOUT = 60  # seconds
DEEPSEEK_API_TIMEOUT = 90  # seconds
MAX_DOCUMENTS = 10000  # Maximum number of documents in vector store
EOF

# Tạo file config cho staging
echo "Tạo file config/staging/config.py..."
cat > config/staging/config.py << 'EOF'
# Staging specific settings
DEBUG = True
USE_MOCK_EMBEDDING = True  # Use mock embeddings to save resources
LOG_LEVEL = "DEBUG"
MEMORY_THRESHOLD_MB = 1500  # Lower threshold for staging
REQUEST_TIMEOUT = 30  # seconds
DEEPSEEK_API_TIMEOUT = 60  # seconds
MAX_DOCUMENTS = 1000  # Limit number of documents for staging
EOF

# Tạo file config cho development
echo "Tạo file config/development/config.py..."
cat > config/development/config.py << 'EOF'
# Development specific settings
DEBUG = True
USE_MOCK_EMBEDDING = True  # Default to mock for development
LOG_LEVEL = "DEBUG"
MEMORY_THRESHOLD_MB = 1000
REQUEST_TIMEOUT = 30  # seconds
DEEPSEEK_API_TIMEOUT = 60  # seconds
MAX_DOCUMENTS = 100  # Small limit for development
EOF

# Tạo docker-compose.yml chính
echo "Tạo docker-compose.yml..."
cat > docker-compose.yml << 'EOF'
version: '3'

services:
  ai-service:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "${PORT:-8000}:8000"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    environment:
      - PYTHONPATH=/app
      - PYTHONUNBUFFERED=1
      - ENVIRONMENT=${ENVIRONMENT:-production}
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
      - USE_MOCK_EMBEDDING=${USE_MOCK_EMBEDDING:-false}
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/ping"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    deploy:
      resources:
        limits:
          memory: ${MEMORY_LIMIT:-6G}
          cpus: ${CPU_LIMIT:-1}
EOF

# Tạo docker-compose cho production
echo "Tạo docker/production/docker-compose.yml..."
cat > docker/production/docker-compose.yml << 'EOF'
version: '3'

services:
  ai-service:
    image: ${DOCKER_REGISTRY:-ai-chatbot-rag}:production-${TAG:-latest}
    ports:
      - "8000:8000"
    volumes:
      - ../../data:/app/data
      - ../../logs/production:/app/logs
    environment:
      - ENVIRONMENT=production
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
      - USE_MOCK_EMBEDDING=false
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 6G
          cpus: "2"
EOF

# Tạo docker-compose cho staging
echo "Tạo docker/staging/docker-compose.yml..."
cat > docker/staging/docker-compose.yml << 'EOF'
version: '3'

services:
  ai-service:
    image: ${DOCKER_REGISTRY:-ai-chatbot-rag}:staging-${TAG:-latest}
    ports:
      - "8001:8000"  # Different port for staging
    volumes:
      - ../../data-staging:/app/data
      - ../../logs/staging:/app/logs
    environment:
      - ENVIRONMENT=staging
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY_STAGING}
      - USE_MOCK_EMBEDDING=true
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: "1"
EOF

# ===== BƯỚC 3: GitHub Actions Setup =====
echo "===== BƯỚC 3: GitHub Actions Setup ====="

# Tạo thư mục GitHub Actions
echo "Tạo thư mục .github/workflows..."
mkdir -p .github/workflows

# Tạo file GitHub Actions cho Production
echo "Tạo .github/workflows/deploy-production.yml..."
cat > .github/workflows/deploy-production.yml << 'EOF'
name: Deploy to Production

on:
  push:
    branches:
      - main

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v3
      
    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v1
    
    - name: Login to Docker Registry
      uses: docker/login-action@v1
      with:
        username: ${{ secrets.DOCKER_USERNAME }}
        password: ${{ secrets.DOCKER_PASSWORD }}
    
    - name: Build and push Docker image
      uses: docker/build-push-action@v2
      with:
        context: .
        push: true
        tags: |
          ${{ secrets.DOCKER_REGISTRY }}/ai-chatbot-rag:production-${{ github.sha }}
          ${{ secrets.DOCKER_REGISTRY }}/ai-chatbot-rag:production-latest
    
    - name: Deploy to Production Server
      uses: appleboy/ssh-action@master
      with:
        host: ${{ secrets.PRODUCTION_HOST }}
        username: ${{ secrets.SSH_USERNAME }}
        key: ${{ secrets.SSH_PRIVATE_KEY }}
        script: |
          cd /opt/ai-chatbot-rag
          echo "DEEPSEEK_API_KEY=${{ secrets.DEEPSEEK_API_KEY }}" > .env
          echo "TAG=${{ github.sha }}" >> .env
          echo "DOCKER_REGISTRY=${{ secrets.DOCKER_REGISTRY }}" >> .env
          docker-compose -f docker/production/docker-compose.yml pull
          docker-compose -f docker/production/docker-compose.yml down
          docker-compose -f docker/production/docker-compose.yml up -d
          docker image prune -af
EOF

# Tạo file GitHub Actions cho Staging
echo "Tạo .github/workflows/deploy-staging.yml..."
cat > .github/workflows/deploy-staging.yml << 'EOF'
name: Deploy to Staging

on:
  push:
    branches:
      - staging

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v3
      
    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v1
    
    - name: Login to Docker Registry
      uses: docker/login-action@v1
      with:
        username: ${{ secrets.DOCKER_USERNAME }}
        password: ${{ secrets.DOCKER_PASSWORD }}
    
    - name: Build and push Docker image
      uses: docker/build-push-action@v2
      with:
        context: .
        push: true
        tags: |
          ${{ secrets.DOCKER_REGISTRY }}/ai-chatbot-rag:staging-${{ github.sha }}
          ${{ secrets.DOCKER_REGISTRY }}/ai-chatbot-rag:staging-latest
    
    - name: Deploy to Staging Server
      uses: appleboy/ssh-action@master
      with:
        host: ${{ secrets.STAGING_HOST }}
        username: ${{ secrets.SSH_USERNAME }}
        key: ${{ secrets.SSH_PRIVATE_KEY }}
        script: |
          cd /opt/ai-chatbot-rag
          echo "DEEPSEEK_API_KEY=${{ secrets.DEEPSEEK_API_KEY_STAGING }}" > .env
          echo "TAG=${{ github.sha }}" >> .env
          echo "DOCKER_REGISTRY=${{ secrets.DOCKER_REGISTRY }}" >> .env
          docker-compose -f docker/staging/docker-compose.yml pull
          docker-compose -f docker/staging/docker-compose.yml down
          docker-compose -f docker/staging/docker-compose.yml up -d
          docker image prune -af
EOF

# Tạo file .env mẫu
echo "Tạo file .env.example..."
cat > .env.example << 'EOF'
# Environment (production, staging, development)
ENVIRONMENT=development

# API Keys
DEEPSEEK_API_KEY=your-deepseek-api-key-here

# Docker settings
PORT=8000
MEMORY_LIMIT=2G
CPU_LIMIT=1
USE_MOCK_EMBEDDING=true
EOF

# Cập nhật file .gitignore
echo "Cập nhật file .gitignore..."
cat >> .gitignore << 'EOF'
# Environment variables
.env

# Logs
logs/
*.log

# Data
data/
data-staging/

# Docker
.dockerignore
EOF

echo "==== Hoàn thành thiết lập môi trường AI Chatbot RAG ===="
echo "Cấu trúc thư mục đã được tạo và các file config đã được thiết lập."
echo ""
echo "Các bước tiếp theo:"
echo "1. Kiểm tra cấu trúc thư mục và nội dung file"
echo "2. Tạo file .env từ .env.example: cp .env.example .env"
echo "3. Điền thông tin API key vào .env"
echo "4. Chạy thử local với Docker: docker-compose up"
echo "5. Đẩy code lên GitHub, thiết lập GitHub Secrets cho CI/CD"