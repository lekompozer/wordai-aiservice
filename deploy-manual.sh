#!/bin/bash

# Script deploy hoàn chỉnh cho AI Chatbot RAG với Docker Network và Authentication
set -e

# ==============================
# Configuration Flags
# ==============================
SKIP_DB_INIT=${SKIP_DB_INIT:-false}  # Set to 'true' to skip DB initialization (faster deploys)
SKIP_INDEX_FIX=${SKIP_INDEX_FIX:-false}  # Set to 'true' to skip index fixing

echo "🚀 Starting deployment with Docker Network and authentication..."
echo "ℹ️  This script will:"
echo "   • Update Docker containers (keep existing data)"
echo "   • Rebuild AI Chatbot with latest code"
echo "   • Verify database connections"
echo "   • Test service connectivity"
echo ""
echo "⚠️  NOTE: This script preserves existing data. Use deploy-fresh-start.sh for clean reset."
echo ""
echo "🔧 Optimization Flags:"
echo "   SKIP_DB_INIT=$SKIP_DB_INIT"
echo "   SKIP_INDEX_FIX=$SKIP_INDEX_FIX"
echo "   To skip initialization: export SKIP_DB_INIT=true && ./deploy-manual.sh"
echo ""

# Load environment variables từ .env
if [ -f .env ]; then
    source .env
    echo "✅ Loaded environment variables from .env"
else
    echo "❌ .env file not found!"
    exit 1
fi

# Định nghĩa tên network
NETWORK_NAME="ai-chatbot-network"

# 1. Tạo Docker Network nếu chưa tồn tại
echo "🌐 Creating Docker Network..."
if ! docker network ls | grep -q "$NETWORK_NAME"; then
    docker network create --driver bridge "$NETWORK_NAME"
    echo "✅ Created network: $NETWORK_NAME"
else
    echo "ℹ️  Network $NETWORK_NAME already exists"
fi

# 2. Deploy Redis với network và configuration tối ưu cho single-instance production
echo "📡 Deploying Redis with single-instance production configuration..."
docker stop redis-server 2>/dev/null || true
docker rm redis-server 2>/dev/null || true

# Create Redis config file to ensure single-instance mode
docker run -d \
  --name redis-server \
  --network "$NETWORK_NAME" \
  --restart unless-stopped \
  -p 6379:6379 \
  -v redis_data:/data \
  redis:7-alpine redis-server \
  --appendonly yes \
  --save 900 1 \
  --save 300 10 \
  --save 60 10000 \
  --tcp-keepalive 300 \
  --timeout 0 \
  --maxmemory-policy allkeys-lru \
  --replica-read-only no \
  --replica-serve-stale-data yes \
  --repl-diskless-sync no \
  --repl-diskless-load disabled \
  --protected-mode no \
  --bind 0.0.0.0

echo "✅ Redis deployed on network $NETWORK_NAME"

# 3. Deploy MongoDB với network và authentication từ .env
echo "🗄️ Deploying MongoDB with authentication from .env..."
docker stop mongodb 2>/dev/null || true
docker rm mongodb 2>/dev/null || true

docker run -d \
  --name mongodb \
  --network "$NETWORK_NAME" \
  --restart unless-stopped \
  -p 27017:27017 \
  -v mongodb_data:/data/db \
  -e MONGO_INITDB_ROOT_USERNAME="$MONGODB_ROOT_USERNAME" \
  -e MONGO_INITDB_ROOT_PASSWORD="$MONGODB_ROOT_PASSWORD" \
  -e MONGO_INITDB_DATABASE="$MONGODB_NAME" \
  mongo:7.0

echo "✅ MongoDB deployed on network $NETWORK_NAME with authentication"

# 4. Chờ services khởi động
echo "⏳ Waiting for services to be ready..."
sleep 20

# 5. Kiểm tra Redis với retry mechanism
echo "🔍 Testing Redis connection with retry..."
REDIS_RETRY_COUNT=0
MAX_REDIS_RETRIES=5

while [ $REDIS_RETRY_COUNT -lt $MAX_REDIS_RETRIES ]; do
    if docker exec redis-server redis-cli ping | grep -q "PONG"; then
        echo "✅ Redis is responding"
        # Test Redis info to check role
        REDIS_ROLE=$(docker exec redis-server redis-cli info replication | grep "role:master" || echo "role:unknown")
        echo "ℹ️  Redis role: $REDIS_ROLE"
        break
    else
        REDIS_RETRY_COUNT=$((REDIS_RETRY_COUNT + 1))
        echo "⏳ Redis not ready, retrying... ($REDIS_RETRY_COUNT/$MAX_REDIS_RETRIES)"
        sleep 3
    fi
done

if [ $REDIS_RETRY_COUNT -eq $MAX_REDIS_RETRIES ]; then
    echo "❌ Redis is not responding after $MAX_REDIS_RETRIES attempts"
    echo "📋 Redis container logs:"
    docker logs redis-server --tail=20
    exit 1
fi

# 6. Thiết lập MongoDB authentication nếu chưa có user
echo "🔐 Checking MongoDB authentication setup..."
sleep 5

# Chỉ kiểm tra kết nối, không tạo lại user hay database
echo "🔍 Verifying existing MongoDB authentication..."
if docker exec mongodb mongosh "$MONGODB_NAME" --username "$MONGODB_APP_USERNAME" --password "$MONGODB_APP_PASSWORD" --authenticationDatabase admin --eval "db.adminCommand('ping')" --quiet | grep -q "ok"; then
    echo "✅ MongoDB authentication verified - existing setup working"

    # 7. Fix production database issues (OPTIONAL - can be skipped)
    if [ "$SKIP_DB_INIT" = "false" ]; then
        echo "🔧 Fixing production database issues..."
        if [ -f "fix_production_database.py" ]; then
            echo "🔗 Running database fix with network connectivity..."
            docker run --rm \
              --network "$NETWORK_NAME" \
              --env-file .env \
              -v $(pwd):/app \
              -w /app \
              python:3.10-slim bash -c "
                echo '📦 Installing dependencies...'
                pip install pymongo python-dotenv >/dev/null 2>&1 &&
                echo '🔧 Running database fix...'
                python fix_production_database.py
              "
            echo "✅ Database fix completed"
        else
            echo "⚠️  fix_production_database.py not found - skipping database fix"
        fi
    else
        echo "⏭️  Skipping database fix (SKIP_DB_INIT=true)"
    fi

    # 7b. Fix MongoDB indexes to prevent conflicts (OPTIONAL - can be skipped)
    if [ "$SKIP_INDEX_FIX" = "false" ]; then
        echo "🔧 Fixing MongoDB indexes..."
        if [ -f "fix_mongodb_indexes.py" ]; then
            echo "🔗 Running MongoDB index fix with network connectivity..."
            docker run --rm \
              --network "$NETWORK_NAME" \
              --env-file .env \
              -v $(pwd):/app \
              -w /app \
              python:3.10-slim bash -c "
                echo '📦 Installing dependencies...'
                pip install pymongo python-dotenv >/dev/null 2>&1 &&
                echo '🔧 Fixing MongoDB indexes (drop old, create new with sparse=True)...'
                python fix_mongodb_indexes.py
              "
            echo "✅ MongoDB indexes fixed"
        else
            echo "⚠️  fix_mongodb_indexes.py not found - skipping index fix"
            echo "ℹ️  Note: This may cause index conflict errors on first startup"
        fi
    else
        echo "⏭️  Skipping MongoDB index fix (SKIP_INDEX_FIX=true)"
    fi
else
    echo "⚠️  MongoDB authentication check failed"
    echo "ℹ️  You may need to run deploy-fresh-start.sh first to set up authentication"
fi

# 8. Build AI Chatbot image với cache để deploy nhanh hơn
echo "🔨 Building AI Chatbot image (using cache for faster build)..."
echo "ℹ️  Note: If you updated requirements.txt, use deploy-no-cache.sh instead"
docker build -t ai-chatbot-rag:latest .

# 9. Deploy AI Chatbot với network và override Redis URL cho Docker network
echo "🤖 Deploying AI Chatbot with Docker network Redis configuration..."
docker stop ai-chatbot-rag 2>/dev/null || true
docker rm ai-chatbot-rag 2>/dev/null || true

docker run -d \
  --name ai-chatbot-rag \
  --network "$NETWORK_NAME" \
  -p 8000:8000 \
  --env-file .env \
  --restart unless-stopped \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/chat_history.db:/app/chat_history.db \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/firebase-credentials.json:/app/firebase-credentials.json:ro \
  -e PYTHONPATH=/app \
  -e PYTHONUNBUFFERED=1 \
  -e ENVIRONMENT=production \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/firebase-credentials.json \
  -e REDIS_URL=redis://redis-server:6379 \
  -e REDIS_HOST=redis-server \
  -e REDIS_PORT=6379 \
  ai-chatbot-rag:latest

echo "✅ AI Chatbot deployed on network $NETWORK_NAME"

# 10. Kiểm tra kết nối giữa các services
echo "🔍 Testing inter-service connectivity..."
sleep 10

# Test Redis connection từ AI Chatbot container với improved error handling
echo "📡 Testing AI Chatbot -> Redis connection with detailed diagnostics..."
sleep 5

# First check if redis-cli is available, install if needed
echo "🔧 Ensuring redis-cli is available in AI container..."
docker exec ai-chatbot-rag sh -c "command -v redis-cli >/dev/null 2>&1 || (apt-get update -qq && apt-get install -y redis-tools -qq)"

# Test Redis connection with multiple methods
echo "🧪 Testing Redis connectivity..."

# Test via container name
echo "  📋 Testing Redis via container name (redis-server)..."
if docker exec ai-chatbot-rag redis-cli -h redis-server ping 2>/dev/null | grep -q "PONG"; then
    echo "  ✅ Container name connection: SUCCESS"
    REDIS_INFO=$(docker exec ai-chatbot-rag redis-cli -h redis-server info server | grep "redis_version" || echo "Version info unavailable")
    echo "  ℹ️  $REDIS_INFO"
else
    echo "  ❌ Container name connection: FAILED"
fi

# Python redis test from container
echo "  📋 Python Redis client test..."
docker exec ai-chatbot-rag python3 -c "
import os
print('🔍 Testing Redis connection from Python...')

try:
    import redis

    # Test via Docker network container name
    r = redis.Redis(host='redis-server', port=6379, decode_responses=True, socket_timeout=5)
    response = r.ping()
    if response:
        print('✅ Python Redis connection: SUCCESS')
        info = r.info('replication')
        role = info.get('role', 'unknown')
        print(f'ℹ️  Redis role: {role}')

        # Test basic operations
        r.set('test_key', 'test_value', ex=10)
        value = r.get('test_key')
        if value == 'test_value':
            print('✅ Redis read/write operations: SUCCESS')
        else:
            print('❌ Redis read/write operations: FAILED')
    else:
        print('❌ Python Redis connection: FAILED - No ping response')
except redis.exceptions.ConnectionError as e:
    print(f'❌ Python Redis connection: FAILED - {e}')
except ImportError:
    print('❌ Redis Python library not available')
except Exception as e:
    print(f'❌ Redis test error: {e}')
"

echo "📊 Redis diagnostics completed"

# Test MongoDB connection với authentication từ .env
echo "🗄️ Testing AI Chatbot -> MongoDB connection with .env authentication..."

# Simple MongoDB connection test from container
echo "🔍 Testing MongoDB connection from container..."
docker exec ai-chatbot-rag python3 -c "
import os
print('Environment variables in container:')
print('MONGODB_URI_AUTH:', os.getenv('MONGODB_URI_AUTH', 'NOT SET'))
print('MONGODB_NAME:', os.getenv('MONGODB_NAME', 'NOT SET'))

try:
    import pymongo
    mongodb_uri = os.getenv('MONGODB_URI_AUTH')
    if mongodb_uri:
        client = pymongo.MongoClient(mongodb_uri, serverSelectionTimeoutMS=10000)
        # Test connection
        result = client.admin.command('ping')
        print('✅ MongoDB connection successful')

        # Test database access
        db_name = os.getenv('MONGODB_NAME', 'ai_service_db')
        db = client[db_name]
        collections = db.list_collection_names()
        print(f'✅ Database {db_name} accessible - Found {len(collections)} collections: {collections}')

        client.close()
    else:
        print('❌ MONGODB_URI_AUTH not found in environment')
except Exception as e:
    print(f'❌ MongoDB connection failed: {e}')
"

echo ""
echo "🔐 Authentication & Configuration Status:"
echo "════════════════════════════════════════════════════════════════"
echo "📁 Configuration source: .env file"
echo ""
echo "🔑 MongoDB (from .env):"
echo "   • Root User: $MONGODB_ROOT_USERNAME"
echo "   • App User: $MONGODB_APP_USERNAME"
echo "   • Database: $MONGODB_NAME"
echo ""
echo "� Redis Configuration:"
echo "   • Container: redis-server (no password)"
echo "   • Network: $NETWORK_NAME"
echo "   • URL Override: redis://redis-server:6379"
echo "   • Host Override: redis-server"
echo "   • Port Override: 6379"
echo ""
echo "🤖 AI Service Configuration:"
echo "   • Network: $NETWORK_NAME"
echo "   • Redis URL: redis://redis-server:6379 (Docker network)"
echo "   • MongoDB: Using MONGODB_URI_AUTH from .env"

# 10. Hiển thị status
echo ""
echo "📊 Deployment Status:"
echo "════════════════════════════════════════════════════════════════"

# Network info
echo "🌐 Network: $NETWORK_NAME"
docker network inspect "$NETWORK_NAME" --format '   Connected containers: {{range .Containers}}{{.Name}} {{end}}'

echo ""
echo "📊 Container Status:"
printf "%-20s %-15s %-10s %s\n" "CONTAINER" "STATUS" "PORTS" "NETWORK"
printf "%-20s %-15s %-10s %s\n" "─────────" "──────" "─────" "───────"

# Redis status
REDIS_STATUS=$(docker ps --filter name=redis-server --format '{{.Status}}' | head -1)
printf "%-20s %-15s %-10s %s\n" "redis-server" "${REDIS_STATUS:-Not Running}" "6379" "$NETWORK_NAME"

# MongoDB status
MONGODB_STATUS=$(docker ps --filter name=mongodb --format '{{.Status}}' | head -1)
printf "%-20s %-15s %-10s %s\n" "mongodb" "${MONGODB_STATUS:-Not Running}" "27017" "$NETWORK_NAME"

# AI Chatbot status
AI_STATUS=$(docker ps --filter name=ai-chatbot-rag --format '{{.Status}}' | head -1)
printf "%-20s %-15s %-10s %s\n" "ai-chatbot-rag" "${AI_STATUS:-Not Running}" "8000" "$NETWORK_NAME"

echo ""
echo "📊 Database Status:"
echo "   • MongoDB: PRESERVING existing data + authentication"
echo "   • Redis: PRESERVING existing cache (NO PASSWORD)"
echo "   • Qdrant: PRESERVING existing vector data"
echo "   • Local files: PRESERVING existing data"

echo ""
echo "🌐 Service URLs:"
echo "   • AI Chatbot API: http://localhost:8000"
echo "   • Health Check:   http://localhost:8000/health"
echo "   • API Docs:       http://localhost:8000/docs"

echo ""
echo "📋 Useful Management Commands:"
echo "════════════════════════════════════════════════════════════════"
echo "🔍 Monitoring:"
echo "   docker logs ai-chatbot-rag -f                    # View AI service logs"
echo "   docker logs redis-server -f                      # View Redis logs"
echo "   docker logs mongodb -f                           # View MongoDB logs"
echo ""
echo "🧪 Testing:"
echo "   docker exec redis-server redis-cli ping                                 # Test Redis (no password)"
echo "   docker exec redis-server redis-cli info replication                     # Check Redis role (should be master)"
echo "   docker exec ai-chatbot-rag python3 -c \"import os; print('REDIS_URL:', os.getenv('REDIS_URL'))\"  # Check Redis env in container"
echo "   docker exec mongodb mongosh $MONGODB_NAME -u $MONGODB_APP_USERNAME -p --eval 'db.adminCommand(\"ping\")' --quiet   # Test MongoDB with auth"
echo "   curl http://localhost:8000/health                                       # Test AI service"
echo ""
echo "🔧 Debugging:"
echo "   docker exec -it ai-chatbot-rag /bin/sh           # Enter AI container"
echo "   docker exec -it redis-server redis-cli           # Enter Redis CLI (no password)"
echo "   docker exec -it mongodb mongosh $MONGODB_NAME -u $MONGODB_APP_USERNAME -p  # Enter MongoDB shell with auth"
echo "   cat .env | grep MONGODB                          # View MongoDB credentials"
echo ""
echo "🔄 Restart Services:"
echo "   docker restart ai-chatbot-rag                    # Restart AI service"
echo "   docker restart redis-server                      # Restart Redis"
echo "   docker restart mongodb                           # Restart MongoDB"
echo ""
echo "🛑 Stop All Services:"
echo "   docker stop ai-chatbot-rag redis-server mongodb # Stop all"
echo "   docker network rm $NETWORK_NAME                  # Remove network"

echo ""
echo "✅ Deployment completed successfully!"
echo "🔗 All services are connected via network: $NETWORK_NAME"
echo "📊 Existing data has been preserved"

# 11. Final health check
echo ""
echo "🏥 Running final health checks..."
sleep 5

# Check if AI service is responding
if curl -s http://localhost:8000/health >/dev/null 2>&1; then
    echo "✅ AI Chatbot service is healthy and responding"
else
    echo "⚠️  AI Chatbot service may still be starting up..."
    echo "   Run 'docker logs ai-chatbot-rag -f' to monitor startup"
fi

echo ""
echo "🎉 Setup complete! Your AI Chatbot RAG system is updated and ready."
echo "📋 All existing data has been preserved."

# 12. Cleanup Docker cache to optimize disk space
echo ""
echo "🧹 Cleaning up Docker cache and unused images..."
echo "ℹ️  This will remove:"
echo "   • Dangling images (untagged)"
echo "   • Build cache"
echo "   • Stopped containers"
echo ""

# Remove dangling images
DANGLING_IMAGES=$(docker images -f "dangling=true" -q | wc -l | tr -d ' ')
if [ "$DANGLING_IMAGES" -gt 0 ]; then
    echo "🗑️  Removing $DANGLING_IMAGES dangling images..."
    docker image prune -f
    echo "✅ Dangling images removed"
else
    echo "ℹ️  No dangling images to remove"
fi

# Remove build cache
echo "🗑️  Removing build cache..."
docker builder prune -f
echo "✅ Build cache cleared"

# Show disk space saved
echo ""
echo "💾 Docker Disk Space After Cleanup:"
docker system df

echo ""
echo "🎉 Deployment complete with cache cleanup!"
echo "💡 Tip: To skip DB initialization on next deploy, run:"
echo "   export SKIP_DB_INIT=true SKIP_INDEX_FIX=true && ./deploy-manual.sh"
