"""
Book Page Audio Service

Generates TTS audio for LetsRead book pages using Google Gemini TTS.
Mirrors the chunking + merge pattern from slide_narration_service.generate_audio_v2().

Key differences from slide narration:
  - No subtitles — page text directly from book_page_texts.text_content
  - page_number instead of slide_index
  - book_page_audio collection instead of presentation_audio
  - Deterministic default voice assignment per book (hash-based)
  - Simpler: one book = one audio file (merged if needed)
"""

import asyncio
import hashlib
import io
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from bson import ObjectId

logger = logging.getLogger("chatbot")

# BCP-47 language code map (same as slide_narration_service)
BCP47_MAP = {
    "ar": "ar-EG",
    "bn": "bn-BD",
    "nl": "nl-NL",
    "en": "en-US",
    "fr": "fr-FR",
    "de": "de-DE",
    "hi": "hi-IN",
    "id": "id-ID",
    "it": "it-IT",
    "ja": "ja-JP",
    "ko": "ko-KR",
    "mr": "mr-IN",
    "pl": "pl-PL",
    "pt": "pt-BR",
    "ro": "ro-RO",
    "ru": "ru-RU",
    "es": "es-ES",
    "ta": "ta-IN",
    "te": "te-IN",
    "th": "th-TH",
    "tr": "tr-TR",
    "uk": "uk-UA",
    "vi": "vi-VN",
    "zh": "zh-CN",
}

MAX_BYTES_PER_CHUNK = 3500  # Safe under Gemini TTS 4000-byte limit


class BookPageAudioService:
    """
    Generates merged TTS audio for all pages of a LetsRead book.

    Workflow:
        1. Load pages from book_page_texts (sorted by page_number)
        2. Chunk pages so each chunk ≤ MAX_BYTES_PER_CHUNK
        3. TTS each chunk → WAV bytes
        4. Calculate per-page timestamps (sentence-proportional)
        5. Merge chunks with pydub if >1 chunk, recalculate global timestamps
        6. Upload final WAV to R2
        7. Upsert book_page_audio document
    """

    # ------------------------------------------------------------------
    # Voice helpers
    # ------------------------------------------------------------------

    def get_default_voice(self, book_id: str) -> str:
        """
        Deterministic voice assignment: same book_id → always same voice.
        ~70% Aoede (Female, Breezy), ~30% Algenib (Male, Gravelly).
        """
        h = int(hashlib.md5(book_id.encode()).hexdigest(), 16)
        return "Aoede" if (h % 10) < 7 else "Algenib"

    def resolve_voice(self, book_id: str, requested_voice: str) -> str:
        """Resolve 'auto' to the deterministic default; otherwise use requested."""
        if not requested_voice or requested_voice.lower() == "auto":
            return self.get_default_voice(book_id)
        # Normalise capitalisation (Aoede / AOEDE / aoede → Aoede)
        return requested_voice.capitalize()

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------

    def _get_db(self):
        from src.database.db_manager import DBManager

        return DBManager().db

    def _load_pages(self, db, book_id: str, language: str = "en") -> List[Dict]:
        """Load all pages for a book sorted by page_number."""
        cursor = db.book_page_texts.find(
            {"book_id": book_id, "language": language}
        ).sort("page_number", 1)
        return list(cursor)

    def _next_version(self, db, book_id: str, voice_name: str) -> int:
        """Return next version number for this book × voice combination."""
        latest = db.book_page_audio.find_one(
            {"book_id": book_id, "voice_name": voice_name},
            sort=[("version", -1)],
        )
        return (latest["version"] + 1) if latest else 1

    # ------------------------------------------------------------------
    # Job status helpers (book_page_audio document acts as the job record)
    # ------------------------------------------------------------------

    def create_job_record(
        self,
        db,
        book_id: str,
        voice_name: str,
        language: str,
        version: int,
        total_pages: int,
    ) -> str:
        """Create a pending job record and return its string ID."""
        doc = {
            "book_id": book_id,
            "voice_name": voice_name,
            "language": language,
            "version": version,
            "status": "pending",
            "total_pages": total_pages,
            "progress": {"done": 0, "total": total_pages},
            "audio_url": None,
            "page_timestamps": [],
            "total_duration_seconds": None,
            "audio_metadata": {},
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        result = db.book_page_audio.insert_one(doc)
        return str(result.inserted_id)

    def _update_job(self, db, job_id: str, update: Dict) -> None:
        update["updated_at"] = datetime.utcnow()
        db.book_page_audio.update_one({"_id": ObjectId(job_id)}, {"$set": update})

    def get_job_status(self, job_id: str) -> Optional[Dict]:
        db = self._get_db()
        doc = db.book_page_audio.find_one({"_id": ObjectId(job_id)})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    def get_latest_audio(self, book_id: str, voice_name: str) -> Optional[Dict]:
        """Return the latest completed audio record for book × voice."""
        db = self._get_db()
        doc = db.book_page_audio.find_one(
            {"book_id": book_id, "voice_name": voice_name, "status": "completed"},
            sort=[("version", -1)],
        )
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    # ------------------------------------------------------------------
    # Main generate function
    # ------------------------------------------------------------------

    async def generate_book_audio(
        self,
        book_id: str,
        voice: str = "auto",
        language: str = "en",
        force_regenerate: bool = False,
        use_pro_model: bool = False,
    ) -> str:
        """
        Convenience wrapper: create job record + start generation.

        Returns:
            job_id (str) — can be polled via GET /audio/generate/status/{job_id}
        """
        db = self._get_db()
        voice_name = self.resolve_voice(book_id, voice)
        total_pages = db.book_page_texts.count_documents(
            {"book_id": book_id, "language": language}
        )
        if total_pages == 0:
            raise ValueError(
                f"No pages found for book_id={book_id} language={language}. "
                "Run the letsread_page_crawler first."
            )
        version = self._next_version(db, book_id, voice_name)
        if force_regenerate:
            db.book_page_audio.delete_many(
                {"book_id": book_id, "voice_name": voice_name}
            )
            version = 1
        job_id = self.create_job_record(
            db, book_id, voice_name, language, version, total_pages
        )
        await self._run_generation(
            job_id=job_id,
            book_id=book_id,
            voice_name=voice_name,
            language=language,
            version=version,
            use_pro_model=use_pro_model,
        )
        return job_id

    async def _run_generation(
        self,
        job_id: str,
        book_id: str,
        voice_name: str,
        language: str,
        version: int,
        use_pro_model: bool = False,
    ) -> None:
        """
        Core audio generation logic that updates an existing job record.

        Designed to run as a FastAPI background task via:
            background_tasks.add_task(svc._run_generation, job_id=..., ...)
        """
        from src.services.google_tts_service import GoogleTTSService
        from src.services.r2_storage_service import get_r2_service

        db = self._get_db()
        tts_service = GoogleTTSService()
        r2_service = get_r2_service()

        tts_language = BCP47_MAP.get(language, f"{language}-US")

        # Load pages
        pages = self._load_pages(db, book_id, language)
        if not pages:
            self._update_job(
                db,
                job_id,
                {"status": "failed", "error": f"No pages found for book_id={book_id}"},
            )
            return

        total_pages = len(pages)
        logger.info(
            f"🎙️ BookPageAudio job={job_id}, book={book_id}, voice={voice_name}, "
            f"lang={tts_language}, pages={total_pages}, v{version}"
        )

        try:
            self._update_job(
                db, job_id, {"status": "processing", "total_pages": total_pages}
            )

            # ----------------------------------------------------------------
            # Build page-text chunks (each ≤ MAX_BYTES_PER_CHUNK)
            # ----------------------------------------------------------------
            chunks: List[Dict] = []  # [{pages: [...], text: str}]
            current_pages: List[Dict] = []
            current_text = ""

            for page in pages:
                text = (page.get("text_content") or "").strip()
                if not text:
                    logger.debug(f"  Page {page['page_number']}: empty text, skipping")
                    continue

                # Ensure sentence ends with period
                if not text.endswith("."):
                    text += "."
                page_text = text + "... "  # pause before next page

                if (
                    len((current_text + page_text).encode("utf-8"))
                    > MAX_BYTES_PER_CHUNK
                    and current_pages
                ):
                    chunks.append({"pages": current_pages, "text": current_text})
                    current_pages = []
                    current_text = ""

                current_pages.append(
                    {
                        "page_number": page["page_number"],
                        "text": page_text,
                    }
                )
                current_text += page_text

            if current_pages:
                chunks.append({"pages": current_pages, "text": current_text})

            if not chunks:
                raise ValueError("No text content found in any page")

            logger.info(f"  Split into {len(chunks)} TTS chunk(s)")

            # ----------------------------------------------------------------
            # Generate audio for each chunk
            # ----------------------------------------------------------------
            chunk_audio_docs: List[Dict] = []
            pages_done = 0

            for chunk_idx, chunk in enumerate(chunks):
                chunk_text = chunk["text"]
                chunk_pages = chunk["pages"]

                logger.info(
                    f"  Chunk {chunk_idx + 1}/{len(chunks)}: "
                    f"{len(chunk_pages)} pages, {len(chunk_text.encode())} bytes"
                )

                # TTS with retry
                audio_data: Optional[bytes] = None
                metadata: Optional[Dict] = None
                max_retries = 5
                retry_delay = 30

                for attempt in range(max_retries):
                    try:
                        audio_data, metadata = await tts_service.generate_audio(
                            text=chunk_text,
                            language=tts_language,
                            voice_name=voice_name,
                            use_pro_model=use_pro_model,
                        )
                        break
                    except Exception as e:
                        err = str(e)
                        retryable = any(
                            k in err
                            for k in [
                                "500",
                                "INTERNAL",
                                "429",
                                "499",
                                "CANCELLED",
                                "ReadTimeout",
                            ]
                        )
                        if attempt < max_retries - 1 and retryable:
                            logger.warning(
                                f"  ⚠️  Chunk {chunk_idx + 1} attempt {attempt + 1} failed: {err}"
                            )
                            await asyncio.sleep(retry_delay)
                        else:
                            raise

                if audio_data is None:
                    raise ValueError(f"Chunk {chunk_idx + 1} TTS failed")

                # Upload chunk to R2
                chunk_filename = f"book-audio/{book_id}/{voice_name}/v{version}/chunk_{chunk_idx}.wav"
                upload_result = await r2_service.upload_file(
                    file_content=audio_data,
                    r2_key=chunk_filename,
                    content_type="audio/wav",
                )
                chunk_url = upload_result["public_url"]

                # Validate and measure actual duration with pydub
                from pydub import AudioSegment  # type: ignore

                audio_segment = AudioSegment.from_wav(io.BytesIO(audio_data))
                actual_duration = len(audio_segment) / 1000.0  # seconds

                # Proportional timestamps based on sentence count
                page_timestamps = _calc_page_timestamps(
                    chunk_pages=chunk_pages,
                    total_duration=actual_duration,
                    chunk_start_time=0.0,  # local, will be adjusted on merge
                )

                chunk_audio_docs.append(
                    {
                        "chunk_index": chunk_idx,
                        "audio_url": chunk_url,
                        "r2_key": chunk_filename,
                        "audio_data_ref": audio_data,  # kept in memory for merge
                        "duration": actual_duration,
                        "page_timestamps": page_timestamps,
                        "metadata": metadata or {},
                    }
                )

                pages_done += len(chunk_pages)
                self._update_job(
                    db, job_id, {"progress": {"done": pages_done, "total": total_pages}}
                )
                logger.info(
                    f"  ✅ Chunk {chunk_idx + 1}: {len(audio_data):,} bytes, {actual_duration:.1f}s"
                )

            # ----------------------------------------------------------------
            # Merge chunks (or use single chunk directly)
            # ----------------------------------------------------------------
            final_url, final_duration, global_page_timestamps, final_r2_key = (
                await _merge_or_single(
                    chunk_audio_docs=chunk_audio_docs,
                    book_id=book_id,
                    voice_name=voice_name,
                    version=version,
                    r2_service=r2_service,
                )
            )

            # ----------------------------------------------------------------
            # Persist final audio record
            # ----------------------------------------------------------------
            audio_meta = chunk_audio_docs[0]["metadata"] if chunk_audio_docs else {}
            self._update_job(
                db,
                job_id,
                {
                    "status": "completed",
                    "audio_url": final_url,
                    "r2_key": final_r2_key,
                    "total_duration_seconds": round(final_duration, 2),
                    "page_timestamps": global_page_timestamps,
                    "progress": {"done": total_pages, "total": total_pages},
                    "audio_metadata": {
                        "duration_seconds": round(final_duration, 2),
                        "format": "wav",
                        "sample_rate": audio_meta.get("sample_rate", 24000),
                        "voice_name": voice_name,
                        "model": audio_meta.get(
                            "model", "gemini-2.5-flash-preview-tts"
                        ),
                        "chunks": len(chunk_audio_docs),
                    },
                    "completed_at": datetime.utcnow(),
                },
            )

            logger.info(
                f"✅ Book audio complete: job={job_id}, {total_pages} pages, "
                f"{final_duration:.1f}s, voice={voice_name}"
            )

        except Exception as e:
            logger.error(f"❌ BookPageAudio job={job_id} failed: {e}", exc_info=True)
            self._update_job(db, job_id, {"status": "failed", "error": str(e)})
            # Don't re-raise in background task context — just log

    # ------------------------------------------------------------------
    # Delete helpers
    # ------------------------------------------------------------------

    async def delete_book_audio(self, book_id: str, voice_name: str) -> bool:
        """
        Delete all audio records for this book × voice from DB (and R2 if accessible).
        Returns True if at least one record was deleted.
        """
        from src.services.r2_storage_service import get_r2_service

        db = self._get_db()
        r2_service = get_r2_service()

        docs = list(
            db.book_page_audio.find({"book_id": book_id, "voice_name": voice_name})
        )
        if not docs:
            return False

        for doc in docs:
            # Best-effort R2 deletion
            r2_key = doc.get("r2_key")
            if r2_key:
                try:
                    r2_service.delete_file(r2_key)
                except Exception as e:
                    logger.warning(f"R2 delete failed for {r2_key}: {e}")

        result = db.book_page_audio.delete_many(
            {"book_id": book_id, "voice_name": voice_name}
        )
        logger.info(
            f"Deleted {result.deleted_count} audio records for book={book_id} voice={voice_name}"
        )
        return result.deleted_count > 0


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _calc_page_timestamps(
    chunk_pages: List[Dict],
    total_duration: float,
    chunk_start_time: float = 0.0,
) -> List[Dict]:
    """
    Assign timestamps to pages proportional to sentence count.

    Each page gets a time slice proportional to its sentence count
    (number of '.' characters). If no '.' found, assume 1 sentence.
    """
    if not chunk_pages or total_duration <= 0:
        return []

    sentence_counts = []
    for p in chunk_pages:
        count = p["text"].count(".")
        sentence_counts.append(max(count, 1))

    total_sentences = sum(sentence_counts)
    timestamps = []
    current = chunk_start_time

    for i, page_info in enumerate(chunk_pages):
        ratio = sentence_counts[i] / total_sentences
        duration = total_duration * ratio
        timestamps.append(
            {
                "page_number": page_info["page_number"],
                "start_time": round(current, 3),
                "end_time": round(current + duration, 3),
                "duration": round(duration, 3),
            }
        )
        current += duration

    return timestamps


async def _merge_or_single(
    chunk_audio_docs: List[Dict],
    book_id: str,
    voice_name: str,
    version: int,
    r2_service,
) -> Tuple[str, float, List[Dict], str]:
    """
    If only one chunk: return it as-is.
    If multiple chunks: merge with pydub and recalculate global timestamps.

    Returns:
        (final_url, total_duration_seconds, global_page_timestamps, r2_key)
    """
    if len(chunk_audio_docs) == 1:
        chunk = chunk_audio_docs[0]
        return (
            chunk["audio_url"],
            chunk["duration"],
            chunk["page_timestamps"],
            chunk["r2_key"],
        )

    # Merge multiple chunks
    logger.info(f"  🔀 Merging {len(chunk_audio_docs)} audio chunks...")
    from pydub import AudioSegment  # type: ignore

    combined = AudioSegment.empty()
    global_timestamps: List[Dict] = []
    current_time = 0.0

    for chunk in chunk_audio_docs:
        # Load from in-memory audio_data_ref
        audio_bytes = chunk.get("audio_data_ref")
        if audio_bytes is None:
            # Fallback: download from R2
            import httpx

            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.get(chunk["audio_url"])
                resp.raise_for_status()
                audio_bytes = resp.content

        segment = AudioSegment.from_wav(io.BytesIO(audio_bytes))
        actual_duration = len(segment) / 1000.0

        # Recalculate timestamps with actual duration (vs predicted)
        predicted_duration = chunk["duration"]
        scale = actual_duration / predicted_duration if predicted_duration > 0 else 1.0

        for ts in chunk["page_timestamps"]:
            global_timestamps.append(
                {
                    "page_number": ts["page_number"],
                    "start_time": round(current_time + ts["start_time"] * scale, 3),
                    "end_time": round(current_time + ts["end_time"] * scale, 3),
                    "duration": round(ts["duration"] * scale, 3),
                }
            )

        combined += segment
        current_time += actual_duration

    # Export merged WAV
    buf = io.BytesIO()
    combined.export(buf, format="wav")
    merged_bytes = buf.getvalue()

    merged_key = f"book-audio/{book_id}/{voice_name}/v{version}/merged.wav"
    upload_result = await r2_service.upload_file(
        file_content=merged_bytes,
        r2_key=merged_key,
        content_type="audio/wav",
    )

    total_dur = len(combined) / 1000.0
    logger.info(f"  ✅ Merged: {len(merged_bytes):,} bytes, {total_dur:.1f}s")
    return upload_result["public_url"], total_dur, global_timestamps, merged_key


# ---------------------------------------------------------------------------
# Module-level factory
# ---------------------------------------------------------------------------


def get_book_page_audio_service() -> BookPageAudioService:
    return BookPageAudioService()
