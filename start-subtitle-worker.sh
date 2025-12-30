#!/bin/bash
# Start Slide Narration Subtitle Worker

echo "🎙️ Starting Slide Narration Subtitle Worker..."

# Activate Python environment if exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run worker
python3 -m src.workers.slide_narration_subtitle_worker
