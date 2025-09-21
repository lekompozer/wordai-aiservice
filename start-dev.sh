#!/bin/bash

# Development Startup Script
# Khởi chạy môi trường development với cấu hình đúng

echo "🚀 Starting AI Chatbot RAG - Development Environment"

# Load development environment variables
echo "📝 Loading development environment variables..."
export $(grep -v '^#' .env.development | xargs)

# Verify MongoDB is running locally
echo "🔍 Checking local MongoDB..."
if ! pgrep -x "mongod" > /dev/null; then
    echo "⚠️  MongoDB is not running. Starting MongoDB..."

    # Try to start MongoDB on macOS
    if command -v brew &> /dev/null; then
        brew services start mongodb-community
    elif command -v systemctl &> /dev/null; then
        sudo systemctl start mongod
    else
        echo "❌ Please start MongoDB manually: mongod --config /usr/local/etc/mongod.conf"
        exit 1
    fi

    # Wait for MongoDB to start
    sleep 3
fi

# Verify MongoDB connection
echo "🔌 Testing MongoDB connection..."
python3 -c "
import pymongo
import os
try:
    client = pymongo.MongoClient('mongodb://localhost:27017/', serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    print('✅ MongoDB connection successful')

    # Show available databases
    dbs = client.list_database_names()
    print(f'📊 Available databases: {dbs}')

    # Check if our database exists
    db_name = os.getenv('MONGODB_NAME', 'ai_service_dev_db')
    if db_name in dbs:
        db = client[db_name]
        collections = db.list_collection_names()
        print(f'📚 Collections in {db_name}: {collections}')
    else:
        print(f'🆕 Database {db_name} will be created on first use')

except Exception as e:
    print(f'❌ MongoDB connection failed: {e}')
    exit(1)
"

# Start the application
echo "🎯 Starting FastAPI application..."
echo "📍 Server will be available at: http://localhost:8000"
echo "📝 API Documentation: http://localhost:8000/docs"
echo "🔧 Environment: ${ENVIRONMENT:-development}"
echo ""

python3 serve.py
