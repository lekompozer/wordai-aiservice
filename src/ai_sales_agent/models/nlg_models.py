"""
NLG Request/Response Models for AI Sales Agent
"""
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field

class NLGRequest(BaseModel):
    """Request model for NLG question generation"""
    step: Union[int, str] = Field(..., description="Step number or sub-step (1.1, 1.2, 2.1, 2.2)")
    stepName: str = Field(..., description="Name of the current step/sub-step")
    missingFields: List[str] = Field(..., description="Fields that need to be collected")
    collectedData: Dict[str, Any] = Field(default={}, description="Data collected so far")
    isFirstQuestion: bool = Field(default=False, description="Is this the first question in the sub-step")
    previousUserMessage: Optional[str] = Field(None, description="Previous user message for context")
    validationError: Optional[Dict[str, str]] = Field(None, description="Validation error to address")

class NLGResponse(BaseModel):
    """Response model for NLG question generation"""
    question: str = Field(..., description="Generated natural language question")
    suggestedOptions: List[str] = Field(default=[], description="Suggested answer options if applicable")
    inputType: str = Field(default="text", description="Expected input type: text, choice, number, etc.")
    hints: List[str] = Field(default=[], description="Helpful hints for the user")
    examples: List[str] = Field(default=[], description="Example answers")
    processingTime: Optional[float] = Field(default=None, description="Processing time in seconds")
    nextSubStep: Optional[str] = Field(default=None, description="Next sub-step after this one")
