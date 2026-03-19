"""
AI Video Generation Service — Step-by-Step Pipeline

Each step runs independently; intermediate results (images, audio) are stored in R2.
Final render (Playwright + FFmpeg) is handled by video_generation_worker.

Duration presets:  15s=2 scenes | 30s=4 scenes | 45s=6 scenes | 60s=8 scenes
Frame format: 9:16 portrait (1080x1920) — TikTok / Reels / Shorts style
"""

import asyncio
import json
import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import soundfile as sf

# ─────────────────────────────────────────────
# Duration presets
# ─────────────────────────────────────────────
DURATION_PRESETS: Dict[int, Dict[str, int]] = {
    12: {"n_scenes": 2, "seconds_per_scene": 6},  # NEW
    18: {"n_scenes": 3, "seconds_per_scene": 6},
    30: {"n_scenes": 5, "seconds_per_scene": 6},
    42: {"n_scenes": 7, "seconds_per_scene": 6},
    60: {"n_scenes": 10, "seconds_per_scene": 6},
    90: {"n_scenes": 15, "seconds_per_scene": 6},  # NEW
    120: {"n_scenes": 20, "seconds_per_scene": 6},  # NEW
}

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# HTML frame template (1080x1920 portrait)
# ─────────────────────────────────────────────
FRAME_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    width: 1080px; height: 1920px;
    overflow: hidden; position: relative;
    font-family: 'Segoe UI', Arial, sans-serif;
  }}
  .bg {{
    position: absolute; inset: 0;
    background-image: url('{image_path}');
    background-size: cover; background-position: center;
  }}
  .overlay {{
    position: absolute; inset: 0;
    background: linear-gradient(
      to bottom,
      rgba(0,0,0,0.15) 0%,
      rgba(0,0,0,0.05) 40%,
      rgba(0,0,0,0.6) 70%,
      rgba(0,0,0,0.85) 100%
    );
  }}
  .top-bar {{
    position: absolute; top: 60px; left: 60px; right: 60px;
    display: flex; align-items: center; gap: 16px;
  }}
  .brand {{
    color: #fff; font-size: 32px; font-weight: 700;
    letter-spacing: 2px; opacity: 0.9;
    text-shadow: 0 2px 8px rgba(0,0,0,0.5);
  }}
  .scene-num {{
    margin-left: auto;
    color: rgba(255,255,255,0.7); font-size: 28px; font-weight: 500;
  }}
  .bottom {{
    position: absolute; bottom: 0; left: 0; right: 0;
    padding: 60px 70px 90px;
  }}
  .title-label {{
    color: rgba(255,255,255,0.75);
    font-size: 30px; font-weight: 600;
    letter-spacing: 1px; text-transform: uppercase;
    margin-bottom: 22px;
    text-shadow: 0 1px 4px rgba(0,0,0,0.8);
  }}
  .main-text {{
    color: #fff;
    font-size: {font_size}px;
    font-weight: 700;
    line-height: 1.45;
    text-shadow: 0 2px 12px rgba(0,0,0,0.9);
    letter-spacing: 0.3px;
  }}
  .progress-bar {{
    position: absolute; bottom: 0; left: 0; right: 0;
    height: 6px; background: rgba(255,255,255,0.2);
  }}
  .progress-fill {{
    height: 100%; width: {progress}%;
    background: linear-gradient(90deg, #3b82f6, #8b5cf6);
  }}
</style>
</head>
<body>
  <div class="bg"></div>
  <div class="overlay"></div>
  <div class="top-bar">
    <span class="brand">WordAI</span>
    <span class="scene-num">{scene_num}/{total_scenes}</span>
  </div>
  <div class="bottom">
    <div class="title-label">{video_title}</div>
    <div class="main-text">{text}</div>
  </div>
  <div class="progress-bar"><div class="progress-fill"></div></div>
</body>
</html>"""


def _calc_font_size(text: str) -> int:
    """Adaptive font size based on text length."""
    n = len(text)
    if n < 80:
        return 52
    if n < 120:
        return 46
    if n < 180:
        return 40
    return 36


# ─────────────────────────────────────────────
# Main service class
# ─────────────────────────────────────────────


class VideoGenerationService:
    """End-to-end pipeline for short-form AI video generation."""

    # ── Script generation ──────────────────────────────────────────────────

    async def generate_script(
        self,
        topic: str,
        n_scenes: int = 6,
        language: str = "vi",
    ) -> Dict[str, Any]:
        """
        One DeepSeek call → title + scenes (narration + image_prompt + text_overlay).

        Returns dict: {title, scenes: [{narration, image_prompt, text_overlay}]}
        """
        prompt = f"""Bạn là nhà sản xuất nội dung video ngắn chuyên nghiệp.
Hãy tạo kịch bản cho một video ngắn theo phong cách TikTok/Reels về chủ đề: "{topic}"

Yêu cầu:
- Số cảnh (scenes): {n_scenes}
- Ngôn ngữ narration: {"Tiếng Việt" if language == "vi" else "English"}
- Mỗi cảnh: 15-20 giây, 1-3 câu ngắn gọn, súc tích, hấp dẫn
- image_prompt: mô tả hình ảnh bằng TIẾNG ANH, chi tiết, phù hợp phong cách cinematic 9:16
- text_overlay: 1 câu hook ngắn (tối đa 15 từ) hiển thị trên màn hình, cùng ngôn ngữ narration

Trả về JSON CHÍNH XÁC theo format sau (không có text ngoài JSON):
{{
  "title": "Tiêu đề video",
  "scenes": [
    {{
      "narration": "Lời thuyết minh cho cảnh này...",
      "image_prompt": "Cinematic wide shot of ..., 9:16 vertical, dramatic lighting, photorealistic",
      "text_overlay": "Hook text ngắn"
    }}
  ]
}}

QUAN TRỌNG: Chỉ trả về JSON, không có markdown, không có giải thích thêm."""

        try:
            api_key = os.getenv("DEEPSEEK_API_KEY")
            if not api_key:
                raise ValueError("DEEPSEEK_API_KEY not set")

            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "deepseek-chat",
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 4000,
                        "temperature": 0.8,
                        "response_format": {"type": "json_object"},
                    },
                )
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]

            # Parse JSON (strip markdown fences if any)
            content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
            script = json.loads(content)

            # Validate structure
            assert "title" in script and "scenes" in script, "Missing title or scenes"
            assert len(script["scenes"]) >= 1, "No scenes generated"

            logger.info(
                f"✅ Script generated: '{script['title']}', {len(script['scenes'])} scenes"
            )
            return script

        except Exception as e:
            logger.error(f"❌ Script generation failed: {e}")
            raise

    # ── Storyboard variants (multi-script) ─────────────────────────────────

    async def generate_storyboards(
        self,
        topic: str,
        n_scenes: int = 5,
        language: str = "vi",
        video_style: str = "cinematic",
        target_audience: str = "general",
        n_variants: int = 2,
    ) -> List[Dict[str, Any]]:
        """
        DeepSeek Reasoner → 2-3 storyboard variants, each with a style_anchor
        for consistent AI image generation across all scenes.
        """
        style_desc = {
            "cinematic": "phong cách điện ảnh chuyên nghiệp, ánh sáng dramatic, góc quay cinematic",
            "anime": "phong cách anime Nhật Bản, màu sắc sống động, nét vẽ anime",
            "ads": "phong cách quảng cáo hiện đại, sạch sẽ, chuyên nghiệp, màu sắc tươi sáng",
            "documentary": "phong cách tài liệu thực tế, hình ảnh chân thực, ánh sáng tự nhiên",
            "cartoon": "phong cách hoạt hình 2D/3D, màu sắc vui tươi, nhân vật dễ thương",
        }.get(video_style, video_style)

        prompt = f"""Bạn là chuyên gia sản xuất nội dung video ngắn viral chuyên nghiệp.

Chủ đề video: \"{topic}\"
Phong cách: {style_desc} ({video_style})
Đối tượng khán giả: {target_audience}
Số cảnh: {n_scenes}
Ngôn ngữ narration: {"Tiếng Việt" if language == "vi" else "English"}

Hãy tạo {n_variants} kịch bản video KHÁC NHAU với góc tiếp cận hoàn toàn khác nhau.

QUAN TRỌNG:
1. style_anchor: Mô tả chi tiết bằng TIẾNG ANH về phong cách hình ảnh NHẤT QUÁN xuyên suốt video.
   - Màu sắc chủ đạo, ánh sáng, kết cấu, phong cách nghệ thuật ({video_style})
   - Nếu có nhân vật: mô tả ngoại hình nhất quán (màu tóc, trang phục, tuổi)
   - VD: "Cinematic 9:16, deep blue and amber tones, moody dramatic lighting, shallow depth of field"
   - VD: "Anime style, vibrant colors, young Vietnamese student with black hair and school uniform"
2. image_prompt của MỖI CẢNH phải BẮT ĐẦU bằng style_anchor đã chọn để đảm bảo ĐỒNG NHẤT hình ảnh.

Trả về JSON (CHÍNH XÁC, không có markdown):
{{
  "variants": [
    {{
      "variant_id": 0,
      "title": "Tiêu đề video hấp dẫn",
      "style_anchor": "Detailed visual style in English for consistent AI image generation...",
      "mood": "Tense and eye-opening",
      "scenes": [
        {{
          "scene_index": 0,
          "narration": "Lời thuyết minh 1-3 câu súc tích...",
          "image_prompt": "[PASTE style_anchor here]. Scene-specific description. Vertical 9:16.",
          "text_overlay": "Hook ngắn tối đa 12 từ"
        }}
      ]
    }}
  ]
}}

Chỉ trả về JSON, KHÔNG có gì khác."""

        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY not set")

        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek-reasoner",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 8000,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        msg = data["choices"][0]["message"]
        content = msg["content"]
        reasoning = msg.get("reasoning_content", "")
        if reasoning:
            logger.info(f"  🧠 Storyboard thinking: {len(reasoning)} chars")

        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
        result = json.loads(content)
        variants = result.get("variants", [])
        assert len(variants) >= 1, "No storyboard variants returned"

        for v in variants:
            v["scenes"] = v["scenes"][:n_scenes]
            for i, s in enumerate(v["scenes"]):
                s["scene_index"] = i

        logger.info(f"✅ {len(variants)} storyboard variants generated for '{topic}'")
        return variants

    # ── Image generation ───────────────────────────────────────────────────

    async def generate_scene_image(
        self,
        prompt: str,
        scene_index: int,
        task_dir: Path,
    ) -> Path:
        """Generate one scene image via Gemini image model → save as PNG."""
        from google import genai
        from google.genai import types as genai_types

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set")

        client = genai.Client(api_key=api_key)

        # Ensure portrait 9:16 aspect
        full_prompt = (
            f"{prompt.rstrip('.')}. "
            "Vertical 9:16 portrait format, cinematic composition, high quality, photorealistic."
        )

        result = client.models.generate_content(
            model="gemini-3.1-flash-image-preview",
            contents=full_prompt,
            config=genai_types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )

        image_data = None
        for part in result.candidates[0].content.parts:
            if hasattr(part, "inline_data") and part.inline_data:
                image_data = part.inline_data.data
                break

        if not image_data:
            raise ValueError(f"No image returned for scene {scene_index}")

        import base64

        raw = (
            base64.b64decode(image_data) if isinstance(image_data, str) else image_data
        )
        out_path = task_dir / f"scene_{scene_index:02d}_image.png"

        # Resize to exactly 1080x1920 via Pillow
        from PIL import Image
        from io import BytesIO

        img = Image.open(BytesIO(raw)).convert("RGB")
        img = img.resize((1080, 1920), Image.Resampling.LANCZOS)
        img.save(str(out_path), "PNG")

        logger.info(
            f"  🖼  Scene {scene_index} image: {out_path.name} ({out_path.stat().st_size // 1024}KB)"
        )
        return out_path

    async def generate_scene_image_xai(
        self,
        prompt: str,
        scene_index: int,
        task_dir: Path,
        style_anchor: str = "",
    ) -> Path:
        """Generate one scene image via xAI Grok Aurora → save as PNG (1080×1920)."""
        import base64 as _b64

        api_key = os.getenv("XAI_API_KEY")
        if not api_key:
            raise ValueError("XAI_API_KEY not set")

        # Prepend style_anchor if not already embedded
        full_prompt = prompt
        if style_anchor and style_anchor[:25] not in prompt:
            full_prompt = f"{style_anchor}. {prompt}"
        if "9:16" not in full_prompt and "portrait" not in full_prompt.lower():
            full_prompt += ". Vertical 9:16 portrait format, high quality."

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                "https://api.x.ai/v1/images/generations",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "grok-imagine-image",
                    "prompt": full_prompt,
                    "n": 1,
                    "response_format": "b64_json",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        img_b64 = data["data"][0]["b64_json"]
        raw = _b64.b64decode(img_b64)
        out_path = task_dir / f"scene_{scene_index:02d}_image.png"

        from PIL import Image
        from io import BytesIO

        img = Image.open(BytesIO(raw)).convert("RGB")
        img = img.resize((1080, 1920), Image.Resampling.LANCZOS)
        img.save(str(out_path), "PNG")

        logger.info(
            f"  🖼  Scene {scene_index} xAI image: {out_path.name} ({out_path.stat().st_size // 1024}KB)"
        )
        return out_path

    async def generate_scene_video_xai(
        self,
        prompt: str,
        scene_index: int,
        task_dir: Path,
        style_anchor: str = "",
        poll_interval: float = 8.0,
        max_wait: float = 300.0,
    ) -> Path:
        """
        Generate a real AI video clip via xAI grok-imagine-video:
        1. POST /v1/videos/generations → {request_id}
        2. Poll GET /v1/videos/{request_id} until status=done
        3. Download MP4 → save to task_dir

        Returns path to downloaded .mp4 file.
        """
        import time

        api_key = os.getenv("XAI_API_KEY")
        if not api_key:
            raise ValueError("XAI_API_KEY not set")

        full_prompt = prompt
        if style_anchor and style_anchor[:25] not in prompt:
            full_prompt = f"{style_anchor}. {prompt}"
        if "9:16" not in full_prompt and "portrait" not in full_prompt.lower():
            full_prompt += ". Vertical 9:16 portrait, cinematic motion."

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=max_wait + 30) as client:
            # Submit job
            resp = await client.post(
                "https://api.x.ai/v1/videos/generations",
                headers=headers,
                json={"model": "grok-imagine-video", "prompt": full_prompt, "n": 1},
            )
            resp.raise_for_status()
            request_id = resp.json()["request_id"]
            logger.info(f"  🎬 Scene {scene_index} xAI video submitted: {request_id}")

            # Poll for completion
            start = time.time()
            while time.time() - start < max_wait:
                await asyncio.sleep(poll_interval)
                poll = await client.get(
                    f"https://api.x.ai/v1/videos/{request_id}",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                poll.raise_for_status()
                result = poll.json()
                status = result.get("status", "pending")

                if status == "failed":
                    raise RuntimeError(f"xAI video gen failed: {result}")

                if status == "done":
                    video_url = result["video"]["url"]
                    duration = result["video"].get("duration", 0)
                    logger.info(
                        f"  🎬 Scene {scene_index} xAI video ready: {duration}s  → downloading"
                    )

                    # Download MP4
                    dl = await client.get(video_url, timeout=120.0)
                    dl.raise_for_status()
                    out_path = task_dir / f"scene_{scene_index:02d}_xai_video.mp4"
                    out_path.write_bytes(dl.content)
                    size_mb = len(dl.content) / 1_048_576
                    logger.info(
                        f"  ✅ Scene {scene_index} xAI video: {out_path.name} ({size_mb:.1f}MB)"
                    )
                    return out_path

                elapsed = time.time() - start
                logger.info(
                    f"  ⏳ Scene {scene_index} video generating... ({elapsed:.0f}s / {max_wait:.0f}s)"
                )

        raise TimeoutError(
            f"xAI video for scene {scene_index} timed out after {max_wait}s"
        )

    # ── TTS audio ──────────────────────────────────────────────────────────

    async def generate_scene_audio(
        self,
        text: str,
        scene_index: int,
        task_dir: Path,
        tts_provider: str = "edge",  # "edge" | "gemini"
        voice: str = "NM1",  # edge voice key (mapped in EDGE_VOICE_MAP)
        edge_voice: str = "vi-VN-NamMinhNeural",  # edge-tts voice
    ) -> Path:
        """Generate TTS audio for one scene → WAV file."""
        out_path = task_dir / f"scene_{scene_index:02d}_audio.wav"

        if tts_provider == "edge":
            await self._tts_edge(text, edge_voice, out_path)
        elif tts_provider == "gemini":
            await self._tts_gemini(text, scene_index, task_dir, out_path)
        else:
            # fallback to edge-tts
            await self._tts_edge(text, edge_voice, out_path)

        logger.info(f"  🔊 Scene {scene_index} audio: {out_path.name}")
        return out_path

    async def _tts_edge(self, text: str, voice: str, out_path: Path) -> None:
        """Use edge-tts (free Microsoft TTS, multi-language)."""
        import edge_tts  # type: ignore

        communicate = edge_tts.Communicate(text, voice)
        # edge-tts saves as MP3 → convert to WAV with ffmpeg
        mp3_path = out_path.with_suffix(".mp3")
        await communicate.save(str(mp3_path))
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(mp3_path), str(out_path)],
            check=True,
            capture_output=True,
        )
        mp3_path.unlink(missing_ok=True)

    async def _tts_gemini(
        self, text: str, scene_index: int, task_dir: Path, out_path: Path
    ) -> None:
        """Use Gemini TTS (existing google_tts_service, highest quality)."""
        from src.services.google_tts_service import GoogleTTSService

        tts_service = GoogleTTSService()
        audio_data, metadata = await tts_service.generate_audio(
            text=text,
            language="vi-VN",
            voice_name="Enceladus",
            use_pro_model=False,
        )
        out_path.write_bytes(audio_data)

    # ── HTML frame render ──────────────────────────────────────────────────

    async def render_frame(
        self,
        image_path: Path,
        text_overlay: str,
        scene_index: int,
        total_scenes: int,
        video_title: str,
        task_dir: Path,
    ) -> Path:
        """Render HTML frame (image + text overlay) → PNG via Playwright."""
        from playwright.async_api import async_playwright

        out_path = task_dir / f"scene_{scene_index:02d}_frame.png"

        import base64 as _b64

        with open(image_path, "rb") as _imgf:
            _data_uri = "data:image/png;base64," + _b64.b64encode(_imgf.read()).decode()

        html = FRAME_TEMPLATE.format(
            image_path=_data_uri,
            text=text_overlay.replace("<", "&lt;").replace(">", "&gt;"),
            font_size=_calc_font_size(text_overlay),
            scene_num=scene_index + 1,
            total_scenes=total_scenes,
            video_title=video_title[:40].replace("<", "&lt;").replace(">", "&gt;"),
            progress=int((scene_index + 1) / total_scenes * 100),
        )

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
            )
            page = await browser.new_page(viewport={"width": 1080, "height": 1920})
            await page.set_content(html, wait_until="networkidle")
            await page.screenshot(path=str(out_path), type="png")
            await browser.close()

        logger.info(
            f"  🎨 Scene {scene_index} frame: {out_path.name} ({out_path.stat().st_size // 1024}KB)"
        )
        return out_path

    # ── FFmpeg ─────────────────────────────────────────────────────────────

    def create_video_segment(
        self,
        frame_path: Path,
        audio_path: Path,
        scene_index: int,
        task_dir: Path,
    ) -> Path:
        """Combine static frame PNG + audio → MP4 segment."""
        out_path = task_dir / f"scene_{scene_index:02d}_segment.mp4"

        cmd = [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            str(frame_path),
            "-i",
            str(audio_path),
            "-c:v",
            "libx264",
            "-tune",
            "stillimage",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-pix_fmt",
            "yuv420p",
            "-shortest",
            "-movflags",
            "+faststart",
            str(out_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg segment failed: {result.stderr[-500:]}")

        logger.info(f"  🎬 Scene {scene_index} segment: {out_path.name}")
        return out_path

    # Ken Burns motion filter chains: scale to 1.25x then crop with time-varying position
    # FFmpeg crop auto-clamps x/y to valid range — no explicit min/max needed
    _KEN_BURNS = [
        # zoom-in feel: start top-left, drift to center
        "scale=1350:2400,crop=w=1080:h=1920:x=135-t*27:y=240-t*48",
        # zoom-out feel: start center, drift to bottom-right
        "scale=1350:2400,crop=w=1080:h=1920:x=t*27:y=t*48",
        # pan right (L→R)
        "scale=1350:2400,crop=w=1080:h=1920:x=t*54:y=240",
        # pan left (R→L)
        "scale=1350:2400,crop=w=1080:h=1920:x=270-t*54:y=240",
        # tilt up (B→T)
        "scale=1350:2400,crop=w=1080:h=1920:x=135:y=480-t*96",
    ]

    def create_video_segment_ken_burns(
        self,
        frame_path: Path,
        audio_path: Path,
        scene_index: int,
        task_dir: Path,
    ) -> Path:
        """
        Convert rendered frame PNG to motion video using Ken Burns effect.
        Scale to 1.25× then time-varying crop → real camera movement.
        Audio duration determines clip length (-shortest).
        """
        out_path = task_dir / f"scene_{scene_index:02d}_segment.mp4"
        vf = self._KEN_BURNS[scene_index % len(self._KEN_BURNS)]

        cmd = [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            str(frame_path),
            "-i",
            str(audio_path),
            "-filter_complex",
            f"[0:v]{vf}[v]",
            "-map",
            "[v]",
            "-map",
            "1:a",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-shortest",
            "-movflags",
            "+faststart",
            str(out_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg Ken Burns failed: {result.stderr[-500:]}")

        logger.info(f"  🎬 Scene {scene_index} Ken Burns: {out_path.name}")
        return out_path

    def merge_video_with_audio(
        self,
        video_path: Path,
        audio_path: Path,
        scene_index: int,
        task_dir: Path,
    ) -> Path:
        """
        Merge an xAI-generated video clip with TTS audio.
        Re-encodes to 1080x1920 portrait, AAC audio, stops at the shorter of the two streams.
        """
        out_path = task_dir / f"scene_{scene_index:02d}_segment.mp4"
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-i",
            str(audio_path),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-vf",
            "scale=1080:1920:force_original_aspect_ratio=decrease,"
            "pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-shortest",
            "-movflags",
            "+faststart",
            str(out_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg merge failed: {result.stderr[-500:]}")
        logger.info(
            f"  🎬 Scene {scene_index} merged (xAI video+audio): {out_path.name}"
        )
        return out_path

    def concat_segments(
        self,
        segments: List[Path],
        task_dir: Path,
        fade_duration: float = 0.3,
    ) -> Path:
        """Concatenate all segments → final.mp4 with smooth cuts."""
        out_path = task_dir / "final.mp4"

        # Write concat file list
        list_path = task_dir / "filelist.txt"
        with open(list_path, "w") as f:
            for seg in segments:
                f.write(f"file '{str(seg.resolve())}'\n")

        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            str(out_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg concat failed: {result.stderr[-500:]}")

        size_mb = out_path.stat().st_size / 1_048_576
        logger.info(f"  ✂️  Final video: {out_path.name} ({size_mb:.1f}MB)")
        return out_path

    # ── R2 upload ──────────────────────────────────────────────────────────

    async def upload_to_r2(
        self,
        video_path: Path,
        task_id: str,
        user_id: str,
    ) -> str:
        """Upload final.mp4 to R2 → return public URL."""
        from src.services.r2_storage_service import get_r2_service

        r2 = get_r2_service()
        r2_key = f"videos/{user_id}/{task_id}/final.mp4"

        with open(video_path, "rb") as f:
            video_bytes = f.read()

        result = await r2.upload_file(
            file_content=video_bytes,
            r2_key=r2_key,
            content_type="video/mp4",
        )
        return result["public_url"]

    async def upload_asset_to_r2(
        self,
        local_path: Path,
        r2_key: str,
        content_type: str,
    ) -> str:
        """Upload an intermediate asset (image/audio) to R2 → return public URL."""
        from src.services.r2_storage_service import get_r2_service

        r2 = get_r2_service()
        data = local_path.read_bytes()
        result = await r2.upload_file(
            file_content=data,
            r2_key=r2_key,
            content_type=content_type,
        )
        return result["public_url"]

    # ── Video Studio AI Pipeline (generate-story / generate-narration / generate-script) ──

    async def generate_story_from_brief(self, brief: dict) -> dict:
        """
        Step 1a: brief → story structure {title, hook, beats[], tone, pacing}
        Model: deepseek-reasoner, timeout=120s
        """
        prompt = build_generate_story_prompt(brief)
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY not set")

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek-reasoner",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 2000,
                },
            )
            resp.raise_for_status()

        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        reasoning = data["choices"][0]["message"].get("reasoning_content", "")
        if reasoning:
            logger.info(f"  🧠 Story reasoning: {len(reasoning)} chars")

        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
        story = json.loads(content)
        assert "beats" in story and len(story["beats"]) > 0, "No beats returned"
        assert "hook" in story, "No hook returned"
        logger.info(
            f"✅ Story generated: '{story.get('title')}', {len(story['beats'])} beats"
        )
        return story

    async def generate_narration_from_story(self, story: dict, brief: dict) -> dict:
        """
        Step 1b: story beats → narration text {suggestedTitle, narration, hookStrengthScore}
        Model: deepseek-reasoner, timeout=120s
        """
        prompt = build_generate_narration_prompt(story, brief)
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY not set")

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek-reasoner",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 3000,
                },
            )
            resp.raise_for_status()

        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        reasoning = data["choices"][0]["message"].get("reasoning_content", "")
        if reasoning:
            logger.info(f"  🧠 Narration reasoning: {len(reasoning)} chars")

        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
        result = json.loads(content)
        assert result.get("narration"), "Narration is empty"
        logger.info(f"✅ Narration generated: {len(result['narration'])} chars")
        return result

    async def generate_script_from_brief(self, brief: dict, n_scenes: int) -> dict:
        """
        Step 2A: brief (with narration) → N scenes {title, style_anchor, mood, scenes[]}
        Model: deepseek-reasoner, timeout=200s
        """
        assert brief.get(
            "narration"
        ), "narration is required in brief for generate_script_from_brief"
        prompt = build_generate_script_prompt(brief, n_scenes)
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY not set")

        async with httpx.AsyncClient(timeout=200.0) as client:
            resp = await client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek-reasoner",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 8000,
                },
            )
            resp.raise_for_status()

        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        reasoning = data["choices"][0]["message"].get("reasoning_content", "")
        if reasoning:
            logger.info(f"  🧠 Script reasoning: {len(reasoning)} chars")

        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
        result = json.loads(content)
        scenes = result.get("scenes", [])
        assert len(scenes) > 0, "No scenes returned"
        logger.info(
            f"✅ Script generated: '{result.get('title')}', {len(scenes)} scenes"
        )
        return result


# ─────────────────────────────────────────────
# Video Studio Prompt Builders
# ─────────────────────────────────────────────

PURPOSE_TONE = {
    "ads": ("copywriter", "Hấp dẫn, benefit-driven, strong CTA"),
    "storytelling": ("storyteller", "Kể chuyện, cảm xúc, narrative arc"),
    "education": ("educator", "Rõ ràng, từng bước, dễ hiểu"),
    "software_intro": ("product_demo", "Professional, feature-focused, clear"),
    "corporate": ("communications", "Formal, authoritative, credible"),
}

VISUAL_STYLE_ANCHOR = {
    "Realistic Film": "Shot on Sony A7IV, natural film grain, color graded, cinematic depth of field",
    "Animation": "2D animated illustration, flat design, vibrant colors, clean lines",
    "Cinematic": "Hollywood cinematic shot, dramatic lighting, IMAX quality, deep shadows",
    "Documentary": "Documentary photography, natural lighting, candid, journalistic",
    "Minimalist": "Clean minimalist design, white space, bold typography, simple shapes",
    "Corporate": "Corporate photography, professional lighting, business setting, polished",
}

PLATFORM_GUIDANCE = {
    "tiktok": "Hook mạnh ở 3 giây đầu (giật title). Tempo nhanh. Trending style.",
    "youtube_shorts": "Hook ở 5 giây đầu. Mobile-first. Share-worthy ending.",
    "instagram_reels": "Visually stunning. Aesthetic-first. Strong hook. Trend sounds.",
    "youtube": "Intro rõ 15s. Chapters logic. CTA ở cuối. Watch-time optimize.",
}

BEAT_STRUCTURES = {
    "ads": ["hook", "problem", "solution", "proof", "cta"],
    "storytelling": ["hook", "setup", "confrontation", "resolution", "reflection"],
    "education": ["hook", "concept", "explanation", "example", "summary"],
    "software_intro": ["hook", "problem", "feature_demo", "benefit", "cta"],
    "corporate": ["hook", "context", "key_message", "evidence", "conclusion"],
}


def build_generate_story_prompt(brief: dict) -> str:
    purpose = brief["purpose"]
    tone_role, tone_desc = PURPOSE_TONE.get(purpose, ("director", purpose))
    platform = brief.get("platform", "tiktok")
    platform_hint = PLATFORM_GUIDANCE.get(platform, "")
    lang_name = "Tiếng Việt" if brief["language"] == "vi" else "English"
    duration = brief["duration"]

    beats = BEAT_STRUCTURES.get(
        purpose, ["hook", "problem", "insight", "solution", "cta"]
    )
    beat_list = "\n".join([f"  - {b}" for b in beats])
    beat_json_example = ",\n    ".join(
        [f'{{"type": "{b}", "text": "..."}}' for b in beats]
    )

    return f"""You are a professional short-form video script director specializing in {tone_role} content.

TASK: Create a story structure (kịch bản) for a {duration}s video on {platform}.

VIDEO BRIEF:
- Purpose: {purpose} — {tone_desc}
- Main Idea: {brief["prompt"]}
- Platform: {platform}
- Duration: {duration}s
- Language for text: {lang_name}

PLATFORM GUIDANCE: {platform_hint}

BEAT STRUCTURE to follow:
{beat_list}

RULES:
- hook: MUST grab attention in first 2-3 seconds on {platform}
- Each beat: 1-2 punchy concept sentences max (NOT full narration yet)
- tone: overall emotional feel (examples: inspiring, urgent, playful, authoritative)
- pacing: "fast" (TikTok/Shorts) | "medium" (Instagram, YouTube) | "slow" (educational)
- All beat text in {lang_name}

Return ONLY valid JSON:
{{
  "title": "Catchy video title in {lang_name}",
  "hook": "Opening attention-grabber sentence",
  "beats": [
    {beat_json_example}
  ],
  "tone": "inspiring",
  "pacing": "fast"
}}"""


def build_generate_narration_prompt(story: dict, brief: dict) -> str:
    lang_name = "Tiếng Việt" if brief["language"] == "vi" else "English"
    platform = brief.get("platform", "tiktok")
    platform_hint = PLATFORM_GUIDANCE.get(platform, "")
    duration = brief["duration"]
    wpm = 120 if brief["language"] == "vi" else 150
    target_words = int((duration / 60) * wpm)
    beats_text = "\n".join(
        [f"- {b['type'].upper()}: {b['text']}" for b in story.get("beats", [])]
    )

    character_clause = (
        f"Main character/subject: {brief['character']}"
        if brief.get("character")
        else ""
    )
    music_clause = (
        f"Background music mood: {brief['music']}" if brief.get("music") else ""
    )

    return f"""You are a professional voiceover writer.

TASK: Convert a story structure into a natural voiceover narration script.

STORY STRUCTURE:
Title: {story.get("title", "")}
Hook: {story.get("hook", "")}
Beats:
{beats_text}
Tone: {story.get("tone", "")} | Pacing: {story.get("pacing", "")}
{character_clause}
{music_clause}

TARGET:
- Duration: {duration}s → target ~{target_words} words
- Language: {lang_name} ONLY
- Platform: {platform}

PLATFORM GUIDANCE: {platform_hint}

RULES:
- Write CONTINUOUS narration (không chia scene)
- Follow the beat structure — KHÔNG thay đổi ý nghĩa hoặc bỏ beat nào
- Natural spoken language, không phải văn viết formal
- Opening line MUST use the hook as the attention-grabber

Return ONLY valid JSON:
{{
  "suggestedTitle": "{story.get("title", "")}",
  "narration": "Full continuous narration text here...",
  "hookStrengthScore": 0.85
}}"""


def build_generate_script_prompt(brief: dict, n_scenes: int) -> str:
    purpose = brief["purpose"]
    tone_role, tone_desc = PURPOSE_TONE.get(purpose, ("director", purpose))
    visual_base = VISUAL_STYLE_ANCHOR.get(
        brief.get("visualStyle", ""), brief.get("visualStyle", "cinematic")
    )
    platform = brief.get("platform", "tiktok")
    platform_hint = PLATFORM_GUIDANCE.get(platform, "")
    lang_name = "Tiếng Việt" if brief["language"] == "vi" else "English"
    aspect = brief.get("aspectRatio", "9:16")
    duration = brief["duration"]

    character_clause = (
        f"Main character/subject: {brief['character']}"
        if brief.get("character")
        else ""
    )
    music_clause = (
        f"Background music mood: {brief['music']}" if brief.get("music") else ""
    )
    extra_clause = (
        f"Additional instructions: {brief['extraInstructions']}"
        if brief.get("extraInstructions")
        else ""
    )

    return f"""You are a professional short-form video scriptwriter specializing in {tone_role} content.

VIDEO BRIEF:
- Purpose: {purpose} ({tone_desc})
- Main Idea: {brief["prompt"]}
- Platform: {platform} | Aspect Ratio: {aspect}
- Visual Style: {brief.get("visualStyle", "Cinematic")} — Base: "{visual_base}"
- Duration: {duration}s | Scenes: {n_scenes} (each ~{duration // n_scenes}s)
- Language for narration: {lang_name}
{character_clause}
{music_clause}
{extra_clause}

PLATFORM GUIDANCE: {platform_hint}

NARRATION (pre-written, do NOT change):
---
{brief["narration"]}
---

TASK: Split the narration into exactly {n_scenes} scenes and generate visual details for each.

STYLE_ANCHOR RULES:
- Write 1 English sentence describing CONSISTENT visual style for ALL scenes
- Include: visual_style aesthetic, aspect ratio ({aspect}), color palette, character appearance (if any)
- All image_prompt MUST START with this style_anchor

SCENE RULES:
- narration: {lang_name}. Assign a logical portion of the full narration. Do NOT change meaning.
- image_prompt: English only. Start with [style_anchor]. Add scene-specific visual description.
- text_overlay: {lang_name}. Max 12 words. Key phrase from this scene.
- camera_motion: one of: static | slow_zoom_in | slow_zoom_out | pan_left | pan_right | tilt_up
- emotion: emotional tone of this scene (e.g. curious, confident, inspired, urgent)
- duration_estimate: integer seconds (~{duration // n_scenes})

SPECIAL: Scene 0 MUST have a strong hook/attention-grabber for {platform}.

Return ONLY valid JSON (no markdown, no explanation):
{{
  "title": "Video title in {lang_name}",
  "style_anchor": "...",
  "mood": "overall mood in English",
  "scenes": [
    {{
      "scene_index": 0,
      "narration": "...",
      "image_prompt": "[style_anchor]. Scene-specific description...",
      "text_overlay": "...",
      "camera_motion": "slow_zoom_in",
      "emotion": "curious",
      "duration_estimate": {duration // n_scenes}
    }}
  ]
}}"""


_service_instance: Optional[VideoGenerationService] = None


def get_video_generation_service() -> VideoGenerationService:
    global _service_instance
    if _service_instance is None:
        _service_instance = VideoGenerationService()
    return _service_instance
