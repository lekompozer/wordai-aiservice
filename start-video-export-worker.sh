#!/bin/bash

# Start Video Export Worker
# This worker processes video export tasks from Redis queue

echo "🎬 Starting Video Export Worker..."

# Activate virtual environment if exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Set environment
export ENVIRONMENT=development
export PYTHONUNBUFFERED=1

# Start worker
python3 src/workers/video_export_worker.py
