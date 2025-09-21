"""
Utility functions for document processing and file handling
NOTE: PDF extraction now uses Gemini AI instead of PyMuPDF
"""

# import fitz  # PyMuPDF - REMOVED: Now using Gemini for PDF extraction
from docx import Document
import base64
from PIL import Image
import io
import os
import json
from datetime import datetime
from pathlib import Path


def extract_text_from_pdf(pdf_base64: str) -> str:
    """
    ⚠️ DEPRECATED: PDF text extraction moved to Gemini AI
    This function now returns empty string and logs a deprecation warning
    """
    print(
        "⚠️ extract_text_from_pdf is deprecated. Use Gemini AI for PDF extraction instead."
    )
    return ""


# def extract_text_from_pdf(pdf_base64: str) -> str:
#     """
#     ✅ Extract text from PDF file (base64 encoded) - REMOVED: Now using Gemini
#     """
#     try:
#         pdf_bytes = base64.b64decode(pdf_base64)
#         doc = fitz.open(stream=pdf_bytes, filetype="pdf")
#
#         text = ""
#         for page in doc:
#             text += page.get_text()
#
#         doc.close()
#         return text.strip()
#
#     except Exception as e:
#         print(f"❌ PDF text extraction failed: {e}")
#         return ""


def extract_text_from_docx(docx_base64: str) -> str:
    """
    ✅ Extract text from DOCX file (base64 encoded)
    """
    try:
        docx_bytes = base64.b64decode(docx_base64)
        doc = Document(io.BytesIO(docx_bytes))

        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"

        return text.strip()

    except Exception as e:
        print(f"❌ DOCX text extraction failed: {e}")
        return ""


def convert_image_to_base64(image_path: str) -> str:
    """
    ✅ Convert image file to base64 string
    """
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    except Exception as e:
        print(f"❌ Image to base64 conversion failed: {e}")
        return ""


def validate_image_base64(image_base64: str) -> bool:
    """
    ✅ Validate base64 encoded image
    """
    try:
        image_data = base64.b64decode(image_base64)
        image = Image.open(io.BytesIO(image_data))
        return True
    except Exception:
        return False


def save_analysis_log(log_data: dict, log_type: str = "analysis"):
    """
    ✅ Save analysis data to log file with timestamp
    """
    try:
        # Create logs directory if it doesn't exist
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)

        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{log_type}_log_{timestamp}.json"
        log_file = logs_dir / filename

        # Add timestamp to log data
        log_data["logged_at"] = datetime.now().isoformat()
        log_data["log_type"] = log_type

        # Save to file
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)

        print(f"📝 {log_type.title()} log saved: {filename}")
        return str(log_file)

    except Exception as e:
        print(f"❌ Failed to save {log_type} log: {e}")
        return None


def save_real_estate_analysis_log(analysis_data: dict):
    """
    ✅ Save real estate analysis log
    """
    return save_analysis_log(analysis_data, "real_estate_analysis")


def save_web_search_detailed_log(search_data: dict):
    """
    ✅ Save web search detailed log
    """
    return save_analysis_log(search_data, "web_search_detailed")


def get_file_type_from_base64(base64_data: str) -> str:
    """
    ✅ Determine file type from base64 data
    """
    try:
        # Decode first few bytes to check file signature
        decoded_data = base64.b64decode(base64_data[:100])

        # Check PDF signature
        if decoded_data.startswith(b"%PDF"):
            return "pdf"

        # Check DOCX signature (ZIP-based)
        if decoded_data.startswith(b"PK"):
            return "docx"

        # Check image signatures
        if decoded_data.startswith(b"\xff\xd8\xff"):
            return "jpeg"
        if decoded_data.startswith(b"\x89PNG"):
            return "png"

        return "unknown"

    except Exception:
        return "unknown"


def process_uploaded_files(files: list, file_names: list, file_types: list) -> list:
    """
    ✅ Process multiple uploaded files and extract text content
    """
    processed_files = []

    for i, (file_content, file_name, file_type) in enumerate(
        zip(files, file_names, file_types)
    ):
        try:
            extracted_text = ""

            # Determine processing method based on file type
            if file_type.lower() in ["pdf", "application/pdf"]:
                extracted_text = extract_text_from_pdf(file_content)
            elif file_type.lower() in [
                "docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ]:
                extracted_text = extract_text_from_docx(file_content)
            elif file_type.lower().startswith("text/"):
                # Plain text file
                try:
                    extracted_text = base64.b64decode(file_content).decode("utf-8")
                except:
                    extracted_text = file_content  # Assume already decoded
            else:
                # Try to auto-detect from content
                detected_type = get_file_type_from_base64(file_content)
                if detected_type == "pdf":
                    extracted_text = extract_text_from_pdf(file_content)
                elif detected_type == "docx":
                    extracted_text = extract_text_from_docx(file_content)

            processed_files.append(
                {
                    "file_name": file_name,
                    "file_type": file_type,
                    "extracted_text": extracted_text,
                    "text_length": len(extracted_text),
                    "processed_successfully": bool(extracted_text.strip()),
                }
            )

        except Exception as e:
            print(f"❌ Failed to process file {file_name}: {e}")
            processed_files.append(
                {
                    "file_name": file_name,
                    "file_type": file_type,
                    "extracted_text": "",
                    "text_length": 0,
                    "processed_successfully": False,
                    "error": str(e),
                }
            )

    return processed_files


# ✅ CHATGPT VISION OCR FUNCTIONS
async def extract_text_with_chatgpt_vision_url(
    image_url: str, filename: str = "image"
) -> str:
    """
    Extract text from image URL using ChatGPT Vision API
    """
    try:
        from src.providers.ai_provider_manager import AIProviderManager
        from config.config import DEEPSEEK_API_KEY, CHATGPT_API_KEY

        # Initialize AI manager
        ai_manager = AIProviderManager(
            deepseek_api_key=DEEPSEEK_API_KEY, chatgpt_api_key=CHATGPT_API_KEY
        )

        # Create OCR prompt
        ocr_prompt = f"""
Hãy đọc và trích xuất toàn bộ văn bản từ hình ảnh này.
Tên file: {filename}

Yêu cầu:
1. Trích xuất chính xác toàn bộ text
2. Giữ nguyên format và cấu trúc
3. Nếu có bảng, danh sách thì format rõ ràng
4. Chỉ trả về nội dung text, không giải thích thêm

Nếu không đọc được text, hãy mô tả nội dung hình ảnh ngắn gọn.
"""

        # Use ChatGPT Vision for OCR with URL
        result = await ai_manager.get_response_with_image_url(
            question=ocr_prompt, image_url=image_url, provider="chatgpt"
        )

        return result or f"[Không thể trích xuất text từ {filename}]"

    except Exception as e:
        print(f"❌ ChatGPT Vision OCR error: {e}")
        return f"[Lỗi OCR {filename}: {str(e)}]"


async def extract_text_with_chatgpt_vision_base64(
    image_base64: str, filename: str = "image"
) -> str:
    """
    Extract text from base64 image using ChatGPT Vision API
    """
    try:
        from src.providers.ai_provider_manager import AIProviderManager
        from config.config import DEEPSEEK_API_KEY, CHATGPT_API_KEY

        # Initialize AI manager
        ai_manager = AIProviderManager(
            deepseek_api_key=DEEPSEEK_API_KEY, chatgpt_api_key=CHATGPT_API_KEY
        )

        # Create OCR prompt
        ocr_prompt = f"""
Hãy đọc và trích xuất toàn bộ văn bản từ hình ảnh này.
Tên file: {filename}

Yêu cầu:
1. Trích xuất chính xác toàn bộ text
2. Giữ nguyên format và cấu trúc
3. Nếu có bảng, danh sách thì format rõ ràng
4. Chỉ trả về nội dung text, không giải thích thêm

Nếu không đọc được text, hãy mô tả nội dung hình ảnh ngắn gọn.
"""

        # Use ChatGPT Vision for OCR with base64
        result = await ai_manager.get_response_with_image(
            question=ocr_prompt, image_base64=image_base64, provider="chatgpt"
        )

        return result or f"[Không thể trích xuất text từ {filename}]"

    except Exception as e:
        print(f"❌ ChatGPT Vision OCR error: {e}")
        return f"[Lỗi OCR {filename}: {str(e)}]"


def extract_text_with_chatgpt_vision_sync(
    image_path: str, filename: str = "image"
) -> str:
    """
    Synchronous wrapper for ChatGPT Vision OCR (for backward compatibility)
    """
    import asyncio

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # Read image and convert to base64
    try:
        with open(image_path, "rb") as image_file:
            image_data = base64.b64encode(image_file.read()).decode("utf-8")

        # Run async function
        result = loop.run_until_complete(
            extract_text_with_chatgpt_vision_base64(image_data, filename)
        )
        return result

    except Exception as e:
        print(f"❌ Sync ChatGPT Vision OCR error: {e}")
        return f"[Lỗi OCR {filename}: {str(e)}]"
