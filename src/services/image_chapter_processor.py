"""
Image Chapter Processor Service
Process image files into chapter pages for manga, comics, photo books

Phase 2: Image Pages Support
"""

import os
import io
import logging
import tempfile
import zipfile
import shutil
from typing import List, Dict, Any, Tuple, Optional
from PIL import Image

logger = logging.getLogger("chatbot")


class ImageChapterProcessor:
    """Process image files into chapter pages (manga, comics, photo books)"""

    # Supported image formats
    SUPPORTED_FORMATS = [".jpg", ".jpeg", ".png", ".webp", ".gif"]

    def __init__(self, s3_client, r2_bucket: str, cdn_base_url: str):
        """
        Initialize Image processor

        Args:
            s3_client: Boto3 S3 client for R2 uploads
            r2_bucket: R2 bucket name
            cdn_base_url: CDN base URL (e.g., https://cdn.wordai.com)
        """
        self.s3_client = s3_client
        self.r2_bucket = r2_bucket
        self.cdn_base_url = cdn_base_url

    async def process_images_to_pages(
        self,
        image_paths: List[str],
        user_id: str,
        chapter_id: str,
        preserve_order: bool = True,
    ) -> Dict[str, Any]:
        """
        Convert image files to pages array

        Args:
            image_paths: List of local image file paths
            user_id: User ID for R2 path organization
            chapter_id: Chapter ID for R2 path organization
            preserve_order: Keep files in provided order (True for manga)

        Returns:
            {
                "pages": [{page_number, background_url, width, height, elements: []}],
                "total_pages": 24
            }
        """
        try:
            logger.info(f"🎨 [IMAGE_PROCESSOR] Processing {len(image_paths)} images")
            logger.info(f"   User: {user_id}, Chapter: {chapter_id}")

            # 1. Load images and validate
            images = []
            for idx, path in enumerate(image_paths, 1):
                try:
                    img = Image.open(path)
                    # Convert to RGB if needed (for PNG with transparency)
                    if img.mode in ("RGBA", "LA", "P"):
                        background = Image.new("RGB", img.size, (255, 255, 255))
                        if img.mode == "P":
                            img = img.convert("RGBA")
                        background.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
                        img = background
                    elif img.mode != "RGB":
                        img = img.convert("RGB")
                    
                    images.append(img)
                    logger.info(
                        f"  ✅ Image {idx}/{len(image_paths)}: "
                        f"{img.width}×{img.height}px ({img.format})"
                    )
                except Exception as e:
                    logger.error(f"❌ Failed to load image {path}: {e}")
                    raise ValueError(f"Invalid image file: {os.path.basename(path)}")

            if not images:
                raise ValueError("No valid images found")

            logger.info(f"✅ Loaded {len(images)} images")

            # 2. Upload images to R2
            background_urls = await self._upload_images_to_r2(
                images, user_id, chapter_id
            )
            logger.info(f"✅ Uploaded {len(background_urls)} images to R2")

            # 3. Build pages array (variable dimensions for manga)
            pages = []
            for idx, (img, url) in enumerate(zip(images, background_urls), 1):
                pages.append(
                    {
                        "page_number": idx,
                        "background_url": url,
                        "width": img.width,  # Variable dimensions
                        "height": img.height,
                        "elements": [],  # Empty initially
                    }
                )

            result = {
                "pages": pages,
                "total_pages": len(pages),
            }

            logger.info(
                f"✅ [IMAGE_PROCESSOR] Successfully processed {result['total_pages']} images"
            )

            return result

        except Exception as e:
            logger.error(f"❌ [IMAGE_PROCESSOR] Failed to process images: {e}")
            raise

    async def process_zip_to_pages(
        self,
        zip_path: str,
        user_id: str,
        chapter_id: str,
        auto_sort: bool = True,
    ) -> Dict[str, Any]:
        """
        Extract manga ZIP and create pages

        Args:
            zip_path: Path to ZIP file
            user_id: User ID
            chapter_id: Chapter ID
            auto_sort: Auto-sort files numerically (True for manga)

        Returns:
            Pages array dict
        """
        temp_dir = None
        try:
            logger.info(f"📦 [IMAGE_PROCESSOR] Extracting ZIP: {zip_path}")

            # 1. Extract ZIP to temp directory
            temp_dir = tempfile.mkdtemp()

            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                # Get all image files
                all_files = zip_ref.namelist()
                image_files = [
                    f
                    for f in all_files
                    if os.path.splitext(f.lower())[1] in self.SUPPORTED_FORMATS
                    and not f.startswith("__MACOSX")  # Skip macOS metadata
                    and not os.path.basename(f).startswith(".")  # Skip hidden files
                ]

                if not image_files:
                    raise ValueError(
                        f"No image files found in ZIP. "
                        f"Supported formats: {', '.join(self.SUPPORTED_FORMATS)}"
                    )

                logger.info(
                    f"📄 Found {len(image_files)} images in ZIP "
                    f"(total files: {len(all_files)})"
                )

                # 2. Sort files (manga order: page-01.jpg, page-02.jpg, ...)
                if auto_sort:
                    image_files = self._sort_image_files(image_files)
                    logger.info(f"✅ Sorted {len(image_files)} files")

                # 3. Extract image files
                for file in image_files:
                    zip_ref.extract(file, temp_dir)

                # 4. Get full paths
                full_paths = [os.path.join(temp_dir, f) for f in image_files]

                logger.info(f"✅ Extracted {len(full_paths)} images to temp dir")

            # 5. Process extracted images
            result = await self.process_images_to_pages(
                full_paths, user_id, chapter_id, preserve_order=True
            )

            logger.info(f"✅ [IMAGE_PROCESSOR] ZIP processed: {result['total_pages']} pages")

            return result

        except Exception as e:
            logger.error(f"❌ Failed to process ZIP: {e}")
            raise
        finally:
            # Cleanup temp directory
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                logger.info(f"🗑️ Cleaned up temp directory")

    def _sort_image_files(self, files: List[str]) -> List[str]:
        """
        Sort image files numerically (for manga page order)

        Handles patterns like:
        - page-01.jpg, page-02.jpg
        - 001.png, 002.png
        - chapter1_page1.jpg

        Args:
            files: List of filenames

        Returns:
            Sorted list
        """
        import re

        def extract_numbers(filename):
            # Extract all numbers from filename
            numbers = re.findall(r"\d+", os.path.basename(filename))
            # Convert to integers for proper sorting
            return [int(n) for n in numbers] if numbers else [0]

        try:
            sorted_files = sorted(files, key=extract_numbers)
            logger.info(
                f"📊 Sorted order: {[os.path.basename(f) for f in sorted_files[:5]]}..."
            )
            return sorted_files
        except Exception as e:
            logger.warning(f"⚠️ Failed to sort files: {e}, using original order")
            return files

    async def _upload_images_to_r2(
        self, images: List[Image.Image], user_id: str, chapter_id: str
    ) -> List[str]:
        """
        Upload image files to R2 CDN

        Args:
            images: List of PIL Images
            user_id: User ID
            chapter_id: Chapter ID

        Returns:
            List of CDN URLs
        """
        urls = []

        try:
            for idx, image in enumerate(images, 1):
                # R2 path: studyhub/chapters/{chapter_id}/page-{idx}.jpg
                object_key = f"studyhub/chapters/{chapter_id}/page-{idx}.jpg"

                # Convert PIL Image to bytes (JPEG format, optimized)
                buffer = io.BytesIO()
                image.save(buffer, format="JPEG", quality=90, optimize=True)
                buffer.seek(0)

                # Upload to R2
                self.s3_client.upload_fileobj(
                    buffer,
                    self.r2_bucket,
                    object_key,
                    ExtraArgs={"ContentType": "image/jpeg"},
                )

                # Generate CDN URL
                cdn_url = f"{self.cdn_base_url}/{object_key}"
                urls.append(cdn_url)

                logger.info(f"  ✅ Uploaded page {idx}: {cdn_url}")

            logger.info(f"✅ Uploaded {len(urls)} images to R2")
            return urls

        except Exception as e:
            logger.error(f"❌ Failed to upload images: {e}")
            raise

    async def download_images_from_urls(
        self, image_urls: List[str], temp_dir: Optional[str] = None
    ) -> List[str]:
        """
        Download images from URLs to local temp files

        Args:
            image_urls: List of image URLs
            temp_dir: Temp directory (created if not provided)

        Returns:
            List of local file paths
        """
        import aiohttp

        if not temp_dir:
            temp_dir = tempfile.mkdtemp()

        local_paths = []

        try:
            async with aiohttp.ClientSession() as session:
                for idx, url in enumerate(image_urls, 1):
                    try:
                        async with session.get(url) as response:
                            if response.status != 200:
                                raise ValueError(
                                    f"Failed to download image: HTTP {response.status}"
                                )

                            # Determine file extension from content type
                            content_type = response.headers.get("Content-Type", "")
                            ext = ".jpg"
                            if "png" in content_type:
                                ext = ".png"
                            elif "webp" in content_type:
                                ext = ".webp"

                            # Save to temp file
                            temp_path = os.path.join(temp_dir, f"image-{idx}{ext}")
                            content = await response.read()

                            with open(temp_path, "wb") as f:
                                f.write(content)

                            local_paths.append(temp_path)
                            logger.info(
                                f"  ✅ Downloaded {idx}/{len(image_urls)}: "
                                f"{len(content)} bytes"
                            )

                    except Exception as e:
                        logger.error(f"❌ Failed to download image {url}: {e}")
                        raise

            logger.info(f"✅ Downloaded {len(local_paths)} images")
            return local_paths

        except Exception as e:
            logger.error(f"❌ Failed to download images: {e}")
            raise
