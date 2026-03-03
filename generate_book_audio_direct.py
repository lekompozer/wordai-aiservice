#!/usr/bin/env python3
"""
One-off script: Generate book audio directly (bypasses HTTP auth).
Usage: python3 generate_book_audio_direct.py <book_id> [voice] [language]

Examples:
  python3 generate_book_audio_direct.py 69a574023e71c1cffad9fd99 auto en
  python3 generate_book_audio_direct.py 69a574023e71c1cffad9fd99 auto vi
"""

import asyncio
import sys
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)

BOOK_ID = sys.argv[1] if len(sys.argv) > 1 else "69a574023e71c1cffad9fd99"
VOICE = sys.argv[2] if len(sys.argv) > 2 else "auto"
LANGUAGE = sys.argv[3] if len(sys.argv) > 3 else "en"


async def main():
    from src.services.book_page_audio_service import BookPageAudioService

    svc = BookPageAudioService()

    # Resolve voice
    voice_name = svc.resolve_voice(BOOK_ID, VOICE)
    logging.info(f"Book: {BOOK_ID} | Voice: {voice_name} | Language: {LANGUAGE}")

    # Check if already completed
    existing = svc.get_latest_audio(BOOK_ID, voice_name, language=LANGUAGE)
    if existing and existing.get("status") == "completed":
        logging.info(f"✅ Audio already exists: {existing.get('audio_url')}")
        logging.info(f"   Duration: {existing.get('total_duration_ms')}ms")
        logging.info(f"   Pages: {len(existing.get('page_timestamps', []))}")
        return

    # Run generation (awaits full completion before returning job_id)
    logging.info(f"Starting audio generation for language='{LANGUAGE}' (this may take several minutes)...")
    job_id = await svc.generate_book_audio(BOOK_ID, voice_name, language=LANGUAGE)
    logging.info(f"Job ID: {job_id}")

    # Fetch final result from DB
    db = svc._get_db()
    doc = db.book_page_audio.find_one({"job_id": job_id})
    if doc and doc.get("status") == "completed":
        logging.info(f"✅ Done! Audio URL: {doc.get('audio_url')}")
        logging.info(f"   Duration: {doc.get('total_duration_ms')}ms")
        ts = doc.get("page_timestamps", [])
        logging.info(f"   Page timestamps: {len(ts)} pages")
        for t in ts[:3]:
            logging.info(
                f"   Page {t['page_number']}: {t['start_ms']}ms - {t['end_ms']}ms"
            )
    else:
        status = doc.get("status") if doc else "not found"
        err = doc.get("error_message") if doc else ""
        logging.error(f"❌ Status: {status} | Error: {err}")


asyncio.run(main())
