"""
Gemini Image Editing Service

Provides image editing capabilities using Google Gemini 3 Pro Image:
- Style Transfer: Apply artistic styles to images
- Object Edit: Modify specific objects in images
- Inpainting: Add/remove elements in masked areas
- Composition: Combine multiple images cohesively

All edited images are:
- Uploaded to Cloudflare R2 storage
- Saved to user's library (library_files collection)
- Tracked with metadata for reference
"""

import os
import time
import uuid
import logging
from typing import Optional, List, Dict, Any, BinaryIO
from fastapi import UploadFile, HTTPException
from PIL import Image
import io
import boto3
from botocore.exceptions import ClientError
from google import genai
from google.genai import types

from src.database.db_manager import DBManager
from src.utils.logger import setup_logger

logger = setup_logger()


# Gemini Model Configuration for Image Editing
# Using Gemini 2.5 Flash Image for image generation/editing capabilities
GEMINI_MODEL = "gemini-2.5-flash-image"

# Style Definitions for Image Editing
STYLE_DEFINITIONS = {
    "Van Gogh": "Post-impressionist style with distinctive swirling brushstrokes, vivid colors and intense emotions.",
    "Picasso": "Cubist style with fragmented forms, multiple perspectives and abstract representation.",
    "Monet": "Impressionist style with natural light, soft brushstrokes and blended colors.",
    "Pop Art": "Vibrant colors, high contrast, mass culture style with bold printed outlines.",
    "Watercolor": "Transparent watercolor effect with soft color bleeds, gentle outlines and airy feeling.",
    "Oil Painting": "Thick oil paint strokes, rich texture, deep colors and classical depth.",
    "Sketch": "Pencil or charcoal sketch with free lines, black and white tones and draft feeling.",
    "Anime: Shonen": "Dynamic, powerful, action-oriented. Sharp lines, determined poses and expressions.",
    "Anime: Shojo": "Romantic, gentle, delicate beauty. Large sparkling eyes, intricate details, bright colors.",
    "Anime: Seinen": "High-quality realistic anime style. Complex details, realistic body proportions, refined lines, cinematic lighting.",
    "Anime: Chibi": "Big head, small body, cute and adorable. Perfect for selfies and cute expressions.",
    "Anime: Manga": "Traditional manga style, black and white with screening, paper drawing effect.",
    "Anime: Studio Ghibli": "Beautiful natural scenery, soft film colors, simple yet lively characters.",
    "Anime: Cyberpunk": "Futuristic high-tech. Neon lights, mechanical details, digital effects.",
    "Anime: Dark Fantasy": "Mysterious, atmospheric, dark fantasy style. Dark colors, strong contrast, magic and supernatural elements.",
    "Anime: Watercolor": "Watercolor effect with soft bleeds, blurred outlines, clear and dreamy feeling.",
    "Anime: Pixel Art": "Early video game graphics simulation. Large pixel blocks, retro nostalgic style.",
    "3D: Final Fantasy": "High-detail 3D with JRPG style. 3D anime characters, cinematic lighting, intricate textures.",
    "3D: Marvel Comics": "Marvel superhero 3D style. Muscular physique, heroic poses, powerful energy effects.",
    # Aliases for common naming variations
    "Cyberpunk": "Futuristic high-tech. Neon lights, mechanical details, digital effects.",
    "Studio Ghibli": "Beautiful natural scenery, soft film colors, simple yet lively characters.",
    "Chibi": "Big head, small body, cute and adorable. Perfect for selfies and cute expressions.",
    "Dark Fantasy": "Mysterious dark, sometimes scary. Dark colors, strong contrast, magic and monster elements.",
}


class GeminiImageEditService:
    """Service for editing images using Gemini 3 Pro Image via Vertex AI"""

    def __init__(self):
        """Initialize Gemini AI Studio client and database"""
        # Initialize Gemini AI Studio client for image editing
        # Use GEMINI_API_KEY2 to avoid rate limiting on primary key
        gemini_api_key = os.getenv("GEMINI_API_KEY2") or os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            raise ValueError("GEMINI_API_KEY2 or GEMINI_API_KEY environment variable not set")

        # Initialize Gemini AI Studio client
        # Using AI Studio API (not Vertex AI) for better model availability
        try:
            # Using AI Studio (without vertexai=True) for global model access
            self.client = genai.Client(
                api_key=gemini_api_key,
            )
            logger.info("✅ Gemini AI Studio client initialized (using GEMINI_API_KEY2)")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Gemini client: {e}")
            raise

        # Initialize database
        db_manager = DBManager()
        self.db = db_manager.db

        # R2 Storage configuration
        self.r2_account_id = os.getenv("R2_ACCOUNT_ID")
        self.r2_access_key = os.getenv("R2_ACCESS_KEY_ID")
        self.r2_secret_key = os.getenv("R2_SECRET_ACCESS_KEY")
        self.r2_bucket_name = os.getenv("R2_BUCKET_NAME", "wordai")
        self.r2_public_url = os.getenv("R2_PUBLIC_URL", "https://static.wordai.pro")

        # Initialize R2 client
        self.r2_client = boto3.client(
            "s3",
            endpoint_url=f"https://{self.r2_account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=self.r2_access_key,
            aws_secret_access_key=self.r2_secret_key,
            region_name="auto",
        )

    def _convert_to_rgb_if_needed(self, image: Image.Image) -> Image.Image:
        """
        Convert image to RGB if it has an alpha channel (RGBA, LA, P with transparency)
        JPEG format does not support transparency, so we need RGB

        Args:
            image: PIL Image object

        Returns:
            PIL Image in RGB mode
        """
        if image.mode in ("RGBA", "LA", "P"):
            logger.info(
                f"🔄 Converting image from {image.mode} to RGB for JPEG compatibility"
            )
            # Create white background
            rgb_image = Image.new("RGB", image.size, (255, 255, 255))
            # Paste image on white background (handles transparency)
            if image.mode == "P":
                image = image.convert("RGBA")
            rgb_image.paste(
                image, mask=image.split()[-1] if image.mode in ("RGBA", "LA") else None
            )
            return rgb_image
        elif image.mode != "RGB":
            logger.info(f"🔄 Converting image from {image.mode} to RGB")
            return image.convert("RGB")
        return image

    def _build_edit_prompt(
        self,
        edit_type: str,
        params: Dict[str, Any],
        has_mask: bool = False,
        num_additional_images: int = 0,
    ) -> str:
        """
        Build Gemini prompt for image editing operations

        Args:
            edit_type: Type of edit (style_transfer, object_edit, inpainting, composition)
            params: Request parameters
            has_mask: Whether a mask image is provided (for inpainting)
            num_additional_images: Number of additional overlay images (for composition)

        Returns:
            Formatted prompt string
        """
        if edit_type == "style_transfer":
            strength = params.get("strength", 80)
            preserve = params.get("preserve_structure", True)
            style = params.get("target_style")
            aspect_ratio = params.get("aspect_ratio", "1:1")

            # Get detailed style definition
            style_description = STYLE_DEFINITIONS.get(
                style, f"the artistic style of {style}"
            )

            # Build comprehensive prompt with style details
            prompt = "Act as an expert digital artist. "
            prompt += f"Generate a new image based on the provided input image, transforming it into the style of '{style}'.\n"
            prompt += f"Style Description: {style_description}\n"

            if preserve:
                prompt += "CRITICAL INSTRUCTION: Preserve the original composition, subject pose, and structural layout exactly as they are. Only change the artistic style, textures, and lighting. "
            else:
                prompt += "You may adapt the composition slightly to better fit the artistic style, but keep the main subject recognizable. "

            prompt += f"Style Strength: {strength}%. "

            if strength >= 80:
                prompt += "Apply the style aggressively. The final image should look like a complete artwork in this style, not just a filter. "
            elif strength <= 40:
                prompt += "Apply the style subtly. The original photo realism should still be visible, with just a hint of the artistic style. "
            else:
                prompt += (
                    "Balance the original image details with the new artistic style. "
                )

            prompt += f"Output Aspect Ratio: {aspect_ratio}. "
            prompt += "Ensure high quality, detailed rendering, and consistent artistic application across the entire image. "
            prompt += "The output MUST be a new image with the requested style applied, not just a copy of the original. "
            prompt += "Make the style transformation obvious and distinct. "

            # Add unique identifier to prevent caching
            prompt += f" [Request ID: {uuid.uuid4()}]"

        elif edit_type == "object_edit":
            target = params.get("target_object")
            modification = params.get("modification")
            preserve_bg = params.get("preserve_background", True)

            prompt = f"Using the provided image, identify {target} and {modification}. "
            if preserve_bg:
                prompt += "Keep the rest of the image completely unchanged, including lighting, shadows, and background. "
            prompt += (
                "Ensure the edited object looks natural and realistic in the scene. "
            )
            prompt += (
                "Match lighting, perspective, and scale of the surrounding elements. "
            )
            prompt += "Blend seamlessly with no visible editing artifacts."

        elif edit_type == "inpainting":
            action = params.get("action", "add")
            prompt_text = params.get("prompt")
            blend_mode = params.get("blend_mode", "natural")

            if action == "remove":
                prompt = f"Remove the following from the image: {prompt_text}. "
                prompt += "Fill the area with appropriate background that matches the surrounding scene. "
                prompt += "Ensure seamless blending with no visible gaps or artifacts."
            elif action == "add":
                prompt = f"Add the following to the image: {prompt_text}. "
                if has_mask:
                    prompt += "Place it in the indicated area. "
                prompt += f"Blend it {blend_mode}ly with the existing scene. "
                prompt += (
                    "Match lighting, shadows, and perspective of the original image. "
                )
                prompt += "Ensure realistic integration."
            else:  # replace
                prompt = f"Replace the indicated area with: {prompt_text}. "
                prompt += f"Blend {blend_mode}ly with surrounding elements. "
                prompt += "Maintain consistent lighting and style."

        elif edit_type == "composition":
            composition_prompt = params.get("prompt")
            style = params.get("composition_style", "realistic")
            adjust_lighting = params.get("lighting_adjustment", True)

            # Build detailed composition prompt with clear image references
            prompt = "You are an expert image compositor specializing in virtual try-on and product visualization.\n\n"
            prompt += "**IMAGES PROVIDED:**\n"
            prompt += (
                "- Image 1 (BASE): The main subject (e.g., model, person, background)\n"
            )

            # Check if we have additional images
            if num_additional_images > 0:
                for i in range(num_additional_images):
                    prompt += f"- Image {i + 2} (OVERLAY): Element to integrate (e.g., clothing, product, accessory)\n"

            prompt += f"\n**YOUR TASK:** {composition_prompt}\n\n"
            prompt += f"**Composition Style:** {style}\n"

            if style == "realistic":
                prompt += "- Create a photorealistic result with natural lighting and shadows\n"
                prompt += "- Match color temperature and tone across all elements\n"
                prompt += "- Ensure realistic depth and perspective\n"
                prompt += "- Make it look like a professional photograph\n"
            elif style == "artistic":
                prompt += "- Create a creative, stylized composition\n"
                prompt += "- Use artistic color grading and effects\n"
                prompt += "- Allow for creative interpretation\n"
            elif style == "professional":
                prompt += "- Create e-commerce/marketing quality composition\n"
                prompt += "- Studio lighting with clean, professional look\n"
                prompt += (
                    "- Perfect for product photography or professional portraits\n"
                )
            elif style == "collage":
                prompt += "- Create an artistic collage style\n"
                prompt += (
                    "- Blend elements creatively with visible edges or transitions\n"
                )
                prompt += "- Artistic and expressive composition\n"

            prompt += "\n**CRITICAL REQUIREMENTS:**\n"
            prompt += "1. **Seamless Integration**: Combine elements from ALL provided images naturally\n"
            prompt += "2. **Preserve Identity**: Keep the identity and key features of the base subject (Image 1)\n"
            prompt += "3. **Transfer Elements**: Apply clothing/products from overlay images (Image 2+) to the base subject\n"

            if adjust_lighting:
                prompt += "4. **Unified Lighting**: Adjust lighting, shadows, and highlights to create a cohesive scene\n"
                prompt += "   - Match color balance and tone across all elements\n"
                prompt += "   - Ensure consistent light direction and intensity\n"
                prompt += (
                    "   - Add realistic shadows and highlights where elements meet\n"
                )

            prompt += "5. **Perfect Fit**: Ensure clothing/products fit naturally on the subject's body\n"
            prompt += "   - Adapt to body shape and pose\n"
            prompt += "   - Show natural folds and wrinkles\n"
            prompt += "   - Respect perspective and depth\n"
            prompt += "6. **Clean Result**: Remove any visible seams, boundaries, or artifacts\n"
            prompt += "7. **Professional Quality**: Create a polished, publication-ready final image\n\n"

            prompt += "**IMPORTANT:** Generate a NEW composed image where the base subject (Image 1) is wearing/using elements from overlay images (Image 2+). "
            prompt += "The result should look natural and professional, as if photographed together originally."

        else:
            raise ValueError(f"Unknown edit type: {edit_type}")

        # Add negative prompt if provided
        negative = params.get("negative_prompt")
        if negative:
            prompt += f"\nNegative Prompt (Avoid these elements): {negative}."

        return prompt

    async def edit_image(
        self,
        edit_type: str,
        user_id: str,
        original_image: UploadFile,
        params: Dict[str, Any],
        additional_images: Optional[List[UploadFile]] = None,
        mask_image: Optional[UploadFile] = None,
    ) -> Dict[str, Any]:
        """
        Edit an image using Gemini API

        Args:
            edit_type: Type of edit operation
            user_id: User ID for storage
            original_image: Original image to edit
            params: Edit parameters
            additional_images: Additional images for composition
            mask_image: Mask image for inpainting

        Returns:
            Dict with image_url, file_id, and metadata
        """
        start_time = time.time()

        logger.info(f"🚀 Starting {edit_type} operation for user {user_id}")

        try:
            # Read and validate original image
            original_bytes = await original_image.read()
            original_pil = Image.open(io.BytesIO(original_bytes))
            logger.info(
                f"🖼️ Original image loaded: {original_pil.size} ({original_pil.mode})"
            )

            # Count additional images for prompt building
            num_additional = len(additional_images) if additional_images else 0

            # Build prompt
            prompt = self._build_edit_prompt(
                edit_type,
                params,
                has_mask=mask_image is not None,
                num_additional_images=num_additional,
            )
            logger.info(f"📝 Generated prompt: {prompt[:200]}...")

            # Prepare reference images for new API
            reference_images = []
            next_ref_id = 1

            # Convert original PIL image to bytes for API
            # ✅ FIX: Convert RGBA to RGB before saving as JPEG
            original_pil = self._convert_to_rgb_if_needed(original_pil)
            original_img_bytes = io.BytesIO()
            original_pil.save(original_img_bytes, format="JPEG")
            original_img_bytes = original_img_bytes.getvalue()

            # Add original image as base reference (RawReferenceImage for editing)
            reference_images.append(
                types.RawReferenceImage(
                    reference_image=types.Image(
                        image_bytes=original_img_bytes, mime_type="image/jpeg"
                    ),
                    reference_id=next_ref_id,
                )
            )
            next_ref_id += 1

            # Add mask image if provided (for inpainting)
            if mask_image:
                mask_bytes = await mask_image.read()
                mask_pil = Image.open(io.BytesIO(mask_bytes))

                # Convert mask PIL to bytes
                mask_img_bytes = io.BytesIO()
                mask_pil.save(mask_img_bytes, format="PNG")
                mask_img_bytes = mask_img_bytes.getvalue()

                reference_images.append(
                    types.MaskReferenceImage(
                        reference_image=types.Image(
                            image_bytes=mask_img_bytes, mime_type="image/png"
                        ),
                        reference_id=next_ref_id,
                    )
                )
                next_ref_id += 1
                logger.info(f"🎭 Mask image added: {mask_pil.size}")

            # Add additional images if provided (for composition)
            additional_img_bytes_list = []  # Store for later use in contents
            if additional_images:
                logger.info(f"🖼️ Adding {len(additional_images)} additional images")
                for idx, img in enumerate(additional_images):
                    img_bytes = await img.read()
                    img_pil = Image.open(io.BytesIO(img_bytes))

                    # Convert PIL to bytes
                    # ✅ FIX: Convert RGBA to RGB before saving as JPEG
                    img_pil = self._convert_to_rgb_if_needed(img_pil)
                    add_img_bytes = io.BytesIO()
                    img_pil.save(add_img_bytes, format="JPEG")
                    add_img_bytes = add_img_bytes.getvalue()

                    # Store for sending to API
                    additional_img_bytes_list.append(add_img_bytes)

                    reference_images.append(
                        types.StyleReferenceImage(
                            reference_image=types.Image(
                                image_bytes=add_img_bytes, mime_type="image/jpeg"
                            ),
                            reference_id=next_ref_id,
                        )
                    )
                    next_ref_id += 1
                    logger.info(f"   - Overlay {idx + 1}: {img_pil.size}")

            # Get aspect ratio configuration
            aspect_ratio = params.get("aspect_ratio", "1:1")
            aspect_ratio_map = {
                "1:1": "1:1",
                "16:9": "16:9",
                "9:16": "9:16",
                "4:3": "4:3",
                "3:4": "3:4",
            }
            gemini_aspect_ratio = aspect_ratio_map.get(aspect_ratio, "1:1")
            logger.info(f"📊 Aspect ratio: {aspect_ratio} -> {gemini_aspect_ratio}")

            # Call Gemini API with generate_content method (Gemini 2.5 Flash Image)
            logger.info(f"🤖 Calling Gemini API: {GEMINI_MODEL}")

            # Run in thread pool to avoid blocking event loop
            import asyncio

            loop = asyncio.get_event_loop()

            # Construct contents for generate_content
            contents = []

            # ✅ CRITICAL FIX: Add ALL images to contents (not just original)
            # Add original/base image (Image 1)
            contents.append(
                types.Part.from_bytes(data=original_img_bytes, mime_type="image/jpeg")
            )

            # Add overlay images (Image 2, 3, ...) for composition
            if additional_img_bytes_list:
                logger.info(
                    f"📎 Adding {len(additional_img_bytes_list)} overlay images to API contents"
                )
                for idx, overlay_bytes in enumerate(additional_img_bytes_list):
                    contents.append(
                        types.Part.from_bytes(
                            data=overlay_bytes, mime_type="image/jpeg"
                        )
                    )
                    logger.info(f"   ✅ Overlay {idx + 1} added to contents")

            # Add prompt (should be last to reference all images)
            contents.append(prompt)

            logger.info(
                f"📦 Total contents parts: {len(contents)} ({len(contents) - 1} images + 1 prompt)"
            )

            # Retry logic for API calls
            max_retries = 2
            response = None

            for attempt in range(max_retries):
                try:
                    logger.info(
                        f"🤖 Calling Gemini API: {GEMINI_MODEL} (Attempt {attempt + 1}/{max_retries})"
                    )
                    response = await loop.run_in_executor(
                        None,
                        lambda: self.client.models.generate_content(
                            model=GEMINI_MODEL,
                            contents=contents,
                            config=types.GenerateContentConfig(
                                response_modalities=["IMAGE", "TEXT"],
                                safety_settings=[
                                    types.SafetySetting(
                                        category="HARM_CATEGORY_HATE_SPEECH",
                                        threshold="BLOCK_ONLY_HIGH",
                                    ),
                                    types.SafetySetting(
                                        category="HARM_CATEGORY_DANGEROUS_CONTENT",
                                        threshold="BLOCK_ONLY_HIGH",
                                    ),
                                    types.SafetySetting(
                                        category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                                        threshold="BLOCK_ONLY_HIGH",
                                    ),
                                    types.SafetySetting(
                                        category="HARM_CATEGORY_HARASSMENT",
                                        threshold="BLOCK_ONLY_HIGH",
                                    ),
                                ],
                            ),
                        ),
                    )

                    # Check if we got a valid response with content
                    if response.candidates and response.candidates[0].content:
                        logger.info(
                            f"✅ Gemini API response received successfully on attempt {attempt + 1}"
                        )
                        break

                    # If we got a response but no content (e.g. safety block or other reason)
                    finish_reason = (
                        response.candidates[0].finish_reason
                        if response.candidates
                        else "UNKNOWN"
                    )
                    logger.warning(
                        f"⚠️ Attempt {attempt + 1} failed. Finish reason: {finish_reason}"
                    )

                    if attempt < max_retries - 1:
                        time.sleep(1)

                except Exception as e:
                    logger.error(f"❌ Attempt {attempt + 1} exception: {e}")
                    if attempt == max_retries - 1:
                        raise
                    time.sleep(1)

            # Debug logging
            logger.info(
                f"🔍 Response structure: candidates={len(response.candidates) if response.candidates else 0}"
            )
            if response.candidates:
                candidate = response.candidates[0]
                logger.info(f"🔍 Candidate finish_reason: {candidate.finish_reason}")
                if candidate.content and candidate.content.parts:
                    logger.info(f"🔍 Content parts: {len(candidate.content.parts)}")
                    # Log part types without printing full binary data
                    for i, part in enumerate(candidate.content.parts):
                        if hasattr(part, "text") and part.text:
                            logger.info(f"   Part {i}: text ({len(part.text)} chars)")
                        elif hasattr(part, "inline_data") and part.inline_data:
                            logger.info(
                                f"   Part {i}: inline_data ({part.inline_data.mime_type})"
                            )
                else:
                    logger.warning("🔍 No content parts in response")

            # Extract image from response
            image_bytes = None
            if response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]

                # Check if content exists
                if not candidate.content:
                    logger.error(
                        f"❌ No content in response. Finish reason: {candidate.finish_reason}"
                    )
                    raise HTTPException(
                        status_code=500,
                        detail=f"No content generated. Reason: {candidate.finish_reason}",
                    )

                # Check if parts exist
                if not candidate.content.parts:
                    logger.error(
                        f"❌ No parts in content. Finish reason: {candidate.finish_reason}"
                    )
                    raise HTTPException(
                        status_code=500,
                        detail=f"No content parts generated. Reason: {candidate.finish_reason}",
                    )

                # Extract image
                for part in candidate.content.parts:
                    if hasattr(part, "inline_data") and part.inline_data:
                        logger.info(f"🖼️ Image extracted from response (inline_data)")
                        image_bytes = part.inline_data.data
                        logger.info(
                            f"📦 Image bytes size: {len(image_bytes) // 1024}KB"
                        )
                        break

            if not image_bytes:
                logger.error("❌ No image generated from Gemini API")
                raise HTTPException(
                    status_code=500, detail="No image generated from Gemini API"
                )

            generation_time = time.time() - start_time
            logger.info(f"⏱️ Generation time: {generation_time:.2f}s")

            # Upload to R2 and save to library
            logger.info("📤 Uploading to R2...")
            file_data = await self.upload_to_r2(image_bytes, user_id)
            file_size = len(image_bytes)

            # Determine points cost based on edit type
            points_map = {
                "style_transfer": 2,
                "object_edit": 3,
                "inpainting": 3,
                "composition": 5,
            }
            points_used = points_map.get(edit_type, 3)

            # Save to library
            logger.info(f"💾 Saving to library (points: {points_used})...")
            library_data = await self.save_to_library(
                user_id=user_id,
                file_url=file_data["file_url"],
                r2_key=file_data["r2_key"],
                file_size=file_size,
                edit_type=edit_type,
                metadata={
                    "prompt": prompt,
                    "edit_type": edit_type,
                    "aspect_ratio": aspect_ratio,
                    "model": GEMINI_MODEL,
                    "generation_time": round(generation_time, 2),
                    "file_size": file_size,
                    "points_used": points_used,
                    "original_image_count": 1
                    + (len(additional_images) if additional_images else 0),
                    "request_params": params,
                },
            )

            logger.info(
                f"✅ Edit complete! File ID: {library_data['file_id']}, URL: {file_data['file_url']}"
            )

            return {
                "image_url": file_data["file_url"],
                "file_id": library_data["file_id"],
                "edit_type": edit_type,
                "metadata": {
                    "prompt": prompt,
                    "aspect_ratio": aspect_ratio,
                    "model": GEMINI_MODEL,
                    "generation_time": round(generation_time, 2),
                    "file_size": file_size,
                    "points_used": points_used,
                },
            }

        except Exception as e:
            logger.error(f"❌ Image editing failed: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Image editing failed: {str(e)}"
            )

    async def upload_to_r2(self, image_bytes: bytes, user_id: str) -> Dict[str, str]:
        """
        Upload edited image to Cloudflare R2 storage

        Args:
            image_bytes: Image data as bytes
            user_id: User ID for folder organization

        Returns:
            Dict with file_url and r2_key
        """
        try:
            # Generate unique filename
            filename = f"{int(time.time())}_{uuid.uuid4().hex[:8]}.jpg"
            r2_key = f"ai-edited-images/{user_id}/{filename}"

            logger.info(f"☁️ Uploading to R2: {r2_key}")

            # Upload to R2
            self.r2_client.put_object(
                Bucket=self.r2_bucket_name,
                Key=r2_key,
                Body=image_bytes,
                ContentType="image/jpeg",
            )

            # Construct public URL
            file_url = f"{self.r2_public_url}/{r2_key}"

            logger.info(f"✅ R2 upload complete: {file_url}")

            return {
                "file_url": file_url,
                "r2_key": r2_key,
            }

        except ClientError as e:
            logger.error(f"❌ R2 upload failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"R2 upload failed: {str(e)}")

    async def save_to_library(
        self,
        user_id: str,
        file_url: str,
        r2_key: str,
        file_size: int,
        edit_type: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Save edited image metadata to user's library

        Args:
            user_id: User ID
            file_url: Public URL of the image
            r2_key: R2 storage key
            file_size: File size in bytes
            edit_type: Type of edit operation
            metadata: Edit metadata

        Returns:
            Dict with file_id and library document
        """
        try:
            file_id = f"file_{uuid.uuid4().hex}"

            library_doc = {
                "file_id": file_id,
                "library_id": file_id,
                "user_id": user_id,
                "filename": r2_key.split("/")[-1],
                "original_name": r2_key.split("/")[-1],
                "file_type": "image/jpeg",
                "file_size": file_size,
                "folder_id": None,
                "r2_key": r2_key,
                "file_url": file_url,
                "category": "images",
                "sub_category": "ai_edited",
                "description": f"AI-edited image ({edit_type})",
                "tags": ["ai-edited", edit_type, "gemini"],
                "metadata": metadata,
                "is_deleted": False,
                "deleted_at": None,
                "uploaded_at": metadata.get("created_at", time.time()),
                "updated_at": time.time(),
            }

            # Insert into library_files collection
            self.db.library_files.insert_one(library_doc)

            return {"file_id": file_id, "library_doc": library_doc}

        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to save to library: {str(e)}"
            )
