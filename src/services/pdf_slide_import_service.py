"""
PDF Slide Import Service
Converts PDF pages to slide backgrounds (image-based slides)
"""

import os
import io
import tempfile
import logging
from typing import List, Dict, Tuple
from PIL import Image

logger = logging.getLogger("chatbot")


class PDFSlideImportService:
    """Service for importing PDF slides as image backgrounds"""

    @staticmethod
    async def convert_pdf_to_slide_images(
        pdf_path: str, dpi: int = 150
    ) -> List[Image.Image]:
        """
        Convert PDF pages to PIL Images

        Args:
            pdf_path: Local path to PDF file
            dpi: Resolution for rendering (150 is good balance of quality/size)

        Returns:
            List of PIL Image objects (one per page)
        """
        try:
            # Try PyMuPDF first (faster, no external deps)
            try:
                import fitz  # PyMuPDF  # type: ignore

                logger.info(f"📄 Converting PDF to images using PyMuPDF (dpi={dpi})")

                doc = fitz.open(pdf_path)
                images = []

                # Calculate zoom factor for desired DPI
                # Default is 72 DPI, so zoom = dpi/72
                zoom = dpi / 72
                mat = fitz.Matrix(zoom, zoom)

                for page_num in range(len(doc)):
                    page = doc.load_page(page_num)
                    pix = page.get_pixmap(matrix=mat)  # type: ignore

                    # Convert to PIL Image
                    img_data = pix.tobytes("png")  # type: ignore
                    img = Image.open(io.BytesIO(img_data))
                    images.append(img)

                    logger.info(
                        f"  ✅ Page {page_num + 1}/{len(doc)}: {img.size[0]}x{img.size[1]}"
                    )

                doc.close()
                logger.info(f"✅ Converted {len(images)} pages to images")
                return images

            except ImportError:
                logger.warning("⚠️ PyMuPDF not available, falling back to pdf2image")

                # Fallback to pdf2image (requires poppler)
                from pdf2image import convert_from_path  # type: ignore

                logger.info(f"📄 Converting PDF to images using pdf2image (dpi={dpi})")

                images = convert_from_path(pdf_path, dpi=dpi)
                logger.info(f"✅ Converted {len(images)} pages to images")
                return images

        except Exception as e:
            logger.error(f"❌ Failed to convert PDF to images: {e}")
            raise

    @staticmethod
    async def upload_images_to_r2(
        images: List[Image.Image],
        user_id: str,
        file_id: str,
        s3_client,
        bucket_name: str,
    ) -> List[str]:
        """
        Upload images to R2 storage

        Args:
            images: List of PIL Images
            user_id: User ID for R2 path
            file_id: Original file ID
            s3_client: Boto3 S3 client
            bucket_name: R2 bucket name

        Returns:
            List of R2 URLs (CDN URLs)
        """
        import asyncio

        image_urls = []

        for i, img in enumerate(images):
            # Save image to temp file
            temp_file = tempfile.NamedTemporaryFile(
                delete=False, suffix=".png", dir=tempfile.gettempdir()
            )
            temp_path = temp_file.name
            temp_file.close()

            try:
                # Save as PNG (lossless, good for slides)
                img.save(temp_path, format="PNG", optimize=True)

                # R2 key: files/{user_id}/slide_import/{file_id}/page-{i}.png
                r2_key = f"files/{user_id}/slide_import/{file_id}/page-{i + 1}.png"

                # Upload to R2 (run in thread since boto3 is sync)
                await asyncio.to_thread(
                    s3_client.upload_file,
                    temp_path,
                    bucket_name,
                    r2_key,
                    ExtraArgs={"ContentType": "image/png"},
                )

                # Build CDN URL (assuming R2_PUBLIC_URL env var)
                r2_public_url = os.getenv("R2_PUBLIC_URL", "")
                if r2_public_url:
                    image_url = f"{r2_public_url}/{r2_key}"
                else:
                    image_url = f"https://{bucket_name}.r2.dev/{r2_key}"

                image_urls.append(image_url)
                logger.info(f"  ✅ Uploaded page {i + 1}: {image_url}")

            finally:
                # Cleanup temp file
                if os.path.exists(temp_path):
                    os.remove(temp_path)

        logger.info(f"✅ Uploaded {len(image_urls)} images to R2")
        return image_urls

    @staticmethod
    def create_slide_backgrounds(image_urls: List[str]) -> List[Dict]:
        """
        Create slide background objects from image URLs

        Args:
            image_urls: List of R2 image URLs

        Returns:
            List of background objects for MongoDB
        """
        backgrounds = []
        for url in image_urls:
            backgrounds.append({"type": "image", "imageUrl": url})

        return backgrounds

    @staticmethod
    def create_minimal_html_slides(num_slides: int) -> str:
        """
        Create minimal HTML for image-based slides

        Args:
            num_slides: Number of slides

        Returns:
            HTML string with empty slide divs
        """
        slides_html = []

        for i in range(num_slides):
            # Empty slide - background image will cover it
            slide_html = f"""<div class="slide" data-slide-number="{i}">
  <!-- Slide {i + 1}: Background image only -->
</div>"""
            slides_html.append(slide_html)

        return "\n\n".join(slides_html)


def get_pdf_slide_import_service() -> PDFSlideImportService:
    """Get singleton instance of PDFSlideImportService"""
    return PDFSlideImportService()
