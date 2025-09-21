"""
FastAPI route handlers for real estate analysis endpoints with complete file processing
"""

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from datetime import datetime
import json
import asyncio
import time
import base64
from typing import Dict, Any, List
import logging

from src.core.models import (
    ChatWithFilesRequest,
    RealEstateAnalysisRequest,
    RealEstateAnalysisResponse,
)
from src.core.document_utils import (
    save_real_estate_analysis_log,
    extract_text_from_pdf,
    extract_text_from_docx,
    extract_text_with_chatgpt_vision_url,
)
from src.utils.real_estate_analyzer import analyze_real_estate_query
from src.providers.ai_provider_manager import AIProviderManager
from config.config import DEEPSEEK_API_KEY, CHATGPT_API_KEY

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/real-estate/deepseek-reasoning")
async def real_estate_deepseek_reasoning(request: ChatWithFilesRequest):
    """
    ✅ COMPLETE: Real estate analysis with DeepSeek reasoning + file processing + web search
    Supports: TXT, PDF, DOCX files and Images (OCR via ChatGPT Vision)
    """

    async def generate():
        # Initialize comprehensive analysis log
        analysis_log = {
            "request": {
                "question": request.question,
                "files_count": len(request.files) if request.files else 0,
                "file_names": (
                    request.file_names if hasattr(request, "file_names") else []
                ),
                "file_types": (
                    request.file_types if hasattr(request, "file_types") else []
                ),
                "user_id": request.user_id or "anonymous",
                "session_id": request.session_id or "default",
                "timestamp": datetime.now().isoformat(),
            },
            "processing_steps": [],
            "web_search": {
                "search_query": None,
                "properties_found": [],
                "performance_metrics": {},
            },
            "processed_files": [],
            "ai_response": "",
            "performance_metrics": {},
            "errors": [],
        }

        start_time = time.time()

        try:
            # Initialize variables
            full_response = ""
            processed_files = []
            user_id = request.user_id or "anonymous"
            session_id = request.session_id or f"re-{int(time.time())}"

            yield f'data: {json.dumps({"status": "started", "message": "Bắt đầu phân tích bất động sản..."})}\n\n'

            # ✅ STEP 0: Quick Analysis
            logger.info("=== STEP 0: QUICK ANALYSIS ===")
            yield f'data: {json.dumps({"status": "analyzing", "message": "Phân tích yêu cầu..."})}\n\n'

            analysis = analyze_real_estate_query(request.question)
            logger.info(f"Quick Analysis - Confidence: {analysis.confidence:.2f}")

            analysis_log["processing_steps"].append(
                {
                    "step": 0,
                    "name": "quick_analysis",
                    "timestamp": time.time(),
                    "result": {
                        "property_type": analysis.property_type,
                        "project_name": analysis.project_name,
                        "location": {
                            "province": (
                                analysis.location.province
                                if hasattr(analysis, "location")
                                else None
                            ),
                            "district": (
                                analysis.location.district
                                if hasattr(analysis, "location")
                                else None
                            ),
                        },
                        "search_query": (
                            analysis.search_query
                            if hasattr(analysis, "search_query")
                            else None
                        ),
                        "confidence": analysis.confidence,
                    },
                }
            )

            # ✅ STEP 1: FILE PROCESSING
            files_context = ""
            if request.files and len(request.files) > 0:
                logger.info("=== STEP 1: PROCESSING FILES ===")
                yield f'data: {json.dumps({"status": "processing_files", "message": f"Đang xử lý {len(request.files)} tài liệu..."})}\n\n'

                ai_manager = AIProviderManager(
                    deepseek_api_key=DEEPSEEK_API_KEY, chatgpt_api_key=CHATGPT_API_KEY
                )

                for i, file_base64 in enumerate(request.files):
                    filename = (
                        request.file_names[i]
                        if i < len(request.file_names)
                        else f"file_{i+1}"
                    )
                    file_type = (
                        request.file_types[i]
                        if i < len(request.file_types)
                        else "unknown"
                    )

                    file_log = {
                        "filename": filename,
                        "file_type": file_type,
                        "file_size": len(file_base64),
                        "extraction_start": time.time(),
                    }

                    extracted_text = ""
                    extraction_method = ""

                    try:
                        # ✅ IMAGE PROCESSING (OCR via ChatGPT Vision)
                        if file_type.startswith("image/") or filename.lower().endswith(
                            (".jpg", ".jpeg", ".png", ".gif", ".bmp")
                        ):
                            logger.info(f"Processing image: {filename}")
                            yield f'data: {json.dumps({"status": "ocr", "message": f"Đang OCR hình ảnh {filename}..."})}\n\n'

                            try:
                                # Create a temporary image for OCR
                                import tempfile
                                import os

                                # Decode base64 image
                                image_data = base64.b64decode(file_base64)

                                # Save to temp file
                                with tempfile.NamedTemporaryFile(
                                    delete=False, suffix=f".{filename.split('.')[-1]}"
                                ) as temp_file:
                                    temp_file.write(image_data)
                                    temp_image_path = temp_file.name

                                # Use ChatGPT Vision for OCR
                                extracted_text = (
                                    await extract_text_with_chatgpt_vision_file(
                                        temp_image_path, filename
                                    )
                                )
                                extraction_method = "ChatGPT Vision OCR"

                                # Clean up temp file
                                os.unlink(temp_image_path)

                            except Exception as e:
                                logger.error(f"Image OCR error for {filename}: {e}")
                                extracted_text = (
                                    f"[Lỗi OCR hình ảnh {filename}: {str(e)}]"
                                )
                                extraction_method = "Failed OCR"
                                file_log["error"] = str(e)

                        # ✅ PDF PROCESSING
                        elif (
                            file_type == "application/pdf"
                            or filename.lower().endswith(".pdf")
                        ):
                            logger.info(f"Processing PDF: {filename}")
                            yield f'data: {json.dumps({"status": "pdf", "message": f"Đang đọc PDF {filename}..."})}\n\n'

                            try:
                                extracted_text = (
                                    await asyncio.get_event_loop().run_in_executor(
                                        None, extract_text_from_pdf, file_base64
                                    )
                                )
                                extraction_method = "PyMuPDF"
                            except Exception as e:
                                logger.error(
                                    f"PDF processing error for {filename}: {e}"
                                )
                                extracted_text = f"[Lỗi đọc PDF {filename}: {str(e)}]"
                                extraction_method = "Failed PDF"
                                file_log["error"] = str(e)

                        # ✅ DOCX PROCESSING
                        elif file_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" or filename.lower().endswith(
                            ".docx"
                        ):
                            logger.info(f"Processing DOCX: {filename}")
                            yield f'data: {json.dumps({"status": "docx", "message": f"Đang đọc DOCX {filename}..."})}\n\n'

                            try:
                                extracted_text = (
                                    await asyncio.get_event_loop().run_in_executor(
                                        None, extract_text_from_docx, file_base64
                                    )
                                )
                                extraction_method = "python-docx"
                            except Exception as e:
                                logger.error(
                                    f"DOCX processing error for {filename}: {e}"
                                )
                                extracted_text = f"[Lỗi đọc DOCX {filename}: {str(e)}]"
                                extraction_method = "Failed DOCX"
                                file_log["error"] = str(e)

                        # ✅ TXT PROCESSING
                        elif file_type == "text/plain" or filename.lower().endswith(
                            ".txt"
                        ):
                            logger.info(f"Processing TXT: {filename}")
                            yield f'data: {json.dumps({"status": "txt", "message": f"Đang đọc TXT {filename}..."})}\n\n'

                            try:
                                # Decode base64 text file
                                text_data = base64.b64decode(file_base64)
                                extracted_text = text_data.decode(
                                    "utf-8", errors="ignore"
                                )
                                extraction_method = "Direct Text"
                            except Exception as e:
                                logger.error(
                                    f"TXT processing error for {filename}: {e}"
                                )
                                extracted_text = f"[Lỗi đọc TXT {filename}: {str(e)}]"
                                extraction_method = "Failed TXT"
                                file_log["error"] = str(e)

                        # ✅ UNSUPPORTED FILE TYPE
                        else:
                            extracted_text = (
                                f"[Loại file {file_type} chưa được hỗ trợ: {filename}]"
                            )
                            extraction_method = "Unsupported"

                    except Exception as e:
                        logger.error(
                            f"General file processing error for {filename}: {e}"
                        )
                        extracted_text = f"[Lỗi xử lý file {filename}: {str(e)}]"
                        extraction_method = "Failed"
                        file_log["error"] = str(e)

                    # Complete file log
                    file_log.update(
                        {
                            "extracted_text": extracted_text,
                            "extraction_method": extraction_method,
                            "text_length": len(extracted_text),
                            "success": len(extracted_text.strip()) > 10
                            and not extracted_text.startswith("[Lỗi"),
                            "processing_time": time.time()
                            - file_log["extraction_start"],
                        }
                    )

                    processed_files.append(file_log)

                    # Add to context if successful
                    if file_log["success"]:
                        files_context += (
                            f"\n\n--- Nội dung từ {filename} ---\n{extracted_text}\n"
                        )
                        yield f'data: {json.dumps({"status": "file_success", "message": f"✅ {filename}: {len(extracted_text)} ký tự"})}\n\n'
                    else:
                        yield f'data: {json.dumps({"status": "file_error", "message": f"❌ {filename}: Lỗi xử lý"})}\n\n'

                # Log file processing step
                analysis_log["processing_steps"].append(
                    {
                        "step": 1,
                        "name": "file_processing",
                        "timestamp": time.time(),
                        "result": {
                            "files_processed": len(processed_files),
                            "successful_files": len(
                                [f for f in processed_files if f["success"]]
                            ),
                            "total_text_length": sum(
                                len(f["extracted_text"]) for f in processed_files
                            ),
                            "files_details": processed_files,
                        },
                    }
                )
                analysis_log["processed_files"] = processed_files

            # ✅ STEP 2: AI ANALYSIS with DeepSeek (Skip web search for better performance)
            yield f'data: {json.dumps({"status": "ai_analysis", "message": "Đang phân tích với AI..."})}\n\n'

            # Create comprehensive prompt
            comprehensive_prompt = f"""
Bạn là chuyên gia phân tích bất động sản hàng đầu tại Việt Nam với hơn 15 năm kinh nghiệm.

YÊU CẦU PHÂN TÍCH: {request.question}

{files_context}

Hãy cung cấp phân tích chuyên sâu theo cấu trúc sau:

🏢 **THÔNG TIN TỔNG QUAN**
- Loại hình bất động sản và thông số kỹ thuật
- Vị trí địa lý và đánh giá location
- Thông tin dự án/chủ đầu tư (nếu có)

💰 **PHÂN TÍCH GIÁ TRỊ & THỊ TRƯỜNG**
- Ước tính giá trị hiện tại
- So sánh với thị trường khu vực
- Xu hướng giá trong 6-12 tháng tới

📈 **TIỀM NĂNG ĐẦU TƯ**
- Khả năng tăng giá trung/dài hạn
- Tiềm năng cho thuê và yield
- Tính thanh khoản

✅ **ƯU ĐIỂM & RỦI RO**
- Điểm mạnh của bất động sản
- Rủi ro và hạn chế cần lưu ý
- Yếu tố tác động giá

🎯 **KHUYẾN NGHỊ CHUYÊN MÔN**
- Phù hợp với nhóm đối tượng nào
- Thời điểm mua/bán/đầu tư
- Lưu ý pháp lý và thủ tục
- Kết luận tổng thể

Phân tích chi tiết, chuyên nghiệp và thực tế dựa trên kinh nghiệm thị trường Việt Nam.
"""

            # Create messages for AI
            messages = [
                {
                    "role": "system",
                    "content": "Bạn là chuyên gia phân tích bất động sản hàng đầu tại Việt Nam với hơn 15 năm kinh nghiệm.",
                },
                {"role": "user", "content": comprehensive_prompt},
            ]

            # Initialize AI manager
            ai_manager = AIProviderManager(
                deepseek_api_key=DEEPSEEK_API_KEY, chatgpt_api_key=CHATGPT_API_KEY
            )

            # Stream AI response using async generator (fix event loop issue)
            full_response = ""

            # Stream the chunks directly without creating new event loop
            async for chunk in ai_manager.chat_completion_stream_with_reasoning(
                messages, "deepseek", use_reasoning=True
            ):
                full_response += chunk
                yield f'data: {json.dumps({"status": "streaming", "content": chunk})}\n\n'
                await asyncio.sleep(0.01)  # Small delay for smooth streaming

            # ✅ SAVE COMPLETE ANALYSIS LOG
            analysis_log.update(
                {
                    "ai_response": full_response,
                    "performance_metrics": {
                        "total_processing_time": time.time() - start_time,
                        "files_processed": len(processed_files),
                        "successful_files": len(
                            [f for f in processed_files if f["success"]]
                        ),
                        "total_characters": len(full_response),
                    },
                }
            )

            # Save log to file
            log_file = save_real_estate_analysis_log(analysis_log)

            # Send completion
            yield f'data: {json.dumps({"status": "completed", "message": "Phân tích hoàn tất", "log_file": log_file, "response_length": len(full_response)})}\n\n'
            yield f"data: [DONE]\n\n"

            logger.info(
                f"✅ Real estate analysis completed. Response length: {len(full_response)}"
            )

        except Exception as e:
            error_msg = f"Xin lỗi, đã có lỗi xảy ra trong quá trình phân tích: {str(e)}"
            logger.error(f"❌ Real estate analysis error: {e}")
            analysis_log["errors"].append(str(e))

            yield f'data: {json.dumps({"status": "error", "error": error_msg})}\n\n'
            yield f"data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


# ✅ HELPER FUNCTION FOR IMAGE OCR
async def extract_text_with_chatgpt_vision_file(image_path: str, filename: str) -> str:
    """
    Extract text from image file using ChatGPT Vision API
    """
    try:
        ai_manager = AIProviderManager(
            deepseek_api_key=DEEPSEEK_API_KEY, chatgpt_api_key=CHATGPT_API_KEY
        )

        # Read image file and encode to base64
        with open(image_path, "rb") as image_file:
            image_data = base64.b64encode(image_file.read()).decode("utf-8")

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

        # Use ChatGPT Vision for OCR
        result = await ai_manager.get_response_with_image(
            question=ocr_prompt, image_base64=image_data, provider="chatgpt"
        )

        return result or f"[Không thể trích xuất text từ {filename}]"

    except Exception as e:
        logger.error(f"ChatGPT Vision OCR error: {e}")
        return f"[Lỗi OCR {filename}: {str(e)}]"


@router.post("/real-estate/analysis-once")
async def real_estate_analysis_once(req: RealEstateAnalysisRequest, request: Request):
    """
    ✅ One-time real estate analysis without file processing (for quick pricing queries)
    Returns JSON response immediately without streaming
    """
    try:
        client_ip = request.client.host
        device_id = request.headers.get("Device-ID", "unknown")
        user_id = request.headers.get("User-ID", "unknown")

        logger.info(f"🏠 [RE-ONCE] Request from {client_ip}: {req.query[:100]}...")

        # Initialize AI manager
        ai_manager = AIProviderManager(
            deepseek_api_key=DEEPSEEK_API_KEY, chatgpt_api_key=CHATGPT_API_KEY
        )

        # Create comprehensive analysis prompt for one-time analysis
        analysis_prompt = f"""
Bạn là chuyên gia định giá bất động sản với 15+ năm kinh nghiệm tại thị trường Việt Nam.

YÊU CẦU ĐỊNH GIÁ: {req.query}

Hãy phân tích và định giá theo cấu trúc sau:

🏢 **THÔNG TIN BẤT ĐỘNG SAN**
- Loại hình: (căn hộ, nhà phố, đất nền, villa...)
- Diện tích và thông số kỹ thuật
- Vị trí và địa chỉ cụ thể (nếu có trong yêu cầu)
- Tình trạng pháp lý

💰 **ĐỊNH GIÁ CHI TIẾT**
- Giá ước tính hiện tại (khoảng giá từ - đến)
- Giá trên m² hoặc m²
- So sánh với giá thị trường khu vực
- Các yếu tố ảnh hưởng đến giá

📊 **PHÂN TÍCH THỊ TRƯỜNG**
- Xu hướng giá 6-12 tháng gần đây
- Dự báo biến động giá trong tương lai
- Tính thanh khoản của loại BĐS này

✅ **ƯU & NHƯỢC ĐIỂM**
- Điểm mạnh về vị trí, tiện ích
- Hạn chế và rủi ro cần lưu ý
- Tiềm năng tăng giá

🎯 **KHUYẾN NGHỊ**
- Phù hợp mua/bán/đầu tư?
- Thời điểm tốt nhất để giao dịch
- Lưu ý về thủ tục pháp lý
- Đánh giá tổng thể (Nên/Không nên)

Trả lời chi tiết, chuyên nghiệp dựa trên kinh nghiệm thực tế thị trường BĐS Việt Nam.
"""

        # Get AI response (using DeepSeek for detailed reasoning - same pattern as serve.py)

        # Create messages for AI
        messages = [
            {
                "role": "system",
                "content": "Bạn là chuyên gia định giá bất động sản với 15+ năm kinh nghiệm tại thị trường Việt Nam.",
            },
            {"role": "user", "content": analysis_prompt},
        ]

        # Initialize AI manager
        ai_manager = AIProviderManager(
            deepseek_api_key=DEEPSEEK_API_KEY, chatgpt_api_key=CHATGPT_API_KEY
        )

        # Get AI response using the same pattern as serve.py (async version)
        async def collect_ai_response():
            """Collect all AI chunks into a single response"""
            try:
                chunks = []
                async for chunk in ai_manager.chat_completion_stream_with_reasoning(
                    messages, "deepseek", use_reasoning=True
                ):
                    chunks.append(chunk)
                return "".join(chunks)
            except Exception as e:
                logger.error(f"AI async call error: {e}")
                return (
                    f"⚠️ Xin lỗi, đã có lỗi xảy ra trong quá trình phân tích: {str(e)}"
                )

        # Get AI response
        ai_response = await collect_ai_response()

        # Create analysis log
        analysis_log = {
            "query": req.query,
            "analysis_type": "one-time",
            "response": ai_response,
            "user_id": req.user_id,
            "session_id": req.session_id,
            "timestamp": datetime.now().isoformat(),
            "response_length": len(ai_response),
        }

        # Save log
        log_file = save_real_estate_analysis_log(analysis_log)

        logger.info(
            f"✅ [RE-ONCE] Analysis completed. Response: {len(ai_response)} chars"
        )

        return RealEstateAnalysisResponse(
            success=True,
            response=ai_response,
            analysis_data={
                "query": req.query,
                "analysis_type": "one-time",
                "timestamp": datetime.now().isoformat(),
                "log_file": log_file,
                "response_length": len(ai_response),
            },
            search_results=None,
            session_id=req.session_id,
        )

    except Exception as e:
        logger.error(f"❌ [RE-ONCE] Error: {e}")
        return RealEstateAnalysisResponse(
            success=False,
            response="Xin lỗi, đã có lỗi xảy ra trong quá trình định giá bất động sản.",
            error=str(e),
            session_id=req.session_id,
        )


@router.post("/real-estate/simple-analysis")
async def simple_real_estate_analysis(req: RealEstateAnalysisRequest, request: Request):
    """
    ✅ Simple real estate analysis without file processing (for quick queries)
    """
    try:
        client_ip = request.client.host
        device_id = request.headers.get("Device-ID", "unknown")
        user_id = request.headers.get("User-ID", "unknown")

        logger.info(f"🏠 [SIMPLE RE] Request from {client_ip}: {req.query[:100]}...")

        # Initialize AI manager
        ai_manager = AIProviderManager(
            deepseek_api_key=DEEPSEEK_API_KEY, chatgpt_api_key=CHATGPT_API_KEY
        )

        # Create simple prompt
        simple_prompt = f"""
Bạn là chuyên gia bất động sản. Hãy phân tích ngắn gọn:

{req.query}

Cung cấp đánh giá nhanh về:
- Loại hình và vị trí
- Ước tính giá trị
- Ưu nhược điểm chính
- Khuyến nghị cơ bản

Trả lời ngắn gọn, súc tích bằng tiếng Việt.
"""

        # Get AI response
        ai_response = await ai_manager.get_response(
            question=simple_prompt,
            session_id=req.session_id,
            user_id=req.user_id,
            provider="deepseek",
        )

        return RealEstateAnalysisResponse(
            success=True,
            response=ai_response,
            analysis_data={
                "query": req.query,
                "analysis_type": "simple",
                "timestamp": datetime.now().isoformat(),
            },
            search_results=None,
            session_id=req.session_id,
        )

    except Exception as e:
        logger.error(f"❌ [SIMPLE RE] Error: {e}")
        return RealEstateAnalysisResponse(
            success=False,
            response="Xin lỗi, đã có lỗi xảy ra trong quá trình phân tích.",
            error=str(e),
            session_id=req.session_id,
        )
