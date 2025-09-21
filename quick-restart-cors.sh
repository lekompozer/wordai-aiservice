#!/bin/bash

# Quick restart script for production CORS fix
set -e

echo "🔄 Quick restart for CORS configuration fix"
echo "=========================================="

# Load environment variables
if [ -f .env ]; then
    source .env
    echo "✅ Loaded environment variables from .env"
else
    echo "❌ .env file not found!"
    exit 1
fi

echo ""
echo "🔍 Current CORS configuration:"
echo "   CORS_ORIGINS: $CORS_ORIGINS"
echo ""

# Quick restart of AI Chatbot container only
echo "🔄 Restarting AI Chatbot container..."
docker stop ai-chatbot-rag 2>/dev/null || true
docker rm ai-chatbot-rag 2>/dev/null || true

# Deploy AI Chatbot with fresh environment
echo "🚀 Starting AI Chatbot with updated CORS..."
docker run -d \
  --name ai-chatbot-rag \
  --network "ai-chatbot-network" \
  -p 8000:8000 \
  --env-file .env \
  --add-host=host.docker.internal:host-gateway \
  --restart unless-stopped \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/chat_history.db:/app/chat_history.db \
  -v $(pwd)/logs:/app/logs \
  -e PYTHONPATH=/app \
  -e PYTHONUNBUFFERED=1 \
  -e REDIS_URL=redis://redis-server:6379 \
  -e REDIS_HOST=redis-server \
  -e REDIS_PORT=6379 \
  ai-chatbot-rag:latest

echo "✅ AI Chatbot container restarted"

# Wait for startup
echo "⏳ Waiting for service to be ready..."
sleep 15

# Test health endpoint
echo "🏥 Testing health endpoint..."
if curl -s http://localhost:8000/health >/dev/null 2>&1; then
    echo "✅ AI Chatbot service is healthy"
else
    echo "⚠️  Service may still be starting up..."
fi

# Test CORS
echo ""
echo "🧪 Testing CORS with aivungtau.com..."
python3 test_cors.py

echo ""
echo "✅ Quick restart completed!"
echo "🌐 Service should now accept requests from https://aivungtau.com"
