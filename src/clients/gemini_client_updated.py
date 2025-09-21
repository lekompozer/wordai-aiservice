import asyncio
import json
import os
from typing import Dict, List, AsyncGenerator

# Use new google-genai package
from google import genai
from google.genai import types
from src.utils.logger import setup_logger
import requests

logger = setup_logger()


class GeminiClient:
    def __init__(self, api_key: str):
        """
        Initialize Gemini client with new google-genai package.
        """
        self.api_key = api_key

        # Configure with new API
        self.client = genai.Client(api_key=api_key)
        self.logger = logger

        # Default models - updated with new models
        self.text_model = "gemini-2.5-flash-lite"
        self.vision_model = "gemini-2.5-flash-lite"

        logger.info("✅ Gemini client initialized with new google-genai package")

    async def chat_completion(
        self, messages: List[Dict], temperature: float = 0.7
    ) -> str:
        """
        Basic chat completion without streaming using new google-genai API.
        """
        try:
            # Convert messages to new Content format
            contents = []
            for msg in messages:
                role = "user" if msg["role"] in ["user", "system"] else "model"
                contents.append(
                    types.Content(role=role, parts=[types.Part(text=msg["content"])])
                )

            # Generate content with new API
            response = self.client.models.generate_content(
                model=self.text_model, contents=contents
            )

            return response.text

        except Exception as e:
            self.logger.error(f"❌ Gemini chat completion error: {e}")
            raise

    async def chat_completion_stream(
        self, messages: List[Dict], temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        """
        Streaming chat completion using new API.
        """
        try:
            # Convert messages to new Content format
            contents = []
            for msg in messages:
                role = "user" if msg["role"] in ["user", "system"] else "model"
                contents.append(
                    types.Content(role=role, parts=[types.Part(text=msg["content"])])
                )

            # Generate streaming content with new API
            response_stream = self.client.models.generate_content_stream(
                model=self.text_model, contents=contents
            )

            for chunk in response_stream:
                if hasattr(chunk, "text") and chunk.text:
                    yield chunk.text
                elif hasattr(chunk, "candidates") and chunk.candidates:
                    for candidate in chunk.candidates:
                        if hasattr(candidate, "content") and candidate.content:
                            for part in candidate.content.parts:
                                if hasattr(part, "text") and part.text:
                                    yield part.text

        except Exception as e:
            self.logger.error(f"❌ Gemini chat completion stream error: {e}")
            yield f"Lỗi Gemini: {str(e)}"

    async def upload_file_and_analyze(
        self, file_content: bytes, file_name: str, prompt: str = ""
    ) -> str:
        """
        Upload file to Gemini and analyze it.
        For DOCX files, extract text first as Gemini doesn't support DOCX format.
        """
        try:
            # Handle DOCX files by extracting text first
            if file_name.lower().endswith(".docx"):
                logger.info("📄 DOCX file detected, extracting text...")
                try:
                    from docx import Document
                    import tempfile
                    import os

                    # Create temporary DOCX file
                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix=".docx"
                    ) as tmp_docx:
                        tmp_docx.write(file_content)
                        tmp_docx_path = tmp_docx.name

                    try:
                        # Extract text from DOCX
                        doc = Document(tmp_docx_path)
                        extracted_text = ""

                        for paragraph in doc.paragraphs:
                            if paragraph.text.strip():
                                extracted_text += paragraph.text.strip() + "\n"

                        logger.info(
                            f"✅ Extracted {len(extracted_text)} characters from DOCX"
                        )

                        # Convert extracted text to bytes for processing
                        file_content = extracted_text.encode("utf-8")
                        file_name = file_name.replace(".docx", "_extracted.txt")
                        mime_type = "text/plain"

                    finally:
                        if os.path.exists(tmp_docx_path):
                            os.unlink(tmp_docx_path)

                except ImportError:
                    logger.warning(
                        "⚠️ python-docx not available, falling back to ChatGPT"
                    )
                    raise Exception("DOCX processing requires python-docx package")
                except Exception as docx_error:
                    logger.error(f"❌ DOCX extraction failed: {docx_error}")
                    raise Exception(f"Failed to extract text from DOCX: {docx_error}")
            else:
                # Determine MIME type for other files
                if file_name.lower().endswith((".png", ".jpg", ".jpeg")):
                    mime_type = f"image/{file_name.split('.')[-1].lower()}"
                elif file_name.lower().endswith(".pdf"):
                    mime_type = "application/pdf"
                elif file_name.lower().endswith((".txt", ".csv")):
                    mime_type = "text/plain"
                elif file_name.lower().endswith(".json"):
                    mime_type = "application/json"
                else:
                    mime_type = "text/plain"  # Default to text

            # Create temporary file for Gemini upload
            import tempfile
            import os

            with tempfile.NamedTemporaryFile(
                delete=False, suffix=f"_{file_name}", mode="wb"
            ) as tmp_file:
                tmp_file.write(file_content)
                tmp_file_path = tmp_file.name

            try:
                # Use new google-genai client.files.upload method with correct parameters
                uploaded_file = self.client.files.upload(
                    file=tmp_file_path,
                    config=types.UploadFileConfig(
                        mime_type=mime_type, display_name=file_name
                    ),
                )
                logger.info(
                    "✅ Gemini file upload successful with new google-genai client"
                )

                # Wait for file processing
                import time

                timeout_start = time.time()
                timeout = 60  # 60 seconds timeout

                while uploaded_file.state.name == "PROCESSING":
                    if time.time() - timeout_start > timeout:
                        raise Exception("File processing timeout")
                    time.sleep(1)
                    # Refresh file status
                    uploaded_file = self.client.files.get(uploaded_file.name)

                if uploaded_file.state.name != "ACTIVE":
                    raise Exception(
                        f"File processing failed with state: {uploaded_file.state.name}"
                    )

                logger.info(f"✅ File processed successfully: {uploaded_file.name}")

                # Generate content with uploaded file using new API
                if not prompt:
                    prompt = "Hãy phân tích và trích xuất thông tin từ file này."

                response = self.client.models.generate_content(
                    model=self.vision_model,
                    contents=[prompt, uploaded_file],  # Simple format that works
                )

                # Clean up uploaded file
                try:
                    self.client.files.delete(name=uploaded_file.name)
                    logger.info("✅ Uploaded file cleaned up successfully")
                except Exception as cleanup_error:
                    logger.warning(
                        f"⚠️ Could not cleanup uploaded file: {cleanup_error}"
                    )

                return response.text

            except Exception as upload_error:
                logger.error(f"❌ Gemini file upload failed: {upload_error}")

                # FALLBACK: Use ChatGPT instead of Gemini
                logger.info("🔄 Falling back to ChatGPT for file processing...")
                raise Exception(
                    f"Gemini upload failed, fallback to ChatGPT: {upload_error}"
                )

            finally:
                # Clean up temporary file
                if os.path.exists(tmp_file_path):
                    os.unlink(tmp_file_path)

        except Exception as e:
            self.logger.error(f"❌ Gemini file upload error: {e}")
            raise

    async def chat_with_file_stream(
        self,
        messages: List[Dict],
        file_content: bytes,
        file_name: str,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat with file upload.
        """
        try:
            # Upload and analyze file first
            file_analysis = await self.upload_file_and_analyze(
                file_content, file_name, "Hãy phân tích file này."
            )

            # Add file analysis to conversation
            enhanced_messages = messages.copy()
            enhanced_messages.append(
                {
                    "role": "system",
                    "content": f"Thông tin từ file {file_name}:\n{file_analysis}",
                }
            )

            # Stream response with enhanced context
            async for chunk in self.chat_completion_stream(
                enhanced_messages, temperature
            ):
                yield chunk

        except Exception as e:
            self.logger.error(f"❌ Gemini chat with file stream error: {e}")
            yield f"Lỗi xử lý file: {str(e)}"
