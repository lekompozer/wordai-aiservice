"""
Document Export Service
Convert HTML documents to various formats (PDF, DOCX, TXT, HTML)
"""

import os
import uuid
import logging
import tempfile
from typing import Optional, Tuple
from datetime import datetime, timedelta
from io import BytesIO

logger = logging.getLogger(__name__)


class DocumentExportService:
    """
    Service để export HTML documents sang các format khác
    - PDF: weasyprint
    - DOCX: python-docx + htmldocx
    - TXT: BeautifulSoup
    - HTML: Raw HTML file
    """

    def __init__(self, r2_client, db):
        """
        Initialize DocumentExportService

        Args:
            r2_client: R2Client instance for file upload
            db: MongoDB database instance
        """
        self.r2_client = r2_client
        self.db = db
        self.exports = db["document_exports"]  # Track export history for rate limiting

        # Create indexes for rate limiting
        self._create_indexes()

    def _create_indexes(self):
        """Create indexes for export tracking collection"""
        try:
            # Index for user + document (per-document cooldown)
            self.exports.create_index(
                [("user_id", 1), ("document_id", 1), ("exported_at", -1)],
                name="user_doc_export_idx",
            )
            # Index for user exports (global rate limit)
            self.exports.create_index(
                [("user_id", 1), ("exported_at", -1)], name="user_export_history_idx"
            )
            logger.info("✅ Export indexes created")
        except Exception as e:
            logger.warning(f"⚠️ Export index creation warning: {e}")

    def check_rate_limits(self, user_id: str, document_id: str) -> Tuple[bool, str]:
        """
        Check if user can export document based on rate limits

        Rate Limits:
        1. Per-document cooldown: 15 seconds between exports of same document
        2. Global limit: Max 10 exports in 30 minutes

        Args:
            user_id: User's Firebase UID
            document_id: Document ID

        Returns:
            (can_export: bool, error_message: str)
        """
        now = datetime.utcnow()

        # Check 1: Per-document cooldown (15 seconds)
        last_export = self.exports.find_one(
            {
                "user_id": user_id,
                "document_id": document_id,
                "exported_at": {"$gte": now - timedelta(seconds=15)},
            },
            sort=[("exported_at", -1)],
        )

        if last_export:
            seconds_ago = (now - last_export["exported_at"]).total_seconds()
            wait_time = 15 - int(seconds_ago)
            return (
                False,
                f"Please wait {wait_time} seconds before exporting this document again",
            )

        # Check 2: Global rate limit (10 exports in 30 minutes)
        exports_count = self.exports.count_documents(
            {"user_id": user_id, "exported_at": {"$gte": now - timedelta(minutes=30)}}
        )

        if exports_count >= 10:
            return (
                False,
                "Export limit reached: Maximum 10 exports per 30 minutes. Please try again later.",
            )

        return True, ""

    def track_export(self, user_id: str, document_id: str, format: str, file_size: int):
        """
        Track export in database for rate limiting

        Args:
            user_id: User's Firebase UID
            document_id: Document ID
            format: Export format (pdf/docx/txt/html)
            file_size: Exported file size in bytes
        """
        try:
            self.exports.insert_one(
                {
                    "export_id": f"exp_{uuid.uuid4().hex[:12]}",
                    "user_id": user_id,
                    "document_id": document_id,
                    "format": format,
                    "file_size": file_size,
                    "exported_at": datetime.utcnow(),
                }
            )
            logger.info(f"📊 Tracked export: {document_id} → {format}")
        except Exception as e:
            # Don't fail export if tracking fails
            logger.error(f"❌ Failed to track export: {e}")

    def _sanitize_filename(self, title: str) -> str:
        """
        Sanitize document title for filename
        Remove special characters, limit length
        """
        import re

        # Remove special characters
        filename = re.sub(r'[<>:"/\\|?*]', "", title)
        # Replace spaces with underscores
        filename = filename.replace(" ", "_")
        # Limit length
        filename = filename[:50] if len(filename) > 50 else filename
        # Add timestamp
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        return f"{filename}_{timestamp}"

    def export_to_pdf(
        self, html_content: str, title: str = "document"
    ) -> Tuple[bytes, str]:
        """
        Convert HTML to PDF using weasyprint

        Args:
            html_content: HTML content to convert
            title: Document title for filename

        Returns:
            (pdf_bytes, filename)
        """
        try:
            from weasyprint import HTML, CSS

            # Add CSS for better PDF rendering
            css = """
            @page {
                size: A4;
                margin: 20mm;
            }
            body {
                font-family: Arial, sans-serif;
                font-size: 12pt;
                line-height: 1.6;
                color: #333;
            }
            h1 { font-size: 24pt; margin-bottom: 12pt; }
            h2 { font-size: 20pt; margin-bottom: 10pt; }
            h3 { font-size: 16pt; margin-bottom: 8pt; }
            p { margin-bottom: 8pt; }
            img { max-width: 100%; height: auto; }
            table { border-collapse: collapse; width: 100%; }
            th, td { border: 1px solid #ddd; padding: 8px; }
            """

            html_with_style = f"<style>{css}</style>{html_content}"

            # Generate PDF in memory
            pdf_file = BytesIO()
            HTML(string=html_with_style).write_pdf(pdf_file)
            pdf_bytes = pdf_file.getvalue()

            filename = f"{self._sanitize_filename(title)}.pdf"

            logger.info(f"✅ Generated PDF: {filename} ({len(pdf_bytes)} bytes)")
            return pdf_bytes, filename

        except Exception as e:
            logger.error(f"❌ Error generating PDF: {e}")
            raise Exception(f"PDF generation failed: {str(e)}")

    def export_to_docx(
        self, html_content: str, title: str = "document"
    ) -> Tuple[bytes, str]:
        """
        Convert HTML to DOCX using Pandoc (via pypandoc)

        Args:
            html_content: HTML content to convert
            title: Document title for filename

        Returns:
            (docx_bytes, filename)
        """
        try:
            import pypandoc

            # Add proper HTML structure if missing
            if not html_content.strip().startswith(
                "<!DOCTYPE"
            ) and not html_content.strip().startswith("<html"):
                html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title}</title>
</head>
<body>
{html_content}
</body>
</html>"""

            # Convert HTML to DOCX using Pandoc
            # Pandoc is much more powerful than htmldocx and handles complex HTML better
            # For docx format, we need to write to a temporary file
            import tempfile
            import os

            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp_file:
                tmp_path = tmp_file.name

            try:
                # Convert HTML to DOCX file
                pypandoc.convert_text(
                    html_content,
                    "docx",
                    format="html",
                    outputfile=tmp_path,
                    extra_args=[
                        f"--metadata=title:{title}",  # Set document title
                    ],
                )

                # Post-process DOCX to add table borders
                # Pandoc doesn't preserve HTML table borders, so we add them manually
                self._add_table_borders_to_docx(tmp_path)

                # Read the generated DOCX file
                with open(tmp_path, "rb") as f:
                    docx_bytes = f.read()

            finally:
                # Clean up temporary file
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

            filename = f"{self._sanitize_filename(title)}.docx"

            logger.info(
                f"✅ Generated DOCX with Pandoc: {filename} ({len(docx_bytes)} bytes)"
            )
            return docx_bytes, filename

        except Exception as e:
            logger.error(f"❌ Error generating DOCX with Pandoc: {e}")
            raise Exception(f"DOCX generation failed: {str(e)}")

    def _add_table_borders_to_docx(self, docx_path: str) -> None:
        """
        Add borders to all tables in a DOCX file.
        Pandoc doesn't preserve HTML table borders, so we add them manually.

        Args:
            docx_path: Path to the DOCX file to modify
        """
        try:
            from docx import Document
            from docx.oxml import OxmlElement
            from docx.oxml.ns import qn

            # Open the document
            doc = Document(docx_path)

            # Process each table
            for table in doc.tables:
                # Set table borders
                tbl = table._element
                tblPr = tbl.tblPr
                if tblPr is None:
                    tblPr = OxmlElement("w:tblPr")
                    tbl.insert(0, tblPr)

                # Create table borders element
                tblBorders = OxmlElement("w:tblBorders")

                # Define border style (single line, 1pt, black)
                border_attrs = {
                    "w:val": "single",
                    "w:sz": "4",  # 4/8 = 0.5pt
                    "w:space": "0",
                    "w:color": "000000",
                }

                # Add all borders
                for border_name in [
                    "top",
                    "left",
                    "bottom",
                    "right",
                    "insideH",
                    "insideV",
                ]:
                    border = OxmlElement(f"w:{border_name}")
                    for attr, value in border_attrs.items():
                        border.set(qn(attr), value)
                    tblBorders.append(border)

                # Remove existing borders if any
                existing_borders = tblPr.find(qn("w:tblBorders"))
                if existing_borders is not None:
                    tblPr.remove(existing_borders)

                # Add new borders
                tblPr.append(tblBorders)

            # Save the modified document
            doc.save(docx_path)
            logger.debug(f"✅ Added borders to {len(doc.tables)} tables in DOCX")

        except Exception as e:
            # Don't fail the entire export if border addition fails
            logger.warning(f"⚠️ Could not add table borders to DOCX: {e}")

    def export_to_txt(
        self, html_content: str, title: str = "document"
    ) -> Tuple[bytes, str]:
        """
        Convert HTML to plain text using BeautifulSoup

        Args:
            html_content: HTML content to convert
            title: Document title for filename

        Returns:
            (txt_bytes, filename)
        """
        try:
            from bs4 import BeautifulSoup
            import re

            # Parse HTML
            soup = BeautifulSoup(html_content, "html.parser")

            # Remove script and style tags
            for tag in soup(["script", "style"]):
                tag.decompose()

            # Handle line breaks and paragraphs
            for br in soup.find_all("br"):
                br.replace_with("\n")

            for p in soup.find_all("p"):
                p.append("\n\n")

            # Extract text with proper formatting
            text = soup.get_text()

            # Clean up whitespace
            # Replace multiple spaces with single space
            text = re.sub(r" +", " ", text)
            # Replace multiple newlines with double newline (paragraph break)
            text = re.sub(r"\n\s*\n+", "\n\n", text)
            # Remove leading/trailing whitespace on each line
            text = "\n".join(line.strip() for line in text.split("\n"))
            # Remove empty lines at start/end
            text = text.strip()

            # Add UTF-8 BOM for better compatibility with Windows/Notepad
            # BOM helps Windows recognize the file as UTF-8
            txt_bytes = "\ufeff".encode("utf-8") + text.encode("utf-8")

            filename = f"{self._sanitize_filename(title)}.txt"

            logger.info(f"✅ Generated TXT: {filename} ({len(txt_bytes)} bytes)")
            return txt_bytes, filename

        except Exception as e:
            logger.error(f"❌ Error generating TXT: {e}")
            raise Exception(f"TXT generation failed: {str(e)}")

    def export_to_html(
        self, html_content: str, title: str = "document"
    ) -> Tuple[bytes, str]:
        """
        Save HTML as standalone file with CSS

        Args:
            html_content: HTML content to save
            title: Document title for filename

        Returns:
            (html_bytes, filename)
        """
        try:
            # Wrap HTML in complete document structure
            html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            max-width: 800px;
            margin: 40px auto;
            padding: 20px;
            color: #333;
        }}
        h1, h2, h3, h4, h5, h6 {{ margin-top: 24px; margin-bottom: 16px; }}
        p {{ margin-bottom: 16px; }}
        img {{ max-width: 100%; height: auto; }}
        table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
{html_content}
</body>
</html>"""

            html_bytes = html_template.encode("utf-8")

            filename = f"{self._sanitize_filename(title)}.html"

            logger.info(f"✅ Generated HTML: {filename} ({len(html_bytes)} bytes)")
            return html_bytes, filename

        except Exception as e:
            logger.error(f"❌ Error generating HTML: {e}")
            raise Exception(f"HTML generation failed: {str(e)}")

    async def export_and_upload(
        self,
        user_id: str,
        document_id: str,
        html_content: str,
        title: str,
        format: str,
    ) -> dict:
        """
        Export document to specified format and upload to R2

        Args:
            user_id: User Firebase UID
            document_id: Document ID
            html_content: HTML content to export
            title: Document title
            format: Export format ("pdf", "docx", "txt", "html")

        Returns:
            {
                "download_url": "https://r2.wordai.pro/...",
                "filename": "document_20251009_153045.pdf",
                "file_size": 123456,
                "expires_in": 3600,
                "expires_at": "2025-10-09T16:30:45Z"
            }
        """
        try:
            # Generate file based on format
            if format == "pdf":
                file_bytes, filename = self.export_to_pdf(html_content, title)
                content_type = "application/pdf"
            elif format == "docx":
                file_bytes, filename = self.export_to_docx(html_content, title)
                content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            elif format == "txt":
                file_bytes, filename = self.export_to_txt(html_content, title)
                content_type = "text/plain"
            elif format == "html":
                file_bytes, filename = self.export_to_html(html_content, title)
                content_type = "text/html"
            else:
                raise ValueError(f"Unsupported format: {format}")

            # R2 key: exports/{user_id}/{document_id}/{format}/{filename}
            r2_key = f"exports/{user_id}/{document_id}/{format}/{filename}"

            # Upload to R2
            logger.info(f"📤 Uploading {format.upper()} to R2: {r2_key}")

            # Create temp file for upload
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{format}") as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name

            try:
                # Upload to R2
                upload_success = await self.r2_client.upload_file(
                    local_path=tmp_path, remote_path=r2_key
                )

                if not upload_success:
                    raise Exception("Failed to upload file to R2")

                # Generate presigned URL (1 hour expiry)
                download_url = await self.r2_client.generate_presigned_url(
                    remote_path=r2_key, expiration=3600, method="GET"
                )

                # Calculate expiry time
                expires_at = datetime.utcnow() + timedelta(seconds=3600)

                result = {
                    "download_url": download_url,
                    "filename": filename,
                    "file_size": len(file_bytes),
                    "format": format,
                    "expires_in": 3600,
                    "expires_at": expires_at.isoformat() + "Z",
                }

                logger.info(
                    f"✅ Export successful: {filename} ({len(file_bytes)} bytes)"
                )

                # Optional: Save export history to MongoDB
                # self.exports.insert_one({
                #     "export_id": f"exp_{uuid.uuid4().hex[:12]}",
                #     "user_id": user_id,
                #     "document_id": document_id,
                #     "format": format,
                #     "filename": filename,
                #     "file_size": len(file_bytes),
                #     "r2_key": r2_key,
                #     "created_at": datetime.utcnow()
                # })

                return result

            finally:
                # Clean up temp file
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

        except Exception as e:
            logger.error(f"❌ Export and upload failed: {e}")
            raise Exception(f"Export failed: {str(e)}")
