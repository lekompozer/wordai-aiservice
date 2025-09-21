#!/bin/bash

# Demo script để test 2-worker architecture
# Khởi chạy 2 workers và test với API call

echo "🚀 Demo: Two-Worker Architecture for AI Extraction + Storage"
echo "============================================================"
echo ""

# Check if required environment variables are set
if [ -z "$REDIS_URL" ]; then
    echo "⚠️  Warning: REDIS_URL not set, using default redis://localhost:6379"
    export REDIS_URL="redis://localhost:6379"
fi

if [ -z "$DEEPSEEK_API_KEY" ]; then
    echo "❌ Error: DEEPSEEK_API_KEY is required"
    exit 1
fi

if [ -z "$QDRANT_URL" ]; then
    echo "⚠️  Warning: QDRANT_URL not set, using default http://localhost:6333"
    export QDRANT_URL="http://localhost:6333"
fi

echo "✅ Environment setup complete"
echo "   📡 Redis: $REDIS_URL"
echo "   🧠 AI Provider: DeepSeek (configured)"
echo "   💾 Qdrant: $QDRANT_URL"
echo ""

echo "🚀 Starting Two-Worker Architecture..."
echo ""

# Start the two workers
python3 start_two_workers.py &
WORKERS_PID=$!

echo "✅ Workers started with PID: $WORKERS_PID"
echo ""
echo "📋 Architecture Flow:"
echo "   1. POST /process-async → ExtractionProcessingTask → Redis Queue"
echo "   2. ExtractionWorker → ai_extraction_service.py → AI extraction"
echo "   3. ExtractionWorker → StorageProcessingTask → Redis Queue"
echo "   4. StorageWorker → enhanced_callback_handler.py → Qdrant + Backend callback"
echo ""
echo "🔍 Workers are running... Check logs for activity"
echo "📞 Test with: POST /api/v1/extraction/process-async"
echo ""
echo "🛑 Press Ctrl+C to stop all workers"

# Wait for interrupt
trap "echo '🛑 Stopping workers...'; kill $WORKERS_PID; exit 0" INT

wait $WORKERS_PID
