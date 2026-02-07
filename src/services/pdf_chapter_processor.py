"""
PDF Chapter Processor Service
Convert PDF files to chapter pages with background images

Phase 1: PDF Pages Support
"""

import os
import io
import logging
import tempfile
from typing import List, Dict, Any, Tuple, Optional
from PIL import Image

logger = logging.getLogger("chatbot")


class PDFChapterProcessor:
    """Process PDF files into chapter pages with A4 backgrounds"""

    def __init__(
        self,
        s3_client,
        r2_bucket: str,
        cdn_base_url: str,
        cloudflare_images_service=None,
    ):
        """
        Initialize PDF processor

        Args:
            s3_client: Boto3 S3 client for R2 uploads (fallback)
            r2_bucket: R2 bucket name (fallback)
            cdn_base_url: CDN base URL (fallback)
            cloudflare_images_service: Cloudflare Images service (preferred)
        """
        self.s3_client = s3_client
        self.r2_bucket = r2_bucket
        self.cdn_base_url = cdn_base_url
        self.cf_images = cloudflare_images_service

        # Check if Cloudflare Images is enabled
        self.use_cf_images = (
            self.cf_images is not None
            and hasattr(self.cf_images, "enabled")
            and self.cf_images.enabled
        )

        if self.use_cf_images:
            logger.info("✅ PDF Processor using Cloudflare Images (auto-optimized)")
        else:
            logger.info("ℹ️ PDF Processor using R2 Storage (manual optimization)")

    async def process_pdf_to_pages(
        self,
        pdf_path: str,
        user_id: str,
        chapter_id: str,
        dpi: int = 150,  # A4 quality: 1240×1754 pixels
    ) -> Dict[str, Any]:
        """
        Convert PDF to pages array with background images

        Args:
            pdf_path: Local path to PDF file
            user_id: User ID for R2 path organization
            chapter_id: Chapter ID for R2 path organization
            dpi: Resolution for rendering (150 DPI = A4 quality)

        Returns:
            {
                "pages": [{page_number, background_url, width, height, elements: []}],
                "total_pages": 10,
                "original_file_name": "file.pdf"
            }
        """
        try:
            logger.info(f"📄 [PDF_PROCESSOR] Processing PDF: {pdf_path}")
            logger.info(f"   User: {user_id}, Chapter: {chapter_id}, DPI: {dpi}")

            # 1. Extract PDF pages to images (PyMuPDF)
            images = await self._extract_pdf_pages(pdf_path, dpi)
            logger.info(f"✅ Extracted {len(images)} pages from PDF")

            # 2. Upload images to R2 with chapter-specific path
            background_urls = await self._upload_page_images(
                images, user_id, chapter_id
            )
            logger.info(f"✅ Uploaded {len(background_urls)} page images to R2")

            # 3. Build pages array
            pages = []
            for idx, (image, url) in enumerate(zip(images, background_urls), 1):
                pages.append(
                    {
                        "page_number": idx,
                        "background_url": url,
                        "width": image.width,  # A4 @ 150 DPI: 1240px
                        "height": image.height,  # A4 @ 150 DPI: 1754px
                        "elements": [],  # Empty initially, frontend adds elements
                    }
                )

            result = {
                "pages": pages,
                "total_pages": len(pages),
                "original_file_name": os.path.basename(pdf_path),
            }

            logger.info(
                f"✅ [PDF_PROCESSOR] Successfully processed PDF: "
                f"{result['total_pages']} pages, "
                f"dimensions: {pages[0]['width']}×{pages[0]['height']}"
            )

            return result

        except Exception as e:
            logger.error(f"❌ [PDF_PROCESSOR] Failed to process PDF: {e}")
            raise

    async def _extract_pdf_pages(self, pdf_path: str, dpi: int) -> List[Image.Image]:
        """
        Extract PDF pages to PIL Images using PyMuPDF

        Args:
            pdf_path: Local path to PDF file
            dpi: Resolution for rendering

        Returns:
            List of PIL Image objects (one per page)
        """
        try:
            # Try PyMuPDF first (faster, better quality)
            try:
                import fitz  # PyMuPDF

                logger.info(f"📄 Using PyMuPDF to extract pages (dpi={dpi})")

                doc = fitz.open(pdf_path)
                images = []

                # Calculate zoom factor for desired DPI
                # PyMuPDF default is 72 DPI, so zoom = target_dpi/72
                zoom = dpi / 72
                mat = fitz.Matrix(zoom, zoom)

                for page_num in range(len(doc)):
                    page = doc.load_page(page_num)
                    pix = page.get_pixmap(matrix=mat)

                    # Convert to PIL Image
                    img_data = pix.tobytes("png")
                    img = Image.open(io.BytesIO(img_data))
                    images.append(img)

                    logger.info(
                        f"  ✅ Page {page_num + 1}/{len(doc)}: "
                        f"{img.width}×{img.height}px"
                    )

                doc.close()
                logger.info(f"✅ Extracted {len(images)} pages using PyMuPDF")
                return images

            except ImportError:
                logger.warning("⚠️ PyMuPDF not available, falling back to pdf2image")

                # Fallback to pdf2image (requires poppler)
                from pdf2image import convert_from_path

                logger.info(f"📄 Using pdf2image to extract pages (dpi={dpi})")

                images = convert_from_path(pdf_path, dpi=dpi)
                logger.info(f"✅ Extracted {len(images)} pages using pdf2image")
                return images

        except Exception as e:
            logger.error(f"❌ Failed to extract PDF pages: {e}")
            raise

    async def _upload_page_images(
        self, images: List[Image.Image], user_id: str, chapter_id: str
    ) -> List[str]:
        """
        Upload page images to Cloudflare Images (preferred) or R2 (fallback)

        Args:
            images: List of PIL Images
            user_id: User ID for path organization
            chapter_id: Chapter ID for path organization

        Returns:
            List of CDN URLs for uploaded images
        """
        urls = []

        try:
            for idx, image in enumerate(images, 1):
                # Convert PIL Image to bytes (WebP format - 25-35% smaller than PNG/JPEG)
                buffer = io.BytesIO()
                image.save(buffer, format="WEBP", quality=85, method=4)
                buffer.seek(0)
                image_bytes = buffer.getvalue()

                if self.use_cf_images:
                    # Upload to Cloudflare Images (auto-optimized)
                    image_id = f"{chapter_id}-page-{idx}"
                    result = await self.cf_images.upload_image(
                        image_bytes=image_bytes,
                        image_id=image_id,
                        metadata={
                            "user_id": user_id,
                            "chapter_id": chapter_id,
                            "page_number": str(idx),
                            "type": "chapter_page",
                        },
                    )
                    cdn_url = result["public_url"]
                    logger.info(f"  ✅ Page {idx} → Cloudflare Images: {cdn_url}")
                else:
                    # Fallback to R2 Storage
                    object_key = f"studyhub/chapters/{chapter_id}/page-{idx}.webp"
                    buffer.seek(0)
                    self.s3_client.upload_fileobj(
                        buffer,
                        self.r2_bucket,
                        object_key,
                        ExtraArgs={"ContentType": "image/webp"},
                    )
                    cdn_url = f"{self.cdn_base_url}/{object_key}"
                    logger.info(f"  ✅ Page {idx} → R2: {cdn_url}")

                urls.append(cdn_url)

            logger.info(
                f"✅ Uploaded {len(urls)} pages to {'Cloudflare Images' if self.use_cf_images else 'R2'}"
            )
            return urls

        except Exception as e:
            logger.error(f"❌ Failed to upload page images: {e}")
            raise
