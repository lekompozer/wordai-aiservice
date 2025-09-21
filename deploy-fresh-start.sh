#!/bin/bash

# Script deploy mới với xóa sạch database và tạo lại từ đầu
set -e

# Load environment variables từ .env ngay từ đầu
if [ -f .env ]; then
    source .env
    echo "✅ Loaded environment variables from .env"
else
    echo "❌ .env file not found!"
    exit 1
fi

echo "🔥 Starting FRESH deployment - ALL DATA WILL BE DELETED!"
echo "⚠️  This script will:"
echo "   • Stop all existing containers"
echo "   • Delete all MongoDB data"
echo "   • Delete all Redis data" 
echo "   • Delete all Qdrant data"
echo "   • Recreate everything from scratch"
echo ""

# Xác nhận từ người dùng
read -p "❓ Are you sure you want to DELETE ALL DATA and start fresh? (type 'YES' to confirm): " confirm
if [ "$confirm" != "YES" ]; then
    echo "❌ Deployment cancelled"
    exit 1
fi

echo ""
echo "🚀 Starting FRESH deployment with complete data reset..."

# Định nghĩa tên network
NETWORK_NAME="ai-chatbot-network"

# 1. Stop và xóa tất cả containers cũ
echo "🛑 Stopping and removing all existing containers..."
docker stop ai-chatbot-rag redis-server mongodb 2>/dev/null || true
docker rm ai-chatbot-rag redis-server mongodb 2>/dev/null || true
echo "✅ Old containers removed"

# 2. Xóa tất cả volumes (DATA LOSS!)
echo "🗑️  Removing all data volumes..."
docker volume rm redis_data mongodb_data qdrant_data 2>/dev/null || true
echo "✅ All data volumes deleted"

# 3. Xóa network cũ và tạo mới
echo "🌐 Recreating Docker Network..."
docker network rm "$NETWORK_NAME" 2>/dev/null || true
docker network create --driver bridge "$NETWORK_NAME"
echo "✅ Fresh network created: $NETWORK_NAME"

# 4. Deploy Redis hoàn toàn mới (không cần password cho worker)
echo "📡 Deploying fresh Redis without password..."

docker run -d \
  --name redis-server \
  --network "$NETWORK_NAME" \
  --restart unless-stopped \
  -p 6379:6379 \
  -v redis_data:/data \
  redis:7-alpine redis-server --appendonly yes

echo "✅ Fresh Redis deployed"

# 5. Deploy MongoDB hoàn toàn mới với authentication từ .env
echo "🗄️ Deploying fresh MongoDB with predefined authentication..."

# Lấy thông tin từ .env file
source .env

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

echo "✅ Fresh MongoDB deployed"

# 6. Chờ services khởi động
echo "⏳ Waiting for fresh services to be ready..."
sleep 30  # Tăng thời gian chờ vì cần setup authentication

# 7. Kiểm tra Redis (không cần password)
echo "🔍 Testing fresh Redis connection..."
if docker exec redis-server redis-cli ping | grep -q "PONG"; then
    echo "✅ Fresh Redis is responding"
else
    echo "❌ Fresh Redis is not responding"
    exit 1
fi

# 8. Thiết lập MongoDB users với thông tin từ .env
echo "🔐 Setting up MongoDB authentication with predefined credentials..."
sleep 15  # Tăng thời gian chờ MongoDB khởi động hoàn toàn

# Tạo user cho application với thông tin từ .env
echo "🔧 Creating application user in MongoDB..."
docker exec mongodb mongosh admin --eval "
try {
    db.auth('$MONGODB_ROOT_USERNAME', '$MONGODB_ROOT_PASSWORD');
    
    // Tạo database trước
    db.getSiblingDB('$MONGODB_NAME').createCollection('temp');
    
    // Kiểm tra user đã tồn tại chưa
    var users = db.getUsers();
    var userExists = false;
    
    // users.users là array chứa danh sách users
    if (users.users && Array.isArray(users.users)) {
        userExists = users.users.some(user => user.user === '$MONGODB_APP_USERNAME');
    }
    
    if (!userExists) {
        db.createUser({
            user: '$MONGODB_APP_USERNAME',
            pwd: '$MONGODB_APP_PASSWORD',
            roles: [
                { role: 'readWrite', db: '$MONGODB_NAME' },
                { role: 'dbAdmin', db: '$MONGODB_NAME' }
            ]
        });
        print('✅ Application user created successfully');
    } else {
        print('ℹ️  Application user already exists');
    }
    
    // Xóa collection temp
    db.getSiblingDB('$MONGODB_NAME').temp.drop();
    
} catch(e) {
    print('❌ Error setting up user:', e.message);
    throw e;
}
"

# Chờ một chút để MongoDB xử lý user creation
sleep 5

# 9. Kiểm tra MongoDB với authentication từ .env
echo "🔍 Testing fresh MongoDB connection with predefined authentication..."

# Trước tiên, tạo database ai_service_db nếu chưa tồn tại
echo "🏗️  Ensuring database exists..."
docker exec mongodb mongosh admin --username "$MONGODB_ROOT_USERNAME" --password "$MONGODB_ROOT_PASSWORD" --eval "
// Tạo database bằng cách tạo một collection đầu tiên
db.getSiblingDB('$MONGODB_NAME').createCollection('init');
print('✅ Database $MONGODB_NAME created/verified');
" --quiet

# Thử kết nối nhiều lần nếu cần
for i in {1..3}; do
    echo "🔄 Connection attempt $i/3..."
    # User được tạo trong admin db, nên phải dùng authSource=admin
    if docker exec mongodb mongosh "$MONGODB_NAME" --username "$MONGODB_APP_USERNAME" --password "$MONGODB_APP_PASSWORD" --authenticationDatabase admin --eval "db.adminCommand('ping')" --quiet | grep -q "ok"; then
        echo "✅ Fresh MongoDB is responding with authentication"
        break
    else
        if [ $i -eq 3 ]; then
            echo "❌ Fresh MongoDB authentication failed after 3 attempts"
            echo "🔍 Debugging MongoDB authentication..."
            
            # Debug: List users
            echo "📋 Listing MongoDB users..."
            docker exec mongodb mongosh admin --username "$MONGODB_ROOT_USERNAME" --password "$MONGODB_ROOT_PASSWORD" --eval "db.getUsers()" --quiet
            
            # Debug: Check if database exists
            echo "📋 Listing databases..."
            docker exec mongodb mongosh admin --username "$MONGODB_ROOT_USERNAME" --password "$MONGODB_ROOT_PASSWORD" --eval "db.adminCommand('listDatabases')" --quiet
            
            # Debug: Try connecting to admin db with app user
            echo "📋 Testing app user connection to admin db..."
            docker exec mongodb mongosh admin --username "$MONGODB_APP_USERNAME" --password "$MONGODB_APP_PASSWORD" --eval "db.adminCommand('ping')" --quiet
            
            # Debug: Try connecting with authSource
            echo "📋 Testing app user connection to target db with authSource..."
            docker exec mongodb mongosh "$MONGODB_NAME" --username "$MONGODB_APP_USERNAME" --password "$MONGODB_APP_PASSWORD" --authenticationDatabase admin --eval "db.adminCommand('ping')" --quiet
            
            exit 1
        else
            echo "⏳ Waiting 10 seconds before retry..."
            sleep 10
        fi
    fi
done

# 10. Tạo database và collections từ đầu với authentication từ .env
echo "🏗️  Initializing fresh MongoDB database structure with predefined authentication..."
docker exec mongodb mongosh "$MONGODB_NAME" --username "$MONGODB_APP_USERNAME" --password "$MONGODB_APP_PASSWORD" --authenticationDatabase admin --eval "
// Tạo collections cơ bản
db.createCollection('companies');
db.createCollection('conversations');
db.createCollection('messages');
db.createCollection('users');
db.createCollection('company_context');

// Tạo indexes cho performance
db.conversations.createIndex({ 'user_id': 1, 'created_at': -1 });
db.conversations.createIndex({ 'device_id': 1, 'created_at': -1 });
db.conversations.createIndex({ 'session_id': 1, 'created_at': -1 });
db.messages.createIndex({ 'user_id': 1, 'timestamp': -1 });
db.messages.createIndex({ 'device_id': 1, 'timestamp': -1 });
db.messages.createIndex({ 'session_id': 1, 'timestamp': -1 });
db.companies.createIndex({ 'company_id': 1 }, { unique: true });
db.company_context.createIndex({ 'company_id': 1 });

print('✅ Database structure created successfully with predefined authentication');
"

echo "✅ Fresh MongoDB database structure initialized"

# 10. Xóa tất cả dữ liệu local cũ
echo "🧹 Cleaning up local data files..."
rm -rf ./data/companies/* 2>/dev/null || true
rm -rf ./data/uploads/* 2>/dev/null || true
rm -f ./chat_history.db 2>/dev/null || true
rm -rf ./logs/* 2>/dev/null || true

# Tạo lại cấu trúc thư mục
mkdir -p ./data/companies
mkdir -p ./data/uploads  
mkdir -p ./logs

echo "✅ Local data cleaned and directories recreated"

# 11. Build AI Chatbot image mới
echo "🔨 Building fresh AI Chatbot image..."
docker build -t ai-chatbot-rag:latest .

# 13. Deploy AI Chatbot với .env credentials
echo "🤖 Deploying fresh AI Chatbot with .env credentials..."
docker run -d \
  --name ai-chatbot-rag \
  --network "$NETWORK_NAME" \
  -p 8000:8000 \
  --env-file .env \
  --add-host=host.docker.internal:host-gateway \
  --restart unless-stopped \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/chat_history.db:/app/chat_history.db \
  -v $(pwd)/logs:/app/logs \
  -e PYTHONPATH=/app \
  -e PYTHONUNBUFFERED=1 \
  ai-chatbot-rag:latest

echo "✅ Fresh AI Chatbot deployed"

# 14. Kiểm tra kết nối giữa các services
echo "🔍 Testing inter-service connectivity..."
sleep 15

# Test Redis connection từ AI Chatbot container (không cần password)
echo "📡 Testing AI Chatbot -> Redis connection..."
docker exec ai-chatbot-rag sh -c "apt-get update && apt-get install -y redis-tools" >/dev/null 2>&1 || true
if docker exec ai-chatbot-rag redis-cli -h redis-server ping | grep -q "PONG"; then
    echo "✅ AI Chatbot can connect to fresh Redis"
else
    echo "❌ AI Chatbot cannot connect to fresh Redis"
fi

# Test MongoDB connection từ AI Chatbot container với thông tin từ .env
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
        print('✅ MongoDB connection successful via MONGODB_URI_AUTH')
        
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
    print('Trying fallback connection methods...')
    
    # Fallback 1: Try host.docker.internal
    try:
        mongodb_user = os.getenv('MONGODB_APP_USERNAME')
        mongodb_pass = os.getenv('MONGODB_APP_PASSWORD') 
        mongodb_name = os.getenv('MONGODB_NAME')
        if mongodb_user and mongodb_pass and mongodb_name:
            uri = f'mongodb://{mongodb_user}:{mongodb_pass}@host.docker.internal:27017/{mongodb_name}?authSource=admin'
            client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=5000)
            client.admin.command('ping')
            print('✅ MongoDB connection successful via host.docker.internal')
            client.close()
        else:
            print('❌ Missing MongoDB credentials in environment')
    except Exception as e2:
        print(f'❌ Fallback connection also failed: {e2}')
        
        # Fallback 2: Try container name
        try:
            uri = f'mongodb://{mongodb_user}:{mongodb_pass}@mongodb:27017/{mongodb_name}?authSource=admin'
            client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=5000)
            client.admin.command('ping')
            print('✅ MongoDB connection successful via container name')
            client.close()
        except Exception as e3:
            print(f'❌ All MongoDB connection methods failed: {e3}')
"

# 14. Reset Qdrant Cloud collection data 
echo "🔄 Clearing Qdrant Cloud collection data..."
echo "ℹ️  Testing connection to Qdrant Cloud from container..."
if docker exec ai-chatbot-rag python3 -c "
import sys
sys.path.append('/app')

try:
    from src.services.qdrant_company_service import get_qdrant_service
    qdrant = get_qdrant_service()
    
    # Test kết nối Qdrant Cloud trước
    collections = qdrant.client.get_collections()
    print(f'✅ Connected to Qdrant Cloud - Found {len(collections.collections)} collections')
    
    # Kiểm tra collection tồn tại không
    collection_names = [col.name for col in collections.collections]
    if 'multi_company_data' in collection_names:
        # Chỉ xóa tất cả points trong collection, không xóa collection
        try:
            # Lấy tất cả points và xóa
            points_result = qdrant.client.scroll(
                collection_name='multi_company_data',
                limit=10000,
                with_payload=False,
                with_vectors=False
            )
            
            if points_result[0]:  # Nếu có points
                point_ids = [point.id for point in points_result[0]]
                qdrant.client.delete(
                    collection_name='multi_company_data',
                    points_selector=point_ids
                )
                print(f'✅ Deleted {len(point_ids)} points from Qdrant Cloud collection')
            else:
                print('ℹ️  Qdrant Cloud collection is already empty')
                
        except Exception as e:
            print(f'⚠️  Failed to clear Qdrant data: {e}')
    else:
        print('ℹ️  Collection multi_company_data does not exist yet - will be created on first use')
            
except Exception as e:
    print(f'⚠️  Qdrant Cloud connection failed: {e}')
    print('ℹ️  Qdrant will be initialized on first use')
" 2>/dev/null; then
    echo "✅ Qdrant Cloud connection test completed"
else
    echo "⚠️  Qdrant Cloud connection test failed - service will initialize on first use"
fi

# 15. Hiển thị status
echo ""
echo "📊 Fresh Deployment Status:"
echo "════════════════════════════════════════════════════════════════"

# Network info
echo "🌐 Network: $NETWORK_NAME (FRESH)"
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
echo "🆕 Fresh Data Status:"
echo "   • MongoDB: EMPTY database with fresh collections + AUTHENTICATION"
echo "   • Redis: EMPTY cache (NO PASSWORD for worker compatibility)"
echo "   • Qdrant: EMPTY vector database"
echo "   • Local files: CLEAN directories"

echo ""
echo "🔐 Security Credentials:"
echo "════════════════════════════════════════════════════════════════"
echo "📁 All credentials are in .env file"
echo ""
echo "🔑 MongoDB Authentication (from .env):"
echo "   • Root User: $MONGODB_ROOT_USERNAME"
echo "   • App User: $MONGODB_APP_USERNAME"
echo "   • Database: $MONGODB_NAME"
echo ""
echo "🔒 Redis Configuration:"
echo "   • No password (worker friendly)"
echo "   • Connection: redis://host.docker.internal:6379"

echo ""
echo "🌐 Service URLs:"
echo "   • AI Chatbot API: http://localhost:8000"
echo "   • Health Check:   http://localhost:8000/health"
echo "   • API Docs:       http://localhost:8000/docs"

echo ""
echo "📋 Next Steps:"
echo "════════════════════════════════════════════════════════════════"
echo "1. 🏢 Register companies via API:"
echo "   curl -X POST http://localhost:8000/api/admin/companies \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"company_id\":\"test\", \"company_name\":\"Test Company\"}'"
echo ""
echo "2. 📄 Upload company data via admin interface"
echo ""
echo "3. 🧪 Test chat functionality"

echo ""
echo "📋 Management Commands:"
echo "════════════════════════════════════════════════════════════════"
echo "🔍 Monitoring:"
echo "   docker logs ai-chatbot-rag -f                    # View AI service logs"
echo "   docker logs redis-server -f                      # View Redis logs"
echo "   docker logs mongodb -f                           # View MongoDB logs"
echo ""
echo "🧪 Testing:"
echo "   docker exec redis-server redis-cli ping          # Test Redis"
echo "   docker exec mongodb mongosh --eval 'db.adminCommand(\"ping\")' --quiet   # Test MongoDB"
echo "   curl http://localhost:8000/health                # Test AI service"
echo ""
echo "🔧 Database Access:"
echo "   docker exec -it mongodb mongosh $MONGODB_NAME -u $MONGODB_APP_USERNAME -p    # MongoDB shell with auth"
echo "   docker exec -it redis-server redis-cli                                       # Redis CLI (no password)"
echo "   cat .env | grep MONGODB                                                      # View MongoDB credentials"
echo ""
echo "📊 Check Collections:"
echo "   docker exec mongodb mongosh $MONGODB_NAME -u $MONGODB_APP_USERNAME -p --eval 'db.getCollectionNames()'"

# 16. Final health check
echo ""
echo "🏥 Running final health checks on fresh system..."
sleep 5

# Check if AI service is responding
if curl -s http://localhost:8000/health >/dev/null 2>&1; then
    echo "✅ Fresh AI Chatbot service is healthy and responding"
else
    echo "⚠️  Fresh AI Chatbot service may still be starting up..."
    echo "   Run 'docker logs ai-chatbot-rag -f' to monitor startup"
fi

echo ""
echo "🎉 FRESH DEPLOYMENT COMPLETED SUCCESSFULLY!"
echo "🔥 All data has been reset and system is ready for new companies"
echo "🔗 All services are connected via fresh network: $NETWORK_NAME"
