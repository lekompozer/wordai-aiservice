"""
FastAPI route handlers for OCR-related endpoints
"""

from fastapi import APIRouter, Request
from datetime import datetime
import json
import time
import base64
from typing import Dict, Any

from src.core.models import CCCDOCRRequest, CCCDOCRResponse
from src.core.document_utils import validate_image_base64
from src.clients.chatgpt_client import ChatGPTClient

router = APIRouter()

@router.post("/api/ocr/cccd", response_model=CCCDOCRResponse)
async def process_cccd_ocr(request: CCCDOCRRequest, req: Request):
    """
    ✅ CCCD (Vietnamese ID Card) OCR processing endpoint
    """
    start_time = time.time()
    
    try:
        client_ip = req.client.host
        print(f"🆔 [CCCD-OCR] Request from {client_ip}")
        
        # Validate image data
        if not request.image:
            return CCCDOCRResponse(
                success=False,
                error="No image data provided",
                processing_time=time.time() - start_time
            )
        
        # Validate base64 format
        if not validate_image_base64(request.image):
            return CCCDOCRResponse(
                success=False,
                error="Invalid image format or corrupted data",
                processing_time=time.time() - start_time
            )
        
        print(f"✅ [CCCD-OCR] Image validation passed")
        
        # Initialize ChatGPT client for OCR processing
        chatgpt = ChatGPTClient()
        
        # Create OCR prompt for CCCD
        ocr_prompt = """
Hãy phân tích hình ảnh Căn cước công dân (CCCD) này và trích xuất thông tin theo định dạng JSON sau:

{
  "id_number": "Số căn cước công dân",
  "full_name": "Họ và tên",
  "date_of_birth": "Ngày sinh (DD/MM/YYYY)",
  "gender": "Giới tính",
  "nationality": "Quốc tịch",
  "place_of_origin": "Quê quán",
  "place_of_residence": "Nơi thường trú",
  "identifying_features": "Dấu hiệu nhận dạng",
  "issue_date": "Ngày cấp (DD/MM/YYYY)",
  "expiry_date": "Có giá trị đến (DD/MM/YYYY)",
  "issuing_authority": "Nơi cấp"
}

Nếu không thể đọc được thông tin nào, hãy để giá trị là null.
Chỉ trả về JSON, không cần giải thích thêm.
"""
        
        # Process with multimodal ChatGPT
        result = await chatgpt.process_image_with_text(
            image_base64=request.image,
            prompt=ocr_prompt
        )
        
        print(f"✅ [CCCD-OCR] ChatGPT processing completed")
        
        # Try to parse JSON response
        try:
            ocr_data = json.loads(result)
            print(f"✅ [CCCD-OCR] Successfully parsed OCR data")
            
            return CCCDOCRResponse(
                success=True,
                data=ocr_data,
                processing_time=time.time() - start_time
            )
            
        except json.JSONDecodeError as e:
            print(f"⚠️ [CCCD-OCR] JSON parsing failed, returning raw text")
            
            return CCCDOCRResponse(
                success=True,
                data={
                    "raw_text": result,
                    "parsed": False,
                    "note": "Could not parse as structured JSON"
                },
                processing_time=time.time() - start_time
            )
            
    except Exception as e:
        print(f"❌ [CCCD-OCR] Processing error: {e}")
        
        return CCCDOCRResponse(
            success=False,
            error=str(e),
            processing_time=time.time() - start_time
        )

@router.post("/test-ocr-url")
async def test_ocr_url(request: Request):
    """
    ✅ Test OCR endpoint with URL-based image
    """
    try:
        body = await request.json()
        image_url = body.get("image_url")
        
        if not image_url:
            return {"success": False, "error": "No image_url provided"}
        
        print(f"🧪 [TEST-OCR] Testing with URL: {image_url}")
        
        # Initialize ChatGPT client
        chatgpt = ChatGPTClient()
        
        # Simple OCR prompt
        ocr_prompt = "Hãy mô tả và trích xuất tất cả văn bản có trong hình ảnh này."
        
        # Process with URL
        result = await chatgpt.process_image_url_with_text(
            image_url=image_url,
            prompt=ocr_prompt
        )
        
        return {
            "success": True,
            "result": result,
            "image_url": image_url,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"❌ [TEST-OCR] Error: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
