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


# Gemini Model Configuration
GEMINI_MODEL = "gemini-3-pro-image-preview"


class GeminiImageEditService:
    """Service for editing images using Gemini 3 Pro Image"""

    def __init__(self):
        """Initialize Gemini client and database"""
        # Initialize Gemini API client
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")

        self.client = genai.Client(api_key=api_key)

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

    def _build_edit_prompt(
        self, edit_type: str, params: Dict[str, Any], has_mask: bool = False
    ) -> str:
        """
        Build Gemini prompt for image editing operations

        Args:
            edit_type: Type of edit (style_transfer, object_edit, inpainting, composition)
            params: Request parameters
            has_mask: Whether a mask image is provided (for inpainting)

        Returns:
            Formatted prompt string
        """
        if edit_type == "style_transfer":
            strength = params.get("strength", 80)
            preserve = params.get("preserve_structure", True)
            style = params.get("target_style")

            prompt = (
                f"Transform the provided image into the artistic style of {style}. "
            )
            if preserve:
                prompt += "Preserve the original composition, layout, and structure of the scene. "
            prompt += f"Style strength: {strength}%. "
            if strength > 80:
                prompt += "Apply bold, dramatic stylistic changes. "
            elif strength < 40:
                prompt += (
                    "Apply subtle stylistic hints while keeping it mostly realistic. "
                )
            else:
                prompt += "Balance between original and stylized aesthetic. "

            prompt += "Ensure all elements are rendered in the target style with consistent artistic treatment. "
            prompt += "Maintain image quality and clarity."

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

            prompt = f"Combine the provided images to create: {composition_prompt}. "
            prompt += f"Composition style: {style}. "
            if adjust_lighting:
                prompt += "Adjust lighting, shadows, and color balance across all elements to create a cohesive, realistic scene. "
            prompt += "Ensure seamless integration between all image elements. "
            prompt += "Match perspectives and scales appropriately. "
            prompt += "Create a professional, polished final composition."

        else:
            raise ValueError(f"Unknown edit type: {edit_type}")

        # Add negative prompt if provided
        negative = params.get("negative_prompt")
        if negative:
            prompt += f" Avoid: {negative}."

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

            # Build prompt
            prompt = self._build_edit_prompt(
                edit_type, params, has_mask=mask_image is not None
            )
            logger.info(f"📝 Generated prompt: {prompt[:200]}...")

            # Prepare reference images for new API
            reference_images = []

            # Add original image as base reference (RawReferenceImage for editing)
            reference_images.append(
                types.RawReferenceImage(
                    reference_image=types.Image(image=original_pil),
                )
            )

            # Add mask image if provided (for inpainting)
            if mask_image:
                mask_bytes = await mask_image.read()
                mask_pil = Image.open(io.BytesIO(mask_bytes))
                reference_images.append(
                    types.MaskReferenceImage(
                        reference_image=types.Image(image=mask_pil),
                    )
                )
                logger.info(f"🎭 Mask image added: {mask_pil.size}")

            # Add additional images if provided (for composition)
            if additional_images:
                logger.info(f"🖼️ Adding {len(additional_images)} additional images")
                for img in additional_images:
                    img_bytes = await img.read()
                    img_pil = Image.open(io.BytesIO(img_bytes))
                    reference_images.append(
                        types.StyleReferenceImage(
                            reference_image=types.Image(image=img_pil),
                        )
                    )
                    logger.info(f"   - Image: {img_pil.size}")

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

            # Call Gemini API with new edit_image method
            logger.info(f"🤖 Calling Gemini API: {GEMINI_MODEL}")

            # Determine edit mode based on edit type
            edit_mode_map = {
                "style_transfer": types.EditMode.EDIT_MODE_STYLE,
                "object_edit": types.EditMode.EDIT_MODE_CONTROLLED_EDITING,
                "inpainting": (
                    types.EditMode.EDIT_MODE_INPAINT_INSERTION
                    if params.get("action") == "add"
                    else types.EditMode.EDIT_MODE_INPAINT_REMOVAL
                ),
                "composition": types.EditMode.EDIT_MODE_PRODUCT_IMAGE,
            }
            edit_mode = edit_mode_map.get(edit_type, types.EditMode.EDIT_MODE_DEFAULT)
            logger.info(f"🎨 Edit mode: {edit_mode}")

            response = self.client.models.edit_image(
                model=GEMINI_MODEL,
                prompt=prompt,
                reference_images=reference_images,
                config=types.EditImageConfig(
                    aspect_ratio=gemini_aspect_ratio,
                    edit_mode=edit_mode,
                ),
            )
            logger.info(f"✅ Gemini API response received")

            # Extract image from response
            image_bytes = None
            if response.generated_images:
                generated_image = response.generated_images[0]
                # Get image from response
                if hasattr(generated_image, "image"):
                    gemini_image = generated_image.image
                    logger.info(f"🖼️ Image extracted from response")
                    # Convert PIL Image to bytes
                    img_byte_arr = io.BytesIO()
                    gemini_image.save(img_byte_arr, format="JPEG", quality=95)
                    image_bytes = img_byte_arr.getvalue()
                    logger.info(f"📦 Image bytes size: {len(image_bytes) // 1024}KB")
                else:
                    logger.error("❌ Generated image has no image data")

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
