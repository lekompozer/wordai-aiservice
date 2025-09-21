"""
Routes for AI Sales Agent - Flexible conversation approach only
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import logging
import time

from src.ai_sales_agent.services.ai_provider import AISalesAgentProvider
from src.ai_sales_agent.services.loan_assessment_client import LoanAssessmentClient
from src.ai_sales_agent.nlg.generator import NLGGenerator
from src.ai_sales_agent.utils.flexible_assessment import FlexibleAssessmentChecker
from src.providers.ai_provider_manager import AIProviderManager
from config.config import DEEPSEEK_API_KEY, CHATGPT_API_KEY

# Initialize components
ai_manager = AIProviderManager(
    deepseek_api_key=DEEPSEEK_API_KEY,
    chatgpt_api_key=CHATGPT_API_KEY
)
ai_provider = AISalesAgentProvider(ai_manager)
assessment_client = LoanAssessmentClient()
nlg_generator = NLGGenerator()
flexible_checker = FlexibleAssessmentChecker()

# Create router
router = APIRouter()

# In-memory session storage (use Redis in production)
sessions: Dict[str, Dict[str, Any]] = {}

@router.post("/chat")
async def chat_flexible(request: Dict[str, Any]):
    """
    Flexible chat endpoint with combined NLU+NLG processing
    Enhanced with configuration support and validation
    """
    try:
        session_id = request.get("sessionId", "default")
        user_message = request.get("message", "")
        config = request.get("config", {})  # Get configuration from request
        
        # Initialize or get session
        if session_id not in sessions:
            sessions[session_id] = {
                "conversation_data": {},
                "history": [],
                "message_count": 0,
                "config": config  # Store config in session
            }
        
        session = sessions[session_id]
        current_data = session["conversation_data"]
        history = session["history"]
        message_count = session["message_count"] + 1
        
        # Update config if provided
        if config:
            session["config"] = {**session.get("config", {}), **config}
        
        # Add message count to data for assessment
        current_data["_message_count"] = message_count
        
        # Build conversation context (last 3 exchanges)
        context = "\n".join([
            f"User: {h['user']}\nAI: {h['ai']}" 
            for h in history[-3:]
        ]) if history else None
        
        # Process message with combined NLU+NLG
        result = await ai_provider.process_message_combined(
            user_message=user_message,
            current_data=current_data,
            message_count=message_count,
            context=context,
            config=session.get("config", {})  # Pass config to AI provider
        )
        
        # Extract components
        nlu_data = result.get("nlu", {})
        nlg_data = result.get("nlg", {})
        
        # Update conversation data with extracted info
        extracted_data = nlu_data.get("extractedData", {})
        validation_errors = nlu_data.get("validationErrors", {})
        
        if extracted_data:
            current_data.update(extracted_data)
            session["conversation_data"] = current_data
        
        # Get AI response for display
        ai_response = nlg_data.get("response", "")
        
        # Check readiness with enhanced logic
        readiness = flexible_checker.assess_readiness(current_data)
        
        # Update history
        session["history"].append({
            "user": user_message,
            "ai": ai_response,
            "extracted": extracted_data,
            "validationErrors": validation_errors,
            "timestamp": int(time.time())
        })
        session["message_count"] = message_count
        
        # Prepare response
        response = {
            "sessionId": session_id,
            "message": ai_response,  # For TTS and display
            "extractedData": extracted_data,  # For database only
            "validationErrors": validation_errors,  # Validation issues found
            "totalData": current_data,
            "readiness": {
                "status": readiness["readiness"].value,
                "score": readiness["score"],
                "percentage": readiness["completion_percentage"],
                "canProceed": readiness["can_proceed"],
                "autoReady": readiness["auto_ready"],
                "missingCritical": readiness["missing_critical"][:3],
                "recommendations": readiness["recommendations"]
            },
            "messageCount": message_count,
            "suggestAssessment": nlg_data.get("suggestAssessment", False),
            "isComplete": nlg_data.get("isComplete", False),
            "language": nlg_data.get("language", "vi"),
            "config": session.get("config", {})
        }
        
        # Auto-suggest assessment if conditions met
        if readiness["auto_ready"] and message_count >= 5:
            response["autoAssessmentReady"] = True
            response["assessmentMessage"] = "Tôi đã thu thập đủ thông tin cần thiết. Anh/chị có muốn tôi thẩm định hồ sơ ngay không?"
        
        return response
        
    except Exception as e:
        logging.error(f"Chat error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/assess")
async def assess_loan(request: Dict[str, Any]):
    """
    Assess loan based on collected data
    """
    try:
        session_id = request.get("sessionId", "default")
        
        if session_id not in sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session = sessions[session_id]
        conversation_data = session["conversation_data"]
        
        # Check if enough data
        readiness = flexible_checker.assess_readiness(conversation_data)
        if not readiness["can_proceed"]:
            return {
                "success": False,
                "message": "Chưa đủ dữ liệu để thẩm định",
                "missingCritical": readiness["missing_critical"],
                "recommendations": readiness["recommendations"]
            }
        
        # Prepare assessment payload
        assessment_payload = nlg_generator.prepare_assessment_payload(conversation_data)
        
        # Call assessment API
        try:
            assessment_result = await assessment_client.assess_loan(assessment_payload)
        except Exception as e:
            # Use mock if API fails
            assessment_result = assessment_client.create_mock_assessment_result(assessment_payload)
        
        # Format result
        formatted_result = nlg_generator.format_assessment_result(assessment_result)
        
        return {
            "success": True,
            "sessionId": session_id,
            "assessmentResult": assessment_result,
            "formattedMessage": formatted_result["question"],
            "summary": formatted_result.get("summary", "")
        }
        
    except Exception as e:
        logging.error(f"Assessment error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/check-readiness")
async def check_readiness(request: Dict[str, Any]):
    """
    Check if current data is ready for assessment
    """
    try:
        session_id = request.get("sessionId", "default")
        
        if session_id not in sessions:
            return {
                "sessionId": session_id,
                "ready": False,
                "message": "Chưa có dữ liệu"
            }
        
        conversation_data = sessions[session_id]["conversation_data"]
        readiness = flexible_checker.assess_readiness(conversation_data)
        
        return {
            "sessionId": session_id,
            "ready": readiness["can_proceed"],
            "readiness": readiness["readiness"].value,
            "score": readiness["score"],
            "percentage": readiness["completion_percentage"],
            "missingCritical": readiness["missing_critical"],
            "recommendations": readiness["recommendations"],
            "currentData": list(conversation_data.keys())
        }
        
    except Exception as e:
        logging.error(f"Check readiness error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/suggest-questions/{session_id}")
async def suggest_questions(session_id: str):
    """
    Get smart question suggestions based on missing priority fields
    """
    try:
        if session_id not in sessions:
            return {
                "sessionId": session_id,
                "suggestions": ["Anh/chị muốn vay vốn với số tiền bao nhiêu?"]
            }
        
        conversation_data = sessions[session_id]["conversation_data"]
        suggestions = flexible_checker.suggest_next_questions(conversation_data)
        
        return {
            "sessionId": session_id,
            "suggestions": suggestions,
            "currentDataCount": len(conversation_data),
            "topMissingFields": ai_provider.get_missing_priority_fields(conversation_data)[:5]
        }
        
    except Exception as e:
        logging.error(f"Suggest questions error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """
    Clear session data
    """
    if session_id in sessions:
        del sessions[session_id]
    
    return {
        "sessionId": session_id,
        "message": "Session cleared"
    }