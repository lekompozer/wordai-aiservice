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
        batch_size: int = 10,  # Process 10 pages at a time to avoid RAM spike
        progress_callback=None,  # Callback for progress updates
    ) -> Dict[str, Any]:
        """
        Convert PDF to pages array with background images
        Processes in batches to avoid memory issues with large PDFs

        Args:
            pdf_path: Local path to PDF file
            user_id: User ID for R2 path organization
            chapter_id: Chapter ID for R2 path organization
            dpi: Resolution for rendering (150 DPI = A4 quality)
            batch_size: Number of pages to process at once (default 10)
            progress_callback: Optional callback(current, total) for progress

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
            logger.info(f"   Batch size: {batch_size} pages")

            # Get total pages count first
            total_pages = await self._get_pdf_page_count(pdf_path)
            logger.info(f"📊 Total pages: {total_pages}")

            pages = []

            # Process in batches
            for batch_start in range(0, total_pages, batch_size):
                batch_end = min(batch_start + batch_size, total_pages)
                logger.info(
                    f"📦 Processing batch: pages {batch_start + 1}-{batch_end}/{total_pages}"
                )

                # Extract batch of pages
                images = await self._extract_pdf_pages_batch(
                    pdf_path, dpi, batch_start, batch_end
                )
                logger.info(f"✅ Extracted {len(images)} pages from batch")

                # Upload batch
                background_urls = await self._upload_page_images(
                    images, user_id, chapter_id, batch_start + 1
                )

                # Build pages array for this batch
                for idx, (image, bg_url) in enumerate(zip(images, background_urls)):
                    page_number = batch_start + idx + 1
                    pages.append(
                        {
                            "page_number": page_number,
                            "background_url": bg_url,
                            "width": image.width,
                            "height": image.height,
                            "elements": [],
                        }
                    )

                # Clear batch from memory
                del images
                del background_urls

                # Progress callback
                if progress_callback:
                    await progress_callback(batch_end, total_pages)

                logger.info(
                    f"✅ Batch {batch_start + 1}-{batch_end} completed and freed from memory"
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

    async def _get_pdf_page_count(self, pdf_path: str) -> int:
        """Get total page count without loading pages"""
        try:
            import fitz

            doc = fitz.open(pdf_path)
            count = len(doc)
            doc.close()
            return count
        except ImportError:
            # Fallback for pdf2image
            from pdf2image import pdfinfo_from_path

            info = pdfinfo_from_path(pdf_path)
            return info["Pages"]

    async def _extract_pdf_pages_batch(
        self, pdf_path: str, dpi: int, start_page: int, end_page: int
    ) -> List[Image.Image]:
        """
        Extract a batch of PDF pages to PIL Images using PyMuPDF
        Pages are 0-indexed internally

        Args:
            pdf_path: Local path to PDF file
            dpi: Resolution for rendering
            start_page: Start page index (0-based)
            end_page: End page index (0-based, exclusive)

        Returns:
            List of PIL Image objects for the batch
        """
        try:
            # Try PyMuPDF first (faster, better quality)
            try:
                import fitz  # PyMuPDF

                doc = fitz.open(pdf_path)
                images = []

                # Calculate zoom factor for desired DPI
                zoom = dpi / 72
                mat = fitz.Matrix(zoom, zoom)

                for page_num in range(start_page, end_page):
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

                    # Clear pixmap memory
                    pix = None

                doc.close()
                return images

            except ImportError:
                logger.warning("⚠️ PyMuPDF not available, falling back to pdf2image")

                # Fallback to pdf2image (requires poppler)
                from pdf2image import convert_from_path

                # pdf2image uses 1-based page numbers
                images = convert_from_path(
                    pdf_path,
                    dpi=dpi,
                    first_page=start_page + 1,
                    last_page=end_page,
                )
                return images

        except Exception as e:
            logger.error(f"❌ Failed to extract PDF batch: {e}")
            raise

    async def _upload_page_images(
        self,
        images: List[Image.Image],
        user_id: str,
        chapter_id: str,
        start_page_number: int = 1,
    ) -> List[str]:
        """
        Upload page images to Cloudflare Images (preferred) or R2 (fallback)

        Args:
            images: List of PIL Images
            user_id: User ID for path organization
            chapter_id: Chapter ID for path organization
            start_page_number: Starting page number for this batch

        Returns:
            List of CDN URLs for uploaded images
        """
        urls = []

        try:
            for idx, image in enumerate(images):
                page_num = start_page_number + idx

                # Convert PIL Image to bytes (WebP format - 25-35% smaller than PNG/JPEG)
                buffer = io.BytesIO()
                image.save(buffer, format="WEBP", quality=85, method=4)
                buffer.seek(0)
                image_bytes = buffer.getvalue()

                if self.use_cf_images:
                    # Upload to Cloudflare Images (auto-optimized)
                    image_id = f"{chapter_id}-page-{page_num}"
                    result = await self.cf_images.upload_image(
                        image_bytes=image_bytes,
                        image_id=image_id,
                        metadata={
                            "user_id": user_id,
                            "chapter_id": chapter_id,
                            "page_number": str(page_num),
                            "type": "chapter_page",
                        },
                    )
                    cdn_url = result["public_url"]
                    logger.info(f"  ✅ Uploaded page {page_num} → Cloudflare Images")
                else:
                    # Fallback to R2 Storage
                    object_key = f"studyhub/chapters/{chapter_id}/page-{page_num}.webp"
                    buffer.seek(0)
                    self.s3_client.upload_fileobj(
                        buffer,
                        self.r2_bucket,
                        object_key,
                        ExtraArgs={"ContentType": "image/webp"},
                    )
                    cdn_url = f"{self.cdn_base_url}/{object_key}"
                    logger.info(f"  ✅ Uploaded page {page_num} → R2")

                urls.append(cdn_url)

                # Clear buffer
                buffer.close()

            return urls

        except Exception as e:
            logger.error(f"❌ Failed to upload page images: {e}")
            raise
