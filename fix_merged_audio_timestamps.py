#!/usr/bin/env python3
"""
Fix merged audio timestamps by remerging chunks with scaled timestamps
Usage: python fix_merged_audio_timestamps.py doc_c49e8af18c03 vi
"""

import os
import sys
import asyncio
from datetime import datetime
from bson import ObjectId

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from database.db_manager import DBManager
from services.slide_narration_service import get_slide_narration_service


async def fix_merged_audio(presentation_id: str, language: str):
    """Remerge audio chunks with fixed timestamp scaling"""
    
    db_manager = DBManager()
    db = db_manager.db
    
    print(f"\n🔧 Fixing merged audio for {presentation_id} ({language})")
    
    # 1. Get latest subtitle
    subtitle = db.presentation_subtitles.find_one(
        {"presentation_id": presentation_id, "language": language},
        sort=[("version", -1)]
    )
    
    if not subtitle:
        print(f"❌ No subtitle found for {presentation_id} ({language})")
        return
    
    subtitle_id = str(subtitle["_id"])
    version = subtitle["version"]
    user_id = subtitle["user_id"]
    
    print(f"   Subtitle ID: {subtitle_id}")
    print(f"   Version: {version}")
    print(f"   User ID: {user_id}")
    
    # 2. Get latest chunks
    chunks = list(db.presentation_audio.find({
        "presentation_id": presentation_id,
        "language": language,
        "audio_type": "chunked"
    }).sort([("chunk_index", 1), ("created_at", -1)]))
    
    # Get only latest chunks (group by chunk_index)
    latest_chunks = {}
    for chunk in chunks:
        idx = chunk["chunk_index"]
        if idx not in latest_chunks or chunk["created_at"] > latest_chunks[idx]["created_at"]:
            latest_chunks[idx] = chunk
    
    audio_docs = [latest_chunks[i] for i in sorted(latest_chunks.keys())]
    
    print(f"   Found {len(audio_docs)} chunks:")
    for chunk in audio_docs:
        print(f"      Chunk {chunk['chunk_index']}: {len(chunk.get('slide_timestamps', []))} slides")
    
    # 3. Call merge function with new logic
    print(f"\n🎵 Merging chunks with scaled timestamps...")
    
    service = get_slide_narration_service()
    
    # Get voice config from first chunk
    voice_config = audio_docs[0].get("voice_config", {
        "voice_name": "vi-VN-Neural2-D",
        "language_code": "vi-VN"
    })
    
    try:
        merged_doc = await service._merge_audio_chunks(
            audio_documents=audio_docs,
            presentation_id=presentation_id,
            subtitle_id=subtitle_id,
            language=language,
            version=version,
            user_id=user_id,
            voice_config=voice_config
        )
        
        print(f"\n✅ Merged audio created:")
        print(f"   ID: {merged_doc['_id']}")
        print(f"   Slides: {merged_doc['slide_count']}")
        print(f"   Duration: {merged_doc['audio_metadata']['duration_seconds']:.1f}s")
        print(f"   URL: {merged_doc['audio_url']}")
        
        # 4. Update subtitle to reference new merged audio
        db.presentation_subtitles.update_one(
            {"_id": ObjectId(subtitle_id)},
            {"$set": {"merged_audio_id": merged_doc["_id"]}}
        )
        
        print(f"\n✅ Updated subtitle to reference new merged audio")
        
        # 5. Verify timestamps
        print(f"\n📊 Verifying timestamps:")
        timestamps = merged_doc["slide_timestamps"]
        print(f"   First slide: {timestamps[0]['start_time']:.1f}s → {timestamps[0]['end_time']:.1f}s")
        print(f"   Last slide: {timestamps[-1]['start_time']:.1f}s → {timestamps[-1]['end_time']:.1f}s")
        print(f"   Audio duration: {merged_doc['audio_metadata']['duration_seconds']:.1f}s")
        
        # Check for overlaps
        has_issues = False
        for i in range(len(timestamps) - 1):
            current_end = timestamps[i]["end_time"]
            next_start = timestamps[i + 1]["start_time"]
            
            if next_start < current_end:
                print(f"   ⚠️ Overlap: Slide {i} ends at {current_end:.1f}s, Slide {i+1} starts at {next_start:.1f}s")
                has_issues = True
            elif next_start > current_end + 1:
                gap = next_start - current_end
                print(f"   ⚠️ Gap: {gap:.1f}s between Slide {i} and {i+1}")
                has_issues = True
        
        if not has_issues:
            print(f"   ✅ No overlaps or gaps detected!")
        
        return merged_doc
        
    except Exception as e:
        print(f"\n❌ Merge failed: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python fix_merged_audio_timestamps.py <presentation_id> <language>")
        print("Example: python fix_merged_audio_timestamps.py doc_c49e8af18c03 vi")
        sys.exit(1)
    
    presentation_id = sys.argv[1]
    language = sys.argv[2]
    
    asyncio.run(fix_merged_audio(presentation_id, language))
