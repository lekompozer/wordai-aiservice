#!/bin/bash
set -e

echo "🚀 Starting AI Chatbot RAG Service with Background Workers..."
echo "   Environment: ${ENVIRONMENT:-production}"
echo "   Redis URL: ${REDIS_URL:-redis://redis:6379}"

# Start the main FastAPI application with workers
echo "📝 Starting main application (includes background workers)..."
exec python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
