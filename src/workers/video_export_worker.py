"""
Video Export Worker
Processes video export tasks from Redis queue using Playwright for screenshots
"""

import os
import sys
import asyncio
import logging
import signal
import time
import shutil
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

# Load environment variables
env_var = os.getenv("ENVIRONMENT", os.getenv("ENV", "production"))
env_file = "development.env" if env_var == "development" else ".env"
load_dotenv(env_file)

from bson import ObjectId

from src.queue.queue_manager import QueueManager, set_job_status
from src.models.ai_queue_tasks import VideoExportTask
from src.database.db_manager import DBManager
from src.utils.logger import setup_logger

logger = setup_logger()


class VideoExportWorker:
    """Worker that processes video export tasks from Redis queue"""

    def __init__(
        self,
        worker_id: Optional[str] = None,
        redis_url: Optional[str] = None,
        batch_size: int = 1,
        max_retries: int = 2,
    ):
        self.worker_id = (
            worker_id or f"video_export_worker_{int(time.time())}_{os.getpid()}"
        )
        self.redis_url = redis_url or os.getenv(
            "REDIS_URL", "redis://redis-server:6379"
        )
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.running = False

        # Initialize components
        self.queue_manager = QueueManager(
            redis_url=self.redis_url, queue_name="video_export"
        )
        self.db_manager = DBManager()
        self.db = self.db_manager.db

        # Frontend URL for loading presentations
        self.frontend_url = os.getenv(
            "FRONTEND_URL", "https://wordai.pro"
        )

        logger.info(f"🔧 Video Export Worker {self.worker_id} initialized")
        logger.info(f"   📡 Redis: {self.redis_url}")
        logger.info(f"   🌐 Frontend: {self.frontend_url}")

    async def initialize(self):
        """Initialize worker components"""
        try:
            await self.queue_manager.connect()
            logger.info(
                f"✅ Worker {self.worker_id}: Connected to Redis video_export queue"
            )

            # Check if Playwright is installed
            try:
                from playwright.async_api import async_playwright
                logger.info("✅ Playwright available")
            except ImportError:
                logger.error(
                    "❌ Playwright not installed. Run: pip install playwright && playwright install chromium"
                )
                raise

        except Exception as e:
            logger.error(f"❌ Worker {self.worker_id}: Initialization failed: {e}")
            raise

    async def shutdown(self):
        """Gracefully shutdown worker"""
        logger.info(f"🛑 Worker {self.worker_id}: Shutting down...")
        self.running = False

        if self.queue_manager:
            await self.queue_manager.disconnect()

        logger.info(f"✅ Worker {self.worker_id}: Shutdown complete")

    async def capture_screenshots_optimized(
        self,
        public_token: str,
        slide_count: int,
        output_dir: Path,
        job_id: str,
    ) -> List[Path]:
        """
        Capture 1 screenshot per slide at 6s mark (after animations)
        
        Args:
            public_token: Public presentation token
            slide_count: Total number of slides
            output_dir: Directory to save screenshots
            job_id: Job ID for progress updates
            
        Returns:
            List of screenshot paths
        """
        from playwright.async_api import async_playwright

        logger.info(f"📸 Optimized mode: Capturing {slide_count} screenshots...")

        screenshot_paths = []
        presentation_url = f"{self.frontend_url}/public/presentations/{public_token}"

        async with async_playwright() as p:
            # Launch browser
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                ]
            )

            page = await browser.new_page(
                viewport={"width": 1920, "height": 1080},
                device_scale_factor=1,
            )

            # Load presentation
            logger.info(f"   🌐 Loading: {presentation_url}")
            await page.goto(presentation_url, wait_until="networkidle")
            await asyncio.sleep(2)  # Wait for initial render

            # Capture each slide
            for slide_idx in range(slide_count):
                try:
                    # Navigate to slide
                    await page.evaluate(f"window.goToSlide({slide_idx})")
                    
                    # Wait 6 seconds for animations to complete
                    await asyncio.sleep(6)

                    # Take screenshot
                    screenshot_path = output_dir / f"slide_{slide_idx:03d}.png"
                    await page.screenshot(
                        path=str(screenshot_path),
                        type="png",
                        full_page=False,
                    )

                    screenshot_paths.append(screenshot_path)
                    logger.info(
                        f"   ✅ Slide {slide_idx + 1}/{slide_count}: {screenshot_path.name}"
                    )

                    # Update progress: screenshots are 50% of total work
                    progress = int(((slide_idx + 1) / slide_count) * 50)
                    await set_job_status(
                        redis_client=self.queue_manager.redis_client,
                        job_id=job_id,
                        status="processing",
                        progress=progress,
                        current_phase="screenshot",
                    )

                except Exception as e:
                    logger.error(f"   ❌ Failed to capture slide {slide_idx}: {e}")
                    # Continue with next slide
                    continue

            await browser.close()

        logger.info(f"✅ Captured {len(screenshot_paths)} screenshots")
        return screenshot_paths

    async def capture_screenshots_animated(
        self,
        public_token: str,
        slide_count: int,
        output_dir: Path,
        job_id: str,
    ) -> Dict[int, List[Path]]:
        """
        Capture 5s animation (150 frames @ 30 FPS) per slide
        
        Args:
            public_token: Public presentation token
            slide_count: Total number of slides
            output_dir: Directory to save screenshots
            job_id: Job ID for progress updates
            
        Returns:
            Dict mapping slide_index to list of frame paths
        """
        from playwright.async_api import async_playwright

        logger.info(
            f"🎬 Animated mode: Capturing {slide_count} slides × 150 frames..."
        )

        slide_frames = {}
        presentation_url = f"{self.frontend_url}/public/presentations/{public_token}"
        fps = 30
        animation_duration = 5  # seconds
        frames_per_slide = fps * animation_duration  # 150 frames

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                ]
            )

            page = await browser.new_page(
                viewport={"width": 1920, "height": 1080},
                device_scale_factor=1,
            )

            # Load presentation
            logger.info(f"   🌐 Loading: {presentation_url}")
            await page.goto(presentation_url, wait_until="networkidle")
            await asyncio.sleep(2)

            # Capture each slide
            for slide_idx in range(slide_count):
                try:
                    # Navigate to slide
                    await page.evaluate(f"window.goToSlide({slide_idx})")
                    await asyncio.sleep(0.5)  # Brief settle time

                    # Create slide directory
                    slide_dir = output_dir / f"slide_{slide_idx:03d}"
                    slide_dir.mkdir(exist_ok=True)

                    frames = []

                    # Capture frames at 30 FPS for 5 seconds
                    frame_interval = 1 / fps  # ~33ms per frame
                    for frame_idx in range(frames_per_slide):
                        frame_path = slide_dir / f"frame_{frame_idx:04d}.png"
                        
                        await page.screenshot(
                            path=str(frame_path),
                            type="png",
                            full_page=False,
                        )
                        
                        frames.append(frame_path)
                        
                        # Sleep for next frame (30 FPS = 33.3ms per frame)
                        await asyncio.sleep(frame_interval)

                    slide_frames[slide_idx] = frames

                    logger.info(
                        f"   ✅ Slide {slide_idx + 1}/{slide_count}: {len(frames)} frames"
                    )

                    # Update progress: screenshots are 50% of total work
                    progress = int(((slide_idx + 1) / slide_count) * 50)
                    await set_job_status(
                        redis_client=self.queue_manager.redis_client,
                        job_id=job_id,
                        status="processing",
                        progress=progress,
                        current_phase="screenshot",
                    )

                except Exception as e:
                    logger.error(f"   ❌ Failed to capture slide {slide_idx}: {e}")
                    slide_frames[slide_idx] = []
                    continue

            await browser.close()

        total_frames = sum(len(frames) for frames in slide_frames.values())
        logger.info(f"✅ Captured {total_frames} frames across {len(slide_frames)} slides")
        return slide_frames

    async def download_audio(
        self, audio_url: str, output_path: Path, job_id: str
    ) -> Path:
        """
        Download merged audio file
        
        Args:
            audio_url: URL to download audio from
            output_path: Path to save audio file
            job_id: Job ID for progress updates
            
        Returns:
            Path to downloaded audio file
        """
        import aiohttp

        logger.info(f"🎵 Downloading audio from: {audio_url}")

        async with aiohttp.ClientSession() as session:
            async with session.get(audio_url) as response:
                if response.status != 200:
                    raise ValueError(f"Failed to download audio: HTTP {response.status}")

                # Stream to file
                with open(output_path, "wb") as f:
                    async for chunk in response.content.iter_chunked(8192):
                        f.write(chunk)

        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        logger.info(f"✅ Audio downloaded: {output_path.name} ({file_size_mb:.1f} MB)")
        return output_path

    async def encode_video_optimized(
        self,
        screenshot_paths: List[Path],
        slide_timestamps: List[Dict[str, float]],
        audio_path: Path,
        output_path: Path,
        settings: Dict[str, Any],
        job_id: str,
    ) -> Path:
        """
        Encode video in optimized mode using FFmpeg slideshow
        
        Args:
            screenshot_paths: List of screenshot image paths
            slide_timestamps: List of slide timestamp dicts with start_time, end_time
            audio_path: Path to audio file
            output_path: Path to save final MP4
            settings: Video export settings (resolution, fps, crf, etc.)
            job_id: Job ID for progress updates
            
        Returns:
            Path to encoded video file
        """
        logger.info(f"🎬 Encoding optimized video...")

        temp_dir = screenshot_paths[0].parent

        # 1. Create durations.txt with slide timestamps
        durations_file = temp_dir / "durations.txt"
        with open(durations_file, "w") as f:
            for idx, screenshot_path in enumerate(screenshot_paths):
                # Get duration from timestamps
                if idx < len(slide_timestamps):
                    duration = slide_timestamps[idx]["end_time"] - slide_timestamps[idx]["start_time"]
                else:
                    duration = 5.0  # Default 5 seconds

                f.write(f"file '{screenshot_path.name}'\n")
                f.write(f"duration {duration}\n")

            # FFmpeg requires last file repeated without duration
            if screenshot_paths:
                f.write(f"file '{screenshot_paths[-1].name}'\n")

        logger.info(f"   Created durations.txt with {len(screenshot_paths)} slides")

        # 2. Get encoding settings
        crf = settings.get("crf", 28)
        fps = settings.get("fps", 24)
        resolution = settings.get("resolution", "1080p")
        width, height = (1920, 1080) if resolution == "1080p" else (1280, 720)

        # 3. Encode video with FFmpeg concat demuxer
        video_only_path = temp_dir / "video_only.mp4"

        ffmpeg_cmd = [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", str(durations_file),
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps={fps}",
            "-c:v", "libx264",
            "-crf", str(crf),
            "-preset", "medium",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-y",
            str(video_only_path),
        ]

        logger.info(f"   FFmpeg command: {' '.join(ffmpeg_cmd)}")

        # Run FFmpeg
        process = await asyncio.create_subprocess_exec(
            *ffmpeg_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(temp_dir),
        )

        # Update progress: encoding (50-80%)
        await set_job_status(
            redis_client=self.queue_manager.redis_client,
            job_id=job_id,
            status="processing",
            progress=65,
            current_phase="encode",
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "FFmpeg encoding failed"
            logger.error(f"   ❌ FFmpeg error: {error_msg}")
            raise RuntimeError(f"FFmpeg encoding failed: {error_msg}")

        logger.info(f"   ✅ Video encoded: {video_only_path.name}")

        # 4. Merge with audio
        await set_job_status(
            redis_client=self.queue_manager.redis_client,
            job_id=job_id,
            status="processing",
            progress=80,
            current_phase="merge",
        )

        merge_cmd = [
            "ffmpeg",
            "-i", str(video_only_path),
            "-i", str(audio_path),
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
            "-movflags", "+faststart",
            "-y",
            str(output_path),
        ]

        logger.info(f"   Merging audio: {' '.join(merge_cmd)}")

        process = await asyncio.create_subprocess_exec(
            *merge_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Audio merge failed"
            logger.error(f"   ❌ Merge error: {error_msg}")
            raise RuntimeError(f"Audio merge failed: {error_msg}")

        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        logger.info(f"✅ Final video: {output_path.name} ({file_size_mb:.1f} MB)")

        return output_path

    async def encode_video_animated(
        self,
        slide_frames: Dict[int, List[Path]],
        slide_timestamps: List[Dict[str, float]],
        audio_path: Path,
        output_path: Path,
        settings: Dict[str, Any],
        job_id: str,
    ) -> Path:
        """
        Encode video in animated mode using FFmpeg image2pipe
        
        Args:
            slide_frames: Dict mapping slide_index to list of frame paths
            slide_timestamps: List of slide timestamp dicts
            audio_path: Path to audio file
            output_path: Path to save final MP4
            settings: Video export settings
            job_id: Job ID for progress updates
            
        Returns:
            Path to encoded video file
        """
        logger.info(f"🎬 Encoding animated video...")

        temp_dir = list(slide_frames.values())[0][0].parent.parent

        # 1. Create concat file listing all frame sequences
        concat_file = temp_dir / "concat.txt"
        with open(concat_file, "w") as f:
            for slide_idx in sorted(slide_frames.keys()):
                frames = slide_frames[slide_idx]
                
                # Animation frames (5 seconds @ 30 FPS = 150 frames)
                for frame_path in frames:
                    f.write(f"file '{frame_path.relative_to(temp_dir)}'\n")
                    f.write(f"duration {1/30}\n")  # 30 FPS

                # Freeze last frame until next slide
                if slide_idx < len(slide_timestamps) - 1:
                    freeze_duration = slide_timestamps[slide_idx]["end_time"] - slide_timestamps[slide_idx]["start_time"] - 5
                    if freeze_duration > 0:
                        last_frame = frames[-1]
                        f.write(f"file '{last_frame.relative_to(temp_dir)}'\n")
                        f.write(f"duration {freeze_duration}\n")

            # FFmpeg requires last file repeated
            if slide_frames:
                last_slide = max(slide_frames.keys())
                last_frame = slide_frames[last_slide][-1]
                f.write(f"file '{last_frame.relative_to(temp_dir)}'\n")

        logger.info(f"   Created concat file for {len(slide_frames)} slides")

        # 2. Get encoding settings
        crf = settings.get("crf", 25)
        fps = settings.get("fps", 30)
        resolution = settings.get("resolution", "1080p")
        width, height = (1920, 1080) if resolution == "1080p" else (1280, 720)

        # 3. Encode video
        video_only_path = temp_dir / "video_only.mp4"

        ffmpeg_cmd = [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps={fps}",
            "-c:v", "libx264",
            "-crf", str(crf),
            "-preset", "medium",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-y",
            str(video_only_path),
        ]

        logger.info(f"   FFmpeg command: {' '.join(ffmpeg_cmd)}")

        await set_job_status(
            redis_client=self.queue_manager.redis_client,
            job_id=job_id,
            status="processing",
            progress=65,
            current_phase="encode",
        )

        process = await asyncio.create_subprocess_exec(
            *ffmpeg_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "FFmpeg encoding failed"
            logger.error(f"   ❌ FFmpeg error: {error_msg}")
            raise RuntimeError(f"FFmpeg encoding failed: {error_msg}")

        logger.info(f"   ✅ Video encoded: {video_only_path.name}")

        # 4. Merge with audio
        await set_job_status(
            redis_client=self.queue_manager.redis_client,
            job_id=job_id,
            status="processing",
            progress=80,
            current_phase="merge",
        )

        merge_cmd = [
            "ffmpeg",
            "-i", str(video_only_path),
            "-i", str(audio_path),
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
            "-movflags", "+faststart",
            "-y",
            str(output_path),
        ]

        logger.info(f"   Merging audio...")

        process = await asyncio.create_subprocess_exec(
            *merge_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Audio merge failed"
            logger.error(f"   ❌ Merge error: {error_msg}")
            raise RuntimeError(f"Audio merge failed: {error_msg}")

        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        logger.info(f"✅ Final video: {output_path.name} ({file_size_mb:.1f} MB)")

        return output_path

    async def process_task(self, task: VideoExportTask) -> bool:
        """
        Process a single video export task
        
        Args:
            task: VideoExportTask from Redis queue
            
        Returns:
            bool: True if processing successful
        """
        job_id = task.job_id
        start_time = datetime.utcnow()

        # Temporary directory for this job
        temp_dir = Path(f"/tmp/export_{job_id}")
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            logger.info(f"🎬 Processing video export job {job_id}")
            logger.info(f"   Presentation: {task.presentation_id}")
            logger.info(f"   Language: {task.language}")
            logger.info(f"   Mode: {task.export_mode}")

            # Update status to processing
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="processing",
                user_id=task.user_id,
                presentation_id=task.presentation_id,
                language=task.language,
                export_mode=task.export_mode,
                started_at=start_time.isoformat(),
                progress=0,
                current_phase="load",
            )

            self.db.video_export_jobs.update_one(
                {"_id": job_id},
                {
                    "$set": {
                        "status": "processing",
                        "started_at": start_time,
                        "updated_at": datetime.utcnow(),
                        "progress": 0,
                        "current_phase": "load",
                    }
                },
            )

            # 1. Load presentation data
            logger.info("📄 Loading presentation data...")
            presentation = self.db.documents.find_one(
                {"document_id": task.presentation_id}
            )
            if not presentation:
                raise ValueError("Presentation not found")

            # Get public token
            sharing_config = self.db.presentation_sharing_config.find_one(
                {"presentation_id": task.presentation_id}
            )
            if not sharing_config or not sharing_config.get("public_token"):
                raise ValueError("Presentation not shared publicly. Generate public link first.")

            public_token = sharing_config["public_token"]
            slide_count = len(presentation.get("slide_backgrounds", []))

            logger.info(f"   Slides: {slide_count}")
            logger.info(f"   Token: {public_token}")

            # 2. Load subtitle and audio data
            subtitle = self.db.presentation_subtitles.find_one(
                {"_id": ObjectId(task.subtitle_id)}
            )
            if not subtitle:
                raise ValueError("Subtitle not found")

            audio = self.db.presentation_audio.find_one(
                {"_id": ObjectId(task.audio_id)}
            )
            if not audio or not audio.get("audio_url"):
                raise ValueError("Audio not found")

            # Get slide timestamps for durations
            slide_timestamps = audio.get("slide_timestamps", [])
            audio_duration = audio.get("audio_metadata", {}).get("duration_seconds", 0)

            logger.info(f"   Audio duration: {audio_duration}s")
            logger.info(f"   Slide timestamps: {len(slide_timestamps)}")

            # Update progress: loaded data
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="processing",
                progress=10,
                current_phase="screenshot",
            )

            # 3. Capture screenshots based on mode
            if task.export_mode == "optimized":
                screenshot_paths = await self.capture_screenshots_optimized(
                    public_token=public_token,
                    slide_count=slide_count,
                    output_dir=temp_dir,
                    job_id=job_id,
                )

                # Store for next phase (FFmpeg)
                screenshot_data = {
                    "mode": "optimized",
                    "screenshots": [str(p) for p in screenshot_paths],
                    "slide_timestamps": slide_timestamps,
                }

            else:  # animated
                slide_frames = await self.capture_screenshots_animated(
                    public_token=public_token,
                    slide_count=slide_count,
                    output_dir=temp_dir,
                    job_id=job_id,
                )

                # Store for next phase (FFmpeg)
                screenshot_data = {
                    "mode": "animated",
                    "slide_frames": {
                        idx: [str(p) for p in frames]
                        for idx, frames in slide_frames.items()
                    },
                    "slide_timestamps": slide_timestamps,
                }

            # Save screenshot metadata for Phase 3 (FFmpeg)
            import json
            metadata_path = temp_dir / "screenshot_metadata.json"
            with open(metadata_path, "w") as f:
                json.dump(screenshot_data, f, indent=2)

            logger.info(f"✅ Screenshot phase complete: {metadata_path}")

            # Update progress: screenshots done (50%)
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="processing",
                progress=50,
                current_phase="encode",
                screenshot_metadata_path=str(metadata_path),
            )

            # 4. Download audio
            logger.info("🎵 Downloading audio...")
            audio_path = temp_dir / "audio.mp3"
            await self.download_audio(
                audio_url=audio["audio_url"],
                output_path=audio_path,
                job_id=job_id,
            )

            # 5. Encode video based on mode
            final_video_path = temp_dir / "final.mp4"

            if task.export_mode == "optimized":
                await self.encode_video_optimized(
                    screenshot_paths=screenshot_paths,
                    slide_timestamps=slide_timestamps,
                    audio_path=audio_path,
                    output_path=final_video_path,
                    settings=task.settings,
                    job_id=job_id,
                )
            else:  # animated
                await self.encode_video_animated(
                    slide_frames=slide_frames,
                    slide_timestamps=slide_timestamps,
                    audio_path=audio_path,
                    output_path=final_video_path,
                    settings=task.settings,
                    job_id=job_id,
                )

            # 6. TODO Phase 4: Upload to S3/R2 (for now, just store local path)
            # Get final file size
            file_size_mb = final_video_path.stat().st_size / (1024 * 1024)
            
            # Mark as completed
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="completed",
                progress=100,
                current_phase="completed",
                output_path=str(final_video_path),
                file_size_mb=file_size_mb,
            )

            self.db.video_export_jobs.update_one(
                {"_id": job_id},
                {
                    "$set": {
                        "status": "completed",
                        "progress": 100,
                        "current_phase": "completed",
                        "output_path": str(final_video_path),
                        "file_size": file_size_mb,
                        "updated_at": datetime.utcnow(),
                        "completed_at": datetime.utcnow(),
                    }
                },
            )

            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"✅ Video export job {job_id} completed in {elapsed:.1f}s")
            logger.info(f"   Output: {final_video_path} ({file_size_mb:.1f} MB)")
            logger.info(f"   TODO Phase 4: Upload to S3/R2 storage")

            return True

        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Video export job {job_id} failed: {error_msg}", exc_info=True)

            # Update status to failed
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="failed",
                user_id=task.user_id,
                error=error_msg,
                failed_at=datetime.utcnow().isoformat(),
            )

            self.db.video_export_jobs.update_one(
                {"_id": job_id},
                {
                    "$set": {
                        "status": "failed",
                        "error_message": error_msg,
                        "updated_at": datetime.utcnow(),
                        "completed_at": datetime.utcnow(),
                    }
                },
            )

            # Cleanup temp directory on failure
            if temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                    logger.info(f"   🗑️  Cleaned up temp directory: {temp_dir}")
                except Exception as cleanup_error:
                    logger.warning(f"   ⚠️  Failed to cleanup {temp_dir}: {cleanup_error}")

            return False

    async def run(self):
        """Main worker loop"""
        self.running = True
        logger.info(f"🚀 Worker {self.worker_id} started")

        while self.running:
            try:
                # Process tasks from queue
                task_dict = await self.queue_manager.dequeue_generic_task(
                    worker_id=self.worker_id
                )

                if task_dict:
                    # Parse task
                    task = VideoExportTask(**task_dict)
                    logger.info(f"📥 Dequeued task: {task.job_id}")

                    # Process task
                    success = await self.process_task(task)

                    if success:
                        logger.info(f"✅ Task {task.job_id} completed successfully")
                    else:
                        logger.error(f"❌ Task {task.job_id} failed")

                else:
                    # No tasks available, sleep briefly
                    await asyncio.sleep(1)

            except asyncio.CancelledError:
                logger.info("🛑 Worker cancelled, shutting down...")
                break
            except Exception as e:
                logger.error(f"❌ Worker error: {e}", exc_info=True)
                await asyncio.sleep(5)  # Back off on error

        logger.info(f"✅ Worker {self.worker_id} stopped")


async def main():
    """Main entry point"""
    worker = VideoExportWorker()

    # Setup signal handlers for graceful shutdown
    def signal_handler(sig, frame):
        logger.info(f"🛑 Received signal {sig}, shutting down...")
        asyncio.create_task(worker.shutdown())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        await worker.initialize()
        await worker.run()
    except KeyboardInterrupt:
        logger.info("🛑 Keyboard interrupt received")
    finally:
        await worker.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
